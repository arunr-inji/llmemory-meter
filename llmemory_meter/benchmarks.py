"""
Industry-standard benchmark suites for AI memory system evaluation.

This module provides pre-configured benchmark workloads based on established
datasets and evaluation frameworks for comprehensive memory system testing.
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from llmemory_meter.workload import Workload, WorkloadStep

# Default random seed for stress test positions (can be overridden in config)
DEFAULT_STRESS_TEST_RANDOM_SEED = 42


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
    def get_all_suites(config: Optional[Dict[str, Any]] = None) -> List[BenchmarkSuite]:
        """Get all available benchmark suites.
        
        Args:
            config: Optional configuration dict containing benchmark settings
        """
        return [
            StandardBenchmarks.conversational_ai_suite(),
            StandardBenchmarks.long_context_suite(),
            StandardBenchmarks.longmemeval_suite(),
            StandardBenchmarks.membench_suite(),
            StandardBenchmarks.persona_consistency_suite(),
            StandardBenchmarks.technical_performance_suite(config),
            StandardBenchmarks.domain_specific_suite(),
            StandardBenchmarks.exact_match_evaluation_suite()
            # memory_stress_suite() omitted - stress test now in technical_performance_suite()
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
                    ground_truth="hiking Max Cascades perfect weather",
                    metadata={"session": 1, "type": "experience_sharing"}
                ),
                WorkloadStep(
                    action="retrieve",
                    content="What do you know about my pet?",
                    ground_truth="dog golden retriever Max",
                    metadata={"session": 2, "type": "memory_recall", "expected": "golden retriever named Max"}
                ),
                WorkloadStep(
                    action="chat",
                    content="I'm thinking of moving to a new city for work. What should I consider?",
                    ground_truth="software engineer Seattle 28 woman work moving",
                    metadata={"session": 2, "type": "advice_seeking"}
                ),
                WorkloadStep(
                    action="retrieve",
                    content="What's my current profession and location?",
                    ground_truth="software engineer Seattle",
                    metadata={"session": 3, "type": "biographical_recall", "expected": "software engineer from Seattle"}
                ),
                WorkloadStep(
                    action="chat",
                    content="Remember when I mentioned hiking in the Cascades? I want to go back there.",
                    ground_truth="hiking Cascades",
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
                    ground_truth="quiet reading books home",
                    metadata={"type": "recommendation_request", "expected_style": "quiet, book-related activities"}
                ),
                WorkloadStep(
                    action="chat",
                    content="My friends want me to go to a concert. What do you think?",
                    ground_truth="introverted dislike loud music crowded",
                    metadata={"type": "social_advice", "expected_consideration": "introversion, dislike of loud music"}
                ),
                WorkloadStep(
                    action="retrieve",
                    content="How many books have I read?",
                    ground_truth="over 500 books",
                    match_type="contains",
                    metadata={"type": "fact_recall", "expected": "over 500 books"}
                ),
                WorkloadStep(
                    action="chat",
                    content="Can you recommend a good book for someone like me?",
                    ground_truth="introverted librarian book lover reading",
                    metadata={"type": "personalized_recommendation", "context": "librarian, book lover"}
                )
            ]
        )
        workloads.append(persona_workload)

        # Conflict resolution workloads (overwrite + reasoning, benchmark-aligned variants)
        conflict_overwrite_workload = Workload(
            name="Conflict Resolution: Overwrite + Reasoning",
            description="Overwrites a fact, then requires direct recall and multi-hop reasoning over the updated graph.",
            steps=[
                WorkloadStep(action="store", content="Alice's manager is Bob."),
                WorkloadStep(action="store", content="Update: Alice's manager is Carol."),
                WorkloadStep(action="store", content="Carol reports to Dave."),
                WorkloadStep(
                    action="retrieve",
                    content="Who is Alice's manager? Return only the name.",
                    ground_truth="Carol",
                    match_type="exact_case_insensitive",
                    metadata={"scenario": "conflict_resolution", "metric": "overwrite_correctness"}
                ),
                WorkloadStep(
                    action="chat",
                    content="Who is Alice's manager's boss? Return only the name.",
                    ground_truth="Dave",
                    match_type="exact_case_insensitive",
                    metadata={"scenario": "conflict_resolution", "metric": "multi_hop_reasoning"}
                )
            ]
        )
        workloads.append(conflict_overwrite_workload)

        factconsolidation_sh_workload = Workload(
            name="Conflict Resolution: FactConsolidation-SH",
            description="Single-hop overwrite tasks where the latest contradictory fact should be returned.",
            steps=[
                WorkloadStep(action="store", content="The capital of Freedonia is Alton."),
                WorkloadStep(action="store", content="Update: The capital of Freedonia is Belltown."),
                WorkloadStep(
                    action="retrieve",
                    content="What is the capital of Freedonia? Return only the city.",
                    ground_truth="Belltown",
                    match_type="exact_case_insensitive",
                    metadata={"scenario": "factconsolidation_sh", "metric": "overwrite_correctness"}
                ),
                WorkloadStep(
                    action="retrieve",
                    content="Name Freedonia's capital city. Return only the city.",
                    ground_truth="Belltown",
                    match_type="exact_case_insensitive",
                    metadata={"scenario": "factconsolidation_sh", "metric": "overwrite_correctness"}
                ),
                WorkloadStep(action="store", content="The CEO of BlueRiver is Maya Chen."),
                WorkloadStep(action="store", content="Update: The CEO of BlueRiver is Luis Ortega."),
                WorkloadStep(
                    action="retrieve",
                    content="Who is the CEO of BlueRiver? Return only the name.",
                    ground_truth="Luis Ortega",
                    match_type="exact_case_insensitive",
                    metadata={"scenario": "factconsolidation_sh", "metric": "overwrite_correctness"}
                )
            ]
        )
        workloads.append(factconsolidation_sh_workload)

        factconsolidation_mh_workload = Workload(
            name="Conflict Resolution: FactConsolidation-MH",
            description="Multi-hop reasoning where one hop depends on the updated fact.",
            steps=[
                WorkloadStep(action="store", content="Nora's mentor is Ethan."),
                WorkloadStep(action="store", content="Update: Nora's mentor is Priya."),
                WorkloadStep(action="store", content="Priya works at Zephyr Labs."),
                WorkloadStep(
                    action="retrieve",
                    content="Who is Nora's mentor? Return only the name.",
                    ground_truth="Priya",
                    match_type="exact_case_insensitive",
                    metadata={"scenario": "factconsolidation_mh", "metric": "overwrite_correctness"}
                ),
                WorkloadStep(
                    action="chat",
                    content="Where does Nora's mentor work? Return only the organization.",
                    ground_truth="Zephyr Labs",
                    match_type="exact_case_insensitive",
                    metadata={"scenario": "factconsolidation_mh", "metric": "multi_hop_reasoning"}
                )
            ]
        )
        workloads.append(factconsolidation_mh_workload)

        knowledge_update_workload = Workload(
            name="Conflict Resolution: Knowledge Update (Temporal)",
            description="Sequential updates across time; requires current and previous value recall.",
            steps=[
                WorkloadStep(action="store", content="In 2021, I lived in Austin."),
                WorkloadStep(action="store", content="In 2023, I moved to Denver."),
                WorkloadStep(action="store", content="In 2024, I moved to Boston."),
                WorkloadStep(
                    action="retrieve",
                    content="Where do I live now? Return only the city.",
                    ground_truth="Boston",
                    match_type="exact_case_insensitive",
                    metadata={"scenario": "knowledge_update", "metric": "overwrite_correctness"}
                ),
                WorkloadStep(
                    action="retrieve",
                    content="Where did I live before Boston? Return only the city.",
                    ground_truth="Denver",
                    match_type="exact_case_insensitive",
                    metadata={"scenario": "knowledge_update", "metric": "temporal_ordering"}
                )
            ]
        )
        workloads.append(knowledge_update_workload)

        interference_workload = Workload(
            name="Conflict Resolution: Interference Check",
            description="Multiple conflicting pairs; verify latest fact per entity with no cross-entity contamination.",
            steps=[
                WorkloadStep(action="store", content="Project Orion lead is Alice."),
                WorkloadStep(action="store", content="Update: Project Orion lead is Ben."),
                WorkloadStep(action="store", content="Project Atlas lead is Carol."),
                WorkloadStep(action="store", content="Update: Project Atlas lead is Dana."),
                WorkloadStep(
                    action="retrieve",
                    content="Who leads Project Orion? Return only the name.",
                    ground_truth="Ben",
                    match_type="exact_case_insensitive",
                    metadata={"scenario": "interference", "metric": "overwrite_correctness"}
                ),
                WorkloadStep(
                    action="retrieve",
                    content="Who leads Project Atlas? Return only the name.",
                    ground_truth="Dana",
                    match_type="exact_case_insensitive",
                    metadata={"scenario": "interference", "metric": "overwrite_correctness"}
                )
            ]
        )
        workloads.append(interference_workload)
        
        return BenchmarkSuite(
            name="Conversational AI Memory",
            description="Legacy synthetic benchmarks based on conversational AI datasets (MSC, PersonaChat)",
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
                    ground_truth="14th 17th century Renaissance",
                    metadata={"type": "temporal_recall", "source_part": 1}
                ),
                WorkloadStep(
                    action="retrieve",
                    content="Who invented the printing press and when?",
                    ground_truth="Johannes Gutenberg around 1440 printing press",
                    metadata={"type": "factual_recall", "source_part": 3}
                ),
                WorkloadStep(
                    action="chat",
                    content="How did Leonardo da Vinci and the printing press contribute to Renaissance innovation?",
                    ground_truth="Leonardo da Vinci polymath greatest minds human history innovation printing press affordable books increased literacy rates rapid dissemination ideas Europe Renaissance",
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
                    ground_truth="ALPHA-7749-BETA",
                    match_type="exact",
                    metadata={"type": "needle_retrieval", "expected": "ALPHA-7749-BETA"}
                ),
                WorkloadStep(
                    action="retrieve",
                    content="What's the weather like today?",
                    ground_truth="sunny 75 degrees weather",
                    metadata={"type": "context_recall"}
                )
            ]
        )
        workloads.append(needle_workload)
        
        return BenchmarkSuite(
            name="Long Context Memory",
            description="Legacy synthetic benchmarks for long-context memory retention (LongBench/InfiniteBench style)",
            category="long_context",
            workloads=workloads,
            reference="Bai et al. 2023 (LongBench), Zhang et al. 2024 (InfiniteBench)",
            metrics=["retrieval_accuracy", "context_retention", "information_synthesis"]
        )

    @staticmethod
    def longmemeval_suite() -> BenchmarkSuite:
        """Placeholder suite for LongMemEval (workloads loaded on-demand)."""
        return BenchmarkSuite(
            name="LongMemEval",
            description="LongMemEval long-term memory benchmark (external dataset)",
            category="long_context",
            workloads=[],
            reference="Wu et al. 2024 (LongMemEval)",
            metrics=["long_term_memory", "abstention", "temporal_reasoning"]
        )

    @staticmethod
    def membench_suite() -> BenchmarkSuite:
        """Placeholder suite for MemBench (workloads loaded on-demand)."""
        return BenchmarkSuite(
            name="MemBench",
            description="MemBench memory benchmark (external dataset)",
            category="domain_specific",
            workloads=[],
            reference="MemBench (ACL 2025 Findings)",
            metrics=["effectiveness", "efficiency", "capacity"]
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
                    content="What is my area of specialization?",
                    ground_truth="interventional cardiology cardiologist",
                    metadata={"type": "professional_response", "expected_expertise": "cardiology"}
                ),
                WorkloadStep(
                    action="retrieve",
                    content="How many cardiac catheterizations have I performed?",
                    ground_truth="over 2000 cardiac catheterizations",
                    match_type="contains",
                    metadata={"type": "experience_recall", "expected": "over 2000"}
                ),
                WorkloadStep(
                    action="chat",
                    content="Someone asks about my training background. What should I tell them?",
                    ground_truth="Johns Hopkins residency Mayo Clinic fellowship cardiology",
                    metadata={"type": "credential_sharing", "expected_content": "Johns Hopkins, Mayo Clinic"}
                )
            ]
        )
        workloads.append(professional_workload)
        
        return BenchmarkSuite(
            name="Persona Consistency",
            description="Legacy synthetic benchmarks for maintaining consistent persona and identity",
            category="conversational",
            workloads=workloads,
            reference="Character consistency evaluation frameworks",
            metrics=["persona_consistency", "expertise_accuracy", "role_adherence"]
        )
    
    @staticmethod
    def technical_performance_suite(config: Optional[Dict[str, Any]] = None) -> BenchmarkSuite:
        """Technical performance benchmarks for memory system evaluation.
        
        Args:
            config: Optional configuration dict containing benchmark settings
        """
        import random
        
        workloads = []
        
        # Get random seed from config or use default
        if config and 'general' in config and 'stress_test_random_seed' in config['general']:
            random_seed = config['general']['stress_test_random_seed']
            
            # Validate seed (None is allowed for truly random)
            if random_seed is not None:
                if not isinstance(random_seed, int):
                    print(f"⚠️  WARNING: stress_test_random_seed must be an integer or null, got {type(random_seed).__name__}: {random_seed}")
                    print(f"    Falling back to default seed: {DEFAULT_STRESS_TEST_RANDOM_SEED}")
                    random_seed = DEFAULT_STRESS_TEST_RANDOM_SEED
                elif random_seed < 0:
                    print(f"⚠️  WARNING: stress_test_random_seed must be non-negative, got {random_seed}")
                    print(f"    Falling back to default seed: {DEFAULT_STRESS_TEST_RANDOM_SEED}")
                    random_seed = DEFAULT_STRESS_TEST_RANDOM_SEED
        else:
            random_seed = DEFAULT_STRESS_TEST_RANDOM_SEED
        
        # Memory load and retention test with unpredictable data
        memory_items = [
            ("Transaction #4721 - $847.23 wire transfer to account ending 9142", "Tokyo branch processed"),
            ("Patient record 8293 - allergy shellfish, blood type O+", "Emergency contact Sarah Lee"),
            ("Inventory SKU-MB-4455 - 23 units blue medium shipped", "Warehouse B aisle 7"),
            ("Support ticket #1829 - printer jam, solution replaced roller", "Customer Acme Corp"),
            ("Meeting notes 03/15 - Q2 budget approved, hired 3 engineers", "Deadline March 30"),
            ("Contract #9821 - annual renewal $45K, expires June", "Legal review pending"),
            ("Lab result ID-7734 - glucose 92 mg/dL normal range", "Dr Martinez ordered"),
            ("Flight booking PNR-KL8765 - Seattle to London May 12", "Seat 14A confirmed"),
            ("Insurance claim #3391 - water damage $2100 approved", "Adjuster Bob Wilson"),
            ("Software license KEY-9182 - expires December 2025", "20 user seats active"),
            ("Recipe batch #147 - reduced salt by 15%, customer feedback positive", "Chef Maria approved"),
            ("Equipment maintenance - HVAC unit 3 filter replaced", "Next service September"),
            ("Supplier invoice #6623 - $890 net 30 terms", "Payment due April 15"),
            ("Training completion - safety course 40 employees passed", "Certificates issued"),
            ("Parking permit #P-8821 - expires next month", "Spot C-14 assigned"),
            ("Network issue ticket #4492 - DNS resolved, closed", "Technician James"),
            ("Book order ISBN-9234 - 15 copies backordered", "Expected delivery May 5"),
            ("Donor record #5512 - contributed $500 annual fund", "Thank you sent"),
            ("Experiment trial T-881 - success rate 78%", "Results published"),
            ("Vehicle inspection #VIN-4493 - passed emissions test", "Valid until 2026"),
            ("Survey response ID-9943 - satisfaction score 8/10", "Feedback about speed"),
            ("Membership #M-7721 - gold tier renewed annually", "Benefits active"),
            ("Complaint case #2847 - noise issue resolved", "Manager followup done"),
            ("Grant proposal #G-1156 - $50K funding approved", "Project starts July"),
            ("Security badge #8834 - access level 3 assigned", "Photo updated"),
            ("Wine inventory Lot-442 - 48 bottles Merlot 2019", "Cellar room 2"),
            ("Audit finding #A-998 - minor discrepancy noted $45", "Corrected immediately"),
            ("Conference registration #CR-5521 - booth 12 reserved", "Setup July 8"),
            ("Patent application #PA-7755 - pending review", "Attorney Smith handling"),
            ("Scholarship award #S-3398 - $5000 semester grant", "Recipient Jane Doe"),
            ("Quality check batch #QC-881 - defect rate 0.3%", "Within tolerance"),
            ("Territory assignment - Northwest region sales", "Contact Mike Chen"),
            ("Prescription #RX-9943 - refills 2 remaining", "Pharmacy notified"),
            ("Lease agreement #L-4456 - 24 months commercial space", "Rent $3200 monthly"),
            ("Translation project #TR-6632 - Spanish 8000 words", "Deadline Friday"),
            ("Backup job #BK-7789 - completed 2.4TB data", "Verified successful"),
            ("Retirement account #RA-5521 - contribution $800 monthly", "Vested 60%"),
            ("Event ticket #E-9921 - concert seats row F", "Guest John Smith"),
            ("Import shipment #IS-4483 - customs cleared", "Delivery Tuesday"),
            ("Volunteer hours - recorded 25 hours March", "Coordinator thanked"),
            ("Equipment rental #ER-6655 - projector 3 days", "Deposit refunded"),
            ("Reference check - candidate scored strong", "Recommended by 3 managers"),
            ("Utility bill account #U-7782 - $156 autopay enabled", "Due 20th monthly"),
            ("Archive folder F-9921 - digitized 450 pages", "Storage location B3"),
            ("Certification exam #CE-8834 - passed score 89%", "Valid 3 years"),
            ("Route optimization - saved 12% fuel costs", "Driver training scheduled"),
            ("Newsletter campaign #NC-5543 - open rate 34%", "Sent 5000 emails"),
            ("Warranty claim #WC-7729 - replacement shipped", "Tracking number provided"),
            ("Tax document ID-1156 - W2 form available", "Download portal active"),
            ("Focus group session #FG-9982 - 8 participants recruited", "Scheduled Tuesday 2pm")
        ]
        
        # Use seeded random for deterministic but unpredictable test positions
        # Seed can be configured in YAML: general.stress_test_random_seed (default: 42)
        # Set to null/None in YAML for truly random positions each run
        random.seed(random_seed)
        test_positions = sorted(random.sample(range(50), 6))
        
        stress_workload = Workload(
            name="Memory Load & Retention Test",
            description="Tests throughput, capacity, and retention under load with 50 diverse entries",
            steps=[
                WorkloadStep(
                    action="store",
                    content=f"Memory entry {i}: {memory_items[i][0]}. Context: {memory_items[i][1]}"
                ) for i in range(50)
            ] + [
                WorkloadStep(
                    action="retrieve",
                    content=f"What do you remember about memory entry {i}?",
                    ground_truth=f"memory entry {i} {memory_items[i][0]} {memory_items[i][1]}"
                ) for i in test_positions
            ]
        )
        workloads.append(stress_workload)
        
        return BenchmarkSuite(
            name="Technical Performance",
            description="Legacy synthetic benchmarks for memory system performance evaluation",
            category="technical",
            workloads=workloads,
            reference="AdaptMemBench, AISBench methodologies",
            metrics=["latency", "throughput", "memory_efficiency", "error_rate", "capacity_degradation"]
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
                    ground_truth="John Smith account 12345 delayed order laptop frustrated March 15 weather delay new delivery date March 25 offered $20 credit",
                    metadata={"type": "context_retrieval", "expected_info": "previous issue and resolution"}
                ),
                WorkloadStep(
                    action="retrieve",
                    content="What compensation was offered to John Smith?",
                    ground_truth="$20 credit compensation",
                    match_type="contains",
                    metadata={"type": "specific_recall", "expected": "$20 credit"}
                )
            ]
        )
        workloads.append(customer_service_workload)
        
        return BenchmarkSuite(
            name="Domain-Specific Applications",
            description="Legacy synthetic real-world domain-specific memory scenarios",
            category="domain_specific",
            workloads=workloads,
            reference="Industry-specific use case analysis",
            metrics=["task_completion", "context_accuracy", "domain_relevance"]
        )
    
    @staticmethod
    def exact_match_evaluation_suite() -> BenchmarkSuite:
        """Benchmark suite for testing exact match evaluation types.

        Tests all four exact match types: exact, exact_case_insensitive, contains, regex.
        """
        workloads = []

        # Exact match workloads (2)
        api_key_workload = Workload(
            name="API Key Exact Match",
            description="Tests exact string matching for API keys and credentials",
            steps=[
                WorkloadStep(
                    action="store",
                    content="Your API configuration: API_KEY=sk-proj-abc123XYZ789, ENDPOINT=https://api.example.com, REGION=us-west-2",
                    metadata={"type": "credentials", "sensitive": True}
                ),
                WorkloadStep(
                    action="retrieve",
                    content="What is my API key? Be concise and return only the key.",
                    ground_truth="sk-proj-abc123XYZ789",
                    match_type="exact",
                    metadata={"type": "credential_recall", "expected": "sk-proj-abc123XYZ789"}
                ),
                WorkloadStep(
                    action="store",
                    content="Database password updated to: P@ssw0rd!2024#Secure",
                    metadata={"type": "password_update"}
                ),
                WorkloadStep(
                    action="retrieve",
                    content="What is the current database password? Provide only the password.",
                    ground_truth="P@ssw0rd!2024#Secure",
                    match_type="exact",
                    metadata={"type": "password_recall", "expected": "P@ssw0rd!2024#Secure"}
                )
            ]
        )
        workloads.append(api_key_workload)

        product_id_workload = Workload(
            name="Product ID Exact Match",
            description="Tests exact matching for product codes and SKUs",
            steps=[
                WorkloadStep(
                    action="store",
                    content="Order received for Product SKU: MB-2024-PRO-X1, Quantity: 5 units, Color: Midnight Blue",
                    metadata={"type": "order_info"}
                ),
                WorkloadStep(
                    action="retrieve",
                    content="What is the product SKU for this order? Be concise and return only the SKU.",
                    ground_truth="MB-2024-PRO-X1",
                    match_type="exact",
                    metadata={"type": "sku_recall", "expected": "MB-2024-PRO-X1"}
                ),
                WorkloadStep(
                    action="store",
                    content="Serial number for device: SN1234567890ABCDEF",
                    metadata={"type": "device_registration"}
                ),
                WorkloadStep(
                    action="retrieve",
                    content="What is the device serial number? Provide only the serial number.",
                    ground_truth="SN1234567890ABCDEF",
                    match_type="exact",
                    metadata={"type": "serial_recall", "expected": "SN1234567890ABCDEF"}
                )
            ]
        )
        workloads.append(product_id_workload)

        # Exact case insensitive workloads (2)
        email_workload = Workload(
            name="Email Case Insensitive Match",
            description="Tests case-insensitive matching for emails and usernames",
            steps=[
                WorkloadStep(
                    action="store",
                    content="Primary contact email: Support@Example.Com, Backup: admin@COMPANY.org",
                    metadata={"type": "contact_info"}
                ),
                WorkloadStep(
                    action="retrieve",
                    content="What is the primary contact email? Be concise and return only the email address.",
                    ground_truth="support@example.com",
                    match_type="exact_case_insensitive",
                    metadata={"type": "email_recall", "note": "should match regardless of case"}
                ),
                WorkloadStep(
                    action="store",
                    content="User account created: Username is JohnDoe2024",
                    metadata={"type": "account_creation"}
                ),
                WorkloadStep(
                    action="retrieve",
                    content="What is the username? Provide only the username.",
                    ground_truth="johndoe2024",
                    match_type="exact_case_insensitive",
                    metadata={"type": "username_recall", "note": "should match regardless of case"}
                )
            ]
        )
        workloads.append(email_workload)

        command_workload = Workload(
            name="Command Case Insensitive Match",
            description="Tests case-insensitive matching for commands and keywords",
            steps=[
                WorkloadStep(
                    action="store",
                    content="System command to restart service: RESTART-SERVICE-NGINX",
                    metadata={"type": "system_command"}
                ),
                WorkloadStep(
                    action="retrieve",
                    content="What is the command to restart the service? Be concise and return only the command.",
                    ground_truth="restart-service-nginx",
                    match_type="exact_case_insensitive",
                    metadata={"type": "command_recall", "note": "commands are case insensitive"}
                ),
                WorkloadStep(
                    action="store",
                    content="Access level required: ADMIN_FULL_ACCESS",
                    metadata={"type": "permission_info"}
                ),
                WorkloadStep(
                    action="retrieve",
                    content="What access level is required? Provide only the access level.",
                    ground_truth="Admin_Full_Access",
                    match_type="exact_case_insensitive",
                    metadata={"type": "permission_recall", "note": "should match regardless of case"}
                )
            ]
        )
        workloads.append(command_workload)

        # Regex match workloads (2)
        phone_pattern_workload = Workload(
            name="Phone Number Regex Match",
            description="Tests regex pattern matching for phone numbers and dates",
            steps=[
                WorkloadStep(
                    action="store",
                    content="Customer phone: +1 (555) 123-4567, alternate format: 555-987-6543",
                    metadata={"type": "contact_info"}
                ),
                WorkloadStep(
                    action="retrieve",
                    content="What is the customer's primary phone number?",
                    ground_truth=r"\+1\s*\(555\)\s*123-4567",
                    match_type="regex",
                    metadata={"type": "phone_recall", "note": "regex allows format flexibility"}
                ),
                WorkloadStep(
                    action="store",
                    content="Appointment scheduled for 2024-03-15 at 14:30",
                    metadata={"type": "appointment"}
                ),
                WorkloadStep(
                    action="retrieve",
                    content="What date is the appointment?",
                    ground_truth=r"202[0-9]-[0-1][0-9]-[0-3][0-9]",
                    match_type="regex",
                    metadata={"type": "date_recall", "note": "matches YYYY-MM-DD format"}
                )
            ]
        )
        workloads.append(phone_pattern_workload)

        email_pattern_workload = Workload(
            name="Email Regex Pattern Match",
            description="Tests regex pattern matching for email formats and IDs",
            steps=[
                WorkloadStep(
                    action="store",
                    content="Support email: john.doe@company.com, Sales: sales-team@business.co.uk",
                    metadata={"type": "email_directory"}
                ),
                WorkloadStep(
                    action="retrieve",
                    content="What is John's email address?",
                    ground_truth=r"[\w\.-]+@[\w\.-]+\.\w+",
                    match_type="regex",
                    metadata={"type": "email_pattern_recall", "note": "matches email pattern"}
                ),
                WorkloadStep(
                    action="store",
                    content="Transaction ID: TXN-2024-03-15-A7B3C9",
                    metadata={"type": "transaction_log"}
                ),
                WorkloadStep(
                    action="retrieve",
                    content="What is the transaction ID?",
                    ground_truth=r"TXN-\d{4}-\d{2}-\d{2}-[A-F0-9]{6}",
                    match_type="regex",
                    metadata={"type": "transaction_id_recall", "note": "matches TXN-YYYY-MM-DD-HEXCODE pattern"}
                )
            ]
        )
        workloads.append(email_pattern_workload)

        return BenchmarkSuite(
            name="Exact Match Evaluation",
            description="Legacy synthetic benchmarks for testing exact match evaluation methods (exact, case-insensitive, regex)",
            category="technical",
            workloads=workloads,
            reference="Exact match evaluation testing framework",
            metrics=["exact_match_accuracy", "pattern_recognition", "case_handling"]
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
