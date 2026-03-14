"""Query decomposition node.

This node breaks down complex queries into multiple sub-queries for parallel retrieval.
The number of sub-queries depends on the complexity and intent type from classification.

Uses Gemini via LangChain for decomposition.
"""

import os
import json
from typing import cast

from langchain_google_genai import ChatGoogleGenerativeAI

from agent.state import AgentState


# Decomposition prompt template
DECOMPOSER_PROMPT = """You are a query decomposition assistant.

Break down the user's query into {max_queries} or fewer search-friendly sub-queries.
Each sub-query should be:
- Self-contained (can be answered independently)
- Focused on a single aspect
- Phrased for information retrieval

Original query: {query}

Intent type: {intent_type}
Complexity: {complexity}

Return a JSON object with this structure:
{{
    "sub_queries": ["sub-query 1", "sub-query 2", ...]
}}

Only return valid JSON, no other text.
"""


def _get_llm(thinking_level: str = "medium") -> ChatGoogleGenerativeAI:
    """Get configured Gemini LLM instance."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable not set")

    return ChatGoogleGenerativeAI(
        model="gemini-3.1-flash-lite-preview-05-20",
        google_api_key=api_key,
        thinking_config={"thinking": {"type": "enabled"}},
        temperature=0.3,
        max_tokens=1024,
    )


def decomposer_node(state: AgentState) -> AgentState:
    """Decompose the user query into sub-queries for parallel retrieval.

    The number of sub-queries is determined by:
    - Simple queries: 1 sub-query
    - Moderate complexity: 1-2 sub-queries
    - Complex queries: 2-4 sub-queries

    Args:
        state: Current agent state with query and classification

    Returns:
        Updated state with sub_queries list
    """
    query = state.get("query", "")
    complexity = state.get("complexity", "simple")
    intent_type = state.get("intent_type", "factual")

    if not query:
        return cast(
            AgentState,
            {
                **state,
                "error": "No query provided to decomposer",
            },
        )

    # Determine max sub-queries based on complexity
    if complexity == "simple":
        max_queries = 1
    elif complexity == "moderate":
        max_queries = 2
    else:  # complex
        max_queries = 4

    # For simple factual queries, no need to decompose
    if complexity == "simple" and intent_type == "factual":
        return cast(
            AgentState,
            {
                **state,
                "sub_queries": [query],
            },
        )

    try:
        llm = _get_llm()

        prompt = DECOMPOSER_PROMPT.format(
            max_queries=max_queries,
            query=query,
            intent_type=intent_type,
            complexity=complexity,
        )

        response = llm.invoke(prompt)
        content = response.content if hasattr(response, "content") else str(response)

        # Parse JSON response
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            # Try to extract JSON from markdown code block
            import re

            json_match = re.search(r"```json\s*(.*?)\s*```", content, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group(1))
            else:
                # Fallback to original query
                parsed = {"sub_queries": [query]}

        sub_queries = parsed.get("sub_queries", [query])

        # Ensure it's a list and limit to max_queries
        if not isinstance(sub_queries, list):
            sub_queries = [query]
        sub_queries = sub_queries[:max_queries]

        # Ensure at least one sub-query
        if not sub_queries:
            sub_queries = [query]

        return cast(
            AgentState,
            {
                **state,
                "sub_queries": sub_queries,
            },
        )

    except Exception as e:
        # Fallback to original query on error
        return cast(
            AgentState,
            {
                **state,
                "sub_queries": [query],
                "error": f"Decomposer error: {str(e)}",
            },
        )
