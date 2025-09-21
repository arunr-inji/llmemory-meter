"""Performance metrics calculation and analysis."""

from dataclasses import dataclass
from typing import List, Dict, Any
import statistics
from .workload import WorkloadResult


@dataclass
class PerformanceMetrics:
    """Performance metrics for a memory tool."""
    tool_name: str
    avg_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    total_tokens: int
    avg_tokens_per_query: float
    success_rate: float
    total_queries: int
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary."""
        return {
            "tool_name": self.tool_name,
            "avg_latency_ms": round(self.avg_latency_ms, 2),
            "p95_latency_ms": round(self.p95_latency_ms, 2),
            "p99_latency_ms": round(self.p99_latency_ms, 2),
            "total_tokens": self.total_tokens,
            "avg_tokens_per_query": round(self.avg_tokens_per_query, 2),
            "success_rate": round(self.success_rate * 100, 1),  # Convert to percentage
            "total_queries": self.total_queries
        }


class MetricsCalculator:
    """Calculate performance metrics from workload results."""
    
    @staticmethod
    def calculate_metrics(results: List[WorkloadResult]) -> PerformanceMetrics:
        """Calculate aggregated metrics from multiple workload results."""
        if not results:
            raise ValueError("No results provided")
        
        tool_name = results[0].tool_name
        all_latencies = []
        all_tokens = []
        successful_queries = 0
        total_queries = 0
        
        for result in results:
            for step_result in result.step_results:
                all_latencies.append(step_result.latency_ms)
                if step_result.tokens_used:
                    all_tokens.append(step_result.tokens_used)
                if step_result.success:
                    successful_queries += 1
                total_queries += 1
        
        # Calculate percentiles
        sorted_latencies = sorted(all_latencies)
        p95_index = int(0.95 * len(sorted_latencies))
        p99_index = int(0.99 * len(sorted_latencies))
        
        return PerformanceMetrics(
            tool_name=tool_name,
            avg_latency_ms=statistics.mean(all_latencies),
            p95_latency_ms=sorted_latencies[min(p95_index, len(sorted_latencies) - 1)],
            p99_latency_ms=sorted_latencies[min(p99_index, len(sorted_latencies) - 1)],
            total_tokens=sum(all_tokens),
            avg_tokens_per_query=statistics.mean(all_tokens) if all_tokens else 0,
            success_rate=successful_queries / total_queries if total_queries > 0 else 0,
            total_queries=total_queries
        )
    
    @staticmethod
    def compare_metrics(metrics_list: List[PerformanceMetrics]) -> Dict[str, Any]:
        """Compare metrics across different tools."""
        if not metrics_list:
            return {}
        
        comparison = {
            "tools": [m.tool_name for m in metrics_list],
            "latency_comparison": {},
            "token_comparison": {},
            "success_rate_comparison": {},
            "rankings": {}
        }
        
        # Latency comparison
        latencies = {m.tool_name: m.avg_latency_ms for m in metrics_list}
        best_latency = min(latencies.values())
        comparison["latency_comparison"] = {
            "values": latencies,
            "best": min(latencies, key=latencies.get),
            "relative_performance": {
                name: f"{((lat / best_latency - 1) * 100):+.1f}%" 
                for name, lat in latencies.items()
            }
        }
        
        # Token comparison
        tokens = {m.tool_name: m.avg_tokens_per_query for m in metrics_list}
        best_tokens = min([t for t in tokens.values() if t > 0], default=0)
        if best_tokens > 0:
            comparison["token_comparison"] = {
                "values": tokens,
                "best": min([k for k, v in tokens.items() if v == best_tokens], default="N/A"),
                "relative_efficiency": {
                    name: f"{((tok / best_tokens - 1) * 100):+.1f}%" if tok > 0 else "N/A"
                    for name, tok in tokens.items()
                }
            }
        
        # Success rate comparison
        success_rates = {m.tool_name: m.success_rate * 100 for m in metrics_list}
        comparison["success_rate_comparison"] = {
            "values": success_rates,
            "best": max(success_rates, key=success_rates.get)
        }
        
        # Overall rankings
        comparison["rankings"] = MetricsCalculator._calculate_rankings(metrics_list)
        
        return comparison
    
    @staticmethod
    def _calculate_rankings(metrics_list: List[PerformanceMetrics]) -> Dict[str, List[str]]:
        """Calculate rankings for different metrics."""
        rankings = {}
        
        # Latency ranking (lower is better)
        latency_sorted = sorted(metrics_list, key=lambda m: m.avg_latency_ms)
        rankings["latency"] = [m.tool_name for m in latency_sorted]
        
        # Token efficiency ranking (lower is better, excluding 0)
        token_sorted = sorted(
            [m for m in metrics_list if m.avg_tokens_per_query > 0], 
            key=lambda m: m.avg_tokens_per_query
        )
        rankings["token_efficiency"] = [m.tool_name for m in token_sorted]
        
        # Success rate ranking (higher is better)
        success_sorted = sorted(metrics_list, key=lambda m: m.success_rate, reverse=True)
        rankings["success_rate"] = [m.tool_name for m in success_sorted]
        
        return rankings
