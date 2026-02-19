# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

LLMemoryMeter is a Python benchmarking framework for comparing AI memory systems (Mem0, OpenAI Memory, MemGPT, Claude Memory, Zep, Baseline). It measures latency, accuracy, and memory quality using standardized workloads.

## Common Commands

```bash
# Quick benchmark (Phase 1 default: industry-benchmarks.yml)
python llmemory run

# Industry benchmarks (store/retrieve only, Phase 1)
python llmemory run --config industry-benchmarks.yml
python llmemory run --config longmemeval-only.yml

# LongMemEval-only run
python llmemory run --config longmemeval-only.yml

# Debug with verbose output
python llmemory run --verbose

# Overnight runner with logging and notifications (preferred for testing)
./run_overnight.sh configs/industry-benchmarks.yml

# Hybrid evaluation (LongMemEval official GPT-4o judge)
python llmemory evaluate --benchmark LongMemEval --judge gpt-4o --results industry_benchmarks_results.json

# Prerequisites: Qdrant for Mem0
docker run -d --name qdrant -p 6333:6333 qdrant/qdrant
```

## Core Architecture

### Execution Flow

`CLI` -> `MemoryComparator` -> `MemoryTool` implementations -> `WorkloadResult`

1. **MemoryComparator** (`comparator.py:15`): Orchestrates benchmark runs, manages tool instances, evaluates accuracy post-hoc
2. **MemoryTool** (`memory_tools/base.py:15`): Abstract base with three methods: `store_memory()`, `retrieve_memory()`, `chat()`
3. **Workload/WorkloadStep** (`workload.py`): Test scenarios composed of store/retrieve/chat operations
4. **StepResult/WorkloadResult**: Performance data with latency, tokens, success, accuracy scores

### Key Design Decisions

**Async Execution**: All tool operations are async. Steps execute via `asyncio.wait_for()` with 5-minute timeout per step (`comparator.py:72-76`).

**Tool Isolation**: Each tool instance auto-generates a unique user_id (not configurable). Memory is cleared between workloads (except first) via `clear_memory()` to prevent context contamination.

**Sequential by Default**: `concurrent_tools: false` in configs prevents resource conflicts and ThreadPoolExecutor exhaustion.

**Two-Phase Evaluation**: Benchmark runs first (pure performance), then accuracy evaluation happens post-hoc so it doesn't affect latency/token metrics.

### Accuracy Evaluation

**Two-Phase Design:** Performance measurement (latency/tokens) happens first, then accuracy evaluation post-hoc.

**Evaluation Modes:**

- **Embedding-based** (`AccuracyEvaluator`): Cosine similarity (0.0-1.0) for semantic matching
- **Exact match** (`ExactMatchEvaluator`): Binary (0.0/1.0) for precise answers

**Match Types:**

- `embedding` (default): Semantic similarity
- `exact`: Case-sensitive exact match
- `exact_case_insensitive`: Case-insensitive exact match
- `contains`: Ground truth substring in response
- `regex`: Ground truth as regex pattern

**Multi-Provider, Multi-Model Support:**

Evaluate responses with multiple embedding models simultaneously:

```yaml
metrics:
  accuracy: true

accuracy:
  providers:
    openai:
      - text-embedding-3-small
      - text-embedding-3-large
    local:
      - all-mpnet-base-v2
      - all-MiniLM-L6-v2
```

Each step stores accuracy scores for all configured models in `StepResult.accuracy_by_provider` with keys like `"openai_text-embedding-3-small"`, `"local_all-mpnet-base-v2"`. The primary accuracy score (used in summaries) is from the first provider's first model.

**Integration:** Set `match_type` field on WorkloadStep:

```python
WorkloadStep(
    action="retrieve",
    content="What is the API key?",
    ground_truth="sk-abc123xyz789",
    match_type="exact"  # Require exact match
)
```

Results stored in `StepResult.accuracy_by_provider` with keys like `"exact_match_exact"` or `"openai_text-embedding-3-small"`.

### Adding a New Memory Tool

1. Copy `memory_tools/template_tool.py` to `memory_tools/new_tool.py`
2. Implement `store_memory()`, `retrieve_memory()`, `chat()`, optionally `clear_memory()`
3. Add import and export in `memory_tools/__init__.py`
4. Add elif branch in `comparator.py:_get_tool_instance()` (~line 31-42)
5. Add tool config in YAML files

### Baseline Tools

**Purpose**: Simple baseline implementations for comparing memory products against basic context management strategies.

**Implementations**: `llmemory_meter/memory_tools/baseline_tool.py`

**Two Strategies**:

1. **NoMemoryTool (baseline)**: Stores only last k messages
   - Simulates "keep recent context" strategy
   - Default: k=5
   - Configuration: `settings.k`

2. **FullContextTool (full_context)**: Stores ALL messages
   - Simulates "stuff everything into prompt" strategy
   - No message limit (optional safety limit: `max_messages`)
   - Default: unlimited (max_messages=null)
   - Configuration: `settings.max_messages`

**Key Features**:

- No API keys required (`api_key_env: null`)
- No LLM calls (zero token usage)
- Stores messages in Python lists (in-memory)
- Zero latency (no network calls)
- 100% success rate (no external dependencies)

**Configuration Examples**:

```yaml
# Last k messages strategy
- name: baseline
  enabled: true
  api_key_env: null
  model: null
  settings:
    k: 5

# Full context strategy
- name: full_context
  enabled: true
  api_key_env: null
  model: null
  settings:
    max_messages: null # unlimited
```

**Use Cases**:

- Smoke testing without API keys
- Baseline comparisons ("is Mem0 better than full context?")
- Validating framework changes without dependencies
- Understanding memory vs context trade-offs
- Comparing context management strategies

**Testing**:

```bash
# Phase 1 runs
./run_overnight.sh configs/industry-benchmarks.yml
python llmemory run --config longmemeval-only.yml
```

## Configuration

Configs live in `configs/`. Key files:

- `industry-benchmarks.yml` - LongMemEval + MemBench (store/retrieve only)
- `longmemeval-only.yml` - LongMemEval only (store/retrieve only)
- Legacy configs moved to `configs/archived/`

Five YAML sections: `memory_tools`, `benchmarks`, `metrics`, `output`, `general`

Required env vars: `MEM0_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY` (tool-dependent)

### Debug Mode

Control whether memory tool responses include tool-specific prefixes via the `debug` flag in the `general` section:

```yaml
general:
  debug: false  # Production mode (default): clean responses
  # debug: true  # Development mode: responses prefixed with [tool_name]
```

**Debug Mode OFF (debug: false)**:
- Clean responses without prefixes
- Suitable for production benchmarks and accuracy evaluation
- Example: `"Hi! I'm Sarah, a software engineer..."`

**Debug Mode ON (debug: true)**:
- Responses prefixed with `[tool_name]`
- Useful for development, debugging, and understanding tool behavior
- Example: `"[mem0] Stored (ID: abc123): Hi! I'm Sarah, a software engineer..."`

All memory tools (mem0, openai_memory, memgpt, claude_memory, zep, baseline) support the debug flag.

### Workload Filtering

Benchmark configs support filtering to specific workloads within a suite:

```yaml
benchmarks:
  - name: Long Context Memory
    enabled: true
    workloads: # Optional: omit to run all workloads in suite
      - Information Needle Test
```

Available workloads per benchmark:

- **Conversational AI Memory**: Multi-Session Memory Retention, Persona Consistency Test
- **Long Context Memory**: Long Document Memory, Information Needle Test
- **Persona Consistency**: Professional Persona Consistency
- **Domain-Specific Applications**: Customer Service Memory
- **Technical Performance**: Memory Load & Retention Test
- **Memory Stress Testing**: (generated workloads)

## Known Limitations

- **Claude Memory**: Rate limits with >20 rapid operations
- **Zep**: Async knowledge graph with eventual consistency — 60s pre-retrieve indexing delay, content chunking for >9K messages, Flex plan ($25/mo) required for benchmarking, LongMemEval limited to 10 questions due to credit constraints
- **MemGPT**: Token usage grows with conversation history
- **Mem0**: Requires Qdrant running on localhost:6333
- **Benchmarks**: Synthetic workloads (inspired by MSC/PersonaChat/LongBench, not actual datasets)

See `KNOWN_ISSUES.md` for detailed issue tracking.

## Validation

No formal test suite. Validate changes with:

```bash
# Phase 1 validation
python llmemory run --config industry-benchmarks.yml
python llmemory run --config longmemeval-only.yml

# Overnight runner with logging (preferred)
./run_overnight.sh configs/industry-benchmarks.yml
```
