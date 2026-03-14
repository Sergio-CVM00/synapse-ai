"""Conversation summary memory for the agent.

This module provides memory capabilities to maintain conversation context
across multiple turns. It uses LLM-based summarization to compress
the conversation history into a context string.

The memory is stored per conversation and can be loaded/updated during
agent execution.
"""

import os
import json
from typing import Optional

from langchain_google_genai import ChatGoogleGenerativeAI

from db.supabase import get_supabase_client


# Prompt for summarization
SUMMARIZATION_PROMPT = """Summarize the following conversation concisely while preserving key information:

{conversation}

Create a summary that captures:
- Main topics discussed
- Key facts or decisions
- Any outstanding questions

Keep the summary under 500 words.
"""


def _get_llm() -> ChatGoogleGenerativeAI:
    """Get configured Gemini LLM for summarization."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not set")

    return ChatGoogleGenerativeAI(
        model="gemini-3.1-flash-lite-preview-05-20",
        google_api_key=api_key,
        temperature=0.3,
        max_tokens=1024,
    )


class ConversationSummaryMemory:
    """Manages conversation history with LLM-based summarization.

    This class:
    - Stores conversation messages
    - Summarizes old messages to save context
    - Provides context string for the agent

    Usage:
        memory = ConversationSummaryMemory()

        # Add messages
        memory.add_message("user", "What is RAG?")
        memory.add_message("assistant", "RAG stands for...")

        # Get context for agent
        context = memory.get_context()

        # Save to database
        memory.save_to_db(conversation_id)

        # Load from database
        memory.load_from_db(conversation_id)
    """

    def __init__(
        self,
        max_messages_before_summary: int = 10,
        summary_threshold: int = 5,
    ):
        """Initialize the memory.

        Args:
            max_messages_before_summary: Messages before triggering summarization
            summary_threshold: How many recent messages to keep when summarizing
        """
        self.max_messages = max_messages_before_summary
        self.summary_threshold = summary_threshold
        self.messages: list[dict] = []
        self.summary: str = ""

    def add_message(self, role: str, content: str) -> None:
        """Add a message to the conversation history.

        Args:
            role: "user" or "assistant"
            content: Message content
        """
        self.messages.append(
            {
                "role": role,
                "content": content,
            }
        )

        # Check if we need to summarize
        if len(self.messages) >= self.max_messages:
            self._summarize_old_messages()

    def _summarize_old_messages(self) -> None:
        """Compress old messages into a summary."""
        if len(self.messages) <= self.summary_threshold:
            return

        # Get messages to summarize (all except recent ones)
        messages_to_summarize = self.messages[: -self.summary_threshold]
        recent_messages = self.messages[-self.summary_threshold :]

        # Format conversation for summarization
        conversation_text = "\n".join(
            [f"{msg['role']}: {msg['content']}" for msg in messages_to_summarize]
        )

        try:
            prompt = SUMMARIZATION_PROMPT.format(conversation=conversation_text)
            llm = _get_llm()
            response = llm.invoke(prompt)

            # Update summary and messages
            self.summary = (
                response.content if hasattr(response, "content") else str(response)
            )
            self.messages = recent_messages

        except Exception as e:
            # On error, just keep messages as-is
            pass

    def get_context(self) -> str:
        """Get the conversation context for the agent.

        Returns:
            Context string with summary and recent messages
        """
        parts = []

        if self.summary:
            parts.append(f"Previous conversation summary:\n{self.summary}")

        if self.messages:
            recent_text = "\n".join(
                [
                    f"{msg['role']}: {msg['content'][:200]}..."
                    if len(msg["content"]) > 200
                    else f"{msg['role']}: {msg['content']}"
                    for msg in self.messages[-3:]  # Last 3 messages
                ]
            )
            parts.append(f"Recent messages:\n{recent_text}")

        return "\n\n".join(parts) if parts else ""

    def get_all_messages(self) -> list[dict]:
        """Get all messages in the conversation.

        Returns:
            List of message dictionaries
        """
        return self.messages.copy()

    def clear(self) -> None:
        """Clear all memory."""
        self.messages = []
        self.summary = ""

    def save_to_db(self, conversation_id: str) -> None:
        """Save memory state to database.

        Args:
            conversation_id: The conversation ID
        """
        supabase = get_supabase_client()

        data = {
            "id": conversation_id,
            "summary": self.summary,
            "messages": json.dumps(self.messages),
        }

        # Upsert into conversations table
        supabase.table("conversations").upsert(data).execute()

    def load_from_db(self, conversation_id: str) -> bool:
        """Load memory state from database.

        Args:
            conversation_id: The conversation ID to load

        Returns:
            True if loaded successfully, False otherwise
        """
        supabase = get_supabase_client()

        response = (
            supabase.table("conversations")
            .select("summary", "messages")
            .eq("id", conversation_id)
            .execute()
        )

        if response.data and len(response.data) > 0:
            row = response.data[0]
            self.summary = row.get("summary", "")

            messages_str = row.get("messages", "[]")
            try:
                self.messages = json.loads(messages_str)
            except json.JSONDecodeError:
                self.messages = []

            return True

        return False

    @classmethod
    def load_for_conversation(cls, conversation_id: str) -> "ConversationSummaryMemory":
        """Factory method to load memory for a conversation.

        Args:
            conversation_id: The conversation ID

        Returns:
            Loaded ConversationSummaryMemory instance
        """
        memory = cls()
        memory.load_from_db(conversation_id)
        return memory
