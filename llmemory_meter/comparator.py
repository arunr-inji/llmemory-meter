"""Main comparison engine for memory tools."""

import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime
import json

from llmemory_meter.memory_tools import MemoryTool, Mem0Tool, OpenAIMemoryTool, MemGPTTool, ClaudeMemoryTool, ZepTool
from llmemory_meter.workload import Workload, WorkloadResult
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
        tool = self._get_tool_instance(tool_name)
        step_results = []
        total_start_time = datetime.now()
        
        for i, step in enumerate(workload.steps):
            step_result = await tool.execute_step(step, i)
            step_results.append(step_result)
        
        total_end_time = datetime.now()
        total_latency_ms = (total_end_time - total_start_time).total_seconds() * 1000
        
        # Calculate aggregated metrics
        successful_steps = sum(1 for r in step_results if r.success)
        success_rate = successful_steps / len(step_results) if step_results else 0
        total_tokens = sum(r.tokens_used or 0 for r in step_results)
        
        return WorkloadResult(
            tool_name=tool_name,
            workload_name=workload.name,
            step_results=step_results,
            total_latency_ms=total_latency_ms,
            total_tokens_used=total_tokens,
            success_rate=success_rate,
            timestamp=total_start_time
        )
    
    async def compare_tools(self, workload: Workload, tools: Optional[List[str]] = None) -> Dict[str, Any]:
        """Compare multiple tools on the same workload."""
        if tools is None:
            tools = self.available_tools
        
        if not tools:
            raise ValueError("No tools available. Please check your API key configuration.")
        
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
        
        return {
            "workload_results": workload_comparisons,
            "overall_metrics": {name: metrics.to_dict() for name, metrics in overall_metrics.items()},
            "comparison_summary": comparison_summary,
            "benchmark_info": {
                "num_workloads": len(workloads),
                "tools_tested": tools,
                "timestamp": datetime.now().isoformat()
            }
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
        all_suites = StandardBenchmarks.get_all_suites()
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
        
        all_suites = StandardBenchmarks.get_all_suites()
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
                if "token_efficiency" in rankings:
                    print(f"💰 Token Efficiency: {' > '.join(rankings['token_efficiency'])}")
        
        print("\n" + "="*60)
