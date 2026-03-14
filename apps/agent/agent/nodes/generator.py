"""Response generation node with citations.

This node generates the final response using the LLM with:
- Retrieved chunks as context
- Thinking level from classification
- Citation markers [CITE:chunk_id]

Supports fallback to OpenRouter if Gemini rate-limits.
"""

import os
import re
from typing import cast

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI

from agent.state import AgentState


# Generation prompt template
GENERATOR_PROMPT = """You are a helpful AI assistant with access to a knowledge base.

Use the provided context to answer the user's question. When you use information
from a specific source, cite it using [CITE:chunk_id] markers.

User question: {query}

Context from knowledge base:
{context}

Instructions:
1. Answer the question based ONLY on the provided context
2. If the context doesn't contain enough information, say so clearly
3. Use [CITE:chunk_id] after any information you take from the context
4. Be concise but comprehensive
5. Maintain a helpful, professional tone

Generate your response now:
"""


def _get_gemini_llm(thinking_level: str = "medium") -> ChatGoogleGenerativeAI:
    """Get configured Gemini LLM.

    Args:
        thinking_level: Controls thinking/reasoning effort

    Returns:
        Configured Gemini LLM
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not set")

    # Configure thinking based on level
    thinking_config = {"thinking": {"type": "enabled"}}
    if thinking_level == "low":
        thinking_config = {"thinking": {"type": "disabled"}}
    elif thinking_level == "medium":
        thinking_config = {
            "thinking": {"type": "enabled", "thoughts_percentage_limit": 5}
        }

    return ChatGoogleGenerativeAI(
        model="gemini-3.1-flash-lite-preview-05-20",
        google_api_key=api_key,
        thinking_config=thinking_config,
        temperature=0.7,
        max_tokens=2048,
    )


def _get_openrouter_llm() -> ChatOpenAI:
    """Get OpenRouter fallback LLM (DeepSeek V3).

    Returns:
        Configured OpenRouter LLM
    """
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY not set")

    return ChatOpenAI(
        model="deepseek/deepseek-v3",
        openai_api_key=api_key,
        base_url="https://openrouter.ai/api/v1",
        temperature=0.7,
        max_tokens=2048,
    )


def _format_context(chunks: list[dict]) -> str:
    """Format retrieved chunks as context for the LLM.

    Args:
        chunks: List of retrieved chunks

    Returns:
        Formatted context string
    """
    context_parts = []

    for i, chunk in enumerate(chunks):
        chunk_id = chunk.get("id", f"unknown-{i}")
        content = chunk.get("content", "")

        # Get metadata for better context
        metadata = chunk.get("metadata", {})
        source_name = metadata.get("source_name", "")
        heading = metadata.get("heading", "")

        # Build context snippet
        source_info = ""
        if source_name:
            source_info = f" (Source: {source_name})"
        if heading:
            source_info += f" - {heading}"

        context_parts.append(f"[CITE:{chunk_id}]{source_info}\n{content}")

    return "\n\n---\n\n".join(context_parts)


def _generate_with_fallback(
    prompt: str,
    thinking_level: str,
) -> str:
    """Generate response with fallback between Gemini and OpenRouter.

    Args:
        prompt: Formatted prompt for generation
        thinking_level: Thinking level for LLM config

    Returns:
        Generated response text
    """
    # Try Gemini first
    try:
        llm = _get_gemini_llm(thinking_level)
        response = llm.invoke(prompt)
        return response.content if hasattr(response, "content") else str(response)
    except Exception as e:
        error_str = str(e).lower()

        # Check if it's a rate limit error
        if "rate limit" in error_str or "resource exhausted" in error_str:
            pass  # Fall through to fallback
        else:
            # Re-raise other errors
            raise

    # Fallback to OpenRouter
    try:
        llm = _get_openrouter_llm()
        response = llm.invoke(prompt)
        return response.content if hasattr(response, "content") else str(response)
    except Exception as e:
        raise RuntimeError(f"Both Gemini and OpenRouter failed: {str(e)}")


def generator_node(state: AgentState) -> AgentState:
    """Generate response with citations.

    This node:
    1. Formats retrieved chunks as context
    2. Generates response using LLM with thinking_level config
    3. Includes [CITE:chunk_id] markers for citations
    4. Falls back to OpenRouter if Gemini rate-limits

    Args:
        state: Current agent state with query and retrieved_chunks

    Returns:
        Updated state with response containing citations
    """
    query = state.get("query", "")
    chunks = state.get("retrieved_chunks", [])
    thinking_level = state.get("thinking_level", "medium")
    memory_context = state.get("memory_context", "")

    if not query:
        return cast(
            AgentState,
            {
                **state,
                "response": "",
                "error": "No query provided to generator",
            },
        )

    # If no chunks, still try to answer (may need to say "I don't know")
    if not chunks:
        context_str = "No relevant context found in the knowledge base."
    else:
        context_str = _format_context(chunks)

    # Include memory context if available
    full_context = context_str
    if memory_context:
        full_context = (
            f"Previous conversation:\n{memory_context}\n\n---\n\n{context_str}"
        )

    try:
        prompt = GENERATOR_PROMPT.format(
            query=query,
            context=full_context,
        )

        response = _generate_with_fallback(prompt, thinking_level)

        # Clean up response - ensure proper citation format
        response = response.strip()

        return cast(
            AgentState,
            {
                **state,
                "response": response,
            },
        )

    except Exception as e:
        return cast(
            AgentState,
            {
                **state,
                "response": f"I encountered an error while generating the response: {str(e)}",
                "error": f"Generator error: {str(e)}",
            },
        )
