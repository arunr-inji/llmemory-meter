"""Workload definition and result classes for memory tool testing."""

from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from datetime import datetime


@dataclass
class WorkloadStep:
    """A single step in a workload test."""
    action: str  # "store", "retrieve", "chat"
    content: str
    expected_response: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class Workload:
    """A complete workload for testing memory tools."""
    name: str
    description: str
    steps: List[WorkloadStep]
    expected_outcomes: Optional[Dict[str, Any]] = None
    
    @classmethod
    def create_simple_workload(cls, name: str, memory_content: str, retrieval_query: str):
        """Create a simple store-and-retrieve workload."""
        steps = [
            WorkloadStep(
                action="store",
                content=memory_content,
                metadata={"type": "information_storage"}
            ),
            WorkloadStep(
                action="retrieve", 
                content=retrieval_query,
                metadata={"type": "information_retrieval"}
            )
        ]
        
        return cls(
            name=name,
            description=f"Simple store and retrieve test: {name}",
            steps=steps
        )
    
    @classmethod
    def create_conversation_workload(cls, name: str, conversation_steps: List[str]):
        """Create a multi-turn conversation workload."""
        steps = []
        for i, content in enumerate(conversation_steps):
            steps.append(WorkloadStep(
                action="chat",
                content=content,
                metadata={"turn": i + 1, "type": "conversation"}
            ))
        
        return cls(
            name=name,
            description=f"Multi-turn conversation test: {name}",
            steps=steps
        )


@dataclass 
class StepResult:
    """Result of executing a single workload step."""
    step_index: int
    action: str
    response: str
    latency_ms: float
    tokens_used: Optional[int] = None
    success: bool = True
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class WorkloadResult:
    """Complete result of running a workload on a memory tool."""
    tool_name: str
    workload_name: str
    step_results: List[StepResult]
    total_latency_ms: float
    total_tokens_used: int
    success_rate: float
    timestamp: datetime
    
    @property
    def avg_latency_ms(self) -> float:
        """Calculate average latency per step."""
        if not self.step_results:
            return 0.0
        return sum(r.latency_ms for r in self.step_results) / len(self.step_results)
    
    @property
    def p95_latency_ms(self) -> float:
        """Calculate 95th percentile latency."""
        if not self.step_results:
            return 0.0
        latencies = sorted([r.latency_ms for r in self.step_results])
        index = int(0.95 * len(latencies))
        return latencies[min(index, len(latencies) - 1)]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary for easy serialization."""
        return {
            "tool_name": self.tool_name,
            "workload_name": self.workload_name,
            "total_latency_ms": self.total_latency_ms,
            "avg_latency_ms": self.avg_latency_ms,
            "p95_latency_ms": self.p95_latency_ms,
            "total_tokens_used": self.total_tokens_used,
            "success_rate": self.success_rate,
            "num_steps": len(self.step_results),
            "timestamp": self.timestamp.isoformat()
        }
