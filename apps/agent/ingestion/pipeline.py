"""Ingestion pipeline: connector → chunk → embed → store.

Orchestrates the full pipeline:
1. Connect to data source (local file or URL)
2. Chunk the content based on file type
3. Generate embeddings using Gemini
4. Store chunks in Supabase
5. Update indexing_jobs status (queued → running → done/failed)

Error handling is graceful - pipeline reports status at each step.
"""

import os
import uuid
from datetime import datetime, timezone
from typing import Any

from connectors.local_files import LocalFilesConnector
from connectors.web_crawler import WebCrawlerConnector
from ingestion.chunker import chunk_content, detect_file_type
from ingestion.embedder import GeminiEmbedder, TASK_TYPE_RETRIEVAL_DOCUMENT
from db.supabase import get_supabase_client


class IngestionPipeline:
    """Orchestrates the full ingestion pipeline.

    Pipeline stages:
    1. Fetch: Connect to source and fetch raw content
    2. Chunk: Split content into manageable pieces
    3. Embed: Generate vector embeddings for chunks
    4. Store: Save chunks with embeddings to Supabase
    """

    def __init__(
        self,
        collection_id: str,
        source_id: str | None = None,
        chunk_size: int = 800,
        chunk_overlap: int = 200,
    ):
        """Initialize the pipeline.

        Args:
            collection_id: UUID of the collection to ingest into
            source_id: UUID of the source (optional)
            chunk_size: Maximum tokens per chunk
            chunk_overlap: Overlap between chunks
        """
        self.collection_id = collection_id
        self.source_id = source_id
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

        self._supabase = None
        self._embedder = None
        self._local_connector = LocalFilesConnector()
        self._web_connector = WebCrawlerConnector()

    @property
    def supabase(self):
        """Lazy-load Supabase client."""
        if self._supabase is None:
            self._supabase = get_supabase_client()
        return self._supabase

    @property
    def embedder(self):
        """Lazy-load Gemini embedder."""
        if self._embedder is None:
            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                raise ValueError("GEMINI_API_KEY environment variable is required")
            self._embedder = GeminiEmbedder(api_key=api_key)
        return self._embedder

    def run(
        self,
        source: str,
        source_type: str,
    ) -> dict[str, Any]:
        """Run the full ingestion pipeline.

        Args:
            source: File path or URL
            source_type: 'file' or 'url'

        Returns:
            Dictionary with status and results:
            - status: 'running', 'done', or 'failed'
            - chunks_created: Number of chunks created
            - error: Error message if failed
        """
        result = {
            "status": "running",
            "chunks_created": 0,
            "chunks_stored": 0,
            "error": None,
        }

        self._update_job_status("running")

        try:
            fetch_result = self._fetch_content(source, source_type)
            if fetch_result.get("error"):
                raise ValueError(f"Fetch failed: {fetch_result['error']}")

            content = fetch_result["content"]
            file_type = fetch_result["file_type"]

            if not content.strip():
                raise ValueError("No content to ingest")

            chunks = chunk_content(
                content=content,
                file_type=file_type,
                file_path=source if source_type == "file" else None,
                chunk_size=self.chunk_size,
                overlap=self.chunk_overlap,
            )

            result["chunks_created"] = len(chunks)

            if not chunks:
                raise ValueError("No chunks generated from content")

            texts = [chunk["content"] for chunk in chunks]
            embeddings = self.embedder.embed_documents(
                texts,
                task_type=TASK_TYPE_RETRIEVAL_DOCUMENT,
            )

            if len(embeddings) != len(chunks):
                raise ValueError(
                    f"Embedding count mismatch: {len(embeddings)} != {len(chunks)}"
                )

            for i, chunk in enumerate(chunks):
                chunk["embedding"] = embeddings[i]

            stored_count = self._store_chunks(chunks, source_type, source)
            result["chunks_stored"] = stored_count

            self._update_source_status("indexed")
            self._update_job_status("done", progress=100)
            result["status"] = "done"

        except Exception as e:
            result["status"] = "failed"
            result["error"] = str(e)
            self._update_job_status("failed", error_message=str(e))
            self._update_source_status("error")

        return result

    def _fetch_content(
        self,
        source: str,
        source_type: str,
    ) -> dict[str, Any]:
        """Fetch content from the source.

        Args:
            source: File path or URL
            source_type: 'file' or 'url'

        Returns:
            Dictionary with content and file_type
        """
        if source_type == "file":
            self._local_connector.connect()
            result = self._local_connector.fetch(source)
            self._local_connector.disconnect()
            return result
        elif source_type == "url":
            self._web_connector.connect()
            result = self._web_connector.fetch(source)
            self._web_connector.disconnect()
            return result
        else:
            raise ValueError(f"Unknown source_type: {source_type}")

    def _store_chunks(
        self,
        chunks: list[dict],
        source_type: str,
        source: str,
    ) -> int:
        """Store chunks in Supabase.

        Args:
            chunks: List of chunk dictionaries with content, metadata, and embedding
            source_type: 'file' or 'url'
            source: Original source path or URL

        Returns:
            Number of chunks stored
        """
        if not chunks:
            return 0

        records = []

        for chunk in chunks:
            metadata = chunk.get("metadata", {})

            record = {
                "id": str(uuid.uuid4()),
                "source_id": self.source_id,
                "collection_id": self.collection_id,
                "content": chunk["content"],
                "embedding": chunk["embedding"],
                "metadata": {
                    "file_path": metadata.get("file_path"),
                    "source_type": source_type,
                    "source_url": source if source_type == "url" else None,
                    "start_line": metadata.get("start_line"),
                    "end_line": metadata.get("end_line"),
                    "heading": metadata.get("heading"),
                },
                "search_vec": self._create_search_vector(chunk["content"]),
                "created_at": datetime.now(timezone.utc).isoformat(),
            }

            records.append(record)

        self.supabase.table("chunks").insert(records).execute()
        self._update_collection_chunk_count(len(records))
        return len(records)

    def _create_search_vector(self, text: str) -> str:
        """Simple search vector from text.

        Production would use pg_trgm or full-text search.
        """
        words = text.lower().split()
        stop_words = {
            "the",
            "a",
            "an",
            "and",
            "or",
            "but",
            "in",
            "on",
            "at",
            "to",
            "for",
        }
        words = [w for w in words if w not in stop_words and len(w) > 2]
        return " ".join(words)

    def _update_job_status(
        self,
        status: str,
        progress: int | None = None,
        error_message: str | None = None,
    ):
        """Update the indexing job status in Supabase."""
        if not self.source_id:
            return

        update_data: dict[str, Any] = {
            "status": status,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        if progress is not None:
            update_data["progress"] = progress

        if error_message:
            update_data["error_message"] = error_message

        if status == "running":
            update_data["started_at"] = datetime.now(timezone.utc).isoformat()

        if status == "done" or status == "failed":
            update_data["completed_at"] = datetime.now(timezone.utc).isoformat()

        try:
            self.supabase.table("indexing_jobs").update(update_data).eq(
                "source_id", self.source_id
            ).execute()
        except Exception:
            pass

    def _update_source_status(self, status: str):
        """Update the source status in Supabase."""
        if not self.source_id:
            return

        update_data = {
            "status": status,
            "indexed_at": datetime.now(timezone.utc).isoformat()
            if status == "indexed"
            else None,
        }

        try:
            self.supabase.table("sources").update(update_data).eq(
                "id", self.source_id
            ).execute()
        except Exception:
            pass

    def _update_collection_chunk_count(self, added_count: int):
        """Update the collection's chunk count."""
        if not self.collection_id:
            return

        try:
            result = (
                self.supabase.table("collections")
                .select("chunk_count")
                .eq("id", self.collection_id)
                .execute()
            )

            if result.data:
                current_count = result.data[0].get("chunk_count", 0) or 0
                new_count = current_count + added_count

                self.supabase.table("collections").update(
                    {"chunk_count": new_count}
                ).eq("id", self.collection_id).execute()
        except Exception:
            pass


def run_ingestion(
    collection_id: str,
    source: str,
    source_type: str,
    source_id: str | None = None,
    chunk_size: int = 800,
    chunk_overlap: int = 200,
) -> dict[str, Any]:
    """Convenience function to run ingestion.

    Args:
        collection_id: UUID of the collection
        source: File path or URL
        source_type: 'file' or 'url'
        source_id: UUID of the source (optional)
        chunk_size: Maximum tokens per chunk
        chunk_overlap: Overlap between chunks

    Returns:
        Pipeline result dictionary
    """
    pipeline = IngestionPipeline(
        collection_id=collection_id,
        source_id=source_id,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )

    return pipeline.run(source, source_type)
