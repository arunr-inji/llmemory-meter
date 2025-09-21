#!/usr/bin/env python3
"""
Basic example of using LLMemoryMeter to compare AI memory tools.

This example demonstrates:
1. Creating simple workloads
2. Running comparisons between memory tools
3. Analyzing results

Run with: python examples/basic_comparison.py
"""

import asyncio
import sys
import os

# Add the parent directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from llmemory_meter import MemoryComparator


async def main():
    """Run a basic comparison between memory tools."""
    
    print("🧠 LLMemoryMeter - Basic Comparison Example")
    print("=" * 50)
    
    # Initialize the comparator
    comparator = MemoryComparator()
    
    # Check available tools
    available_tools = comparator.available_tools
    print(f"Available tools: {available_tools}")
    
    if not available_tools:
        print("❌ No tools available! Please set up your API keys in .env file")
        print("Copy .env.example to .env and add your API keys")
        return
    
    # Create some test workloads
    workloads = []
    
    # Simple information storage and retrieval
    workload1 = comparator.create_simple_workload(
        name="Personal Info Test",
        memory_content="My name is John Doe and I work as a software engineer at TechCorp. I love Python programming.",
        retrieval_query="What is my profession?"
    )
    workloads.append(workload1)
    
    # Multi-turn conversation
    workload2 = comparator.create_conversation_workload(
        name="Multi-turn Chat",
        conversation_steps=[
            "Hi! I'm planning a trip to Japan next month.",
            "I'm particularly interested in visiting Tokyo and Kyoto.",
            "What did I mention about my travel plans?",
            "Which cities was I interested in visiting?"
        ]
    )
    workloads.append(workload2)
    
    # Technical knowledge storage
    workload3 = comparator.create_simple_workload(
        name="Technical Knowledge",
        memory_content="Python uses duck typing. If it walks like a duck and quacks like a duck, it's a duck. This means you don't need to specify types explicitly.",
        retrieval_query="What is duck typing in Python?"
    )
    workloads.append(workload3)
    
    print(f"\n📝 Created {len(workloads)} test workloads")
    
    # For demo purposes, we'll test with mock tools (since API keys might not be set up)
    # In real usage, you'd have actual API keys configured
    test_tools = ["mem0", "openai_memory", "memgpt", "langmem"]
    
    try:
        # Run comprehensive benchmark
        print("\n🚀 Running benchmark...")
        results = await comparator.benchmark_tools(workloads, test_tools)
        
        # Print summary
        comparator.print_summary(results)
        
        # Save detailed results
        output_file = "benchmark_results.json"
        comparator.save_results(results, output_file)
        
        print(f"\n💾 Detailed results saved to: {output_file}")
        
        # Show some specific insights
        print("\n🔍 Key Insights:")
        if "comparison_summary" in results and "latency_comparison" in results["comparison_summary"]:
            latency_comp = results["comparison_summary"]["latency_comparison"]
            fastest_tool = latency_comp.get("best", "Unknown")
            print(f"  • Fastest tool: {fastest_tool}")
            
            if "relative_performance" in latency_comp:
                print("  • Relative latency performance:")
                for tool, perf in latency_comp["relative_performance"].items():
                    print(f"    - {tool}: {perf}")
    
    except Exception as e:
        print(f"❌ Error running benchmark: {e}")
        print("This might be because API keys are not configured.")
        print("The tools are currently using mock implementations for demonstration.")


if __name__ == "__main__":
    asyncio.run(main())
