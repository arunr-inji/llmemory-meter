#!/usr/bin/env python3
"""
Benchmark Example - Run industry-standard benchmarks on memory tools.

This example demonstrates how to use the built-in benchmark suites
to evaluate AI memory systems like Mem0 and OpenAI Memory.

Usage:
    python benchmark_example.py
"""

import asyncio
from llmemory_meter import MemoryComparator


async def main():
    print("🧠 LLMemoryMeter - Benchmark Suite Example")
    print("=" * 60)
    
    # Initialize comparator
    comparator = MemoryComparator()
    
    # Show available benchmarks
    available_benchmarks = comparator.get_available_benchmarks()
    print("\n📊 Available Benchmark Suites:")
    print("-" * 40)
    for category, suites in available_benchmarks.items():
        print(f"\n📁 {category.upper()}:")
        for suite in suites:
            info = comparator.get_benchmark_info(suite)
            if info:
                print(f"  • {suite}: {info['num_workloads']} workloads")
                print(f"    └─ {info['description']}")
    
    # Available tools (currently mock implementations)
    tools = ["mem0", "openai_memory"]
    print(f"\n🔧 Testing with tools: {tools}")
    print("Note: Currently using mock implementations for demonstration")
    
    # Example 1: Run a specific benchmark suite
    print(f"\n" + "="*60)
    print("🧪 EXAMPLE 1: Running Conversational AI Memory Benchmark")
    print("="*60)
    
    try:
        results = await comparator.run_benchmark_suite("Conversational AI Memory", tools)
        
        # Print results summary
        print(f"\n📊 Results Summary:")
        print("-" * 40)
        
        if "standard_results" in results and "overall_metrics" in results["standard_results"]:
            metrics = results["standard_results"]["overall_metrics"]
            for tool_name, tool_metrics in metrics.items():
                print(f"\n🔧 {tool_name.upper()}:")
                print(f"  • Avg Latency: {tool_metrics['avg_latency_ms']:.1f}ms")
                print(f"  • Success Rate: {tool_metrics['success_rate']:.1f}%")
                print(f"  • Total Queries: {tool_metrics['total_queries']}")
        
        # Show benchmark-specific info
        if "benchmark_info" in results:
            benchmark_info = results["benchmark_info"]
            print(f"\n📝 Benchmark Details:")
            print(f"  • Category: {benchmark_info['category']}")
            print(f"  • Reference: {benchmark_info['reference']}")
            print(f"  • Recommended Metrics: {', '.join(benchmark_info['recommended_metrics'] or [])}")
        
    except Exception as e:
        print(f"❌ Error running benchmark: {e}")
    
    # Example 2: Run Long Context Memory benchmark
    print(f"\n" + "="*60)
    print("🧪 EXAMPLE 2: Running Long Context Memory Benchmark")
    print("="*60)
    
    try:
        results = await comparator.run_benchmark_suite("Long Context Memory", tools)
        
        # Print workload-specific results
        if "standard_results" in results and "workload_results" in results["standard_results"]:
            workload_results = results["standard_results"]["workload_results"]
            print(f"\n📊 Workload Results:")
            print("-" * 40)
            
            for workload_name, workload_comparison in workload_results.items():
                print(f"\n📝 {workload_name}:")
                for tool_name, result in workload_comparison.items():
                    print(f"  🔧 {tool_name}: {result.success_rate*100:.1f}% success, {result.total_latency_ms:.0f}ms")
        
    except Exception as e:
        print(f"❌ Error running benchmark: {e}")
    
    # Example 3: Show technical performance benchmark
    print(f"\n" + "="*60)
    print("🧪 EXAMPLE 3: Running Technical Performance Benchmark")
    print("="*60)
    
    try:
        results = await comparator.run_benchmark_suite("Technical Performance", tools)
        
        # Show step-by-step results for stress test
        if "standard_results" in results and "workload_results" in results["standard_results"]:
            workload_results = results["standard_results"]["workload_results"]
            
            for workload_name, workload_comparison in workload_results.items():
                if "Stress Test" in workload_name:
                    print(f"\n📊 {workload_name} Results:")
                    print("-" * 40)
                    
                    for tool_name, result in workload_comparison.items():
                        print(f"\n🔧 {tool_name.upper()}:")
                        print(f"  • Total Steps: {len(result.step_results)}")
                        print(f"  • Success Rate: {result.success_rate*100:.1f}%")
                        print(f"  • Avg Latency/Step: {result.avg_latency_ms:.1f}ms")
                        print(f"  • P95 Latency: {result.p95_latency_ms:.1f}ms")
                        
                        # Show failed steps if any
                        failed_steps = [r for r in result.step_results if not r.success]
                        if failed_steps:
                            print(f"  • Failed Steps: {len(failed_steps)}")
        
    except Exception as e:
        print(f"❌ Error running benchmark: {e}")
    
    # Example 4: Quick comparison across multiple benchmarks
    print(f"\n" + "="*60)
    print("🧪 EXAMPLE 4: Quick Multi-Benchmark Comparison")
    print("="*60)
    
    benchmark_names = ["Persona Consistency", "Memory Stress Testing"]
    comparison_results = {}
    
    for benchmark_name in benchmark_names:
        try:
            print(f"\n🔄 Running {benchmark_name}...")
            results = await comparator.run_benchmark_suite(benchmark_name, tools)
            comparison_results[benchmark_name] = results
        except Exception as e:
            print(f"❌ Error with {benchmark_name}: {e}")
    
    # Summary comparison
    print(f"\n📊 Multi-Benchmark Summary:")
    print("-" * 40)
    
    for benchmark_name, results in comparison_results.items():
        print(f"\n📝 {benchmark_name}:")
        if "standard_results" in results and "overall_metrics" in results["standard_results"]:
            metrics = results["standard_results"]["overall_metrics"]
            for tool_name, tool_metrics in metrics.items():
                print(f"  🔧 {tool_name}: {tool_metrics['avg_latency_ms']:.1f}ms avg, {tool_metrics['success_rate']:.1f}% success")
    
    print(f"\n" + "="*60)
    print("✅ Benchmark Examples Complete!")
    print("💡 Next Steps:")
    print("  1. Set up real API keys in .env file")
    print("  2. Replace mock implementations with actual API calls")
    print("  3. Run benchmarks on production memory systems")
    print("  4. Compare results across different tools")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(main())
