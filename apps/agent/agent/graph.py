"""LangGraph agent state machine.

This module assembles the complete agent graph with all nodes and edges:

```
Query
  │
  ▼
[1] Classifier ──────────────► intent_type, complexity, thinking_level
  │
  ▼
[2] Decomposer ──────────────► sub_queries[]
  │
  ▼
[3] Retriever ───────────────► chunks[]
  │
  ▼
[4] Evaluator ──(conditional)─► sufficient
  │    │
  │    ├── NOT sufficient & iter<2 ──► reformulates query
  │    │                              │
  │    │                              ▼
  │    │                         [3] Retriever
  │    │
  │    └── sufficient (or iter>=2) ──►
  │
  ▼
[5] Ranker ──────────────────► retrieved_chunks (top-8)
  │
  ▼
[6] Generator ───────────────► response with [CITE:chunk_id]
  │
  ▼
[7] Formatter ───────────────► final response, cited_chunks
```

Key features:
- Conditional edge from evaluator for retry logic
- Proper iteration tracking
- Memory context support
"""

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from agent.state import AgentState
from agent.nodes import (
    classifier_node,
    decomposer_node,
    retriever_node,
    evaluator_node,
    ranker_node,
    generator_node,
    formatter_node,
    should_retry,
)


def create_agent_graph() -> StateGraph:
    """Create and configure the agent state graph.

    Returns:
        Compiled LangGraph StateGraph
    """
    # Create the state graph
    graph = StateGraph(AgentState)

    # Add all nodes
    graph.add_node("classifier", classifier_node)
    graph.add_node("decomposer", decomposer_node)
    graph.add_node("retriever", retriever_node)
    graph.add_node("evaluator", evaluator_node)
    graph.add_node("ranker", ranker_node)
    graph.add_node("generator", generator_node)
    graph.add_node("formatter", formatter_node)

    # Set entry point
    graph.set_entry_point("classifier")

    # Linear edges
    graph.add_edge("classifier", "decomposer")
    graph.add_edge("decomposer", "retriever")
    graph.add_edge("ranker", "generator")
    graph.add_edge("generator", "formatter")
    graph.add_edge("formatter", END)

    # Conditional edge from evaluator
    # If not sufficient and iteration < 2: retry retrieval
    # Otherwise: proceed to ranker
    graph.add_conditional_edges(
        "evaluator",
        should_retry,
        {
            "retriever": "retriever",
            "ranker": "ranker",
        },
    )

    return graph


def compile_agent_graph() -> StateGraph:
    """Compile the agent graph with checkpointing.

    Uses MemorySaver for state persistence during execution.
    This allows the graph to maintain state across streaming events.

    Returns:
        Compiled graph ready for execution
    """
    graph = create_agent_graph()

    # Add checkpointing for state persistence
    checkpointer = MemorySaver()

    compiled = graph.compile(checkpointer=checkpointer)

    return compiled


# Singleton compiled graph
agent_graph = compile_agent_graph()


def run_agent(
    query: str,
    collection_ids: list[str],
    conversation_id: str | None = None,
    memory_context: str = "",
) -> AgentState:
    """Run the agent with a user query.

    This is a synchronous wrapper for the async graph.

    Args:
        query: User question
        collection_ids: UUIDs of collections to search
        conversation_id: Optional conversation ID for memory
        memory_context: Optional conversation history

    Returns:
        Final agent state with response and cited_chunks
    """
    from datetime import datetime

    initial_state: AgentState = {
        "query": query,
        "collection_ids": collection_ids,
        "conversation_id": conversation_id,
        "memory_context": memory_context,
        "iteration": 0,
        "started_at": datetime.utcnow(),
    }

    # Run the graph
    final_state = agent_graph.invoke(initial_state)

    return final_state


async def run_agent_async(
    query: str,
    collection_ids: list[str],
    conversation_id: str | None = None,
    memory_context: str = "",
) -> AgentState:
    """Run the agent asynchronously.

    Args:
        query: User question
        collection_ids: UUIDs of collections to search
        conversation_id: Optional conversation ID for memory
        memory_context: Optional conversation history

    Returns:
        Final agent state with response and cited_chunks
    """
    from datetime import datetime

    initial_state: AgentState = {
        "query": query,
        "collection_ids": collection_ids,
        "conversation_id": conversation_id,
        "memory_context": memory_context,
        "iteration": 0,
        "started_at": datetime.utcnow(),
    }

    # Run the graph asynchronously
    final_state = await agent_graph.ainvoke(initial_state)

    return final_state
