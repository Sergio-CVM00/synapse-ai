from typing import TypedDict, NotRequired, Literal
from datetime import datetime


class AgentState(TypedDict):
    """State schema for the LangGraph agent.

    This TypedDict defines all fields used throughout the agent's execution.
    Fields are populated as the state flows through each node.
    """

    # Input fields (required at start)
    query: str
    collection_ids: list[str]
    conversation_id: NotRequired[str | None]

    # Classifier output
    intent_type: NotRequired[
        Literal["factual", "explanatory", "analytical", "comparative", "creative"]
    ]
    complexity: NotRequired[Literal["simple", "moderate", "complex"]]
    thinking_level: NotRequired[Literal["low", "medium", "high"]]

    # Decomposer output
    sub_queries: NotRequired[list[str]]

    # Retriever output
    chunks: NotRequired[list[dict]]

    # Evaluator output
    sufficient: NotRequired[bool]
    evaluation_reasoning: NotRequired[str]

    # Ranker output
    retrieved_chunks: NotRequired[list[dict]]

    # Generator output
    response: NotRequired[str]

    # Formatter output
    cited_chunks: NotRequired[list[dict]]

    # Execution metadata
    iteration: NotRequired[int]
    error: NotRequired[str]

    # Memory context (populated from conversation history)
    memory_context: NotRequired[str]

    # Timestamps for debugging
    started_at: NotRequired[datetime]
    updated_at: NotRequired[datetime]
