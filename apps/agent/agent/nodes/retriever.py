"""Parallel retrieval node using hybrid search.

This node retrieves relevant chunks from the vector database using hybrid search:
- Dense: Semantic search using embeddings (gemini-embedding-001)
- Sparse: Full-text search using BM25
- RRF: Reciprocal Rank Fusion to combine results

Each sub-query is searched in parallel for efficiency.
"""

import os
import asyncio
from typing import cast

from google import genai
from google.genai import types

from agent.state import AgentState
from db.supabase import get_supabase_client


# Default search parameters
DEFAULT_MATCH_COUNT = 20  # Retrieve more than needed for ranking


def _get_embedding(text: str) -> list[float]:
    """Generate embedding using gemini-embedding-001.

    Args:
        text: Text to embed

    Returns:
        1536-dimensional embedding vector
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not set")

    client = genai.Client(api_key=api_key)

    response = client.models.embed_content(
        model="gemini-embedding-001",
        contents=text,
        config=types.EmbedContentConfig(
            task_type="RETRIEVAL_QUERY",
        ),
    )

    # Extract embedding vector
    embedding = response.embeddings[0].values
    return embedding


def _hybrid_search(
    supabase,
    query_embedding: list[float],
    query_text: str,
    collection_ids: list[str],
    match_count: int = DEFAULT_MATCH_COUNT,
) -> list[dict]:
    """Execute hybrid search using the Supabase RPC function.

    Args:
        supabase: Supabase client
        query_embedding: Query embedding vector
        query_text: Original query text for BM25
        collection_ids: UUIDs of collections to search
        match_count: Number of results to return

    Returns:
        List of chunks with scores
    """
    try:
        response = supabase.rpc(
            "hybrid_search",
            {
                "query_embedding": query_embedding,
                "query_text": query_text,
                "collection_ids": collection_ids,
                "match_count": match_count,
            },
        ).execute()

        if response.data:
            return response.data
        return []

    except Exception as e:
        # Fallback to basic vector search if hybrid_search not available
        try:
            response = supabase.rpc(
                "match_chunks",
                {
                    "query_embedding": query_embedding,
                    "collection_ids": collection_ids,
                    "match_count": match_count,
                },
            ).execute()

            if response.data:
                return response.data
            return []
        except Exception:
            raise RuntimeError(f"Hybrid search failed: {str(e)}")


async def _retrieve_for_query(
    supabase,
    sub_query: str,
    collection_ids: list[str],
    match_count: int = DEFAULT_MATCH_COUNT,
) -> list[dict]:
    """Retrieve chunks for a single sub-query.

    Args:
        supabase: Supabase client
        sub_query: Individual sub-query to search
        collection_ids: Collections to search
        match_count: Number of results

    Returns:
        List of retrieved chunks
    """
    # Generate embedding for sub-query
    embedding = _get_embedding(sub_query)

    # Execute hybrid search
    results = _hybrid_search(
        supabase, embedding, sub_query, collection_ids, match_count
    )

    # Add source query to each chunk for debugging
    for chunk in results:
        chunk["_sub_query"] = sub_query

    return results


async def _retrieve_all(
    sub_queries: list[str],
    collection_ids: list[str],
    match_count: int = DEFAULT_MATCH_COUNT,
) -> list[dict]:
    """Execute parallel retrieval for all sub-queries.

    Args:
        sub_queries: List of sub-queries
        collection_ids: Collections to search
        match_count: Results per sub-query

    Returns:
        Merged list of all retrieved chunks
    """
    supabase = get_supabase_client()

    # Run all retrievals in parallel
    tasks = [
        _retrieve_for_query(supabase, sq, collection_ids, match_count)
        for sq in sub_queries
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Merge results from all sub-queries
    all_chunks: list[dict] = []
    for result in results:
        if isinstance(result, Exception):
            continue
        if isinstance(result, list):
            all_chunks.extend(result)

    return all_chunks


def retriever_node(state: AgentState) -> AgentState:
    """Retrieve relevant chunks using hybrid search.

    This node executes parallel retrieval for all sub-queries and merges
    the results. Uses both dense (embedding) and sparse (BM25) search.

    Args:
        state: Current agent state with sub_queries and collection_ids

    Returns:
        Updated state with retrieved chunks
    """
    sub_queries = state.get("sub_queries", [])
    collection_ids = state.get("collection_ids", [])

    if not sub_queries:
        return cast(
            AgentState,
            {
                **state,
                "chunks": [],
                "error": "No sub-queries provided to retriever",
            },
        )

    if not collection_ids:
        return cast(
            AgentState,
            {
                **state,
                "chunks": [],
                "error": "No collection_ids provided to retriever",
            },
        )

    try:
        # Run async retrieval
        chunks = asyncio.run(_retrieve_all(sub_queries, collection_ids))

        # Deduplicate by chunk ID
        seen_ids = set()
        unique_chunks = []
        for chunk in chunks:
            chunk_id = chunk.get("id")
            if chunk_id and chunk_id not in seen_ids:
                seen_ids.add(chunk_id)
                unique_chunks.append(chunk)

        return cast(
            AgentState,
            {
                **state,
                "chunks": unique_chunks,
            },
        )

    except Exception as e:
        return cast(
            AgentState,
            {
                **state,
                "chunks": [],
                "error": f"Retriever error: {str(e)}",
            },
        )
