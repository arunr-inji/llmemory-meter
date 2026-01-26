# Known Issues and Limitations

## Performance & Reliability

### Claude Memory: Rate Limiting Under Stress (Issue #1)

**Status**: ⚠️ Known Limitation

**Description**: Claude Memory shows 97.2% overall success rate due to failures under high-volume stress testing.

**Details**:

- **Observed**: 3 consecutive failures (steps 25-27) in Memory Capacity Test (50 rapid stores)
- **All benchmarks**: 100% success in normal conversational workloads
- **Stress test only**: 94.5% success (52/55 operations)
- **Root cause**: Likely API rate limiting during burst operations

**Impact**:

- ✅ Reliable for normal conversational use cases
- ⚠️ May hit rate limits with >20 rapid operations
- ❌ Not ideal for high-volume batch processing

**Recommendation**: For production, implement rate limiting/backoff or use OpenAI/Mem0 for bulk operations.

---

### MemGPT: Token Usage Growth (Issue #2)

**Status**: ✅ Fixed (v0.1.1)

**Description**: MemGPT token usage grew 11x across benchmarks (3.4K → 38K) due to context accumulation.

**Root Cause**: Same agent was reused across all benchmarks, accumulating conversation history.

**Fix Applied**: Each benchmark run now creates a unique agent (user_id with timestamp).

**Before Fix**:

```text
Conversational AI:     3,413 tokens
Domain-Specific:      38,092 tokens  (11x growth!)
```

**After Fix** (expected):

```text
All benchmarks:    ~3,000-5,000 tokens (consistent)
```

---

### Zep: Artificial Processing Delays (Issue #4)

**Status**: ⚠️ By Design

**Description**: Zep includes 8-second delays for knowledge graph processing, inflating latency.

**Details**:

- `asyncio.sleep(8)` after store/chat operations
- Ensures graph processing completes before next operation
- Real API latency is ~0.3-1.5s

**Measured Impact**:

```text
Without delays (estimated):  ~1.5s avg
With delays (actual):        ~6.3s avg  (4x higher)
```

**Recommendation**:

- For benchmarking: Note that latency includes graph processing time
- For production: Consider async graph processing to hide latency

---

### Mem0: Token Accounting + Result Parsing Inconsistencies (Issue #5)

**Status**: ⚠️ Known Limitation

**Description**: Mem0 tool token usage and result handling can be inconsistent with actual responses.

**Details**:

- `execute_step` overwrites `_last_tokens` for store/retrieve, discarding the more complete estimates from `store_memory`/`retrieve_memory`
- `retrieve_memory` ignores non-dict result items, which can lead to "No memories found" even when results exist
- `chat` uses the raw `len(memories)` count even when no memory text is extracted, producing misleading response text
- `_sync_search` accepts `metadata` but does not pass it into `Memory.search`, so metadata filtering is ignored

**Impact**:

- ⚠️ Underreported `tokens_used` in `StepResult`
- ⚠️ Potential false negatives in retrieval results
- ⚠️ Misleading chat response context count

**Recommendation**: Align token accounting to a single source of truth and normalize result parsing across dict/list responses.

---

## Data Format Issues

### JSON Serialization (Issue #3)

**Status**: ✅ Fixed (v0.1.1)

**Description**: Benchmark results were stored as string representations instead of structured JSON.

**Before**:

```json
{
  "workload_results": {
    "mem0": "WorkloadResult(tool_name='mem0', ...)"
  }
}
```

**After**:

```json
{
  "workload_results": {
    "mem0": {
      "tool_name": "mem0",
      "step_results": [...]
    }
  }
}
```

**Impact**: Results are now programmatically parseable without regex.

---

## General Limitations

### Cost Analysis: Missing Model Metadata

Cost estimation is skipped when a step has token usage but no model identifier.

**Impact**: Some tools may report tokens without a model, resulting in missing cost metrics.

**Recommendation**: When a model isn't specified in config, attempt to infer it from API responses and attach it to `StepResult`.

### Cost Analysis: Estimated Tokens for Mem0/Zep

Mem0 and Zep currently estimate token usage (no API usage fields are exposed), and may apply overhead multipliers.

**Impact**: Cost comparisons can be skewed relative to tools that return exact token usage.

**Recommendation**: Use `token_overhead_ratio` to tune/disable overhead and treat estimates as approximate.

### Pricing Coverage Gaps

The default pricing map does not include some commonly used models (e.g., GPT-4o variants, Claude 3 Opus/Sonnet, Gemini).

**Impact**: Cost coverage may be incomplete out of the box for these models.

**Recommendation**: Add pricing for commonly used models or override pricing in config.

### Token Split Ratios Are Global Defaults

Default input ratios (store=0.7, retrieve=0.4, chat=0.5) are global and may not match tool-specific patterns.

**Impact**: Estimated cost splits can be off for some tools.

**Recommendation**: Support per-tool ratio overrides in config (e.g., under each tool's settings).

### Repeated Missing-Model Warnings

Missing model warnings can repeat once per step for tools without a model identifier.

**Impact**: Console output can become noisy for large workloads.

**Recommendation**: Track warned models in a set and warn once per unique model.

### Terminal Summary Aggregation

The final terminal summary aggregates success rates across all benchmarks, which can hide individual benchmark failures.

**Example**:

```text
Terminal: "claude_memory: 100.0% success"
Reality:  97.2% (3 failures in Memory Capacity Test)
```

**Recommendation**: Always review per-benchmark output or JSON results for detailed analysis.

### Synthetic Benchmarks

Current benchmarks are **inspired by** MSC/PersonaChat but are **not** the actual academic datasets.

**For academic publication**:

- Clearly state benchmarks are synthetic
- Position as "tool contribution + comparative study"
- Note Phase 2B plan for standard benchmark support

---

## Fixed Issues

### Zep: Knowledge Graph Accumulation

**Fixed in**: v0.1.0  
**Issue**: Same user across runs led to 22x context growth  
**Fix**: Unique user_id per run

### Mem0: SQLite Threading Issues

**Fixed in**: v0.1.0  
**Issue**: Concurrent access to default SQLite storage  
**Fix**: Create new Memory() instances per operation

---

## Schema & Reporting Issues

### Workload Metadata Schema Is Inconsistent (Issue #6)

**Status**: ⚠️ Known Limitation

**Description**: `WorkloadStep.metadata` is an unstructured dict with no required keys.
Conflict-resolution workloads use `scenario`/`metric` keys, while other workloads
use unrelated keys like `type`, `session`, `expected`, etc. Store steps often have
no scenario/metric tags at all.

**Details**:

- `WorkloadStep.metadata` is typed as `Optional[Dict[str, Any]]` in `llmemory_meter/workload.py`.
- Scenario metrics aggregation in `llmemory_meter/metrics.py` only looks for
  `metadata["scenario"]` and `metadata["metric"]` when `accuracy` is present.
- Store steps never have `accuracy` and typically lack `scenario`/`metric`, so they
  are excluded from scenario metrics by design.

**Impact**:

- Inconsistent metadata schema makes it harder to build general-purpose analysis tools.
- Scenario metrics only reflect tagged retrieve/chat steps; missing or malformed metadata
  silently drops from aggregation.

**Recommendation**:

- Define a dedicated metadata dataclass (required + optional fields) and standardize keys.
- At minimum, document the schema in `llmemory_meter/workload.py` or `docs/architecture.md`.
- Consider adding explicit `scenario` tags to existing workloads for consistent filtering.

---

## Configuration Issues

### Legacy `general.concurrent` Key in Configs (Issue #7)

**Status**: ✅ Fixed (2026-01-26)

**Description**: Several configs used `general.concurrent`, but the code reads
`general.concurrent_tools` (`llmemory_meter/comparator.py`) and the default config
in `llmemory_meter/config_parser/manager.py` uses `concurrent_tools`.

**Impact**:

- `general.concurrent` was ignored, defaulting to `concurrent_tools=True`,
  causing unintended parallel execution for those configs.

**Fix Applied**:

- Updated configs to use `general.concurrent_tools` consistently:
  `configs/mem0-only.yml`, `configs/openai-only.yml`, `configs/claude-only.yml`,
  `configs/zep-only.yml`, `configs/memgpt-only.yml`, `configs/memgpt-quick-test.yml`.

---

## Repository Hygiene

### Example/Test Scripts Need Pruning (Issue #8)

**Status**: ⚠️ Backlog

**Description**: The repo includes multiple demo/test scripts that overlap in purpose
and add noise (`benchmark_demo.py`, `benchmark_example.py`, `simple_example.py`, etc.).

**Impact**:

- Harder to determine the canonical entrypoint for users.
- Increases maintenance burden and confusion for benchmarking workflows.

**Recommendation**:

- Archive deprecated examples under `docs/archived/` or `examples/archived/`.
- Keep a single, documented demo path in `README.md` and remove redundant scripts.

---

_Last Updated: January 26, 2026_
_Version: 0.1.1_
