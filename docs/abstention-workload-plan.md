# Abstention Workload Implementation Plan

## Goal
Add an "Abstention / Unknown Unknowns" workload that measures whether tools
avoid hallucinating when a memory is missing, and report abstention accuracy
and hallucinated-memory rate.

## References
- `docs/roadmap.md` (Tier 3.2: Abstention / Unknown Unknowns)
- `llmemory_meter/workload.py` (WorkloadStep schema and match_type)
- `llmemory_meter/benchmarks.py` (workload definitions)
- `llmemory_meter/accuracy_evaluator.py` (match_type evaluation)
- `llmemory_meter/metrics.py` (failure-mode counters / aggregation)
- `llmemory_meter/comparator.py` (summary printing / output)

## Plan
1) **Define abstention criteria**
   - Decide on acceptable abstention phrases (e.g., "I don't know", "not provided",
     "no memory", "not available") and whether to allow tool-specific wrappers.
   - Specify expected outputs for "abstention" match_type (exact or keyword-based).

2) **Extend schema and evaluator for abstention**
   - Add/confirm `match_type="abstention"` handling in `WorkloadStep`.
   - Implement `AbstentionEvaluator` or extend existing evaluator logic to score:
     - correct abstention when memory absent
     - incorrect abstention when memory present (if included)

3) **Add abstention workloads**
   - Create a new benchmark suite or add to an existing suite in `benchmarks.py`.
   - Include steps that:
     - store a known fact
     - retrieve a non-existent fact (should abstain)
     - optionally retrieve a known fact (should not abstain)

4) **Add failure-mode metrics**
   - Track hallucinated-memory rate and abstention accuracy in `metrics.py`.
   - Aggregate per tool and per operation type (retrieve/chat).

5) **Wire output + summary**
   - Include abstention metrics in JSON output and `print_summary()`.
   - Call out "hallucinated memory rate" and "abstention accuracy" explicitly.

6) **Document usage**
   - Add a short note in `docs/architecture.md` or `README.md` on the new
     abstention workload and scoring assumptions.

7) **Manual validation**
   - Run with a single-tool config (e.g., `configs/mem0-only.yml`) and verify:
     - abstention steps appear in results
     - metrics are computed and printed
     - false positives (hallucinated answers) are counted
