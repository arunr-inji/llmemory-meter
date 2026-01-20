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
```
Conversational AI:     3,413 tokens
Domain-Specific:      38,092 tokens  (11x growth!)
```

**After Fix** (expected):
```
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
```
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
```
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

*Last Updated: December 11, 2024*
*Version: 0.1.1*
