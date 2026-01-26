# Conflict Resolution Workload Implementation Plan

## Goal
Add a "Conflict Resolution with Overwrite + Reasoning" workload that verifies
the system uses the *latest* memory update and can reason over updated facts.
Report overwrite correctness and multi-hop reasoning accuracy, and provide a
config to run this workload in isolation.

## References
- `docs/roadmap.md` (Tier 3.1: Conflict Resolution with Overwrite + Reasoning)
- `docs/architecture.md` (benchmark/workload flow and evaluation model)
- `llmemory_meter/benchmarks.py` (workload definitions, suite wiring)
- `llmemory_meter/workload.py` (WorkloadStep schema + match_type)
- `llmemory_meter/comparator.py` (accuracy evaluation + step execution)
- `llmemory_meter/metrics.py` (aggregation and reporting)
- `configs/*.yml` + `configs/README.md` (config patterns and documentation)

## Benchmark-aligned extensions (from recent conflict-resolution benchmarks)
These are additional workloads we want to implement to align with the latest
public benchmarks (e.g., MemoryAgentBench 2025, LongMemEval 2024/2025).

- **MemoryAgentBench: FactConsolidation-SH (single-hop overwrite)**
  - Design: Use counterfactual edit pairs where the later fact contradicts
    the earlier one; require the latest fact in the answer.
  - Workload variant: store old fact, store updated fact, retrieve updated
    value with `match_type="exact_case_insensitive"` or `contains`.
  - Add *multiple queries after a single injection* to test stability
    (their "inject once, query multiple times" pattern).

- **MemoryAgentBench: FactConsolidation-MH (multi-hop overwrite)**
  - Design: Resolve conflicts and then reason over the updated entity graph.
  - Workload variant: store old relation, store updated relation, store a
    second fact about the updated entity, then query a derived fact.
  - Scoring: exact/contains on the final entity to avoid embedding ambiguity.

- **LongMemEval: knowledge_update (multi-session updates)**
  - Design: Facts change across sessions; queries ask for the *current* value
    (and optionally the previous value) with explicit time markers.
  - Workload variant: multiple "I moved to X" updates, then retrieve "Where
    do I live now?" and "Where did I live before X?"
  - Scoring: exact/contains for current value; optional temporal correctness
    checks for previous value.

- **Interference variants (from MemoryAgentBench setup)**
  - Add multiple conflicting pairs in one workload to test interference
    between unrelated entities and ensure correct "latest-fact" selection.

## Plan
1) **Define the workload scenario**
   - Add a new workload named `Conflict Resolution: Overwrite + Reasoning`.
   - Use the roadmap example with an explicit update and a multi-hop query:
     - Store: “Alice’s manager is Bob.”
     - Store: “Update: Alice’s manager is Carol.”
     - Store: “Carol reports to Dave.”
     - Retrieve: “Who is Alice’s manager? Return only the name.” → `ground_truth="Carol"`
     - Chat: “Who is Alice’s manager’s boss? Return only the name.” → `ground_truth="Dave"`
   - Use `match_type="exact_case_insensitive"` (or `exact`) for the two evaluation steps
     to avoid embedding ambiguity. If tools tend to include extra text, switch to
     `match_type="contains"` with concise prompts.
   - Add `metadata` tags to the two scored steps (e.g., `metric: overwrite_correctness`,
     `metric: multi_hop_reasoning`, `scenario: conflict_resolution`) so they can be
     aggregated and reported.

2) **Add the workload to a benchmark suite**
   - Insert the workload into `StandardBenchmarks.conversational_ai_suite()` so it runs
     in default configs (starter/comprehensive), and can be filtered via `workloads`.
   - Alternative if isolation is preferred: create a new `BenchmarkSuite` named
     “Conflict Resolution” with category `conversational` and add it to
     `StandardBenchmarks.get_all_suites()`.

3) **Preserve step metadata for reporting**
   - In `comparator.run_workload_on_tool()`, attach `step.metadata` to each
     `StepResult.metadata` (including timeout results). If a tool already set metadata,
     merge into a single dict rather than overwrite.
   - This keeps per-step tags available for aggregation in `metrics.py`.

4) **Add conflict-resolution metrics (optional but aligns with roadmap)**
   - In `metrics.py`, aggregate accuracy for tagged steps:
     - `overwrite_correctness` = average accuracy for overwrite retrieval steps
     - `multi_hop_reasoning` = average accuracy for reasoning steps
   - Add a `scenario_metrics` (or similar) dict to `PerformanceMetrics` and include it
     in `to_dict()` output.
   - In `comparator.print_summary()`, surface these metrics when present.

5) **Documentation updates**
   - `docs/architecture.md`: add a brief note in the Benchmarks section describing
     the conflict resolution workload and how it is scored (exact/contains).
   - `docs/roadmap.md`: mark Feature #5 “Conflict Resolution Workload” as complete
     after implementation and update MVP deliverables if needed.
   - `configs/README.md`: list the new config for quick conflict-resolution testing.

6) **Add a focused config for validation**
   - Create `configs/conflict-resolution.yml` (or `configs/conflict-resolution-only.yml`)
     that enables a small tool set and runs only this workload via:
     ```yaml
     benchmarks:
       - name: Conversational AI Memory
         enabled: true
         workloads:
           - Conflict Resolution: Overwrite + Reasoning
     ```
   - Turn `metrics.accuracy: true` and choose a lightweight embedding provider if
     embeddings are still used for other steps.
   - Set `output.output_file` to something like `conflict_resolution_results.json`.

7) **Manual validation**
   - Run: `python llmemory run --config conflict-resolution.yml`
   - Confirm the two scored steps show correct `accuracy` / exact-match results.
   - If scenario metrics were added, verify they appear in JSON output and summary.

## Detailed workload specs (ready to copy into benchmarks.py)
These are the concrete workloads (questions + expected answers) we plan to add.
Keep prompts concise and answers strict to minimize variability across tools.

### 1) Conflict Resolution: Overwrite + Reasoning (base)
**Goal:** Latest-fact overwrite + multi-hop reasoning.

```python
Workload(
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
        ),
    ],
)
```

### 2) FactConsolidation-SH (single-hop overwrite)
**Goal:** Latest fact wins on a direct question; include multiple queries after one injection.

```python
Workload(
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
        # inject once, query multiple times (same updated fact, different surface form)
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
        ),
    ],
)
```

### 3) FactConsolidation-MH (multi-hop overwrite)
**Goal:** Use the updated fact as the basis for multi-hop reasoning.

```python
Workload(
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
        ),
    ],
)
```

### 4) LongMemEval-style knowledge update (temporal)
**Goal:** Identify current vs previous values after sequential updates.

```python
Workload(
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
        ),
    ],
)
```

### 5) Interference variant (multiple entities, multiple updates)
**Goal:** Ensure updates do not bleed across entities and latest-fact selection remains correct.

```python
Workload(
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
        ),
    ],
)
```
