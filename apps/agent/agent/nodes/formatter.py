"""Citation validation and formatting node.

This node is the final step in the agent pipeline. It:
1. Extracts all [CITE:chunk_id] citations from the response
2. Validates each citation exists in retrieved_chunks
3. Removes invalid citations silently
4. Returns final response with validated cited_chunks

Per AGENTS.md: "Citas inventadas se eliminan silenciosamente"
"""

import re
from typing import cast

from agent.state import AgentState


# Pattern to match citation markers
CITE_PATTERN = re.compile(r"\[CITE:([^\]]+)\]")


def _extract_citation_ids(response: str) -> set[str]:
    """Extract all chunk IDs from citations in response.

    Args:
        response: Generated response text

    Returns:
        Set of chunk IDs found in citations
    """
    matches = CITE_PATTERN.findall(response)
    return set(matches)


def _build_cited_chunks_map(chunks: list[dict]) -> dict[str, dict]:
    """Build a map of chunk_id -> chunk data.

    Args:
        chunks: List of retrieved chunks

    Returns:
        Map of chunk_id to chunk
    """
    chunk_map = {}
    for chunk in chunks:
        chunk_id = chunk.get("id")
        if chunk_id:
            chunk_map[chunk_id] = chunk
    return chunk_map


def _remove_invalid_citations(
    response: str,
    valid_chunk_ids: set[str],
) -> tuple[str, set[str]]:
    """Remove citations that don't exist in retrieved chunks.

    Args:
        response: Original response with citations
        valid_chunk_ids: Set of valid chunk IDs

    Returns:
        Tuple of (cleaned_response, used_chunk_ids)
    """
    # Find all citations in the response
    used_ids: set[str] = set()

    def replace_citation(match):
        chunk_id = match.group(1)
        if chunk_id in valid_chunk_ids:
            used_ids.add(chunk_id)
            return match.group(0)  # Keep valid citation
        else:
            return ""  # Remove invalid citation

    cleaned = CITE_PATTERN.sub(replace_citation, response)

    # Clean up any double spaces or artifacts
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = cleaned.strip()

    return cleaned, used_ids


def _format_final_response(
    response: str,
    cited_chunk_ids: set[str],
    chunk_map: dict[str, dict],
) -> str:
    """Format the final response with source references.

    Optionally adds a sources section at the end.

    Args:
        response: Cleaned response text
        cited_chunk_ids: IDs of chunks that were actually cited
        chunk_map: Map of chunk_id to chunk data

    Returns:
        Final formatted response
    """
    # Add sources section if there are citations
    if cited_chunk_ids:
        sources_lines = ["\n\n--- Sources ---"]

        for chunk_id in sorted(cited_chunk_ids):
            chunk = chunk_map.get(chunk_id, {})
            metadata = chunk.get("metadata", {})

            source_name = metadata.get("source_name", "Unknown source")
            url = metadata.get("url", "")

            if url:
                sources_lines.append(f"- [{source_name}]({url})")
            else:
                sources_lines.append(f"- {source_name}")

        response = response + "\n" + "\n".join(sources_lines)

    return response


def formatter_node(state: AgentState) -> AgentState:
    """Validate and format citations in the response.

    This final node:
    1. Extracts all [CITE:chunk_id] citations
    2. Validates each exists in retrieved_chunks
    3. Removes invalid citations (per AGENTS.md: "silenciosamente")
    4. Returns final response with cited_chunks

    Args:
        state: Current agent state with response and retrieved_chunks

    Returns:
        Updated state with final response and validated cited_chunks
    """
    response = state.get("response", "")
    chunks = state.get("retrieved_chunks", [])

    if not response:
        return cast(
            AgentState,
            {
                **state,
                "cited_chunks": [],
            },
        )

    # Build map of valid chunk IDs
    chunk_map = _build_cited_chunks_map(chunks)
    valid_chunk_ids = set(chunk_map.keys())

    # Remove invalid citations and get used IDs
    cleaned_response, used_chunk_ids = _remove_invalid_citations(
        response, valid_chunk_ids
    )

    # Get the cited chunks data
    cited_chunks = [
        chunk_map[chunk_id] for chunk_id in used_chunk_ids if chunk_id in chunk_map
    ]

    # Format final response with sources
    final_response = _format_final_response(
        cleaned_response,
        used_chunk_ids,
        chunk_map,
    )

    return cast(
        AgentState,
        {
            **state,
            "response": final_response,
            "cited_chunks": cited_chunks,
        },
    )
