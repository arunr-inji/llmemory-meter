# Abstention Workload Implementation Plan

## Goal

Add an "Abstention / Unknown Unknowns" workload and scoring pipeline that measures whether tools avoid hallucinating when a memory is missing. Report abstention accuracy, hallucinated-memory rate, and over-abstention rate (abstaining when memory exists).

## Scope (and non-goals)

- In scope: new workload(s) in `llmemory_meter/benchmarks.py`, abstention evaluator, failure-mode metrics, output/reporting updates, config/docs updates, manual validation.
- Out of scope: LLM-as-judge scoring, new baselines, tool behavior changes, or embedding model tuning.

## Definitions

- **Abstention:** Response explicitly indicates the requested fact is unknown / not in memory (e.g., "I don't know", "no memories found").
- **Hallucinated memory:** Non-abstaining response when memory is missing (i.e., provides a specific value anyway).
- **Over-abstention:** Abstains when memory exists and should be retrieved.

## Workload design (benchmarks.py)

**Target file:** `llmemory_meter/benchmarks.py` (add to `technical_performance_suite()` or create a new "Failure Modes" suite).

### Proposed workload: "Abstention / Unknown Unknowns"

- Keep the workload compact (6-8 steps) and include both `retrieve` and `chat`.
- Use prompts that explicitly instruct abstention to minimize LLM guessing.
- Include at least one distractor query to catch cross-attribute leakage.

### Example step sequence

1. `store`: "Favorite color is blue."
2. `store`: "Pet is a golden retriever named Max."
3. `retrieve` (unknown): "What is my passport number? If it isn't stored, say you don't know."
   - `match_type="abstention"`
   - `metadata`: `{"scenario": "abstention", "abstention_expected": True, "metric": "abstention_accuracy"}`
4. `retrieve` (known): "What is my favorite color? Return only the color."
   - `match_type="exact_case_insensitive"`
   - `metadata`: `{"scenario": "abstention", "abstention_expected": False, "metric": "over_abstention_rate"}`
5. `store`: "Driver license number is D-123-456." (distractor)
6. `retrieve` (unknown): "What is my passport number? If it isn't stored, say you don't know."
   - `match_type="abstention"` + `abstention_expected: True`
7. `chat` (unknown): "Do you remember my bank routing number? If not stored, say you don't know."
   - `match_type="abstention"` + `abstention_expected: True`
8. `chat` (known): "What's my pet's name? Return only the name."
   - `match_type="exact_case_insensitive"` + `abstention_expected: False`

### Notes

- Use `match_type="abstention"` for unknowns and exact/contains for knowns.
- Include `metadata` flags so metrics can be computed from `StepResult` alone.
- If adding a new suite, update `StandardBenchmarks.get_all_suites()` and `BenchmarkRunner` info accordingly.

## Abstention evaluation (accuracy_evaluator.py + comparator.py)

**Target files:** `llmemory_meter/accuracy_evaluator.py`, `llmemory_meter/comparator.py`, `llmemory_meter/workload.py`

### Schema updates

- Extend `WorkloadStep.match_type` docstring to include `"abstention"`.

### Evaluator design

- Add `AbstentionEvaluator` (new class or helper):
  - Input: cleaned response string + optional override phrases from `metadata` or `ground_truth`.
  - Default phrase/regex list (case-insensitive, word-boundary where possible):
    - "I don't know", "I do not know", "I'm not sure"
    - "no memory", "no memories", "no messages stored"
    - "no relevant memories found", "no memories found"
    - "not provided", "not available", "not in memory"
    - "cannot find", "can't find", "unknown"
  - Avoid overly broad matches (e.g., skip bare "none").
  - Empty response or failed step should score as non-abstention (0.0) and be excluded from denominators (see metrics section).

### Integration in comparator

- Update `MemoryComparator._evaluate_accuracy()`:
  - Add a branch for `match_type="abstention"`.
  - Use `_strip_formatting_prefix()` before detection (ensure stripping doesn’t remove abstention cues; adjust patterns if needed).
  - Write results to `step_result.accuracy_by_provider["abstention"] = 1.0/0.0`.
  - Optionally set `step_result.accuracy` to abstention score for these steps (decide if this should affect overall avg accuracy).
  - Store `step_result.metadata["abstention_detected"] = bool` for downstream metrics.

## Metrics & aggregation (metrics.py)

**Target files:** `llmemory_meter/metrics.py`, `llmemory_meter/config_parser/manager.py`, `llmemory_meter/comparator.py`

### New metrics block

- Add `failure_mode_metrics` to `PerformanceMetrics`:
  - `abstention_accuracy`
  - `hallucinated_memory_rate` (1 - abstention_accuracy)
  - `over_abstention_rate` (abstained when abstention_expected is False)
  - Optional counts: expected/total, correct, over_abstentions
  - Optional per-action breakdown (`retrieve`, `chat`)

### Computation

- Use `step_result.metadata["abstention_expected"]` and `step_result.metadata["abstention_detected"]`.
- Exclude failed steps (`success == False`) from denominators.
- If no applicable steps, leave metrics unset to avoid misleading 0/0.

### Config toggle

- Add `metrics.failure_modes: bool` to `MetricsConfig` so abstention evaluation can run without embedding-based accuracy.
- In `MemoryComparator.run_workload_on_tool()`, call abstention evaluation when `failure_modes` is enabled (even if `accuracy` is false).
- Update `configs/*.yml` as needed to enable this in targeted runs.

## Output & summary

- Include `failure_mode_metrics` in `PerformanceMetrics.to_dict()` so JSON output contains abstention rates.
- Update `MemoryComparator.print_summary()` to show:
  - Abstention accuracy
  - Hallucinated-memory rate
  - Over-abstention rate
- Keep scenario metrics (`scenario_metrics`) available for drill-down if desired.

## Config & docs updates

- Add a focused config (e.g., `configs/abstention-only.yml`) that runs only the abstention workload and enables `metrics.failure_modes`.
- Update `docs/architecture.md`:
  - Add `AbstentionEvaluator` in Evaluators section.
  - Add failure-mode metrics in Results section.
- Update `docs/roadmap.md` (optional) to mark abstention workload as in-progress/implemented when done.

## Manual validation checklist

- Run `./run_overnight.sh configs/abstention-only.yml` (or add workload filter to an existing config).
- Confirm:
  - Step results include `abstention_expected` + `abstention_detected` in metadata.
  - `failure_mode_metrics` appears in JSON and summary output.
  - Tools with empty memory produce abstention, not hallucinated content.
  - Over-abstention is counted on known-memory steps.

## Open questions / decisions

- Final abstention phrase list and strictness (e.g., require explicit "I don't know" vs. allow "no memory").
- Whether to include an unprompted variant (no abstention instruction) to assess baseline hallucination.
- Should abstention scores contribute to overall `avg_accuracy`, or be reported only in `failure_mode_metrics`?
