"""
Base Memory Tool Abstract Class

Defines the interface that all memory tools must implement.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Callable
import asyncio
from functools import partial
import time
import uuid

from llmemory_meter.logging_utils import get_logger

logger = get_logger(__name__)
import tiktoken

from llmemory_meter.workload import WorkloadStep, StepResult


class MemoryTool(ABC):
    """Abstract base class for memory tools."""
    
    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        self.name = name
        self.config = config or {}
        self._last_tokens = 0
        self._reset_session()

    def _reset_session(self) -> None:
        """Regenerate session/user ids for workload isolation."""
        self._session_id = f"{self.name}_{uuid.uuid1().hex}"
        # Generate a unique user_id for workload isolation.
        self.user_id = f"benchmark_user_{self._session_id}"

    async def _run_in_executor(self, func: Callable, *args, **kwargs):
        """Run blocking code in the tool's executor (or default executor)."""
        loop = asyncio.get_event_loop()
        executor = getattr(self, "_executor", None)
        return await loop.run_in_executor(executor, partial(func, *args, **kwargs))

    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count using tiktoken if available, fallback to heuristic."""
        if not text:
            return 0
        try:
            encoding = tiktoken.get_encoding("cl100k_base")
            return len(encoding.encode(text))
        except Exception as e:
            # Fail loudly if token estimation is misconfigured or tiktoken errors.
            logger.error("Token estimation failed: %s", e)
            raise

    @abstractmethod
    async def store_memory(self, content: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Store information in memory."""
        pass
    
    @abstractmethod
    async def retrieve_memory(self, query: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Retrieve information from memory."""
        pass
    
    @abstractmethod
    async def chat(self, message: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Have a conversation using memory context."""
        pass
    
    async def clear_memory(self, session_id: Optional[str] = None) -> str:
        """Clear memory context. Optional method for tools that need isolation between workloads.
        
        Default implementation does nothing. Tools with persistent context (like Zep, MemGPT)
        should override this to clear their user/agent state between workloads.
        """
        return "No memory clearing needed for this tool"
    
    async def execute_step(self, step: WorkloadStep, step_index: int) -> StepResult:
        """Execute a single workload step and measure performance."""
        start_time = time.time()
        if hasattr(self, "_last_tokens"):
            self._last_tokens = 0
        
        try:
            if step.action == "store":
                response = await self.store_memory(step.content, step.metadata)
            elif step.action == "retrieve":
                response = await self.retrieve_memory(step.content, step.metadata)
            elif step.action == "chat":
                response = await self.chat(step.content, step.metadata)
            else:
                raise ValueError(f"Unknown action: {step.action}")
            
            latency_ms = (time.time() - start_time) * 1000
            
            return StepResult(
                step_index=step_index,
                action=step.action,
                response=response,
                latency_ms=latency_ms,
                tokens_used=getattr(self, "_last_tokens", 0),
                success=True
            )
            
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            return StepResult(
                step_index=step_index,
                action=step.action,
                response="",
                latency_ms=latency_ms,
                tokens_used=0,
                success=False,
                error_message=str(e)
            )
