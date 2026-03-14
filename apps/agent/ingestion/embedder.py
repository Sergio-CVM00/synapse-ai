"""Embeddings generation using Gemini.

- GeminiEmbedding model (gemini-embedding-001)
- Batch processing with configurable batch size
- Retry logic with exponential backoff for rate limits
- Use RETRIEVAL_DOCUMENT task_type
- 1536 dimensions (MRL)
"""

import os
import time
from typing import Any

from google.genai import types
from google import genai


# Embedding dimensions for gemini-embedding-001 (MRL = 1536)
EMBEDDING_DIMENSIONS = 1536

# Task types for embedding
TASK_TYPE_RETRIEVAL_DOCUMENT = "RETRIEVAL_DOCUMENT"
TASK_TYPE_RETRIEVAL_QUERY = "RETRIEVAL_QUERY"

# Default configuration
DEFAULT_BATCH_SIZE = 20
DEFAULT_MAX_RETRIES = 3
DEFAULT_INITIAL_DELAY = 1.0  # seconds
DEFAULT_MAX_DELAY = 60.0  # seconds


class GeminiEmbedder:
    """Embeddings generator using Gemini API.

    Supports batch processing and retry logic for rate limits.
    """

    def __init__(
        self,
        api_key: str | None = None,
        batch_size: int = DEFAULT_BATCH_SIZE,
        max_retries: int = DEFAULT_MAX_RETRIES,
        initial_delay: float = DEFAULT_INITIAL_DELAY,
        max_delay: float = DEFAULT_MAX_DELAY,
    ):
        """Initialize the embedder.

        Args:
            api_key: Gemini API key (reads from GEMINI_API_KEY env if not provided)
            batch_size: Number of texts to embed per API call
            max_retries: Maximum retry attempts on rate limit
            initial_delay: Initial delay between retries (seconds)
            max_delay: Maximum delay between retries (seconds)
        """
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is required")

        self.batch_size = batch_size
        self.max_retries = max_retries
        self.initial_delay = initial_delay
        self.max_delay = max_delay

        # Initialize client
        self.client = genai.Client(api_key=self.api_key)

    def embed_documents(
        self,
        texts: list[str],
        task_type: str = TASK_TYPE_RETRIEVAL_DOCUMENT,
    ) -> list[list[float]]:
        """Embed multiple documents in batches.

        Args:
            texts: List of text strings to embed
            task_type: Task type (RETRIEVAL_DOCUMENT or RETRIEVAL_QUERY)

        Returns:
            List of embedding vectors (1536 dimensions each)
        """
        if not texts:
            return []

        all_embeddings = []

        # Process in batches
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i : i + self.batch_size]
            batch_embeddings = self._embed_batch_with_retry(batch, task_type)
            all_embeddings.extend(batch_embeddings)

        return all_embeddings

    def embed_query(self, query: str) -> list[float]:
        """Embed a single query.

        Args:
            query: Query string to embed

        Returns:
            Embedding vector (1536 dimensions)
        """
        return self._embed_batch_with_retry(
            [query], task_type=TASK_TYPE_RETRIEVAL_QUERY
        )[0]

    def _embed_batch_with_retry(
        self,
        texts: list[str],
        task_type: str,
    ) -> list[list[float]]:
        """Embed a batch with retry logic for rate limits."""
        delay = self.initial_delay
        last_error = None

        for attempt in range(self.max_retries + 1):
            try:
                return self._embed_batch(texts, task_type)
            except Exception as e:
                last_error = e
                error_str = str(e).lower()

                # Check if it's a rate limit error
                is_rate_limit = any(
                    keyword in error_str
                    for keyword in ["rate limit", "quota", "resource exhausted", "429"]
                )

                if is_rate_limit and attempt < self.max_retries:
                    # Exponential backoff
                    time.sleep(delay)
                    delay = min(delay * 2, self.max_delay)
                elif not is_rate_limit:
                    # Not a rate limit error, don't retry
                    break

        # All retries exhausted or non-retryable error
        raise last_error if last_error else ValueError("Embedding failed")

    def _embed_batch(
        self,
        texts: list[str],
        task_type: str,
    ) -> list[list[float]]:
        """Embed a single batch using Gemini API."""
        # Build content for the API request
        # Gemini embedding API format
        result = self.client.models.embed_content(
            model="gemini-embedding-001",
            contents=texts,
            config={
                "task_type": task_type,
                "output_dimensionality": EMBEDDING_DIMENSIONS,
            },
        )

        # Extract embeddings from response
        embeddings = []
        for embedding_obj in result.embeddings:
            # The embedding values are in the embedding object
            if hasattr(embedding_obj, "values"):
                embeddings.append(embedding_obj.values)
            elif hasattr(embedding_obj, "embedding"):
                embeddings.append(embedding_obj.embedding)
            else:
                # Try to get from the response dict
                raise ValueError(f"Unexpected embedding response format")

        return embeddings


def embed_texts(
    texts: list[str],
    batch_size: int = DEFAULT_BATCH_SIZE,
    task_type: str = TASK_TYPE_RETRIEVAL_DOCUMENT,
) -> list[list[float]]:
    """Embed multiple texts using default embedder.

    Convenience function that creates an embedder from env vars.

    Args:
        texts: List of text strings to embed
        batch_size: Number of texts per batch
        task_type: Task type for embedding

    Returns:
        List of embedding vectors
    """
    embedder = GeminiEmbedder(batch_size=batch_size)
    return embedder.embed_documents(texts, task_type)


def embed_query(query: str) -> list[float]:
    """Embed a query using default embedder.

    Convenience function that creates an embedder from env vars.

    Args:
        query: Query string to embed

    Returns:
        Embedding vector
    """
    embedder = GeminiEmbedder()
    return embedder.embed_query(query)
