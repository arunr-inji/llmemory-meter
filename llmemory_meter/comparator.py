"""Main comparison engine for memory tools."""

import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime
import json
from scipy.stats import spearmanr

from llmemory_meter.memory_tools import MemoryTool, Mem0Tool, OpenAIMemoryTool, MemGPTTool, ClaudeMemoryTool, ZepTool
from llmemory_meter.workload import Workload, WorkloadResult, StepResult
from llmemory_meter.metrics import MetricsCalculator
from llmemory_meter.config_parser import Config
from llmemory_meter.benchmarks import StandardBenchmarks, BenchmarkRunner


class MemoryComparator:
    """Main class for comparing memory tools with custom workloads."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.available_tools = Config.get_available_tools()
        self._tool_instances: Dict[str, MemoryTool] = {}
        # Get concurrent_tools setting from config
        self.concurrent_tools = self.config.get('concurrent_tools', True)
        # Track if this is the first workload (skip clear_memory for first workload)
        self._workload_count = 0
    
    def _get_tool_instance(self, tool_name: str) -> MemoryTool:
        """Get or create a tool instance."""
        if tool_name not in self._tool_instances:
            try:
                if tool_name == "mem0":
                    self._tool_instances[tool_name] = Mem0Tool(self.config.get("mem0", {}))
                elif tool_name == "openai_memory":
                    self._tool_instances[tool_name] = OpenAIMemoryTool(self.config.get("openai_memory", {}))
                elif tool_name == "memgpt":
                    self._tool_instances[tool_name] = MemGPTTool(self.config.get("memgpt", {}))
                elif tool_name == "claude_memory":
                    self._tool_instances[tool_name] = ClaudeMemoryTool(self.config.get("claude_memory", {}))
                elif tool_name == "zep":
                    self._tool_instances[tool_name] = ZepTool(self.config.get("zep", {}))
                else:
                    raise ValueError(f"Unknown tool: {tool_name}. Supported tools: mem0, openai_memory, memgpt, claude_memory, zep")
            except (ValueError, ImportError) as e:
                # Re-raise configuration and import errors
                raise e
            except Exception as e:
                # Wrap other initialization errors
                raise Exception(f"Failed to initialize {tool_name}: {e}")
        
        return self._tool_instances[tool_name]
    
    async def run_workload_on_tool(self, workload: Workload, tool_name: str) -> WorkloadResult:
        """Run a workload on a specific memory tool."""
        print(f"  → {tool_name} starting...")
        tool = self._get_tool_instance(tool_name)
        step_results = []
        total_start_time = datetime.now()
        
        # Phase 1: Run benchmark (pure performance measurement)
        for i, step in enumerate(workload.steps):
            # Progress print every 10 steps
            if i > 0 and i % 10 == 0:
                from datetime import timezone, timedelta
                pst = timezone(timedelta(hours=-8))
                timestamp = datetime.now(pst).strftime("%H:%M:%S")
                print(f"    [{tool_name}] Progress: {i}/{len(workload.steps)} steps @ {timestamp} PST")
            
            try:
                # Add timeout per step to prevent indefinite hangs (especially for Zep)
                # 5 minutes = 3.2x the max ever observed (92s) with generous buffer
                # Prevents deadlocks while allowing legitimate slow operations
                STEP_TIMEOUT = 300.0  # 5 minutes
                step_result = await asyncio.wait_for(
                    tool.execute_step(step, i),
                    timeout=STEP_TIMEOUT
                )
            except asyncio.TimeoutError:
                # Step timed out - mark as failed
                print(f"⏱️ Timeout: Step {i} ({step.action}) exceeded {STEP_TIMEOUT/60:.0f} minutes - marking as failed")
                step_result = StepResult(
                    step_index=i,
                    action=step.action,
                    response="",
                    latency_ms=STEP_TIMEOUT * 1000,
                    tokens_used=0,
                    success=False,
                    error_message=f"Operation timed out after {STEP_TIMEOUT/60:.0f} minutes"
                )
            step_results.append(step_result)
        
        total_end_time = datetime.now()
        total_latency_ms = (total_end_time - total_start_time).total_seconds() * 1000
        
        # Phase 2: Evaluate accuracy post-hoc (doesn't affect latency/tokens)
        if self.config.get('metrics', {}).get('accuracy', False):
            step_results = self._evaluate_accuracy(step_results, workload.steps)
        
        # Calculate aggregated metrics
        successful_steps = sum(1 for r in step_results if r.success)
        success_rate = successful_steps / len(step_results) if step_results else 0
        total_tokens = sum(r.tokens_used or 0 for r in step_results)
        
        print(f"  ✓ {tool_name} completed ({len(step_results)} steps, {total_latency_ms:.0f}ms)")
        
        return WorkloadResult(
            tool_name=tool_name,
            workload_name=workload.name,
            step_results=step_results,
            total_latency_ms=total_latency_ms,
            total_tokens_used=total_tokens,
            success_rate=success_rate,
            timestamp=total_start_time
        )
    
    def _strip_formatting_prefix(self, response: str) -> str:
        """Strip framework-added formatting prefixes for fair accuracy comparison.
        
        Removes tool-specific prefixes like:
        - "Retrieved from Zep: "
        - "Retrieved from Letta for query: "
        - "OpenAI Memory response: "
        - "Based on context: Retrieved from..."
        - Mem0 score metadata: "[Score: 0.XXX]"
        
        Args:
            response: Raw response string from tool
            
        Returns:
            Response with formatting prefix and metadata stripped
        """
        import re
        
        # Patterns to strip (in order of priority)
        patterns = [
            r'^Mem0 chat response to .+?\(with \d+ memories\):\s*',  # Mem0 chat wrapper
            r'^Based on context:\s*Retrieved from .+?:\s*',  # Nested prefix (Zep chat)
            r'^Retrieved from .+? for query:\s*[^:]+$',  # MemGPT with query only (no content after)
            r'^Retrieved from .+? for [\'"][^\'"]+[\'"]:',  # OpenAI with quoted query
            r'^Retrieved from .+?:\s*',  # Simple "Retrieved from X:"
            r'^.+? Memory response:\s*',  # "OpenAI Memory response:"
            r'^Stored in .+?:\s*',  # Store operation responses
            r'^Received response from .+?\.',  # MemGPT fallback
        ]
        
        cleaned = response
        for pattern in patterns:
            cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)
            if cleaned != response:  # Found a match, stop
                break
        
        # Additional cleanup: Strip Mem0 metadata and boilerplate
        # Remove "[Score: 0.XXX] " patterns
        cleaned = re.sub(r'\[Score:\s*[\d.]+\]\s*', '', cleaned)
        
        # Remove Mem0 boilerplate phrases
        cleaned = re.sub(r'^Based on your memories,?\s*I can help you with this request\.\s*', '', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'^Relevant memories:\s*', '', cleaned, flags=re.IGNORECASE)
        
        # Clean up pipe separators from multi-result responses
        # Take first (highest-scored) fact only for fair comparison across embedding models
        # This matches industry best practices (semantic search, RAG benchmarks)
        # and ensures both OpenAI and local embeddings evaluate the same content
        if '|' in cleaned:
            cleaned = cleaned.split('|')[0].strip()
        
        return cleaned.strip()
    
    def _evaluate_accuracy(self, step_results: List, steps: List) -> List:
        """Evaluate accuracy post-hoc (doesn't affect latency/tokens).
        
        Args:
            step_results: List of StepResult objects
            steps: List of WorkloadStep objects with ground truth
            
        Returns:
            Updated step_results with accuracy scores populated
        """
        from llmemory_meter.accuracy_evaluator import AccuracyEvaluator
        
        # Get accuracy config
        accuracy_config = self.config.get('accuracy', {})
        providers = accuracy_config.get('providers', ['openai'])
        
        # Ensure providers is a list
        if isinstance(providers, str):
            providers = [providers]
        
        # Collect responses and ground truths, stripping formatting for fair comparison
        responses = [self._strip_formatting_prefix(sr.response) for sr in step_results]
        ground_truths = [step.ground_truth for step in steps]
        
        # Initialize accuracy_by_provider dict for each step result
        for sr in step_results:
            sr.accuracy_by_provider = {}
        
        # Evaluate with each provider
        for provider in providers:
            try:
                # Get provider-specific model if configured
                provider_config = accuracy_config.get(provider, {})
                model = provider_config.get('model') if isinstance(provider_config, dict) else None
                
                evaluator = AccuracyEvaluator(provider=provider, model=model)
                accuracy_scores = evaluator.evaluate_batch(responses, ground_truths)
                
                # Store scores in accuracy_by_provider dict
                for sr, score in zip(step_results, accuracy_scores):
                    sr.accuracy_by_provider[provider] = score
            except Exception as e:
                print(f"Warning: Failed to evaluate accuracy with {provider}: {e}")
                # Set None for all steps for this provider
                for sr in step_results:
                    sr.accuracy_by_provider[provider] = None
        
        # Set primary accuracy field to first provider's score
        if providers:
            primary_provider = providers[0]
            for sr in step_results:
                sr.accuracy = sr.accuracy_by_provider.get(primary_provider)
        
        return step_results
    
    async def compare_tools(self, workload: Workload, tools: Optional[List[str]] = None) -> Dict[str, Any]:
        """Compare multiple tools on the same workload."""
        if tools is None:
            tools = self.available_tools
        
        if not tools:
            raise ValueError("No tools available. Please check your API key configuration.")
        
        # Clear memory for all tools before starting new workload (but skip first workload)
        # This ensures workload isolation (prevents fact accumulation across workloads)
        if self._workload_count > 0:  # Only clear for 2nd+ workloads
            for tool_name in tools:
                if tool_name in ["mem0", "openai_memory", "memgpt", "claude_memory", "zep"]:
                    try:
                        tool = self._get_tool_instance(tool_name)
                        await tool.clear_memory()
                    except Exception as e:
                        print(f"❌ Error clearing memory for {tool_name}: {e}")
        
        self._workload_count += 1  # Increment after clearing decision
        
        results = {}
        
        if self.concurrent_tools:
            # Run workload on all tools concurrently
            tasks = []
            for tool_name in tools:
                if tool_name in ["mem0", "openai_memory", "memgpt", "claude_memory", "zep"]:  # Supported tools
                    task = self.run_workload_on_tool(workload, tool_name)
                    tasks.append((tool_name, task))
            
            for tool_name, task in tasks:
                try:
                    result = await task
                    results[tool_name] = result
                except Exception as e:
                    print(f"Error running {tool_name}: {e}")
                    # Create a failed result
                    results[tool_name] = WorkloadResult(
                        tool_name=tool_name,
                        workload_name=workload.name,
                        step_results=[],
                        total_latency_ms=0,
                        total_tokens_used=0,
                        success_rate=0,
                        timestamp=datetime.now()
                    )
        else:
            # Run workload on tools sequentially (thread-safe)
            for tool_name in tools:
                if tool_name in ["mem0", "openai_memory", "memgpt", "claude_memory", "zep"]:  # Supported tools
                    try:
                        result = await self.run_workload_on_tool(workload, tool_name)
                        results[tool_name] = result
                    except Exception as e:
                        print(f"Error running {tool_name}: {e}")
                        # Create a failed result
                        results[tool_name] = WorkloadResult(
                            tool_name=tool_name,
                            workload_name=workload.name,
                            step_results=[],
                            total_latency_ms=0,
                            total_tokens_used=0,
                            success_rate=0,
                            timestamp=datetime.now()
                        )
        
        return results
    
    async def benchmark_tools(self, workloads: List[Workload], tools: Optional[List[str]] = None) -> Dict[str, Any]:
        """Run comprehensive benchmark across multiple workloads."""
        if tools is None:
            tools = self.available_tools
        
        all_results = {tool: [] for tool in tools}
        workload_comparisons = {}
        
        # Run each workload
        for workload in workloads:
            print(f"Running workload: {workload.name}")
            comparison = await self.compare_tools(workload, tools)
            
            # Convert WorkloadResult objects to dictionaries for proper JSON serialization
            workload_comparisons[workload.name] = {
                tool_name: result.to_dict() if hasattr(result, 'to_dict') else result
                for tool_name, result in comparison.items()
            }
            
            # Collect results for each tool
            for tool_name, result in comparison.items():
                all_results[tool_name].append(result)
        
        # Calculate overall metrics
        overall_metrics = {}
        for tool_name, results in all_results.items():
            if results:  # Only calculate if we have results
                try:
                    metrics = MetricsCalculator.calculate_metrics(results)
                    overall_metrics[tool_name] = metrics
                except Exception as e:
                    print(f"Error calculating metrics for {tool_name}: {e}")
        
        # Compare metrics
        metrics_list = list(overall_metrics.values())
        comparison_summary = MetricsCalculator.compare_metrics(metrics_list) if metrics_list else {}
        
        result = {
            "workload_results": workload_comparisons,
            "overall_metrics": {name: metrics.to_dict() for name, metrics in overall_metrics.items()},
            "comparison_summary": comparison_summary,
            "benchmark_info": {
                "num_workloads": len(workloads),
                "tools_tested": tools,
                "timestamp": datetime.now().isoformat()
            }
        }
        
        # Add accuracy comparison if accuracy evaluation is enabled
        if self.config.get('metrics', {}).get('accuracy', False):
            # Collect all WorkloadResult objects for provider comparison
            all_workload_results = {}
            for tool_name, results_list in all_results.items():
                if results_list:
                    all_workload_results[tool_name] = results_list
            
            if all_workload_results:
                provider_comparison = self._generate_provider_comparison(all_workload_results)
                if provider_comparison:
                    result["accuracy_comparison"] = provider_comparison
        
        return result
    
    def _generate_provider_comparison(self, all_results: Dict[str, List]) -> Dict:
        """Generate comparative analysis of embedding providers.
        
        Args:
            all_results: Dict mapping tool names to lists of WorkloadResult objects
            
        Returns:
            Dict with provider comparison analysis including deltas and correlations
        """
        # Extract scores by provider for each tool
        tool_scores = {}
        for tool_name, results_list in all_results.items():
            scores_by_provider = {}
            
            # Aggregate accuracy scores across all workloads
            for workload_result in results_list:
                for step_result in workload_result.step_results:
                    if step_result.accuracy_by_provider:
                        for provider, score in step_result.accuracy_by_provider.items():
                            if score is not None:
                                scores_by_provider.setdefault(provider, []).append(score)
            
            # Calculate averages
            if scores_by_provider:
                tool_scores[tool_name] = {
                    provider: sum(scores) / len(scores)
                    for provider, scores in scores_by_provider.items()
                    if scores  # Only include if we have scores
                }
        
        if not tool_scores:
            return {}
        
        # Get list of providers (should be same across all tools)
        providers_list = list(next(iter(tool_scores.values())).keys())
        if len(providers_list) < 2:
            return {}  # Need at least 2 providers for comparison
        
        # Calculate deltas and interpretation for each tool
        by_tool_analysis = {}
        deltas = []
        
        for tool_name, scores in tool_scores.items():
            if len(scores) >= 2:
                provider_scores = list(scores.values())
                delta = max(provider_scores) - min(provider_scores)
                deltas.append(delta)
                
                # Interpret delta using thresholds
                if delta < 0.05:
                    interpretation = "negligible"
                elif delta < 0.10:
                    interpretation = "small"
                elif delta < 0.15:
                    interpretation = "moderate"
                else:
                    interpretation = "large"
                
                by_tool_analysis[tool_name] = {
                    **{k: round(v, 3) for k, v in scores.items()},
                    "delta": round(delta, 3),
                    "delta_interpretation": interpretation
                }
        
        if not deltas:
            return {}
        
        # Calculate rank correlation if we have exactly 2 providers
        correlation = None
        if len(providers_list) == 2:
            p1, p2 = providers_list
            # Get scores for all tools that have both provider scores
            tools_with_both = [t for t in tool_scores.keys() 
                             if p1 in tool_scores[t] and p2 in tool_scores[t]]
            
            if len(tools_with_both) >= 3:  # Need at least 3 data points for correlation
                scores_p1 = [tool_scores[t][p1] for t in tools_with_both]
                scores_p2 = [tool_scores[t][p2] for t in tools_with_both]
                try:
                    correlation, _ = spearmanr(scores_p1, scores_p2)
                except Exception as e:
                    print(f"⚠️ Spearman correlation failed: {type(e).__name__}: {e}")
                    correlation = None
        
        # Calculate overall consistency metrics
        avg_delta = sum(deltas) / len(deltas)
        max_delta = max(deltas)
        
        # Determine consistency level
        if avg_delta < 0.05 and max_delta < 0.10 and (correlation is None or correlation > 0.90):
            consistency = "excellent"
            interpretation = "Provider choice has minimal impact on results"
        elif avg_delta < 0.10 and max_delta < 0.15 and (correlation is None or correlation > 0.70):
            consistency = "good"
            interpretation = "Minor differences but rankings mostly consistent"
        elif avg_delta < 0.15:
            consistency = "moderate"
            interpretation = "Some disagreement between providers, investigate further"
        else:
            consistency = "poor"
            interpretation = "Significant disagreement between providers"
        
        return {
            "summary": {
                "provider_correlation": round(correlation, 3) if correlation is not None else None,
                "avg_delta": round(avg_delta, 3),
                "max_delta": round(max_delta, 3),
                "ranking_consistent": correlation > 0.90 if correlation is not None else True,
                "consistency_level": consistency,
                "interpretation": interpretation
            },
            "thresholds": {
                "negligible": 0.05,
                "small": 0.10,
                "moderate": 0.15,
                "explanation": "Delta < 0.05 = negligible, 0.05-0.10 = small, 0.10-0.15 = moderate, > 0.15 = large"
            },
            "by_tool": by_tool_analysis
        }
    
    def create_simple_workload(self, name: str, memory_content: str, retrieval_query: str) -> Workload:
        """Helper method to create a simple workload."""
        return Workload.create_simple_workload(name, memory_content, retrieval_query)
    
    def create_conversation_workload(self, name: str, conversation_steps: List[str]) -> Workload:
        """Helper method to create a conversation workload."""
        return Workload.create_conversation_workload(name, conversation_steps)
    
    def get_available_benchmarks(self) -> Dict[str, List[str]]:
        """Get available benchmark suites organized by category."""
        return BenchmarkRunner.get_available_benchmarks()
    
    def get_benchmark_info(self, benchmark_name: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific benchmark."""
        return BenchmarkRunner.get_benchmark_info(benchmark_name)
    
    async def run_benchmark_suite(self, suite_name: str, tools: Optional[List[str]] = None) -> Dict[str, Any]:
        """Run a specific benchmark suite on selected tools."""
        if tools is None:
            tools = self.available_tools
        
        # Get the benchmark suite
        all_suites = StandardBenchmarks.get_all_suites(self.config)
        suite = None
        for s in all_suites:
            if s.name == suite_name:
                suite = s
                break
        
        if not suite:
            raise ValueError(f"Benchmark suite '{suite_name}' not found. Available suites: {[s.name for s in all_suites]}")
        
        print(f"🧪 Running benchmark suite: {suite.name}")
        print(f"📝 Description: {suite.description}")
        print(f"📊 Category: {suite.category}")
        print(f"🔧 Testing {len(suite.workloads)} workloads on {len(tools)} tools")
        
        # Run the benchmark
        results = await self.benchmark_tools(suite.workloads, tools)
        
        # Create specialized benchmark report
        benchmark_report = BenchmarkRunner.create_benchmark_report(results, suite_name)
        
        return benchmark_report
    
    async def run_all_benchmarks(self, tools: Optional[List[str]] = None) -> Dict[str, Any]:
        """Run all available benchmark suites."""
        if tools is None:
            tools = self.available_tools
        
        all_suites = StandardBenchmarks.get_all_suites(self.config)
        all_results = {}
        
        print(f"🚀 Running all {len(all_suites)} benchmark suites...")
        
        for suite in all_suites:
            print(f"\n--- Running: {suite.name} ---")
            try:
                suite_results = await self.run_benchmark_suite(suite.name, tools)
                all_results[suite.name] = suite_results
            except Exception as e:
                print(f"❌ Error running {suite.name}: {e}")
                all_results[suite.name] = {"error": str(e)}
        
        return {
            "all_benchmark_results": all_results,
            "summary": {
                "total_suites": len(all_suites),
                "successful_suites": len([r for r in all_results.values() if "error" not in r]),
                "tools_tested": tools,
                "timestamp": datetime.now().isoformat()
            }
        }
    
    def save_results(self, results: Dict[str, Any], filename: str):
        """Save benchmark results to a JSON file."""
        with open(filename, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        print(f"Results saved to {filename}")
    
    def _print_provider_comparison(self, comparison: Dict[str, Any]):
        """Print provider comparison analysis."""
        print(f"\n📊 Embedding Provider Comparison:")
        print("-" * 40)
        
        if "summary" in comparison:
            summary = comparison["summary"]
            
            # Correlation
            if summary.get("provider_correlation") is not None:
                corr = summary["provider_correlation"]
                print(f"  • Spearman Correlation: {corr:.3f} ({'very high' if corr > 0.9 else 'high' if corr > 0.7 else 'moderate'} agreement)")
            
            # Deltas
            avg_delta = summary.get("avg_delta", 0)
            max_delta = summary.get("max_delta", 0)
            print(f"  • Avg Delta: {avg_delta:.3f} ({avg_delta*100:.1f}%)")
            print(f"  • Max Delta: {max_delta:.3f} ({max_delta*100:.1f}%)")
            
            # Consistency level
            consistency = summary.get("consistency_level", "unknown")
            consistency_icons = {
                "excellent": "✅",
                "good": "✓",
                "moderate": "⚠️",
                "poor": "❌"
            }
            icon = consistency_icons.get(consistency, "")
            print(f"  • Consistency Level: {icon} {consistency.upper()}")
            print(f"  • Interpretation: {summary.get('interpretation', 'N/A')}")
        
        # Threshold reference
        if "thresholds" in comparison:
            print(f"\n  Delta Thresholds:")
            thresholds = comparison["thresholds"]
            print(f"    < {thresholds.get('negligible', 0.05)} = Negligible ✅")
            print(f"    {thresholds.get('negligible', 0.05)}-{thresholds.get('small', 0.10)} = Small")
            print(f"    {thresholds.get('small', 0.10)}-{thresholds.get('moderate', 0.15)} = Moderate ⚠️")
            print(f"    > {thresholds.get('moderate', 0.15)} = Large ❌")
        
        # Per-tool analysis
        if "by_tool" in comparison and comparison["by_tool"]:
            print(f"\n  Per-Tool Analysis:")
            for tool_name, data in comparison["by_tool"].items():
                delta = data.get("delta", 0)
                interp = data.get("delta_interpretation", "unknown")
                interp_icon = "✅" if interp == "negligible" else "⚠️" if interp in ["small", "moderate"] else "❌"
                
                # Get provider scores
                provider_scores = {k: v for k, v in data.items() 
                                 if k not in ["delta", "delta_interpretation"]}
                provider_str = ", ".join([f"{p}={s:.3f}" for p, s in provider_scores.items()])
                
                print(f"    {tool_name}: {provider_str}, Δ={delta:.3f} {interp_icon} {interp}")
    
    def print_summary(self, results: Dict[str, Any]):
        """Print a formatted summary of benchmark results."""
        print("\n" + "="*60)
        print("🧠 LLMemoryMeter - Benchmark Results Summary")
        print("="*60)
        
        if "overall_metrics" in results:
            print("\n📊 Overall Performance Metrics:")
            print("-" * 40)
            
            for tool_name, metrics in results["overall_metrics"].items():
                success_rate = metrics['success_rate']
                status_icon = "✅" if success_rate == 100.0 else "⚠️"
                
                print(f"\n🔧 {tool_name.upper()}: {status_icon}")
                print(f"  • Avg Latency: {metrics['avg_latency_ms']}ms")
                print(f"  • P95 Latency: {metrics['p95_latency_ms']}ms") 
                print(f"  • Success Rate: {success_rate}%")
                
                # Display accuracy per-provider if available (skip overall avg to avoid confusion)
                if 'accuracy_by_provider' in metrics and metrics['accuracy_by_provider']:
                    provider_strs = [f"{p}: {s*100:.1f}%" for p, s in metrics['accuracy_by_provider'].items()]
                    print(f"  • Accuracy: {' | '.join(provider_strs)}")
                
                print(f"  • Avg Tokens/Query: {metrics['avg_tokens_per_query']}")
                
                # Warn if not 100% reliable
                if success_rate < 100.0:
                    print(f"  ⚠️  Note: Some operations failed (see detailed results)")
        
        if "comparison_summary" in results and results["comparison_summary"]:
            summary = results["comparison_summary"]
            print(f"\n🏆 Performance Rankings:")
            print("-" * 40)
            
            if "rankings" in summary:
                rankings = summary["rankings"]
                if "latency" in rankings:
                    print(f"⚡ Speed (Latency): {' > '.join(rankings['latency'])}")
                if "success_rate" in rankings:
                    print(f"✅ Reliability: {' > '.join(rankings['success_rate'])}")
                if "accuracy" in rankings:
                    print(f"🎯 Accuracy: {' > '.join(rankings['accuracy'])}")
                if "token_efficiency" in rankings:
                    print(f"💰 Token Efficiency: {' > '.join(rankings['token_efficiency'])}")
        
        # Display provider comparison if accuracy evaluation is enabled
        if "accuracy_comparison" in results and results["accuracy_comparison"]:
            self._print_provider_comparison(results["accuracy_comparison"])
        
        print("\n" + "="*60)
