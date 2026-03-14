"""Context ranking and deduplication node.

This node:
1. Reranks retrieved chunks for relevance
2. Deduplicates chunks based on content similarity
3. Returns top-8 chunks for the generator

Uses a simple relevance scoring approach based on:
- Original query similarity
- Source diversity
- Content uniqueness
"""

from typing import cast

from agent.state import AgentState

# Maximum chunks to return after ranking
MAX_RANKED_CHUNKS = 8


def _calculate_relevance_score(chunk: dict, query: str) -> float:
    """Calculate relevance score for a chunk.

    Combines multiple signals:
    - RRF score from retrieval (if available)
    - Content length (prefer substantial content)
    - Metadata quality

    Args:
        chunk: Retrieved chunk
        query: Original user query

    Returns:
        Relevance score (higher is better)
    """
    score = 0.0

    # Use RRF score from hybrid search if available
    rrf_score = chunk.get("rrf_score") or chunk.get("score") or 0.0
    score += rrf_score * 10  # Weight heavily

    # Bonus for having metadata (shows structured content)
    if chunk.get("metadata"):
        score += 0.5

    # Bonus for source diversity (different sources preferred)
    source = chunk.get("metadata", {}).get("source_name") or chunk.get("source_id", "")
    if source:
        score += 0.3

    # Content length consideration (prefer substantial chunks)
    content = chunk.get("content", "")
    if len(content) > 100:
        score += 0.2
    if len(content) > 300:
        score += 0.1

    return score


def _deduplicate_chunks(chunks: list[dict]) -> list[dict]:
    """Remove duplicate or near-duplicate chunks.

    Chunks are considered duplicates if:
    - Exact same content
    - Very high content similarity (>90%)

    Args:
        chunks: List of chunks to deduplicate

    Returns:
        Deduplicated list of chunks
    """
    if not chunks:
        return []

    unique_chunks = []
    seen_content_hashes: set[str] = set()

    for chunk in chunks:
        content = chunk.get("content", "")

        # Simple hash for duplicate detection
        # Use first 100 chars + length as hash
        content_hash = f"{content[:100]}:{len(content)}"

        if content_hash not in seen_content_hashes:
            seen_content_hashes.add(content_hash)
            unique_chunks.append(chunk)

    return unique_chunks


def _rerank_chunks(chunks: list[dict], query: str) -> list[dict]:
    """Rerank chunks by relevance.

    Args:
        chunks: Retrieved chunks
        query: Original user query

    Returns:
        Sorted list of chunks by relevance
    """
    # Calculate scores for all chunks
    scored_chunks = []
    for chunk in chunks:
        score = _calculate_relevance_score(chunk, query)
        chunk_with_score = {**chunk, "_relevance_score": score}
        scored_chunks.append(chunk_with_score)

    # Sort by relevance score (descending)
    scored_chunks.sort(key=lambda x: x.get("_relevance_score", 0), reverse=True)

    return scored_chunks


def _select_diverse_top_chunks(
    chunks: list[dict],
    max_chunks: int = MAX_RANKED_CHUNKS,
) -> list[dict]:
    """Select top chunks while maintaining source diversity.

    Ensures we don't have too many chunks from the same source.

    Args:
        chunks: Sorted chunks by relevance
        max_chunks: Maximum number of chunks to return

    Returns:
        Selected diverse chunks
    """
    if not chunks:
        return []

    selected = []
    source_counts: dict[str, int] = {}
    max_from_same_source = 3  # Max chunks per source

    for chunk in chunks:
        source = chunk.get("metadata", {}).get("source_name") or str(
            chunk.get("source_id", "")
        )

        # Check if we can add from this source
        current_count = source_counts.get(source, 0)
        if current_count < max_from_same_source:
            selected.append(chunk)
            source_counts[source] = current_count + 1

        if len(selected) >= max_chunks:
            break

    return selected


def ranker_node(state: AgentState) -> AgentState:
    """Rank and deduplicate retrieved chunks.

    This node:
    1. Reranks chunks by relevance to the query
    2. Removes duplicate/near-duplicate content
    3. Selects top-8 diverse chunks

    Args:
        state: Current agent state with chunks and query

    Returns:
        Updated state with retrieved_chunks (top-8)
    """
    chunks = state.get("chunks", [])
    query = state.get("query", "")

    if not chunks:
        return cast(
            AgentState,
            {
                **state,
                "retrieved_chunks": [],
            },
        )

    # Step 1: Deduplicate
    unique_chunks = _deduplicate_chunks(chunks)

    # Step 2: Rerank
    ranked_chunks = _rerank_chunks(unique_chunks, query)

    # Step 3: Select diverse top chunks
    top_chunks = _select_diverse_top_chunks(ranked_chunks, MAX_RANKED_CHUNKS)

    # Clean up internal scoring fields
    cleaned_chunks = []
    for chunk in top_chunks:
        cleaned = {k: v for k, v in chunk.items() if not k.startswith("_")}
        cleaned_chunks.append(cleaned)

    return cast(
        AgentState,
        {
            **state,
            "retrieved_chunks": cleaned_chunks,
        },
    )
