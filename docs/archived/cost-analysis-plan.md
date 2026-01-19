# Cost Analysis ($/1K ops) Implementation Plan

## Goal
Add cost reporting that translates token usage into dollar costs per operation type
(`store`, `retrieve`, `chat`) and per 1K operations, with totals in JSON output and
console summaries.

## References
- `docs/roadmap.md` (Tier 2: Cost Analysis)
- `docs/architecture.md` (metrics pipeline and config flow)
- `llmemory_meter/workload.py` (token tracking in step results)
- `llmemory_meter/metrics.py` (aggregation and output shaping)
- `llmemory_meter/comparator.py` (summary printing and output structure)
- `llmemory_meter/config_parser/manager.py` (metrics/config schema)
- `llmemory_meter/memory_tools/*.py` (token usage collection per tool)

## Plan
1) **Audit token tracking and model selection**
   - Review each memory tool to confirm where token usage is captured and which model
     is used per operation.
   - Note gaps: tools that only record total tokens, missing input/output splits, or
     tools that do not expose model names.

2) **Extend result schema for cost inputs**
   - Update `StepResult` in `llmemory_meter/workload.py` to carry `input_tokens` and
     `output_tokens` (with `tokens_used` preserved for backwards compatibility).
   - Store model identifiers per step (either on `StepResult.metadata` or a new field)
     so pricing can be mapped to the correct model.

3) **Introduce pricing map and config overrides**
   - Add `llmemory_meter/pricing.py` with a `PRICING` dict (model → input/output $/1M).
   - Add an optional config section (e.g., `pricing` or `metrics.cost_analysis`) to
     allow overrides and to enable/disable cost analysis explicitly.

4) **Populate token splits in tools**
   - Update tool implementations to set `input_tokens` and `output_tokens` where
     API usage details exist (OpenAI, Claude, Letta) and estimate split ratios where
     only totals are known (Mem0, Zep).
   - Ensure each tool attaches the model name used for the request.

5) **Add cost aggregation in metrics**
   - Extend `PerformanceMetrics` in `llmemory_meter/metrics.py` with cost fields:
     total cost, avg cost/op, and cost per 1K ops overall and per action.
   - For each action, compute:
     - total cost from token counts + pricing
     - cost per op and cost per 1K ops
   - Guard gracefully if pricing is missing or tokens are unavailable.

6) **Update output and summary formatting**
   - Include cost fields in JSON output (overall and per-operation).
   - Add cost lines to `MemoryComparator.print_summary()` with clear labels like
     `Cost/1K ops (store/retrieve/chat)` and `Total cost`.

7) **Document assumptions and usage**
   - Add a short note in `docs/architecture.md` or `README.md` on how pricing is
     computed, how to override pricing, and that estimates may be used when
     input/output splits are unavailable.

8) **Manual validation**
   - Run a quick benchmark (`configs/quick-test.yml`) and verify:
     - costs appear in JSON output
     - costs appear in console summary
     - missing pricing models are reported clearly (or skipped).

