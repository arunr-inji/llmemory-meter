"""
Base Memory Tool Abstract Class

Defines the interface that all memory tools must implement.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import time
import random
from datetime import datetime

from llmemory_meter.workload import WorkloadStep, StepResult


class MemoryTool(ABC):
    """Abstract base class for memory tools."""
    
    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        self.name = name
        self.config = config or {}
        self._session_id = f"{name}_{int(time.time())}"
        self.user_id = self._generate_user_id()

    def _generate_user_id(self) -> str:
        """Generate a unique user_id for workload isolation."""
        return f"benchmark_user_{int(time.time() * 1000)}_{random.randint(1000, 9999)}"
    
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
