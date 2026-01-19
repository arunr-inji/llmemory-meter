# LLMemoryMeter Feature Roadmap

## Objective Alignment
Your two objectives:
1. **Extensible benchmark harness** - plugin benchmarks, bring-your-own tools, or both
2. **Comprehensive practitioner guide** - no such comparison exists; fill this gap

---

## Prioritized Feature Roadmap

### Tier 1: High ROI / Publication-Critical (Do First)

#### 1.1 Add Baseline Tools Practitioners Actually Use
**Priority: CRITICAL | Effort: Medium | Impact: Very High**

Currently you only compare "memory products." Add baselines so practitioners can map results to what they do today:

| Baseline | Description | Implementation Complexity | Status |
|----------|-------------|--------------------------|---------|
| **No-Memory** | Only last-k messages, discard rest | Trivial - mock store/retrieve | ✅ Complete |
| **Full-Context** | Stuff everything into prompt until limit | Simple - list storage, no retrieval | ✅ Complete |
| **Summarize-then-Append** | Rolling LLM summary + recent turns | Medium - LLM call on store | 📋 Planned |
| **RAG** | Vector store retrieval of prior turns | Medium - local embeddings + chromadb | 📋 Planned |
| **Hybrid** | Summary + retrieval | Medium - combines above | 📋 Planned |

**Why critical:** Without baselines, readers can't answer "is Mem0 better than just stuffing context?" This makes your framework useful to teams who won't buy a SaaS memory layer.

**Files to modify:**
- Create `memory_tools/baseline_tools.py` (NoMemoryTool, FullContextTool, SummarizeTool, RAGTool)
- Add tool registration in `comparator.py:_get_tool_instance()` (~line 31-42)
- Add config entries in `configs/*.yml`

---

#### 1.2 Separate Write vs Read Cost Reporting
**Priority: HIGH | Effort: Low | Impact: High**

You already have raw data; just need to report it separately:

```
store_latency_ms, retrieve_latency_ms, chat_latency_ms
store_tokens, retrieve_tokens, chat_tokens
p95/p99 by operation type
```

**Why important:** Different agent architectures have different read/write patterns:
- Planners: write-heavy
- Customer support: read-heavy
- Coding agents: both

**Files to modify:**
- `workload.py` - add operation-specific fields to PerformanceMetrics
- `metrics.py` - aggregate by action type in MetricsCalculator
- `comparator.py:print_summary()` - display breakdown
- Output JSON structure update

---

#### 1.3 Upgrade Scorer to Handle Exact Match + LLM-as-Judge
**Priority: HIGH | Effort: Medium | Impact: High**

Embedding similarity is vulnerable to:
- Longer answers looking "more similar"
- Numeric/key-value answers being underweighted
- Can't measure abstention quality

Add two evaluation modes:

1. **Exact Match Mode** - for "needle" tasks
   ```python
   # If expected is "ALPHA-7749-BETA", check exact/regex match
   WorkloadStep(ground_truth="ALPHA-7749-BETA", match_type="exact")
   ```

2. **LLM-as-Judge Mode** - for open-ended tasks
   ```python
   # Bounded rubric (0/1/2) with structured judging prompt
   WorkloadStep(ground_truth="User prefers hiking", match_type="llm_judge", rubric="...")
   ```

**Why important:** LongMemEval explicitly includes abstention and knowledge updates as core abilities that need discrete scoring, not embeddings.

**Files to modify:**
- `workload.py` - add `match_type` field to WorkloadStep
- `accuracy_evaluator.py` - add ExactMatchEvaluator, LLMJudgeEvaluator
- `benchmarks.py` - annotate steps with appropriate match_type

---

#### 1.4 Add Failure Mode Metrics (Your Differentiator)
**Priority: HIGH | Effort: Medium | Impact: Very High**

Beyond average accuracy, measure:

| Metric | Description | How to Detect |
|--------|-------------|---------------|
| **Hallucinated memory rate** | Mentions a fact never stored | Compare response entities to stored facts |
| **Stale memory rate** | Returns outdated value after update | Track updates, check which version returned |
| **Cross-entity contamination** | Mixes two users/items | Multi-session isolation tests |
| **Abstention quality** | Says "I don't know" appropriately | Explicit abstention workloads |

**Why important:** MemoryAgentBench emphasizes conflict resolution + update as distinct competency. This makes your suite feel "current" vs modern research AND more useful to builders.

**Files to modify:**
- `metrics.py` - add failure mode counters to PerformanceMetrics
- `accuracy_evaluator.py` - add FailureModeAnalyzer class
- `benchmarks.py` - add workloads that specifically trigger failure modes

---

### Tier 2: Publication-Ready (Strengthens Credibility)

#### 2.1 Add Scale Sweeps (Turn One Datapoint Into a Curve)
**Priority: MEDIUM-HIGH | Effort: Medium | Impact: High**

Current stress test: one "50-entry" run. Make it parameterized:

```yaml
scale_sweep:
  memory_items: [10, 50, 200, 1000]
  retrieval_queries_pct: [5, 10, 20]
  similarity_distractors: [true, false]
```

Plot:
- Accuracy vs N
- p95 store latency vs N
- p95 retrieve latency vs N
- tokens/query vs N

**Why important:** Curves are much more publishable than single numbers. Shows degradation characteristics.

**Files to modify:**
- `benchmarks.py` - parameterized stress test generator
- `cli.py` - `--scale-sweep` flag
- New output format for sweep results

---

#### 2.2 Statistical Rigor (Multiple Runs + Confidence Intervals)
**Priority: MEDIUM-HIGH | Effort: Low | Impact: Medium**

Current: 1 run per benchmark. Need:
- N≥5 runs with variance/std dev
- Bootstrap confidence intervals
- Paired t-tests for rankings

**Files to modify:**
- `cli.py` - add `--runs N` parameter
- `metrics.py` - calculate std dev, CI in MetricsCalculator
- `comparator.py` - run loop with aggregation

---

#### 2.3 Report Experimental Conditions
**Priority: MEDIUM | Effort: Low | Impact: Medium**

Add to output for reproducibility:
- Region/network (local vs hosted)
- Cold-start vs warmed-up
- Tool versions/commit hashes
- Vector DB config + persistence
- Concurrency settings

**Files to modify:**
- `comparator.py` - collect system info at start
- Output JSON structure

---

#### 2.4 Cost Analysis ($/1K Operations)
**Priority: MEDIUM | Effort: Low | Impact: High**

Track tokens → translate to actual dollar costs:

```python
# pricing.py
PRICING = {
    "gpt-4o-mini": {"input": 0.15/1M, "output": 0.60/1M},
    "gpt-4o": {"input": 2.50/1M, "output": 10.00/1M},
    "claude-3-5-sonnet": {"input": 3.00/1M, "output": 15.00/1M},
}
```

Report: cost per store, cost per retrieve, cost per chat, total cost.

**Files to modify:**
- Create `llmemory_meter/pricing.py`
- `metrics.py` - add cost calculations
- Output reports

---

### Tier 3: New Benchmark Workloads (Research Alignment)

These align with MemoryAgentBench, LongMemEval, and modern research:

#### 3.1 Conflict Resolution with Overwrite + Reasoning
```python
# Does the system use the *latest* fact and reason with it?
WorkloadStep(action="store", content="Alice's manager is Bob.")
WorkloadStep(action="store", content="Update: Alice's manager is Carol.")
WorkloadStep(action="store", content="Carol reports to Dave.")
WorkloadStep(action="retrieve", content="Who is Alice's manager?", ground_truth="Carol")
WorkloadStep(action="chat", content="Who is Alice's manager's boss?", ground_truth="Dave")
```
**Metrics:** overwrite correctness, multi-hop reasoning after update

---

#### 3.2 Abstention / Unknown Unknowns
```python
# Does the tool hallucinate when no memory exists?
WorkloadStep(action="store", content="User's favorite color is blue")
WorkloadStep(action="retrieve", content="What's my passport number?",
             ground_truth="not provided", match_type="abstention")
```
**Metrics:** hallucinated-memory rate, abstention accuracy

---

#### 3.3 Similarity Distractor Retrieval
```python
# Can it pick the right memory among near-duplicates?
# Store 20 similar orders, retrieve specific one
WorkloadStep(action="store", content="Order #12345: delayed laptop, $50 comp")
WorkloadStep(action="store", content="Order #12346: delayed laptop, $75 comp")
# ...
WorkloadStep(action="retrieve", content="What compensation for order #12346?",
             ground_truth="$75")
```
**Metrics:** exact match on order ID + compensation, retrieval precision@k

---

#### 3.4 Temporal Reasoning
```python
# Remember sequence, answer "current vs previous"
WorkloadStep(action="store", content="I moved to Austin in 2021.")
WorkloadStep(action="store", content="In 2024 I moved to Boston.")
WorkloadStep(action="retrieve", content="Where do I live now?", ground_truth="Boston")
WorkloadStep(action="retrieve", content="Where did I live before Boston?", ground_truth="Austin")
```
**Metrics:** temporal ordering accuracy, recency vs history distinction

---

#### 3.5 Multi-Session Interleaving (Isolation Test)
```python
# Two interleaved sessions - no cross-contamination
# Session A stores preferences, Session B stores different ones
# Retrieve A-specific, then B-specific
```
**Metrics:** cross-session contamination rate, isolation score

---

#### 3.6 Tool-Output Memory (Agentic Workflow)
```python
# Store tool outputs, reuse later
WorkloadStep(action="store", content="API response: user_id=X, plan=pro, quota=300")
WorkloadStep(action="store", content="Billing note: 15% discount until Feb")
WorkloadStep(action="chat", content="What will customer be charged next renewal?",
             ground_truth="...", match_type="llm_judge")
```
**Metrics:** exact match on numbers/dates, reasoning correctness

---

### Tier 4: Context Management Solutions to Add

Beyond Zep/Mem0/MemGPT, benchmark architectures practitioners actually ship:

| Solution | Type | Why Include |
|----------|------|-------------|
| **LangMem** | Memory framework | LangChain ecosystem, extraction + consolidation |
| **LlamaIndex Memory** | Memory blocks | Popular framework, fact extraction + vector blocks |
| **Contextual Compression** | Retriever | Compress retrieved docs before injection |
| **LLMLingua** | Prompt compression | Microsoft, shrink prompts without forgetting |
| **OpenAI Prompt Caching** | Provider feature | Affects cost/latency, not memory |
| **Claude Prompt Caching** | Provider feature | Affects cost/latency, not memory |

---

## Implementation Priority Order

### 🎯 MVP Sprint (2-4 Weeks) - Publishable State

**Week 1-2: Core Infrastructure**
| # | Feature | Effort | Why First |
|---|---------|--------|-----------|
| 1 | **Exact Match Scoring** | Low | Unblocks needle tasks, minimal code |
| 2 | **Read/Write Cost Separation** | Low | Already have data, just report it |
| 3 | **No-Memory Baseline** | Low | Trivial implementation, huge value |
| 4 | **Full-Context Baseline** | Low | Simple list storage, no retrieval |

**Week 2-3: Core Workloads**
| # | Feature | Effort | Why Now |
|---|---------|--------|---------|
| 5 | **Conflict Resolution Workload** | Medium | Aligns with MemoryAgentBench |
| 6 | **Abstention Workload** | Medium | Aligns with LongMemEval |
| 7 | **Temporal Reasoning Workload** | Medium | Core research competency |

**Week 3-4: Polish**
| # | Feature | Effort | Why Now |
|---|---------|--------|---------|
| 8 | **Cost Analysis ($/1K ops)** | Low | Practitioners care most about this |
| 9 | **RAG Baseline** | Medium | Most common production pattern |
| 10 | **Summarize-then-Append Baseline** | Medium | Cost-conscious deployments |

---

### Phase 2: Differentiation (Month 2)
| # | Feature | Effort | Impact |
|---|---------|--------|--------|
| 11 | **Failure Mode Metrics** | Medium | Your paper's differentiator |
| 12 | **Similarity Distractor Workload** | Medium | Precision under interference |
| 13 | **Multi-Session Isolation Workload** | Medium | Cross-entity contamination |
| 14 | **Hybrid Baseline** (summary + retrieval) | Medium | Common real-world pattern |

### Phase 3: Statistical Rigor (Month 2-3)
| # | Feature | Effort | Impact |
|---|---------|--------|--------|
| 15 | **Multiple Runs + CI** | Low | Required for peer review |
| 16 | **Scale Sweeps** | Medium | Curves > single numbers |
| 17 | **Experimental Conditions** | Low | Reproducibility |

### Phase 4: Expanded Coverage (Month 3+)
| # | Feature | Effort | Impact |
|---|---------|--------|--------|
| 18 | **LLM-as-Judge Scoring** | Medium | Open-ended task accuracy |
| 19 | **Tool-Output Memory Workload** | Medium | Agentic workflow realism |
| 20 | **LangMem/LlamaIndex Tools** | High | Framework coverage |
| 21 | **Prompt Compression (LLMLingua)** | High | Context optimization |

---

## MVP Deliverables (2-4 Weeks)

By end of Week 4, you'll have:

✅ **4 baseline tools**: No-Memory, Full-Context, RAG, Summarize-then-Append
✅ **Read/write cost separation**: store vs retrieve vs chat latency/tokens
✅ **Exact-match scoring**: For needle tasks alongside embedding similarity
✅ **3 new workloads**: Conflict resolution, Abstention, Temporal reasoning
✅ **Cost analysis**: $/1K operations per tool

This gives you:
- **Framework + methodology** (main contribution)
- **Initial results** (clearly labeled preliminary)
- **Actionable guidance** (write vs read, cost breakdowns)
- **Research alignment** (MemoryAgentBench/LongMemEval competencies)
- **Practitioner value** (baselines they can compare against)

---

## Files Summary

| Feature | Files to Create/Modify |
|---------|----------------------|
| Baseline tools | `memory_tools/baseline_tools.py`, `comparator.py`, `configs/*.yml` |
| Read/write separation | `workload.py`, `metrics.py`, `comparator.py` |
| Exact match scorer | `workload.py`, `accuracy_evaluator.py` |
| LLM-as-judge | `accuracy_evaluator.py`, `benchmarks.py` |
| Failure modes | `metrics.py`, `accuracy_evaluator.py` |
| Scale sweeps | `benchmarks.py`, `cli.py` |
| Cost analysis | `pricing.py` (new), `metrics.py` |
| New workloads | `benchmarks.py` |
| Statistical rigor | `cli.py`, `metrics.py`, `comparator.py` |
