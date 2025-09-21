"""
Industry-standard benchmark suites for AI memory system evaluation.

This module provides pre-configured benchmark workloads based on established
datasets and evaluation frameworks for comprehensive memory system testing.
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from llmemory_meter.workload import Workload, WorkloadStep


@dataclass
class BenchmarkSuite:
    """A collection of related benchmark workloads."""
    name: str
    description: str
    category: str  # "conversational", "long_context", "technical", "domain_specific"
    workloads: List[Workload]
    reference: Optional[str] = None  # Paper/dataset reference
    metrics: Optional[List[str]] = None  # Recommended evaluation metrics


class StandardBenchmarks:
    """Factory class for creating industry-standard benchmark suites."""
    
    @staticmethod
    def get_all_suites() -> List[BenchmarkSuite]:
        """Get all available benchmark suites."""
        return [
            StandardBenchmarks.conversational_ai_suite(),
            StandardBenchmarks.long_context_suite(),
            StandardBenchmarks.persona_consistency_suite(),
            StandardBenchmarks.technical_performance_suite(),
            StandardBenchmarks.domain_specific_suite(),
            StandardBenchmarks.memory_stress_suite()
        ]
    
    @staticmethod
    def get_suite_by_category(category: str) -> List[BenchmarkSuite]:
        """Get benchmark suites by category."""
        all_suites = StandardBenchmarks.get_all_suites()
        return [suite for suite in all_suites if suite.category == category]
    
    @staticmethod
    def get_suite_by_name(name: str) -> Optional[BenchmarkSuite]:
        """Get a specific benchmark suite by name."""
        all_suites = StandardBenchmarks.get_all_suites()
        for suite in all_suites:
            if suite.name == name:
                return suite
        return None
    
    @staticmethod
    def conversational_ai_suite() -> BenchmarkSuite:
        """
        Benchmark suite based on conversational AI datasets.
        Tests memory retention across multi-turn conversations.
        """
        workloads = []
        
        # Multi-Session Chat (MSC) inspired workloads
        msc_workload = Workload(
            name="Multi-Session Memory Retention",
            description="Tests memory retention across multiple conversation sessions",
            steps=[
                WorkloadStep(
                    action="store",
                    content="Hi! I'm Sarah, a 28-year-old software engineer from Seattle. I love hiking and have a golden retriever named Max.",
                    metadata={"session": 1, "type": "introduction"}
                ),
                WorkloadStep(
                    action="chat",
                    content="I went hiking with Max yesterday in the Cascades. The weather was perfect!",
                    metadata={"session": 1, "type": "experience_sharing"}
                ),
                WorkloadStep(
                    action="retrieve",
                    content="What do you know about my pet?",
                    metadata={"session": 2, "type": "memory_recall", "expected": "golden retriever named Max"}
                ),
                WorkloadStep(
                    action="chat",
                    content="I'm thinking of moving to a new city for work. What should I consider?",
                    metadata={"session": 2, "type": "advice_seeking"}
                ),
                WorkloadStep(
                    action="retrieve",
                    content="What's my current profession and location?",
                    metadata={"session": 3, "type": "biographical_recall", "expected": "software engineer from Seattle"}
                ),
                WorkloadStep(
                    action="chat",
                    content="Remember when I mentioned hiking in the Cascades? I want to go back there.",
                    metadata={"session": 3, "type": "experience_reference"}
                )
            ]
        )
        workloads.append(msc_workload)
        
        # PersonaChat inspired workload
        persona_workload = Workload(
            name="Persona Consistency Test",
            description="Tests consistency of persona-based responses",
            steps=[
                WorkloadStep(
                    action="store",
                    content="My personality: I'm an introverted book lover who prefers quiet evenings at home. I work as a librarian and have read over 500 books. I don't like crowded places or loud music.",
                    metadata={"type": "persona_definition"}
                ),
                WorkloadStep(
                    action="chat",
                    content="What should I do this weekend?",
                    metadata={"type": "recommendation_request", "expected_style": "quiet, book-related activities"}
                ),
                WorkloadStep(
                    action="chat",
                    content="My friends want me to go to a concert. What do you think?",
                    metadata={"type": "social_advice", "expected_consideration": "introversion, dislike of loud music"}
                ),
                WorkloadStep(
                    action="retrieve",
                    content="How many books have I read?",
                    metadata={"type": "fact_recall", "expected": "over 500 books"}
                ),
                WorkloadStep(
                    action="chat",
                    content="Can you recommend a good book for someone like me?",
                    metadata={"type": "personalized_recommendation", "context": "librarian, book lover"}
                )
            ]
        )
        workloads.append(persona_workload)
        
        return BenchmarkSuite(
            name="Conversational AI Memory",
            description="Benchmarks based on conversational AI datasets (MSC, PersonaChat)",
            category="conversational",
            workloads=workloads,
            reference="Xu et al. 2021 (MSC), Zhang et al. 2018 (PersonaChat)",
            metrics=["persona_consistency", "fact_accuracy", "memory_retention", "response_relevance"]
        )
    
    @staticmethod
    def long_context_suite() -> BenchmarkSuite:
        """
        Benchmark suite for long-context memory evaluation.
        Based on LongBench and InfiniteBench methodologies.
        """
        workloads = []
        
        # Long document comprehension
        long_doc_workload = Workload(
            name="Long Document Memory",
            description="Tests memory retention over long document processing",
            steps=[
                WorkloadStep(
                    action="store",
                    content="Document Part 1: The Renaissance was a cultural movement that spanned roughly from the 14th to the 17th century, beginning in Italy in the Late Middle Ages and later spreading to the rest of Europe. The term is also used more loosely to refer to the historical era, but since the changes of the Renaissance were not uniform across Europe, this is a general use of the term.",
                    metadata={"document_part": 1, "topic": "renaissance_overview"}
                ),
                WorkloadStep(
                    action="store", 
                    content="Document Part 2: Leonardo da Vinci (1452-1519) was an Italian polymath whose areas of interest included invention, drawing, painting, sculpture, architecture, science, music, mathematics, engineering, literature, anatomy, geology, astronomy, botany, paleontology, and cartography. He is widely considered one of the greatest minds in human history.",
                    metadata={"document_part": 2, "topic": "leonardo_da_vinci"}
                ),
                WorkloadStep(
                    action="store",
                    content="Document Part 3: The printing press, invented by Johannes Gutenberg around 1440, revolutionized the spread of knowledge during the Renaissance. It made books more affordable and accessible, leading to increased literacy rates and the rapid dissemination of new ideas across Europe.",
                    metadata={"document_part": 3, "topic": "printing_press"}
                ),
                WorkloadStep(
                    action="retrieve",
                    content="What time period did the Renaissance span?",
                    metadata={"type": "temporal_recall", "source_part": 1}
                ),
                WorkloadStep(
                    action="retrieve",
                    content="Who invented the printing press and when?",
                    metadata={"type": "factual_recall", "source_part": 3}
                ),
                WorkloadStep(
                    action="chat",
                    content="How did Leonardo da Vinci and the printing press contribute to Renaissance innovation?",
                    metadata={"type": "synthesis", "requires_parts": [2, 3]}
                )
            ]
        )
        workloads.append(long_doc_workload)
        
        # Needle in haystack test
        needle_workload = Workload(
            name="Information Needle Test",
            description="Tests retrieval of specific information from large context",
            steps=[
                WorkloadStep(
                    action="store",
                    content="Random context: The weather today is sunny with a temperature of 75 degrees. Traffic is moderate on the highways. Stock market opened higher this morning. The special code for today's system access is: ALPHA-7749-BETA. Local news reports a new restaurant opening downtown. Sports scores from yesterday's games are available online.",
                    metadata={"type": "haystack", "contains_needle": True, "needle": "ALPHA-7749-BETA"}
                ),
                WorkloadStep(
                    action="store",
                    content="Additional context: Meeting scheduled for 2 PM today. Email server maintenance planned for weekend. New employee orientation next Monday. Budget review due by end of month. Project deadline extended to next Friday. Conference call with clients at 3 PM.",
                    metadata={"type": "additional_context"}
                ),
                WorkloadStep(
                    action="retrieve",
                    content="What is the special code mentioned in the information?",
                    metadata={"type": "needle_retrieval", "expected": "ALPHA-7749-BETA"}
                ),
                WorkloadStep(
                    action="retrieve",
                    content="What's the weather like today?",
                    metadata={"type": "context_recall"}
                )
            ]
        )
        workloads.append(needle_workload)
        
        return BenchmarkSuite(
            name="Long Context Memory",
            description="Benchmarks for long-context memory retention (LongBench/InfiniteBench style)",
            category="long_context",
            workloads=workloads,
            reference="Bai et al. 2023 (LongBench), Zhang et al. 2024 (InfiniteBench)",
            metrics=["retrieval_accuracy", "context_retention", "information_synthesis"]
        )
    
    @staticmethod
    def persona_consistency_suite() -> BenchmarkSuite:
        """Benchmark suite focused on persona consistency and character memory."""
        workloads = []
        
        # Professional persona consistency
        professional_workload = Workload(
            name="Professional Persona Consistency",
            description="Tests consistency of professional identity and expertise",
            steps=[
                WorkloadStep(
                    action="store",
                    content="I am Dr. Emily Chen, a cardiologist with 15 years of experience. I specialize in interventional cardiology and have performed over 2,000 cardiac catheterizations. I completed my residency at Johns Hopkins and fellowship at Mayo Clinic.",
                    metadata={"persona_type": "professional", "domain": "medical"}
                ),
                WorkloadStep(
                    action="chat",
                    content="A patient asks about chest pain symptoms. How should I respond?",
                    metadata={"type": "professional_response", "expected_expertise": "cardiology"}
                ),
                WorkloadStep(
                    action="retrieve",
                    content="How many cardiac catheterizations have I performed?",
                    metadata={"type": "experience_recall", "expected": "over 2,000"}
                ),
                WorkloadStep(
                    action="chat",
                    content="Someone asks about my training background. What should I tell them?",
                    metadata={"type": "credential_sharing", "expected_content": "Johns Hopkins, Mayo Clinic"}
                ),
                WorkloadStep(
                    action="chat",
                    content="Should I give advice about a dermatology condition?",
                    metadata={"type": "scope_awareness", "expected_behavior": "refer to specialist"}
                )
            ]
        )
        workloads.append(professional_workload)
        
        return BenchmarkSuite(
            name="Persona Consistency",
            description="Benchmarks for maintaining consistent persona and identity",
            category="conversational",
            workloads=workloads,
            reference="Character consistency evaluation frameworks",
            metrics=["persona_consistency", "expertise_accuracy", "role_adherence"]
        )
    
    @staticmethod
    def technical_performance_suite() -> BenchmarkSuite:
        """Technical performance benchmarks for memory system evaluation."""
        workloads = []
        
        # High-frequency operations
        stress_workload = Workload(
            name="Memory System Stress Test",
            description="High-frequency memory operations to test system limits",
            steps=[
                WorkloadStep(
                    action="store",
                    content=f"Data chunk {i}: {' '.join([f'item_{j}' for j in range(10)])}"
                ) for i in range(20)
            ] + [
                WorkloadStep(
                    action="retrieve",
                    content=f"What was in data chunk {i}?"
                ) for i in range(0, 20, 5)
            ]
        )
        workloads.append(stress_workload)
        
        return BenchmarkSuite(
            name="Technical Performance",
            description="Technical benchmarks for memory system performance evaluation",
            category="technical",
            workloads=workloads,
            reference="AdaptMemBench, AISBench methodologies",
            metrics=["latency", "throughput", "memory_efficiency", "error_rate"]
        )
    
    @staticmethod
    def domain_specific_suite() -> BenchmarkSuite:
        """Domain-specific benchmark workloads."""
        workloads = []
        
        # Customer service scenario
        customer_service_workload = Workload(
            name="Customer Service Memory",
            description="Customer service interaction with memory requirements",
            steps=[
                WorkloadStep(
                    action="store",
                    content="Customer: John Smith, Account: #12345, Issue: Delayed order, Order Date: March 15, Product: Laptop, Status: Frustrated",
                    metadata={"domain": "customer_service", "priority": "high"}
                ),
                WorkloadStep(
                    action="store",
                    content="Resolution: Checked shipping - weather delay, new delivery date March 25, offered $20 credit compensation",
                    metadata={"domain": "customer_service", "type": "resolution"}
                ),
                WorkloadStep(
                    action="chat",
                    content="Customer John Smith is calling back. What do I need to know?",
                    metadata={"type": "context_retrieval", "expected_info": "previous issue and resolution"}
                ),
                WorkloadStep(
                    action="retrieve",
                    content="What compensation was offered to John Smith?",
                    metadata={"type": "specific_recall", "expected": "$20 credit"}
                )
            ]
        )
        workloads.append(customer_service_workload)
        
        return BenchmarkSuite(
            name="Domain-Specific Applications",
            description="Real-world domain-specific memory scenarios",
            category="domain_specific",
            workloads=workloads,
            reference="Industry-specific use case analysis",
            metrics=["task_completion", "context_accuracy", "domain_relevance"]
        )
    
    @staticmethod
    def memory_stress_suite() -> BenchmarkSuite:
        """Memory stress testing benchmark suite."""
        workloads = []
        
        # Memory capacity test
        capacity_workload = Workload(
            name="Memory Capacity Test",
            description="Tests memory system capacity and retention under load",
            steps=[
                WorkloadStep(
                    action="store",
                    content=f"Memory item {i}: This is a test entry containing information about item number {i}. It includes details like timestamp {i*100}, category type-{i%5}, and status active-{i%3}.",
                    metadata={"item_id": i, "category": i%5, "status": i%3}
                ) for i in range(50)
            ] + [
                WorkloadStep(
                    action="retrieve",
                    content=f"What do you know about memory item {i}?",
                    metadata={"type": "capacity_test", "item_id": i}
                ) for i in [0, 10, 25, 35, 49]  # Test various positions
            ]
        )
        workloads.append(capacity_workload)
        
        return BenchmarkSuite(
            name="Memory Stress Testing",
            description="Stress testing for memory system limits and performance",
            category="technical",
            workloads=workloads,
            reference="Memory system stress testing methodologies",
            metrics=["capacity_limit", "retention_accuracy", "performance_degradation"]
        )


class BenchmarkRunner:
    """Helper class for running benchmark suites with MemoryComparator."""
    
    @staticmethod
    def get_available_benchmarks() -> Dict[str, List[str]]:
        """Get available benchmarks organized by category."""
        suites = StandardBenchmarks.get_all_suites()
        categories = {}
        for suite in suites:
            if suite.category not in categories:
                categories[suite.category] = []
            categories[suite.category].append(suite.name)
        return categories
    
    @staticmethod
    def get_benchmark_info(benchmark_name: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific benchmark."""
        suites = StandardBenchmarks.get_all_suites()
        for suite in suites:
            if suite.name == benchmark_name:
                return {
                    "name": suite.name,
                    "description": suite.description,
                    "category": suite.category,
                    "num_workloads": len(suite.workloads),
                    "reference": suite.reference,
                    "recommended_metrics": suite.metrics,
                    "workload_names": [w.name for w in suite.workloads]
                }
        return None
    
    @staticmethod
    def create_benchmark_report(results: Dict[str, Any], suite_name: str) -> Dict[str, Any]:
        """Create a specialized report for benchmark results."""
        suite_info = BenchmarkRunner.get_benchmark_info(suite_name)
        if not suite_info:
            return results
        
        # Add benchmark-specific analysis
        benchmark_report = {
            "benchmark_info": suite_info,
            "standard_results": results,
            "benchmark_specific_analysis": {
                "category": suite_info["category"],
                "reference": suite_info["reference"],
                "evaluation_focus": suite_info["recommended_metrics"]
            }
        }
        
        return benchmark_report
