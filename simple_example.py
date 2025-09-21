#!/usr/bin/env python3
"""
Simple example: Compare Mem0 vs OpenAI Memory

This is the minimal starting point for LLMemoryMeter.
Just two tools, one simple workload, clear results.

Usage:
1. Copy .env.example to .env
2. Add your API keys
3. Run: python simple_example.py
"""

import asyncio
from llmemory_meter import MemoryComparator


async def main():
    print("🧠 LLMemoryMeter - Simple Mem0 vs OpenAI Memory Comparison")
    print("=" * 60)
    
    # Initialize comparator
    comparator = MemoryComparator()
    
    # Create a simple test workload
    workload = comparator.create_simple_workload(
        name="Basic Memory Test",
        memory_content="I am a software engineer who loves Python and works remotely from San Francisco.",
        retrieval_query="What is my profession and where do I work?"
    )
    
    print(f"📝 Testing workload: {workload.name}")
    print(f"   Memory content: {workload.steps[0].content}")
    print(f"   Query: {workload.steps[1].content}")
    
    # Test both tools
    tools = ["mem0", "openai_memory"]
    
    try:
        print(f"\n🚀 Comparing {len(tools)} memory tools...")
        
        # Run comparison
        results = await comparator.compare_tools(workload, tools)
        
        # Print simple results
        print(f"\n📊 Results:")
        print("-" * 40)
        
        for tool_name, result in results.items():
            print(f"\n🔧 {tool_name.upper()}:")
            print(f"   ✅ Success Rate: {result.success_rate*100:.0f}%")
            print(f"   ⚡ Total Time: {result.total_latency_ms:.0f}ms")
            print(f"   💬 Response: {result.step_results[-1].response[:100]}...")
            
            if not result.step_results[-1].success:
                print(f"   ❌ Error: {result.step_results[-1].error_message}")
        
        # Simple winner determination
        successful_results = {name: result for name, result in results.items() 
                            if result.success_rate > 0}
        
        if successful_results:
            fastest_tool = min(successful_results.items(), 
                             key=lambda x: x[1].total_latency_ms)
            print(f"\n🏆 Fastest successful tool: {fastest_tool[0].upper()}")
            print(f"   Time: {fastest_tool[1].total_latency_ms:.0f}ms")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        print("\n💡 Make sure to:")
        print("   1. Copy .env.example to .env")
        print("   2. Add your MEM0_API_KEY and OPENAI_API_KEY")
        print("   3. Install dependencies: pip install -r requirements.txt")


if __name__ == "__main__":
    asyncio.run(main())
