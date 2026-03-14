"""Sufficiency evaluation node.

This node evaluates whether the retrieved context is sufficient to answer
the user's query. It determines if more iterations are needed.

The evaluation logic:
- If sufficient: proceed to ranker
- If NOT sufficient AND iteration < 2: reformulate query → back to retriever
- If NOT sufficient AND iteration >= 2: force true (max iterations reached)

Uses a lightweight LLM for evaluation.
"""

import os
import json
from typing import cast

from langchain_google_genai import ChatGoogleGenerativeAI

from agent.state import AgentState


# Maximum retrieval iterations as per AGENTS.md
MAX_RETRIEVAL_ITERATIONS = 2

# Evaluation prompt template
EVALUATOR_PROMPT = """You are a context sufficiency evaluator.

Evaluate whether the retrieved context is sufficient to answer the user's query.

User query: {query}

Retrieved context chunks ({chunk_count}):
{context_preview}

Evaluate:
1. Does the context contain relevant information to answer the query?
2. Are there enough distinct sources/information pieces?
3. Is the information detailed enough?

Return a JSON object:
{{
    "sufficient": true/false,
    "reasoning": "Brief explanation of why context is/isn't sufficient",
    "gaps": ["Gap 1", "Gap 2"]  // Only if insufficient
}}

Only return valid JSON, no other text.
"""


def _get_llm() -> ChatGoogleGenerativeAI:
    """Get configured Gemini LLM for evaluation."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not set")

    return ChatGoogleGenerativeAI(
        model="gemini-3.1-flash-lite-preview-05-20",
        google_api_key=api_key,
        thinking_config={"thinking": {"type": "disabled"}},  # Fast evaluation
        temperature=0.1,
        max_tokens=512,
    )


def _create_reformulated_query(
    original_query: str,
    gaps: list[str],
    retrieved_context: str,
) -> str:
    """Create a reformulated query to address gaps.

    Args:
        original_query: The original user query
        gaps: Identified gaps in the context
        retrieved_context: Summary of what was retrieved

    Returns:
        Reformulated query targeting the gaps
    """
    gaps_text = ", ".join(gaps[:3])  # Limit to top 3 gaps

    reformulation_prompt = f"""Original query: {original_query}

Current context covers: {retrieved_context}

Missing information (gaps): {gaps_text}

Create a reformulated search query that addresses these gaps.
The query should be specific and targeted to find the missing information.

Return only the reformulated query, no explanation."""

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return original_query

    try:
        llm = _get_llm()
        response = llm.invoke(reformulation_prompt)
        content = response.content if hasattr(response, "content") else str(response)

        # Clean up response
        reformulated = content.strip().strip('"').strip("'")

        if reformulated and len(reformulated) > 10:
            return reformulated
    except Exception:
        pass

    # Fallback: append gaps to original query
    return f"{original_query} {gaps_text}"


def evaluator_node(state: AgentState) -> AgentState:
    """Evaluate if the retrieved context is sufficient.

    This is a conditional node that determines the next step:
    - If sufficient: proceed to ranker
    - If NOT sufficient AND iteration < 2: reformulate → retriever
    - If NOT sufficient AND iteration >= 2: force true (max iterations)

    Args:
        state: Current agent state with chunks and query

    Returns:
        Updated state with sufficient flag and potentially reformulated query
    """
    query = state.get("query", "")
    chunks = state.get("chunks", [])
    iteration = state.get("iteration", 0)

    if not query:
        return cast(
            AgentState,
            {
                **state,
                "sufficient": True,  # Default to proceeding
                "evaluation_reasoning": "No query provided",
            },
        )

    # If no chunks retrieved, need more iterations
    if not chunks:
        if iteration >= MAX_RETRIEVAL_ITERATIONS:
            # Max iterations reached, force sufficient
            return cast(
                AgentState,
                {
                    **state,
                    "sufficient": True,
                    "evaluation_reasoning": "Max iterations reached",
                    "iteration": iteration,
                },
            )
        else:
            # Need to retrieve more
            return cast(
                AgentState,
                {
                    **state,
                    "sufficient": False,
                    "evaluation_reasoning": "No chunks retrieved",
                    "iteration": iteration,
                },
            )

    # Check if we have enough chunks
    if len(chunks) < 2 and iteration >= MAX_RETRIEVAL_ITERATIONS:
        return cast(
            AgentState,
            {
                **state,
                "sufficient": True,
                "evaluation_reasoning": "Max iterations with limited chunks",
                "iteration": iteration,
            },
        )

    # Prepare context preview for evaluation
    context_preview = "\n\n".join(
        [
            f"[Chunk {i + 1}]: {chunk.get('content', '')[:300]}..."
            for i, chunk in enumerate(chunks[:5])  # Limit to 5 chunks
        ]
    )

    try:
        llm = _get_llm()

        prompt = EVALUATOR_PROMPT.format(
            query=query,
            chunk_count=len(chunks),
            context_preview=context_preview,
        )

        response = llm.invoke(prompt)
        content = response.content if hasattr(response, "content") else str(response)

        # Parse JSON response
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            import re

            json_match = re.search(r"```json\s*(.*?)\s*```", content, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group(1))
            else:
                # Default to sufficient if parsing fails
                parsed = {
                    "sufficient": True,
                    "reasoning": "Parse failed, defaulting to sufficient",
                }

        sufficient = parsed.get("sufficient", True)
        reasoning = parsed.get("reasoning", "")

        # If not sufficient and we can still iterate
        if not sufficient:
            if iteration >= MAX_RETRIEVAL_ITERATIONS:
                # Max iterations reached, force sufficient
                return cast(
                    AgentState,
                    {
                        **state,
                        "sufficient": True,
                        "evaluation_reasoning": f"Max iterations ({MAX_RETRIEVAL_ITERATIONS}) reached. {reasoning}",
                        "iteration": iteration,
                    },
                )
            else:
                # Reformulate query and increase iteration
                gaps = parsed.get("gaps", [])
                retrieved_context = context_preview[:500]

                reformulated_query = _create_reformulated_query(
                    query, gaps, retrieved_context
                )

                return cast(
                    AgentState,
                    {
                        **state,
                        "query": reformulated_query,  # Update to reformulated query
                        "sufficient": False,
                        "evaluation_reasoning": f"Need more context. {reasoning}",
                        "iteration": iteration + 1,
                    },
                )

        # Sufficient - proceed to ranker
        return cast(
            AgentState,
            {
                **state,
                "sufficient": True,
                "evaluation_reasoning": reasoning,
                "iteration": iteration,
            },
        )

    except Exception as e:
        # On error, default to proceeding
        return cast(
            AgentState,
            {
                **state,
                "sufficient": True,
                "evaluation_reasoning": f"Error during evaluation: {str(e)}",
                "iteration": iteration,
            },
        )


def should_retry(state: AgentState) -> str:
    """Determine if the agent should retry retrieval or proceed to ranking.

    This is used as a conditional edge function in the graph.

    Args:
        state: Current agent state

    Returns:
        "retriever" if should retry, "ranker" if should proceed
    """
    sufficient = state.get("sufficient", True)
    iteration = state.get("iteration", 0)

    if not sufficient and iteration < MAX_RETRIEVAL_ITERATIONS:
        return "retriever"

    return "ranker"
