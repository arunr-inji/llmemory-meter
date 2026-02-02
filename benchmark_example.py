#!/usr/bin/env python3
"""
Benchmark Example - Run industry benchmark subsets on memory tools.

This example demonstrates how to use BenchmarkLoader to run a small
subset of LongMemEval/MemBench in store/retrieve-only mode.

Usage:
    python benchmark_example.py
"""

import asyncio
from llmemory_meter import MemoryComparator
from llmemory_meter.benchmark_loader import BenchmarkLoader


async def main():
    print("🧠 LLMemoryMeter - Benchmark Suite Example")
    print("=" * 60)
    
    # Initialize comparator in store/retrieve-only mode
    comparator = MemoryComparator({"general": {"store_retrieve_only": True}})

    # Use baseline tool for a quick, no-API-key demo
    tools = ["baseline"]
    print(f"\n🔧 Testing with tools: {tools}")

    print(f"\n" + "=" * 60)
    print("🧪 EXAMPLE 1: LongMemEval (subset of 5 questions)")
    print("=" * 60)

    try:
        workloads = BenchmarkLoader.load_longmemeval(subset="S", limit=5)
        results = await comparator.benchmark_tools(workloads, tools)
        comparator.print_summary(results)
    except Exception as e:
        print(f"❌ Error running LongMemEval subset: {e}")

    print(f"\n" + "=" * 60)
    print("🧪 EXAMPLE 2: MemBench (subset of 5 items)")
    print("=" * 60)

    try:
        workloads = BenchmarkLoader.load_membench(limit=5)
        results = await comparator.benchmark_tools(workloads, tools)
        comparator.print_summary(results)
    except Exception as e:
        print(f"❌ Error running MemBench subset: {e}")

    print(f"\n" + "=" * 60)
    print("✅ Benchmark Examples Complete!")
    print("💡 Next Steps:")
    print("  1. Set up real API keys in .env file")
    print("  2. Enable Mem0/Zep/MemGPT in configs/industry-benchmarks.yml")
    print("  3. Run full Phase 1 benchmarks")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
