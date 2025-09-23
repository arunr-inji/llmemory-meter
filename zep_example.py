#!/usr/bin/env python3
"""
Zep Example: Testing Zep Memory Tool

This example demonstrates how to use the Zep memory tool with LLMemoryMeter.
Shows store, retrieve, and chat operations using Zep's long-term memory capabilities.

Usage:
1. Copy .env.example to .env
2. Add your ZEP_API_KEY
3. Run: python zep_example.py
"""

import asyncio
from llmemory_meter import MemoryComparator


async def main():
    print("🧠 LLMemoryMeter - Zep Memory Tool Example")
    print("=" * 50)

    # Initialize comparator
    comparator = MemoryComparator()

    # Create a simple test workload
    workload = comparator.create_simple_workload(
        name="Zep Memory Test",
        memory_content="I am a data scientist who loves machine learning and works on NLP projects. I prefer Python and PyTorch.",
        retrieval_query="What are my professional interests and preferred tools?"
    )

    print(f"📝 Testing workload: {workload.name}")
    print(f"   Memory content: {workload.steps[0].content}")
    print(f"   Query: {workload.steps[1].content}")

    # Test Zep tool specifically
    tools = ["zep"]

    try:
        print(f"\n🚀 Testing Zep memory tool...")

        # Run comparison
        results = await comparator.compare_tools(workload, tools)

        # Print results
        print(f"\n📊 Zep Results:")
        print("-" * 40)

        for tool_name, result in results.items():
            print(f"\n🔧 {tool_name.upper()}:")
            print(f"   ✅ Success Rate: {result.success_rate*100:.0f}%")
            print(f"   ⚡ Total Time: {result.total_latency_ms:.0f}ms")

            # Show step results
            for i, step_result in enumerate(result.step_results):
                action = step_result.action.upper()
                status = "✅" if step_result.success else "❌"
                print(f"   {status} Step {i+1} ({action}): {step_result.latency_ms:.0f}ms")
                print(f"      Response: {step_result.response[:100]}...")

                if not step_result.success:
                    print(f"      Error: {step_result.error_message}")

        print(f"\n🎯 Zep Features Demonstrated:")
        print("   • Long-term memory storage")
        print("   • Context-aware retrieval")
        print("   • Session-based memory management")
        print("   • Temporal knowledge graphs")

    except Exception as e:
        print(f"❌ Error: {e}")
        print("\n💡 Make sure to:")
        print("   1. Copy .env.example to .env")
        print("   2. Add your ZEP_API_KEY")
        print("   3. Install dependencies: pip install -r requirements.txt")
        print("   4. Check Zep service availability")


if __name__ == "__main__":
    asyncio.run(main())