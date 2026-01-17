# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

LLMemoryMeter is a Python benchmarking framework for comparing AI memory systems (Mem0, OpenAI Memory, MemGPT, Claude Memory, Zep). It measures latency, accuracy, and memory quality using standardized workloads.

## Common Commands

```bash
# Quick benchmark (2-3 min, uses configs/starter.yml)
python llmemory run

# Comprehensive benchmark (15-20 min)
python llmemory run --config comprehensive

# Single-tool testing
python llmemory run --config mem0-only.yml

# Debug with verbose output
python llmemory run --verbose

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

**Integration:** Set `match_type` field on WorkloadStep:

```python
WorkloadStep(
    action="retrieve",
    content="What is the API key?",
    ground_truth="sk-abc123xyz789",
    match_type="exact"  # Require exact match
)
```

Results stored in `StepResult.accuracy_by_provider` with keys like `"exact_match_exact"`.

### Adding a New Memory Tool

1. Copy `memory_tools/template_tool.py` to `memory_tools/new_tool.py`
2. Implement `store_memory()`, `retrieve_memory()`, `chat()`, optionally `clear_memory()`
3. Add import and export in `memory_tools/__init__.py`
4. Add elif branch in `comparator.py:_get_tool_instance()` (~line 31-42)
5. Add tool config in YAML files

## Configuration

Configs live in `configs/`. Key files:
- `starter.yml` - Default (2 tools, 2 benchmarks)
- `comprehensive.yml` - Full suite (all tools/benchmarks)
- `*-only.yml` - Single-tool configs for focused testing
- `test-exact-match.yml` - Workloads with exact match checks only

Five YAML sections: `memory_tools`, `benchmarks`, `metrics`, `output`, `general`

Required env vars: `MEM0_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY` (tool-dependent)

### Workload Filtering

Benchmark configs support filtering to specific workloads within a suite:

```yaml
benchmarks:
- name: Long Context Memory
  enabled: true
  workloads:  # Optional: omit to run all workloads in suite
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
- **Zep**: 8-second artificial delays for knowledge graph processing
- **MemGPT**: Token usage grows with conversation history
- **Mem0**: Requires Qdrant running on localhost:6333
- **Benchmarks**: Synthetic workloads (inspired by MSC/PersonaChat/LongBench, not actual datasets)

See `KNOWN_ISSUES.md` for detailed issue tracking.

## Validation

No formal test suite. Validate changes with:

```bash
python llmemory run --config quick-test.yml   # Fast smoke test
python llmemory run --config comprehensive.yml  # Full validation
```
