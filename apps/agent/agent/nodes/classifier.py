"""Classifier node for intent and thinking level classification.

This node analyzes the user query to determine:
- intent_type: What type of question is being asked
- complexity: How complex the query is
- thinking_level: How much reasoning/thinking the LLM should apply

Uses Gemini via LangChain for classification.
"""

import os
import json
from typing import Any, cast

from langchain_google_genai import ChatGoogleGenerativeAI

from agent.state import AgentState


# Classification prompt template
CLASSIFIER_PROMPT = """You are a query classifier for an AI assistant.

Analyze the user's query and classify it according to these categories:

**INTENT TYPE:**
- factual: Query asking for specific facts, definitions, or concrete information
- explanatory: Query asking why or how something works, needs explanation
- analytical: Query requiring analysis, synthesis, or evaluation of information
- comparative: Query comparing multiple things, entities, or approaches
- creative: Query requiring generation of new ideas, content, or solutions

**COMPLEXITY:**
- simple: Single concept, straightforward answer expected
- moderate: Multiple concepts, some analysis needed
- complex: Multiple interconnected concepts, deep analysis required

**THINKING LEVEL:**
- low: Quick, direct answer. Use for simple factual queries.
- medium: Moderate reasoning. Use for explanatory and moderate complexity.
- high: Deep reasoning, step-by-step analysis. Use for analytical, complex, or comparative.

User query: {query}

Return a JSON object with this exact structure:
{{
    "intent_type": "...",
    "complexity": "...",
    "thinking_level": "..."
}}

Only return valid JSON, no other text.
"""


def _get_llm(thinking_level: str = "low") -> ChatGoogleGenerativeAI:
    """Get configured Gemini LLM instance.

    Args:
        thinking_level: Controls the thinking/reasoning effort
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable not set")

    # Configure thinking based on level
    thinking_config = {"thinking": {"type": "enabled"}}
    if thinking_level == "low":
        thinking_config = {"thinking": {"type": "disabled"}}
    elif thinking_level == "medium":
        thinking_config = {
            "thinking": {"type": "enabled", "thoughts_percentage_limit": 5}
        }
    # High uses default (more thinking)

    return ChatGoogleGenerativeAI(
        model="gemini-3.1-flash-lite-preview-05-20",
        google_api_key=api_key,
        thinking_config=thinking_config,
        temperature=0.3,
        max_tokens=1024,
    )


def classifier_node(state: AgentState) -> AgentState:
    """Classify the user query for intent, complexity, and thinking level.

    This is the first node in the agent graph. It analyzes the query
    to determine how to process it through the rest of the pipeline.

    Args:
        state: Current agent state containing the user query

    Returns:
        Updated state with classification results
    """
    query = state.get("query", "")

    if not query:
        return {
            **state,
            "error": "No query provided to classifier",
        }

    try:
        # Use a low-thinking LLM for initial classification
        llm = _get_llm("low")

        # Format prompt with query
        prompt = CLASSIFIER_PROMPT.format(query=query)

        # Get classification result
        response = llm.invoke(prompt)
        content = response.content if hasattr(response, "content") else str(response)

        # Parse JSON response
        try:
            # Try to extract JSON from response
            parsed = json.loads(content)
        except json.JSONDecodeError:
            # Try to extract JSON from markdown code block
            import re

            json_match = re.search(r"```json\s*(.*?)\s*```", content, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group(1))
            else:
                # Fallback to default values
                parsed = {
                    "intent_type": "factual",
                    "complexity": "simple",
                    "thinking_level": "low",
                }

        # Validate and normalize results
        intent_type: str = parsed.get("intent_type", "factual")
        complexity: str = parsed.get("complexity", "simple")
        thinking_level: str = parsed.get("thinking_level", "low")

        # Ensure values are valid
        valid_intents = [
            "factual",
            "explanatory",
            "analytical",
            "comparative",
            "creative",
        ]
        valid_complexities = ["simple", "moderate", "complex"]
        valid_thinking = ["low", "medium", "high"]

        if intent_type not in valid_intents:
            intent_type = "factual"
        if complexity not in valid_complexities:
            complexity = "simple"
        if thinking_level not in valid_thinking:
            thinking_level = "low"

        return cast(
            AgentState,
            {
                **state,
                "intent_type": intent_type,
                "complexity": complexity,
                "thinking_level": thinking_level,
                "iteration": state.get("iteration", 0),
            },
        )

    except Exception as e:
        # Fallback to defaults on error
        return cast(
            AgentState,
            {
                **state,
                "intent_type": "factual",
                "complexity": "simple",
                "thinking_level": "low",
                "iteration": state.get("iteration", 0),
                "error": f"Classifier error: {str(e)}",
            },
        )
