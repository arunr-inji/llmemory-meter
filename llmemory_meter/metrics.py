"""Performance metrics calculation and analysis."""

from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple
import statistics
from llmemory_meter.workload import WorkloadResult
from llmemory_meter.pricing import merge_pricing, split_tokens, calculate_cost_usd


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
    avg_accuracy: float = None  # Average accuracy score (primary provider)
    accuracy_by_provider: Dict[str, float] = None  # Accuracy by embedding provider
    operation_metrics: Optional[Dict[str, Dict[str, Any]]] = None  # Per-action metrics
    total_cost: Optional[float] = None
    avg_cost_per_query: Optional[float] = None
    cost_per_1k_ops: Optional[float] = None
    cost_priced_queries: Optional[int] = None
    cost_unpriced_models: Optional[List[str]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary."""
        result = {
            "tool_name": self.tool_name,
            "avg_latency_ms": round(self.avg_latency_ms, 2),
            "p95_latency_ms": round(self.p95_latency_ms, 2),
            "p99_latency_ms": round(self.p99_latency_ms, 2),
            "total_tokens": self.total_tokens,
            "avg_tokens_per_query": round(self.avg_tokens_per_query, 2),
            "success_rate": round(self.success_rate * 100, 1),  # Convert to percentage
            "total_queries": self.total_queries
        }
        
        # Add accuracy if available
        if self.avg_accuracy is not None:
            result["avg_accuracy"] = round(self.avg_accuracy, 3)
        if self.accuracy_by_provider:
            result["accuracy_by_provider"] = {
                provider: round(score, 3) for provider, score in self.accuracy_by_provider.items()
            }

        if self.operation_metrics:
            result["operation_metrics"] = self._format_operation_metrics(self.operation_metrics)

        if self.cost_priced_queries is not None:
            result["cost_priced_queries"] = self.cost_priced_queries
            if self.cost_unpriced_models:
                result["cost_unpriced_models"] = sorted(self.cost_unpriced_models)
        if self.total_cost is not None:
            result["total_cost_usd"] = round(self.total_cost, 6)
            if self.avg_cost_per_query is not None:
                result["avg_cost_per_query_usd"] = round(self.avg_cost_per_query, 6)
            if self.cost_per_1k_ops is not None:
                result["cost_per_1k_ops_usd"] = round(self.cost_per_1k_ops, 6)
        
        return result

    @staticmethod
    def _format_operation_metrics(operation_metrics: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """Round operation metrics for output."""
        formatted = {}
        for action, metrics in operation_metrics.items():
            formatted[action] = {
                "avg_latency_ms": round(metrics["avg_latency_ms"], 2),
                "p95_latency_ms": round(metrics["p95_latency_ms"], 2),
                "p99_latency_ms": round(metrics["p99_latency_ms"], 2),
                "total_tokens": metrics["total_tokens"],
                "avg_tokens_per_query": round(metrics["avg_tokens_per_query"], 2),
                "success_rate": round(metrics["success_rate"] * 100, 1),
                "total_queries": metrics["total_queries"]
            }
            if "total_cost" in metrics and metrics["total_cost"] is not None:
                formatted[action]["total_cost_usd"] = round(metrics["total_cost"], 6)
            if "avg_cost_per_query" in metrics and metrics["avg_cost_per_query"] is not None:
                formatted[action]["avg_cost_per_query_usd"] = round(metrics["avg_cost_per_query"], 6)
            if "cost_per_1k_ops" in metrics and metrics["cost_per_1k_ops"] is not None:
                formatted[action]["cost_per_1k_ops_usd"] = round(metrics["cost_per_1k_ops"], 6)
            if "cost_priced_queries" in metrics and metrics["cost_priced_queries"] is not None:
                formatted[action]["cost_priced_queries"] = metrics["cost_priced_queries"]
        return formatted


class MetricsCalculator:
    """Calculate performance metrics from workload results."""
    
    @staticmethod
    def calculate_metrics(results: List[WorkloadResult], config: Optional[Dict[str, Any]] = None) -> PerformanceMetrics:
        """Calculate aggregated metrics from multiple workload results."""
        if not results:
            raise ValueError("No results provided")
        
        tool_name = results[0].tool_name
        all_latencies = []
        all_tokens = []
        successful_queries = 0
        total_queries = 0
        all_accuracy_scores = []
        accuracy_by_provider = {}
        operation_buckets = {}
        all_step_results = []
        
        for result in results:
            for step_result in result.step_results:
                all_step_results.append(step_result)
                all_latencies.append(step_result.latency_ms)
                if step_result.tokens_used is not None:
                    all_tokens.append(step_result.tokens_used)
                if step_result.success:
                    successful_queries += 1
                total_queries += 1

                operation_buckets.setdefault(step_result.action, []).append(step_result)
                
                # Collect accuracy scores
                if step_result.accuracy is not None:
                    all_accuracy_scores.append(step_result.accuracy)
                
                # Collect accuracy by provider
                if step_result.accuracy_by_provider:
                    for provider, score in step_result.accuracy_by_provider.items():
                        if score is not None:
                            accuracy_by_provider.setdefault(provider, []).append(score)
        
        # Calculate percentiles
        sorted_latencies = sorted(all_latencies)
        p95_index = int(0.95 * len(sorted_latencies))
        p99_index = int(0.99 * len(sorted_latencies))
        
        # Calculate average accuracy
        avg_accuracy = statistics.mean(all_accuracy_scores) if all_accuracy_scores else None
        
        # Calculate average accuracy by provider
        avg_accuracy_by_provider = None
        if accuracy_by_provider:
            avg_accuracy_by_provider = {
                provider: statistics.mean(scores)
                for provider, scores in accuracy_by_provider.items()
            }

        # Calculate per-action metrics
        operation_metrics = {}
        for action, steps in operation_buckets.items():
            operation_metrics[action] = MetricsCalculator._calculate_operation_metrics(steps)

        # Cost analysis
        cost_total = None
        avg_cost_per_query = None
        cost_per_1k_ops = None
        cost_priced_queries = None
        cost_unpriced_models = None

        metrics_config = (config or {}).get("metrics", {})
        if metrics_config.get("cost_analysis", False):
            pricing = merge_pricing((config or {}).get("pricing"))
            (
                cost_total,
                cost_priced_queries,
                cost_unpriced_models,
                cost_by_action,
            ) = MetricsCalculator._calculate_costs(all_step_results, pricing)

            if cost_priced_queries:
                avg_cost_per_query = cost_total / cost_priced_queries
                cost_per_1k_ops = avg_cost_per_query * 1000

            for action, costs in cost_by_action.items():
                operation_metrics.setdefault(action, {})
                operation_metrics[action].update(costs)
        
        return PerformanceMetrics(
            tool_name=tool_name,
            avg_latency_ms=statistics.mean(all_latencies),
            p95_latency_ms=sorted_latencies[min(p95_index, len(sorted_latencies) - 1)],
            p99_latency_ms=sorted_latencies[min(p99_index, len(sorted_latencies) - 1)],
            total_tokens=sum(all_tokens),
            avg_tokens_per_query=statistics.mean(all_tokens) if all_tokens else 0,
            success_rate=successful_queries / total_queries if total_queries > 0 else 0,
            total_queries=total_queries,
            avg_accuracy=avg_accuracy,
            accuracy_by_provider=avg_accuracy_by_provider,
            operation_metrics=operation_metrics,
            total_cost=cost_total,
            avg_cost_per_query=avg_cost_per_query,
            cost_per_1k_ops=cost_per_1k_ops,
            cost_priced_queries=cost_priced_queries,
            cost_unpriced_models=sorted(cost_unpriced_models) if cost_unpriced_models else None
        )

    @staticmethod
    def _calculate_operation_metrics(step_results: List[Any]) -> Dict[str, Any]:
        """Calculate metrics for a single operation type."""
        if not step_results:
            return {
                "avg_latency_ms": 0.0,
                "p95_latency_ms": 0.0,
                "p99_latency_ms": 0.0,
                "total_tokens": 0,
                "avg_tokens_per_query": 0.0,
                "success_rate": 0.0,
                "total_queries": 0
            }

        latencies = [r.latency_ms for r in step_results]
        sorted_latencies = sorted(latencies)
        p95_index = int(0.95 * len(sorted_latencies))
        p99_index = int(0.99 * len(sorted_latencies))
        tokens = [r.tokens_used for r in step_results if r.tokens_used is not None]
        successful = sum(1 for r in step_results if r.success)
        total = len(step_results)

        return {
            "avg_latency_ms": statistics.mean(latencies),
            "p95_latency_ms": sorted_latencies[min(p95_index, len(sorted_latencies) - 1)],
            "p99_latency_ms": sorted_latencies[min(p99_index, len(sorted_latencies) - 1)],
            "total_tokens": sum(tokens),
            "avg_tokens_per_query": statistics.mean(tokens) if tokens else 0,
            "success_rate": successful / total if total > 0 else 0,
            "total_queries": total
        }

    @staticmethod
    def _calculate_costs(
        step_results: List[Any],
        pricing: Dict[str, Dict[str, float]],
    ) -> Tuple[Optional[float], int, List[str], Dict[str, Dict[str, Any]]]:
        """Calculate cost totals and per-action cost metrics."""
        total_cost = 0.0
        priced_queries = 0
        missing_models = set()
        cost_by_action: Dict[str, Dict[str, Any]] = {}

        for step in step_results:
            model = getattr(step, "model", None)
            if not model:
                continue
            model_pricing = pricing.get(model)
            if not model_pricing:
                missing_models.add(model)
                continue

            input_tokens = getattr(step, "input_tokens", None)
            output_tokens = getattr(step, "output_tokens", None)
            total_tokens = getattr(step, "tokens_used", None)

            if input_tokens is None and output_tokens is None:
                if total_tokens is None:
                    continue
                input_tokens, output_tokens = split_tokens(total_tokens)
            else:
                if input_tokens is None and total_tokens is not None and output_tokens is not None:
                    input_tokens = max(total_tokens - output_tokens, 0)
                if output_tokens is None and total_tokens is not None and input_tokens is not None:
                    output_tokens = max(total_tokens - input_tokens, 0)
                input_tokens = input_tokens or 0
                output_tokens = output_tokens or 0

            cost = calculate_cost_usd(input_tokens, output_tokens, model_pricing)
            total_cost += cost
            priced_queries += 1

            action = getattr(step, "action", "unknown")
            bucket = cost_by_action.setdefault(
                action,
                {"total_cost": 0.0, "cost_priced_queries": 0},
            )
            bucket["total_cost"] += cost
            bucket["cost_priced_queries"] += 1

        for action, bucket in cost_by_action.items():
            if bucket["cost_priced_queries"]:
                bucket["avg_cost_per_query"] = bucket["total_cost"] / bucket["cost_priced_queries"]
                bucket["cost_per_1k_ops"] = bucket["avg_cost_per_query"] * 1000
            else:
                bucket["avg_cost_per_query"] = None
                bucket["cost_per_1k_ops"] = None

        if priced_queries == 0:
            return None, 0, list(missing_models), {}

        return total_cost, priced_queries, list(missing_models), cost_by_action
    
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
            "accuracy_comparison": {},
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
        
        # Accuracy comparison
        accuracy_scores = {m.tool_name: m.avg_accuracy for m in metrics_list if m.avg_accuracy is not None}
        if accuracy_scores:
            best_accuracy = max(accuracy_scores.values())
            comparison["accuracy_comparison"] = {
                "values": accuracy_scores,
                "best": max(accuracy_scores, key=accuracy_scores.get),
                "relative_performance": {
                    name: f"{((acc / best_accuracy - 1) * 100):+.1f}%" 
                    for name, acc in accuracy_scores.items()
                }
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
        
        # Accuracy ranking (higher is better, excluding None)
        accuracy_sorted = sorted(
            [m for m in metrics_list if m.avg_accuracy is not None],
            key=lambda m: m.avg_accuracy,
            reverse=True
        )
        if accuracy_sorted:
            rankings["accuracy"] = [m.tool_name for m in accuracy_sorted]
        
        return rankings
