"""
No-Memory Baseline Tool

Simple baseline that keeps only the last k messages in memory.
Provides comparison baseline for memory products.
"""

from typing import Dict, Any, Optional, List
from llmemory_meter.memory_tools.base import MemoryTool


class NoMemoryTool(MemoryTool):
    """Baseline tool: stores only last k messages, discards the rest."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__("baseline", config)

        # Configuration
        self.k = self.config.get("k", 5)
        self.include_metadata = self.config.get("include_metadata", False)

        # In-memory storage
        self.stored_messages: List[str] = []
        self.conversation_history: List[Dict[str, str]] = []

    async def store_memory(self, content: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Store message, keeping only last k."""
        # Append new message
        self.stored_messages.append(content)

        # Trim to last k messages
        if len(self.stored_messages) > self.k:
            self.stored_messages = self.stored_messages[-self.k:]

        return f"Baseline stored (last {self.k}): {content[:80]}..."

    async def retrieve_memory(self, query: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Retrieve last k stored messages."""
        if not self.stored_messages:
            return f"No messages stored for query: '{query}'"

        # Format stored messages
        formatted = "\n".join([
            f"  {i+1}. {msg}"
            for i, msg in enumerate(self.stored_messages)
        ])

        return f"Baseline retrieved (last {len(self.stored_messages)} messages) for '{query}':\n{formatted}"

    async def chat(self, message: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Chat using last k messages as context."""
        # Build context from stored messages
        if self.stored_messages:
            context = " | ".join([msg[:50] for msg in self.stored_messages])
            response = f"Baseline response to '{message}' (using {len(self.stored_messages)} messages as context): Based on context [{context}], here is the response."
        else:
            response = f"Baseline response to '{message}': No prior context available."

        # Update conversation history
        self.conversation_history.append({"role": "user", "content": message})
        self.conversation_history.append({"role": "assistant", "content": response})

        # Trim to last k turns (k turns = 2k messages)
        if len(self.conversation_history) > self.k * 2:
            self.conversation_history = self.conversation_history[-(self.k * 2):]

        return response

    async def clear_memory(self, session_id: Optional[str] = None) -> str:
        """Clear memory between workloads."""
        self.stored_messages = []
        self.conversation_history = []
        return "Baseline memory cleared"
