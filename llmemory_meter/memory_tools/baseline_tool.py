"""
Baseline Memory Tools

Simple baseline implementations for comparing memory products:
- NoMemoryTool: Keeps only last k messages
- FullContextTool: Keeps all messages (no limit)
"""

from typing import Dict, Any, Optional, List
from llmemory_meter.memory_tools.base import MemoryTool


class NoMemoryTool(MemoryTool):
    """Baseline tool: stores only last k messages, discards the rest.

    Maintains two storage mechanisms:
    - stored_messages: All content from store_memory() and chat() calls, trimmed to last k
    - conversation_history: Chat turns in user/assistant format, trimmed to last k turns

    Both store/chat operations add to stored_messages, ensuring consistent context
    across all operations.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__("baseline", config)

        # Configuration
        self.k = self.config.get("k", 5)

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

        return f"Baseline stored (last {self.k}): {content[:50]}..."

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
        # Add user message to stored messages
        self.stored_messages.append(message)
        if len(self.stored_messages) > self.k:
            self.stored_messages = self.stored_messages[-self.k:]

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


class FullContextTool(MemoryTool):
    """Full-context baseline: stores ALL messages without limit.

    Simulates "stuff everything into prompt" strategy.
    WARNING: Memory grows unbounded unless max_messages is set.

    Maintains two storage mechanisms:
    - stored_messages: All content from store_memory() and chat() calls, no limit
    - conversation_history: Chat turns in user/assistant format, no limit

    Both store/chat operations add to stored_messages, ensuring consistent context
    across all operations. Optional max_messages provides safety limit.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__("full_context", config)

        # Configuration
        self.max_messages = self.config.get("max_messages", None)  # None = unlimited

        # In-memory storage
        self.stored_messages: List[str] = []
        self.conversation_history: List[Dict[str, str]] = []

    async def store_memory(self, content: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Store message, keeping all messages (no limit)."""
        self.stored_messages.append(content)

        # Apply safety limit if configured
        if self.max_messages and len(self.stored_messages) > self.max_messages:
            self.stored_messages = self.stored_messages[-self.max_messages:]

        return f"Full-context stored (total {len(self.stored_messages)} messages): {content[:50]}..."

    async def retrieve_memory(self, query: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Retrieve all stored messages."""
        if not self.stored_messages:
            return f"No messages stored for query: '{query}'"

        # Format messages (show preview if many messages to avoid huge logs)
        msg_count = len(self.stored_messages)

        if msg_count <= 6:
            formatted = "\n".join([
                f"  {i+1}. {msg}"
                for i, msg in enumerate(self.stored_messages)
            ])
        else:
            # Show first 3 and last 3 to keep logs readable
            first_three = "\n".join([f"  {i+1}. {msg}" for i, msg in enumerate(self.stored_messages[:3])])
            last_three = "\n".join([f"  {msg_count-2+i}. {msg}" for i, msg in enumerate(self.stored_messages[-3:])])
            formatted = f"{first_three}\n  ... ({msg_count-6} more messages) ...\n{last_three}"

        return f"Full-context retrieved (all {msg_count} messages) for '{query}':\n{formatted}"

    async def chat(self, message: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Chat using ALL messages as context (no limit)."""
        # Add user message to stored messages
        self.stored_messages.append(message)

        # Apply safety limit if configured
        if self.max_messages and len(self.stored_messages) > self.max_messages:
            self.stored_messages = self.stored_messages[-self.max_messages:]

        # Build context from stored messages
        if self.stored_messages:
            # Preview last 5 messages to keep logs readable
            context_preview = " | ".join([msg[:50] for msg in self.stored_messages[-5:]])
            response = f"Full-context response to '{message}' (using all {len(self.stored_messages)} messages as context): Based on full context [{context_preview}...], here is the response."
        else:
            response = f"Full-context response to '{message}': No prior context available."

        # Update conversation history (store ALL)
        self.conversation_history.append({"role": "user", "content": message})
        self.conversation_history.append({"role": "assistant", "content": response})

        # Apply safety limit if configured
        if self.max_messages and len(self.conversation_history) > self.max_messages * 2:
            self.conversation_history = self.conversation_history[-(self.max_messages * 2):]

        return response

    async def clear_memory(self, session_id: Optional[str] = None) -> str:
        """Clear memory between workloads."""
        self.stored_messages = []
        self.conversation_history = []
        return "Full-context memory cleared"
