#!/usr/bin/env python3
"""
Example showing how to create custom workloads for specific use cases.

This example demonstrates:
1. Creating complex multi-step workloads
2. Testing specific memory scenarios
3. Customizing evaluation criteria

Run with: python examples/custom_workload.py
"""

import asyncio
import sys
import os

# Add the parent directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from llmemory_meter import MemoryComparator
from llmemory_meter.workload import Workload, WorkloadStep


async def main():
    """Run custom workload examples."""
    
    print("🎯 LLMemoryMeter - Custom Workload Example")
    print("=" * 50)
    
    comparator = MemoryComparator()
    
    # Create a complex customer service scenario
    customer_service_workload = Workload(
        name="Customer Service Scenario",
        description="Test memory in a customer service context with multiple interactions",
        steps=[
            WorkloadStep(
                action="store",
                content="Customer John Smith called about order #12345. He ordered a laptop on March 15th. Shipping address: 123 Main St, Boston, MA. He's frustrated about delayed delivery.",
                metadata={"type": "customer_info", "priority": "high"}
            ),
            WorkloadStep(
                action="store", 
                content="Checked order #12345 status: Package was delayed due to weather. New estimated delivery: March 25th. Offered $20 credit for inconvenience.",
                metadata={"type": "order_update", "order_id": "12345"}
            ),
            WorkloadStep(
                action="retrieve",
                content="What was John Smith's order number?",
                metadata={"type": "info_lookup"}
            ),
            WorkloadStep(
                action="chat",
                content="The customer is calling back. What do I need to know about his previous interaction?",
                metadata={"type": "context_recall"}
            ),
            WorkloadStep(
                action="retrieve",
                content="What compensation did we offer for the delay?",
                metadata={"type": "policy_check"}
            )
        ]
    )
    
    # Create a research assistant scenario
    research_workload = Workload(
        name="Research Assistant",
        description="Test memory for research and knowledge accumulation",
        steps=[
            WorkloadStep(
                action="store",
                content="Paper: 'Attention Is All You Need' (2017) introduced the Transformer architecture. Key innovation: self-attention mechanism replacing RNNs and CNNs for sequence modeling.",
                metadata={"type": "research_paper", "year": 2017}
            ),
            WorkloadStep(
                action="store",
                content="Paper: 'BERT: Pre-training of Deep Bidirectional Transformers' (2018) applied Transformers to language understanding with bidirectional training.",
                metadata={"type": "research_paper", "year": 2018}
            ),
            WorkloadStep(
                action="store",
                content="Paper: 'GPT-3: Language Models are Few-Shot Learners' (2020) demonstrated emergent abilities in large language models with 175B parameters.",
                metadata={"type": "research_paper", "year": 2020}
            ),
            WorkloadStep(
                action="retrieve",
                content="What was the key innovation in the original Transformer paper?",
                metadata={"type": "knowledge_query"}
            ),
            WorkloadStep(
                action="chat",
                content="Can you trace the evolution from Transformers to GPT-3 based on the papers I mentioned?",
                metadata={"type": "synthesis"}
            )
        ]
    )
    
    # Create a personal assistant scenario
    personal_assistant_workload = Workload(
        name="Personal Assistant",
        description="Test memory for personal task and preference management",
        steps=[
            WorkloadStep(
                action="store",
                content="User preferences: Likes coffee (no sugar, oat milk), prefers morning meetings before 10 AM, works out at 6 PM on weekdays, vegetarian diet.",
                metadata={"type": "preferences"}
            ),
            WorkloadStep(
                action="store",
                content="Upcoming events: Team meeting March 20th 9 AM, Doctor appointment March 22nd 2 PM, Dinner with Sarah March 23rd 7 PM at Green Garden restaurant.",
                metadata={"type": "calendar"}
            ),
            WorkloadStep(
                action="chat",
                content="I want to schedule a coffee meeting with a client next week. What would be good times for me?",
                metadata={"type": "scheduling"}
            ),
            WorkloadStep(
                action="retrieve",
                content="What are my dietary restrictions?",
                metadata={"type": "preference_lookup"}
            ),
            WorkloadStep(
                action="chat",
                content="Suggest a restaurant for my dinner with Sarah that would work for my diet.",
                metadata={"type": "recommendation"}
            )
        ]
    )
    
    workloads = [customer_service_workload, research_workload, personal_assistant_workload]
    
    print(f"📝 Created {len(workloads)} custom workloads:")
    for workload in workloads:
        print(f"  • {workload.name}: {len(workload.steps)} steps")
    
    # Test with available tools
    test_tools = ["mem0", "openai_memory"]  # Start with main competitors
    
    try:
        print(f"\n🚀 Testing {len(test_tools)} tools on custom workloads...")
        
        # Run each workload individually for detailed analysis
        for workload in workloads:
            print(f"\n--- Testing: {workload.name} ---")
            
            comparison = await comparator.compare_tools(workload, test_tools)
            
            # Print results for this workload
            for tool_name, result in comparison.items():
                print(f"\n{tool_name.upper()}:")
                print(f"  Success Rate: {result.success_rate*100:.1f}%")
                print(f"  Total Latency: {result.total_latency_ms:.0f}ms")
                print(f"  Avg Latency/Step: {result.avg_latency_ms:.0f}ms")
                
                # Show failed steps if any
                failed_steps = [r for r in result.step_results if not r.success]
                if failed_steps:
                    print(f"  Failed Steps: {len(failed_steps)}")
                    for step in failed_steps:
                        print(f"    - Step {step.step_index}: {step.error_message}")
        
        # Run comprehensive benchmark
        print(f"\n📊 Running comprehensive benchmark across all workloads...")
        results = await comparator.benchmark_tools(workloads, test_tools)
        
        # Print final summary
        comparator.print_summary(results)
        
        # Save results
        comparator.save_results(results, "custom_workload_results.json")
        
    except Exception as e:
        print(f"❌ Error running custom workloads: {e}")
        print("Note: This example uses mock implementations for demonstration.")


if __name__ == "__main__":
    asyncio.run(main())
