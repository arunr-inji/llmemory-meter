# Plan: Read/Write Cost Separation (Roadmap 1.2)

Goal: separate store vs retrieve vs chat latency/token reporting while keeping overall metrics intact.

1) Audit current metrics data flow
- Confirm where `StepResult.action`, `latency_ms`, and `tokens_used` are produced and consumed.
- Validate that actions map cleanly to store/retrieve/chat for aggregation.

2) Define per-action metrics schema
- Add an `operation_metrics` section with per-action stats:
  - `avg_latency_ms`, `p95_latency_ms`, `p99_latency_ms`
  - `total_tokens`, `avg_tokens_per_query`
  - `success_rate`, `total_queries`
- Keep existing overall metrics for backward compatibility.

3) Implement per-action aggregation
- Update `MetricsCalculator` to compute grouped metrics by `StepResult.action`.
- Ensure missing actions are omitted or reported as empty safely.

4) Update JSON output structure
- Include `operation_metrics` in the overall metrics payload.
- Preserve existing JSON fields and names.

5) Update console summary display
- Extend `print_summary()` to show store/retrieve/chat breakdowns under each tool.

6) Validate via quick test
- Run `python llmemory run --config quick-test` and confirm per-action totals align with step counts.
