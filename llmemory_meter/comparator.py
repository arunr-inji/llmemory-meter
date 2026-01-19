"""Main comparison engine for memory tools."""

import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime
import json

from llmemory_meter.memory_tools import MemoryTool, Mem0Tool, OpenAIMemoryTool, MemGPTTool, ClaudeMemoryTool, ZepTool, NoMemoryTool, FullContextTool
from llmemory_meter.workload import Workload, WorkloadResult, StepResult, WorkloadStep
from llmemory_meter.metrics import MetricsCalculator
from llmemory_meter.config_parser import Config
from llmemory_meter.benchmarks import StandardBenchmarks, BenchmarkRunner


class MemoryComparator:
    """Main class for comparing memory tools with custom workloads."""

    # Provider comparison thresholds for accuracy delta interpretation
    # Delta = max(provider_scores) - min(provider_scores) for each tool
    DELTA_NEGLIGIBLE = 0.05   # Difference < 0.05: providers essentially agree
    DELTA_SMALL = 0.10        # Difference < 0.10: minor disagreement
    DELTA_MODERATE = 0.15     # Difference < 0.15: moderate disagreement
    # Difference >= 0.15: large disagreement (suggests provider choice matters)

    # Consistency thresholds for overall provider agreement
    CONSISTENCY_EXCELLENT_AVG_DELTA = 0.05   # Average delta for excellent consistency
    CONSISTENCY_EXCELLENT_MAX_DELTA = 0.10   # Max delta for excellent consistency
    CONSISTENCY_EXCELLENT_CORRELATION = 0.90  # Min correlation for excellent (Spearman's ρ)

    CONSISTENCY_GOOD_AVG_DELTA = 0.10        # Average delta for good consistency
    CONSISTENCY_GOOD_MAX_DELTA = 0.15        # Max delta for good consistency
    CONSISTENCY_GOOD_CORRELATION = 0.70      # Min correlation for good (Spearman's ρ)

    CONSISTENCY_MODERATE_AVG_DELTA = 0.15    # Average delta threshold for moderate

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config_obj = None
        if config is not None and hasattr(config, "benchmarks"):
            self.config_obj = config
            self.config = self._build_config_dict(config)
        else:
            self.config = config or {}
        self.available_tools = Config.get_available_tools()
        self._tool_instances: Dict[str, MemoryTool] = {}
        # Get concurrent_tools setting from config
        self.concurrent_tools = self.config.get('concurrent_tools', True)
        # Track if this is the first workload (skip clear_memory for first workload)
        self._workload_count = 0

    def _build_config_dict(self, config) -> Dict[str, Any]:
        """Normalize LLMemoryMeterConfig into the dict shape used by tools."""
        from dataclasses import asdict, is_dataclass

        config_dict: Dict[str, Any] = {}

        if getattr(config, "general", None):
            config_dict.update(config.general)
            config_dict["general"] = config.general

        if getattr(config, "memory_tools", None):
            for tool_config in config.memory_tools:
                if hasattr(tool_config, "name") and hasattr(tool_config, "settings"):
                    config_dict[tool_config.name] = tool_config.settings

        if getattr(config, "metrics", None):
            config_dict["metrics"] = asdict(config.metrics) if is_dataclass(config.metrics) else config.metrics

        if getattr(config, "accuracy", None):
            config_dict["accuracy"] = config.accuracy

        return config_dict
    
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
                elif tool_name == "baseline":
                    self._tool_instances[tool_name] = NoMemoryTool(self.config.get("baseline", {}))
                elif tool_name == "full_context":
                    self._tool_instances[tool_name] = FullContextTool(self.config.get("full_context", {}))
                else:
                    raise ValueError(f"Unknown tool: {tool_name}. Supported tools: mem0, openai_memory, memgpt, claude_memory, zep, baseline, full_context")
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

    def _evaluate_accuracy(self, step_results: List[StepResult], steps: List[WorkloadStep]) -> List[StepResult]:
        """Evaluate accuracy using embedding and/or exact match based on match_type.

        Two-phase evaluation:
        1. Embedding-based: For steps with match_type=None or "embedding"
        2. Exact match: For steps with match_type="exact", "exact_case_insensitive", etc.

        Results stored in accuracy_by_provider dict with keys:
        - Provider names (openai, local) for embedding scores
        - "exact_match_{type}" for exact match scores

        Args:
            step_results: List of StepResult objects
            steps: List of WorkloadStep objects with ground truth

        Returns:
            Updated step_results with accuracy scores populated
        """
        from llmemory_meter.accuracy_evaluator import AccuracyEvaluator, ExactMatchEvaluator

        # Strip formatting prefixes for fair comparison
        responses = [self._strip_formatting_prefix(sr.response) for sr in step_results]
        ground_truths = [step.ground_truth for step in steps]

        # Initialize accuracy_by_provider dict
        for sr in step_results:
            sr.accuracy_by_provider = {}

        # Separate steps by match_type
        embedding_indices = []
        exact_match_indices = []
        match_types_map = {}  # index -> match_type

        for i, step in enumerate(steps):
            match_type = step.match_type or "embedding"
            match_types_map[i] = match_type

            if match_type == "embedding":
                embedding_indices.append(i)
            elif match_type in ["exact", "exact_case_insensitive", "contains", "regex"]:
                exact_match_indices.append(i)
            else:
                print(f"Warning: Unknown match_type '{match_type}' at step {i}, defaulting to embedding")
                embedding_indices.append(i)

        # Evaluate embedding-based steps
        if embedding_indices:
            accuracy_config = self.config.get('accuracy', {})
            providers = accuracy_config.get('providers', ['openai'])
            if isinstance(providers, str):
                providers = [providers]

            for provider in providers:
                try:
                    # Get model config
                    if provider == 'openai':
                        model = accuracy_config.get('openai', {}).get('model', 'text-embedding-3-small')
                    elif provider == 'local':
                        model = accuracy_config.get('local', {}).get('model', 'all-mpnet-base-v2')
                    else:
                        model = None

                    # Create evaluator
                    evaluator = AccuracyEvaluator(provider=provider, model=model)

                    # Evaluate only embedding indices
                    embedding_responses = [responses[i] for i in embedding_indices]
                    embedding_ground_truths = [ground_truths[i] for i in embedding_indices]

                    accuracy_scores = evaluator.evaluate_batch(embedding_responses, embedding_ground_truths)

                    # Store scores
                    for idx, score in zip(embedding_indices, accuracy_scores):
                        step_results[idx].accuracy_by_provider[provider] = score

                except Exception as e:
                    print(f"Warning: Failed to evaluate accuracy with {provider}: {e}")
                    for idx in embedding_indices:
                        step_results[idx].accuracy_by_provider[provider] = None

        # Evaluate exact-match steps
        if exact_match_indices:
            # Group by match_type for efficiency
            for match_type in ["exact", "exact_case_insensitive", "contains", "regex"]:
                type_indices = [i for i in exact_match_indices if match_types_map[i] == match_type]

                if type_indices:
                    try:
                        evaluator = ExactMatchEvaluator(match_type=match_type)

                        # Evaluate only these indices
                        type_responses = [responses[i] for i in type_indices]
                        type_ground_truths = [ground_truths[i] for i in type_indices]

                        scores = evaluator.evaluate_batch(type_responses, type_ground_truths)

                        # Store scores with descriptive key
                        for idx, score in zip(type_indices, scores):
                            step_results[idx].accuracy_by_provider[f"exact_match_{match_type}"] = score

                    except Exception as e:
                        print(f"Warning: Failed to evaluate exact match ({match_type}): {e}")
                        for idx in type_indices:
                            step_results[idx].accuracy_by_provider[f"exact_match_{match_type}"] = None

        # Set primary accuracy field
        # Priority: first embedding provider > first exact match type
        accuracy_config = self.config.get('accuracy', {})
        providers = accuracy_config.get('providers', ['openai'])
        if isinstance(providers, str):
            providers = [providers]

        for sr in step_results:
            # Try embedding providers first
            primary_set = False
            if providers:
                for provider in providers:
                    if provider in sr.accuracy_by_provider and sr.accuracy_by_provider[provider] is not None:
                        sr.accuracy = sr.accuracy_by_provider[provider]
                        primary_set = True
                        break

            # Fallback to exact match if no embedding provider
            if not primary_set:
                for key in sr.accuracy_by_provider:
                    if key.startswith("exact_match_") and sr.accuracy_by_provider[key] is not None:
                        sr.accuracy = sr.accuracy_by_provider[key]
                        break

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
                if tool_name in ["mem0", "openai_memory", "memgpt", "claude_memory", "zep", "baseline", "full_context"]:
                    try:
                        tool = self._get_tool_instance(tool_name)
                        await tool.clear_memory()
                    except Exception as e:
                        # Silently ignore errors (some tools may not need clearing)
                        pass
        
        self._workload_count += 1  # Increment after clearing decision
        
        results = {}
        
        if self.concurrent_tools:
            # Run workload on all tools concurrently
            tasks = []
            for tool_name in tools:
                if tool_name in ["mem0", "openai_memory", "memgpt", "claude_memory", "zep", "baseline", "full_context"]:  # Supported tools
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
                if tool_name in ["mem0", "openai_memory", "memgpt", "claude_memory", "zep", "baseline", "full_context"]:  # Supported tools
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
        try:
            from scipy.stats import spearmanr
        except ImportError:
            print("Warning: scipy not installed. Spearman correlation will not be calculated.")
            spearmanr = None
        
        # Extract scores by provider for each tool
        # Only include embedding providers (not exact_match_* keys)
        tool_scores = {}
        for tool_name, results_list in all_results.items():
            scores_by_provider = {}

            # Aggregate accuracy scores across all workloads
            for workload_result in results_list:
                for step_result in workload_result.step_results:
                    if step_result.accuracy_by_provider:
                        for provider, score in step_result.accuracy_by_provider.items():
                            # Only include embedding providers, not exact match evaluators
                            if score is not None and not provider.startswith("exact_match_"):
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
                if delta < self.DELTA_NEGLIGIBLE:
                    interpretation = "negligible"
                elif delta < self.DELTA_SMALL:
                    interpretation = "small"
                elif delta < self.DELTA_MODERATE:
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
        if len(providers_list) == 2 and spearmanr:
            p1, p2 = providers_list
            # Get scores for all tools that have both provider scores
            tools_with_both = [t for t in tool_scores.keys() 
                             if p1 in tool_scores[t] and p2 in tool_scores[t]]
            
            if len(tools_with_both) >= 3:  # Need at least 3 data points for correlation
                scores_p1 = [tool_scores[t][p1] for t in tools_with_both]
                scores_p2 = [tool_scores[t][p2] for t in tools_with_both]
                try:
                    correlation, _ = spearmanr(scores_p1, scores_p2)
                except:
                    correlation = None
        
        # Calculate overall consistency metrics
        avg_delta = sum(deltas) / len(deltas)
        max_delta = max(deltas)
        
        # Determine consistency level
        if (avg_delta < self.CONSISTENCY_EXCELLENT_AVG_DELTA and
            max_delta < self.CONSISTENCY_EXCELLENT_MAX_DELTA and
            (correlation is None or correlation > self.CONSISTENCY_EXCELLENT_CORRELATION)):
            consistency = "excellent"
            interpretation = "Provider choice has minimal impact on results"
        elif (avg_delta < self.CONSISTENCY_GOOD_AVG_DELTA and
              max_delta < self.CONSISTENCY_GOOD_MAX_DELTA and
              (correlation is None or correlation > self.CONSISTENCY_GOOD_CORRELATION)):
            consistency = "good"
            interpretation = "Minor differences but rankings mostly consistent"
        elif avg_delta < self.CONSISTENCY_MODERATE_AVG_DELTA:
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
                "negligible": self.DELTA_NEGLIGIBLE,
                "small": self.DELTA_SMALL,
                "moderate": self.DELTA_MODERATE,
                "explanation": f"Delta < {self.DELTA_NEGLIGIBLE} = negligible, {self.DELTA_NEGLIGIBLE}-{self.DELTA_SMALL} = small, {self.DELTA_SMALL}-{self.DELTA_MODERATE} = moderate, > {self.DELTA_MODERATE} = large"
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

        # Get benchmark config to check for workload filtering
        if self.config_obj is not None:
            from llmemory_meter.config_parser.manager import ConfigManager
            benchmark_config = ConfigManager.get_benchmark_config(self.config_obj, suite_name)
        else:
            benchmark_config = None

        # Filter workloads if specific ones are requested
        workloads_to_run = suite.workloads
        if benchmark_config and benchmark_config.workloads:
            # Filter to only the requested workloads
            requested_workload_names = set(benchmark_config.workloads)
            workloads_to_run = [w for w in suite.workloads if w.name in requested_workload_names]

            if not workloads_to_run:
                print(f"⚠️  No matching workloads found for {suite_name}. Requested: {benchmark_config.workloads}")
                print(f"   Available workloads: {[w.name for w in suite.workloads]}")
                print(f"   Skipping this benchmark.")
                return {}
            else:
                print(f"🔍 Filtering to {len(workloads_to_run)} of {len(suite.workloads)} workloads: {[w.name for w in workloads_to_run]}")
        elif not workloads_to_run:
            print(f"⚠️  Benchmark suite '{suite_name}' has no workloads.")
            print(f"   Skipping this benchmark.")
            return {}

        print(f"🧪 Running benchmark suite: {suite.name}")
        print(f"📝 Description: {suite.description}")
        print(f"📊 Category: {suite.category}")
        print(f"🔧 Testing {len(workloads_to_run)} workloads on {len(tools)} tools")

        # Run the benchmark
        results = await self.benchmark_tools(workloads_to_run, tools)
        
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
        print(f"  Note: This compares embedding-based accuracy only (e.g., OpenAI, local).")
        print(f"        Exact match evaluators are excluded from this comparison.\n")
        
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
                print(f"  • Total Queries: {metrics['total_queries']}")
                
                # Display accuracy per-provider if available (skip overall avg to avoid confusion)
                if 'accuracy_by_provider' in metrics and metrics['accuracy_by_provider']:
                    # Separate embedding providers from exact match evaluators
                    embedding_providers = {}
                    exact_match_evaluators = {}

                    for p, s in metrics['accuracy_by_provider'].items():
                        if p.startswith('exact_match_'):
                            exact_match_evaluators[p] = s
                        else:
                            embedding_providers[p] = s

                    # Display embedding provider accuracy
                    if embedding_providers:
                        provider_strs = [f"{p}: {s*100:.1f}%" for p, s in embedding_providers.items()]
                        print(f"  • Accuracy (Embedding): {' | '.join(provider_strs)}")

                    # Display exact match accuracy separately
                    if exact_match_evaluators:
                        match_strs = [f"{p.replace('exact_match_', '')}: {s*100:.1f}%"
                                     for p, s in exact_match_evaluators.items()]
                        print(f"  • Accuracy (Exact Match): {' | '.join(match_strs)}")
                
                print(f"  • Avg Tokens/Query: {metrics['avg_tokens_per_query']}")

                if 'operation_metrics' in metrics and metrics['operation_metrics']:
                    print("  • Operation Breakdown:")
                    for action in ["store", "retrieve", "chat"]:
                        if action not in metrics['operation_metrics']:
                            continue
                        op = metrics['operation_metrics'][action]
                        print(
                            f"    - {action.capitalize()} ({op['total_queries']} ops): "
                            f"avg {op['avg_latency_ms']}ms "
                            f"(p95 {op['p95_latency_ms']}ms, p99 {op['p99_latency_ms']}ms), "
                            f"tokens avg {op['avg_tokens_per_query']} "
                            f"(total {op['total_tokens']}), "
                            f"success {op['success_rate']}%"
                        )
                
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
        # Only show if there are actually embedding providers to compare
        if "accuracy_comparison" in results and results["accuracy_comparison"]:
            comparison = results["accuracy_comparison"]
            # Check if we have actual data (not just empty dict from no providers)
            if "summary" in comparison or "by_tool" in comparison:
                self._print_provider_comparison(comparison)
        
        print("\n" + "="*60)
