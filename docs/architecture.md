# LLMemoryMeter Architecture Documentation

## Overview

LLMemoryMeter is a plug-and-play benchmarking harness for comparing AI memory systems. The architecture follows a clean flow:

```
Config (YAML) → CLI → MemoryComparator → MemoryTools → Results
                                ↓
                          Benchmarks/Workloads
                                ↓
                           Evaluators
```

**Core Design Principles:**
- **Two-phase evaluation**: Performance measured first, accuracy evaluated post-hoc
- **Tool isolation**: Each tool gets unique user_id, memory cleared between workloads
- **Plug-and-play**: Tools, benchmarks, and evaluators are modular and extensible
- **Sequential by default**: `concurrent_tools: false` prevents resource exhaustion

---

## Configuration System

**Location:** `configs/*.yml`

**How benchmarks start from config:**
1. User runs: `python llmemory run --config starter.yml`
2. CLI loads YAML via `ConfigManager.load_config()` (`config_parser/manager.py:168`)
3. Auto-resolves paths (tries `configs/` if file not found directly)
4. Converts to `LLMemoryMeterConfig` dataclass with validation
5. Passes config to `MemoryComparator` for execution

### Config Structure: Five Sections

#### 1. `memory_tools` - Which AI memory systems to test

```yaml
memory_tools:
- name: mem0                    # Tool identifier (mem0|openai_memory|memgpt|claude_memory|zep)
  enabled: true                 # Toggle this tool on/off
  api_key_env: MEM0_API_KEY    # Environment variable containing API key
  model: gpt-4o-mini           # LLM model to use
  settings:                    # Tool-specific configuration
    llm_provider: openai
    vector_store:
      provider: qdrant
      host: localhost
      port: 6333
```

**What it tunes:**
- Which memory systems to benchmark (enable/disable tools)
- Which LLM models each tool uses (affects cost, latency, quality)
- Tool-specific settings (vector stores, API configurations)
- API key sources (environment variables for security)

**How it maps to execution:**
- Parsed at `config_parser/manager.py:196-199` → `MemoryToolConfig` dataclass
- Tool instances created at `comparator.py:27-50` via `_get_tool_instance()` factory
- Each tool gets its own config dict: `self.config.get(tool_name, {})`

#### 2. `benchmarks` - Which test suites to run

```yaml
benchmarks:
- name: Conversational AI Memory
  enabled: true
  settings: null  # Reserved for future per-benchmark tuning
```

**What it tunes:**
- Which benchmark suites to execute (6 available: conversational, long context, persona, technical, stress, domain-specific)
- Test coverage scope (quick smoke test vs comprehensive suite)

**How it maps to execution:**
- Parsed at `config_parser/manager.py:202-204` → `BenchmarkConfig` dataclass
- Matched to suite definitions in `benchmarks.py` via `StandardBenchmarks.get_all_suites()`
- Suite workloads executed via `comparator.run_benchmark_suite()` at line 497-524

#### 3. `metrics` - What to measure

```yaml
metrics:
  latency: true          # Measure response times
  success_rate: true     # Track operation success/failure
  token_usage: true      # Count LLM tokens consumed
  accuracy: true         # Post-hoc semantic similarity evaluation
  memory_quality: false  # Future: qualitative assessment
  cost_analysis: false   # Estimate $ cost per op and per 1K ops
```

**What it tunes:**
- Which performance metrics to collect and report
- Whether to run accuracy evaluation (embedding API cost/time)
- Whether to compute cost estimates from token usage
- What appears in output reports

**How it maps to execution:**
- Parsed at `config_parser/manager.py:207-208` → `MetricsConfig` dataclass
- `accuracy: true` triggers `_evaluate_accuracy()` at `comparator.py:95-96`
- Latency/tokens always collected but only reported if enabled

#### 4. `pricing` (optional) - Cost overrides

```yaml
pricing:
  gpt-4o-mini:
    input: 0.15   # USD per 1M input tokens
    output: 0.60  # USD per 1M output tokens
  input_ratio: 0.4  # Optional global input/output split fallback
  input_ratio_by_action:
    default: 0.6
    retrieve: 0.4
```

**What it tunes:**
- Overrides the default pricing table for cost analysis
- Enables cost estimates for custom or newer models
- Controls how $/1K ops is computed per action
- Keep defaults up to date with provider pricing (override as needed)

**How it maps to execution:**
- Parsed at `config_parser/manager.py:215`
- Merged with defaults in `pricing.py`
- Costs computed from `StepResult` input/output token splits (estimated when only totals are available)
- When only total tokens are available, `input_ratio` or `input_ratio_by_action` is used. Defaults: store 0.7, retrieve 0.4, chat 0.5 (input ratios).

**Cost analysis flow:**
```
StepResult (tokens_used, input_tokens, output_tokens, model)
   ↓
MetricsCalculator._calculate_costs()
   ↓
PerformanceMetrics (total_cost, cost/1K ops, per-action cost)
   ↓
JSON output + print_summary()
```

#### 5. `accuracy` (optional) - Semantic similarity configuration

```yaml
accuracy:
  providers: [openai, local]  # Which embedding models to use
  openai:
    model: text-embedding-3-small
  local:
    model: all-mpnet-base-v2  # Sentence-transformers model
```

**What it tunes:**
- Which embedding providers to use for accuracy scoring
- Embedding model quality (affects accuracy precision)
- Cost vs speed tradeoff (OpenAI vs local embeddings)
- Multi-provider comparison (test provider agreement)

**How it maps to execution:**
- Parsed at `config_parser/manager.py:211-212`
- Passed to `AccuracyEvaluator` in `comparator._evaluate_accuracy()` at line 181-200
- Calculates cosine similarity between responses and ground truth
- Stores per-provider scores in `StepResult.accuracy_by_provider`

#### 6. `output` - Results saving and display

```yaml
output:
  save_results: true           # Save JSON to file
  output_file: results.json    # Output filename
  print_summary: true          # Print console summary
  detailed_logs: true          # Verbose logging
```

**What it tunes:**
- Where results are saved (file path)
- What's displayed during execution (logs, summaries)
- Output verbosity level

**How it maps to execution:**
- Checked at `cli.py:141-166`
- Calls `comparator.save_results()` and `comparator.print_summary()`

#### 7. `general` - Execution behavior

```yaml
general:
  timeout: 60                    # NOT enforced (hardcoded 5min timeout)
  max_retries: 2                 # NOT implemented
  concurrent_tools: false        # Run tools sequentially (recommended)
  debug: false                   # Debug output
  stress_test_random_seed: 42    # Random seed for stress test (null = random)
```

**What it tunes:**
- **concurrent_tools**: Parallel vs sequential tool execution (affects resource usage)
- **stress_test_random_seed**: Reproducibility vs randomness in stress tests
- **debug**: Logging verbosity

**Note:** `timeout` and `max_retries` are defined but not currently used. Per-step timeout is hardcoded to 300s at `comparator.py:72`.

---

## How Benchmarks, Tools, and Evaluators Interact

### The Harness Model

```
┌─────────────────────────────────────────────────────────┐
│                   MemoryComparator                      │
│              (Orchestration Engine)                     │
│                                                         │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐  │
│  │ Benchmark   │   │  MemoryTool │   │  Evaluator  │  │
│  │  Suites     │→→→│ Abstraction │→→→│   System    │  │
│  └─────────────┘   └─────────────┘   └─────────────┘  │
│        ↓                   ↓                   ↓        │
│   Workloads            Execution           Metrics      │
└─────────────────────────────────────────────────────────┘
```

### Component Details

#### Benchmarks (`benchmarks.py`)

**Structure:**
- `BenchmarkSuite` - Collection of related workloads with metadata
- `Workload` - Test scenario (name, description, list of steps)
- `WorkloadStep` - Single operation (action, content, ground_truth)

**Responsibilities:**
- Define test scenarios (conversations, persona tests, stress tests)
- Provide ground truth for accuracy evaluation
- Organize steps into meaningful sequences

**Integration:**
- `StandardBenchmarks.get_all_suites()` returns all 6 suites
- `MemoryComparator.run_benchmark_suite()` executes suite workloads
- Each workload runs on all enabled tools via `benchmark_tools()`

#### Tools (`memory_tools/base.py` + implementations)

**Abstract Interface:**
```python
class MemoryTool:
    async def store_memory(content, metadata) -> str
    async def retrieve_memory(query, metadata) -> str
    async def chat(message, metadata) -> str
    async def clear_memory(session_id) -> None  # Optional
    async def execute_step(step, step_index) -> StepResult
```

**Implementations:**
- `Mem0Tool` - Mem0 API integration
- `OpenAIMemoryTool` - OpenAI Memory API integration
- `MemGPTTool` - MemGPT local instance
- `ClaudeMemoryTool` - Claude API with memory
- `ZepTool` - Zep memory platform

**Responsibilities:**
- Execute memory operations (store/retrieve/chat)
- Measure latency and token usage
- Handle errors and timeouts
- Clear memory between workloads

**Isolation Mechanism:**
- Each instance has unique `user_id` (generated from session_id)
- `clear_memory()` regenerates `user_id` for workload isolation
- Called between workloads (except first) at `comparator.py:231-243`

**Integration:**
- `MemoryComparator._get_tool_instance()` creates tool instances (factory pattern)
- Tools cached in `_tool_instances` dict
- `run_workload_on_tool()` executes all steps with 5-minute timeout per step

#### Evaluators (`accuracy_evaluator.py` + `embeddings/`)

**Structure:**
- `AccuracyEvaluator` - Main evaluation coordinator
- `EmbeddingProvider` - Abstract interface for embedding models
- `OpenAIEmbeddings` - OpenAI API embeddings
- `LocalEmbeddings` - Sentence-transformers local embeddings

**Responsibilities:**
- Generate embeddings for responses and ground truth
- Calculate cosine similarity (semantic matching)
- Support multiple providers for comparison
- Batch processing for efficiency

**Integration:**
- Called in `comparator._evaluate_accuracy()` (Phase 2)
- Receives all step responses + ground truths
- Returns list of accuracy scores (0.0-1.0)
- Stores scores in `StepResult.accuracy_by_provider`

### Execution Flow

```
1. CLI (cli.py:16-233)
   ├─ Load config YAML
   ├─ Validate API keys
   ├─ Create MemoryComparator
   └─ For each enabled benchmark:
      │
      2. MemoryComparator.run_benchmark_suite() (comparator.py:497-524)
         ├─ Get benchmark suite from StandardBenchmarks
         └─ Call benchmark_tools(suite.workloads)
            │
            3. MemoryComparator.benchmark_tools() (comparator.py:293-354)
               ├─ For each workload:
               │  ├─ Clear tool memory (except first workload)
               │  ├─ Call compare_tools(workload)
               │  └─ Collect WorkloadResults
               ├─ Calculate metrics (MetricsCalculator)
               └─ Evaluate accuracy if enabled
                  │
                  4. MemoryComparator.compare_tools() (comparator.py:223-291)
                     ├─ For each enabled tool:
                     │  └─ Call run_workload_on_tool()
                     └─ Return {tool_name: WorkloadResult}
                        │
                        5. MemoryComparator.run_workload_on_tool() (comparator.py:52-113)
                           ├─ Get tool instance
                           ├─ For each WorkloadStep:
                           │  ├─ tool.execute_step() [Phase 1: Performance]
                           │  └─ Store StepResult (response, latency, tokens)
                           ├─ _evaluate_accuracy() [Phase 2: Accuracy]
                           │  ├─ AccuracyEvaluator.evaluate_batch()
                           │  └─ Update StepResults with accuracy scores
                           └─ Return WorkloadResult
                              │
                              6. MemoryTool.execute_step() (base.py:53-89)
                                 ├─ Start timer
                                 ├─ Route to store_memory/retrieve_memory/chat
                                 ├─ Stop timer → latency_ms
                                 ├─ Count tokens → tokens_used
                                 └─ Return StepResult
```

### Two-Phase Evaluation

**Phase 1: Performance Collection** (Lines 59-92 in `comparator.py`)
- Execute all workload steps
- Measure latency and token usage
- Record responses
- **NO accuracy evaluation yet**

**Phase 2: Post-Hoc Accuracy** (Lines 94-96)
- After all steps complete
- Strip formatting prefixes for fair comparison
- Batch evaluate with AccuracyEvaluator
- Update StepResults with scores

**Why two phases?**
1. Latency measurements are pure (no embedding API overhead)
2. Token counts reflect only memory tool usage
3. Parallel tool execution doesn't interfere with accuracy
4. Can compare multiple embedding providers without re-running

---

## Results and Metrics

### Data Flow

```
StepResult (per operation)
    ↓
WorkloadResult (per workload, per tool)
    ↓
PerformanceMetrics (aggregated per tool)
    ↓
ComparisonSummary (cross-tool rankings)
    ↓
Output (JSON file + console summary)
```

### Metrics Collected

**Per-Step Metrics** (`StepResult`):
- `latency_ms` - Execution time
- `tokens_used` - LLM tokens consumed
- `success` - Boolean success flag
- `accuracy` - Primary accuracy score (0.0-1.0)
- `accuracy_by_provider` - Per-provider scores

**Aggregated Metrics** (`PerformanceMetrics`):
- `avg_latency_ms`, `p95_latency_ms`, `p99_latency_ms` - Latency percentiles
- `total_tokens`, `avg_tokens_per_query` - Token usage
- `success_rate` - Percentage successful
- `avg_accuracy` - Average across all steps
- `accuracy_by_provider` - Per-provider averages

**Comparison Metrics** (`ComparisonSummary`):
- Rankings (latency, token efficiency, success rate, accuracy)
- Relative performance percentages
- Provider agreement analysis (Spearman correlation, delta analysis)

### Output Formats

**JSON** (`benchmark_results.json`):
- Complete step-by-step results
- Aggregated metrics
- Comparison rankings
- Provider comparison analysis

**Console Summary**:
- Quick results per tool
- Performance rankings
- Embedding provider consistency analysis

---

## Critical Files Reference

**Entry Point:**
- `llmemory_meter/cli.py:16-233` - CLI and orchestration

**Core Harness:**
- `llmemory_meter/comparator.py:18-667` - MemoryComparator orchestration
- `llmemory_meter/workload.py:8-135` - Data structures (Workload, Step, Results)
- `llmemory_meter/benchmarks.py:16-476` - Benchmark suite definitions

**Tool System:**
- `llmemory_meter/memory_tools/base.py:16-89` - Abstract MemoryTool interface
- `llmemory_meter/memory_tools/mem0_tool.py` - Example implementation
- `llmemory_meter/memory_tools/template_tool.py` - New tool template

**Evaluation:**
- `llmemory_meter/accuracy_evaluator.py:13-125` - AccuracyEvaluator
- `llmemory_meter/embeddings/openai_embeddings.py` - OpenAI provider
- `llmemory_meter/embeddings/local_embeddings.py` - Local provider
- `llmemory_meter/metrics.py:47-667` - MetricsCalculator

**Configuration:**
- `llmemory_meter/config_parser/manager.py:150-259` - Config loading/validation
- `configs/starter.yml` - Default config
- `configs/comprehensive.yml` - Full suite
- `configs/example.yml` - Documented example

---

## Key Design Decisions

1. **Tool Isolation**: Auto-generated unique `user_id` per session, not user-configurable
2. **Memory Clearing**: Between workloads (except first) via `clear_memory()`
3. **Sequential Default**: `concurrent_tools: false` prevents resource exhaustion
4. **Two-Phase Evaluation**: Performance measured first, accuracy post-hoc
5. **Async Execution**: All operations async with 5-minute timeout per step
6. **Provider Abstraction**: Easy to add new embedding providers
7. **Batch Evaluation**: Efficient accuracy scoring via batch embedding APIs
8. **Factory Pattern**: Lazy tool instantiation with caching

---

## Extensibility Points

**Add New Memory Tool:**
1. Copy `memory_tools/template_tool.py`
2. Implement `store_memory()`, `retrieve_memory()`, `chat()`, `clear_memory()`
3. Add to `__init__.py` exports
4. Add elif branch in `comparator._get_tool_instance()`
5. Add config in YAML

**Add New Benchmark:**
1. Define `Workload` with `WorkloadStep` list in `benchmarks.py`
2. Add to appropriate suite or create new `BenchmarkSuite`
3. Add to config YAML `benchmarks` section

**Add New Evaluator:**
1. Create evaluator class with `evaluate_batch()` method
2. Call from `comparator._evaluate_accuracy()`
3. Update `StepResult` dataclass with new field
4. Add config toggle in YAML `metrics` section

**Add New Embedding Provider:**
1. Implement `EmbeddingProvider` interface
2. Register in `AccuracyEvaluator.__init__()` provider routing
3. Add to config YAML `accuracy.providers`
