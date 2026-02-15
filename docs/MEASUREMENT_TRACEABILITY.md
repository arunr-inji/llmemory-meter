# Measurement Traceability

This document maps each published metric to raw inputs, transformation code, and validation checks.

| Metric | Raw Source Fields | Transformation Code | Recompute Rule | Tolerance | Failure Action |
|---|---|---|---|---|---|
| `success_rate` | `step_results[].success` | `llmemory_meter/metrics.py:108` | `successful_steps / total_steps` (as percent in output) | exact after rounding | Block run, emit reconciliation mismatch |
| `avg_latency_ms` | `step_results[].latency_ms` | `llmemory_meter/metrics.py:108` | arithmetic mean of all latencies | exact after rounding | Block run, emit reconciliation mismatch |
| `p95_latency_ms` | sorted `step_results[].latency_ms` | `llmemory_meter/metrics.py:150` | `sorted[int(0.95*N)]` clamped | exact | Block run, emit reconciliation mismatch |
| `p99_latency_ms` | sorted `step_results[].latency_ms` | `llmemory_meter/metrics.py:151` | `sorted[int(0.99*N)]` clamped | exact | Block run, emit reconciliation mismatch |
| `total_tokens` | `step_results[].tokens_used` | `llmemory_meter/metrics.py:108` | sum of non-null token counts | exact | Block run, emit reconciliation mismatch |
| `avg_tokens_per_query` | `step_results[].tokens_used` | `llmemory_meter/metrics.py:150` | mean of non-null token counts | exact after rounding | Block run, emit reconciliation mismatch |
| `total_cost_usd` | `input_tokens/output_tokens/tokens_used/model` | `llmemory_meter/metrics.py:193`, `llmemory_meter/pricing.py` | sum per-step cost for priced models | exact after rounding | Block run, emit reconciliation mismatch |
| `avg_cost_per_query_usd` | cost + priced query count | `llmemory_meter/metrics.py:203` | `total_cost / cost_priced_queries` | exact after rounding | Block run, emit reconciliation mismatch |
| `cost_per_1k_ops_usd` | average cost per query | `llmemory_meter/metrics.py:204` | `avg_cost_per_query * 1000` | exact after rounding | Block run, emit reconciliation mismatch |
| LongMemEval judged accuracy | eval logs `.eval-results-*` | `llmemory_meter/hybrid_evaluator.py:198` | labels mean from official eval output | exact | Block publication, inspect judge/eval artifact |
| LongMemEval per-question-type | eval logs + reference JSON | `llmemory_meter/hybrid_evaluator.py:210` | grouped label means by type | exact | Block publication, inspect eval join |
| MemBench primary accuracy (`accuracy`) | hypothesis JSONL + question/choices + model response | `scripts/membench_llm_eval.py` | MCQ label match after deterministic parsing + LLM adjudication | exact | Block publication, inspect row-level eval + judge cache |
| MemBench MCQ-only accuracy (`accuracy_mcq`) | same as above | `scripts/membench_llm_eval.py` | label match on MCQ-scored rows | exact | Block publication, inspect category-specific failures |
| MemBench adjudication rate | same as above | `scripts/membench_llm_eval.py` | `scored_llm_count / scored_mcq_count` | exact | Flag high-judge dependence for review |
| MemBench deterministic `accuracy_contains` | hypothesis JSONL with ground truth | `scripts/membench_eval.py` or `scripts/membench_llm_eval.py` | normalized substring match ratio on scored rows | exact | Diagnostic only; do not publish as headline metric |
| MemBench deterministic `accuracy_exact` | hypothesis JSONL with ground truth | `scripts/membench_eval.py` or `scripts/membench_llm_eval.py` | normalized exact-match ratio on scored rows | exact | Diagnostic only; do not publish as headline metric |

## Gate

- `scripts/check_metrics_reconciliation.py` enforces raw-to-reported consistency.
- `scripts/check_metric_fixtures.py` enforces deterministic behavior on edge cases.
- `scripts/membench_llm_eval.py` enforces MemBench MCQ adjudication with cached LLM decisions.
