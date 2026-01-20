"""
Base Memory Tool Abstract Class

Defines the interface that all memory tools must implement.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import time
import uuid
from datetime import datetime

from llmemory_meter.workload import WorkloadStep, StepResult

try:
    import tiktoken
    _has_tiktoken = True
except ImportError:
    _has_tiktoken = False


class MemoryTool(ABC):
    """Abstract base class for memory tools."""
    
    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        self.name = name
        self.config = config or {}
        self.model = self.config.get("model")
        self._reset_session()

    def _reset_session(self) -> None:
        """Regenerate session/user ids for workload isolation."""
        self._session_id = f"{self.name}_{uuid.uuid1().hex}"
        # Generate a unique user_id for workload isolation.
        self.user_id = f"benchmark_user_{self._session_id}"
    
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

    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count using tiktoken if available, fallback to heuristic.

        Tools should call this helper instead of re-implementing token estimation.
        """
        if not text:
            return 0
        if _has_tiktoken:
            try:
                encoding = tiktoken.get_encoding("cl100k_base")  # GPT-4 tokenizer
                return len(encoding.encode(text))
            except Exception:
                pass
        return len(text) // 4
    
    async def execute_step(self, step: WorkloadStep, step_index: int) -> StepResult:
        """Execute a single workload step and measure performance."""
        start_time = time.time()
        tokens_used = 0
        
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
                tokens_used=tokens_used,
                input_tokens=0,
                output_tokens=0,
                model=self.model,
                tokens_estimated=False,
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
                input_tokens=0,
                output_tokens=0,
                model=self.model,
                tokens_estimated=False,
                success=False,
                error_message=str(e)
            )
