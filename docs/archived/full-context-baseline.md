# Implementation Plan: Full-Context Baseline Tool

## Overview
Implement "Full-Context Baseline" tool that stores ALL messages without any limit, simulating the "stuff everything into prompt" strategy. This provides practitioners with a comparison baseline to answer: "Is a memory system better than just keeping all context?"

**Priority**: Week 1-2 Core Infrastructure, Feature #4 (Roadmap)
**Effort**: Low | **Impact**: High

---

## What to Build

A new memory tool class `FullContextTool` that:
- Stores ALL messages in a Python list (no k-message limit like NoMemoryTool)
- Returns all stored messages on retrieval (full context)
- Uses all messages as context in chat operations
- Optional safety limit (`max_messages`) to prevent runaway growth
- Zero token usage (no LLM calls)
- No API keys required

---

## Implementation Steps

### 1. Add FullContextTool Class to baseline_tool.py

**File**: `llmemory_meter/memory_tools/baseline_tool.py`

**Changes**:
1. Update module docstring (lines 1-6) to describe both baseline tools
2. Add `FullContextTool` class after `NoMemoryTool` (after line 73)

**Key Implementation Details**:

```python
# Update module docstring (lines 1-6)
"""
Baseline Memory Tools

Simple baseline implementations for comparing memory products:
- NoMemoryTool: Keeps only last k messages
- FullContextTool: Keeps all messages (no limit)
"""

# Add new class after NoMemoryTool (after line 73)
class FullContextTool(MemoryTool):
    """Full-context baseline: stores ALL messages without limit.

    Simulates "stuff everything into prompt" strategy.
    WARNING: Memory grows unbounded unless max_messages is set.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__("full_context", config)

        # Configuration
        self.max_messages = self.config.get("max_messages", None)  # None = unlimited
        self.include_metadata = self.config.get("include_metadata", False)

        # In-memory storage
        self.stored_messages: List[str] = []
        self.conversation_history: List[Dict[str, str]] = []

    async def store_memory(self, content: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Store message, keeping all messages (no limit)."""
        self.stored_messages.append(content)

        # Apply safety limit if configured
        if self.max_messages and len(self.stored_messages) > self.max_messages:
            self.stored_messages = self.stored_messages[-self.max_messages:]

        return f"Full-context stored (total {len(self.stored_messages)} messages): {content[:80]}..."

    async def retrieve_memory(self, query: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Retrieve all stored messages."""
        if not self.stored_messages:
            return f"No messages stored for query: '{query}'"

        # Format messages (show preview if many messages to avoid huge logs)
        msg_count = len(self.stored_messages)

        if msg_count <= 6:
            formatted = "\n".join([
                f"  {i+1}. {msg}"
                for i, msg in enumerate(self.stored_messages)
            ])
        else:
            # Show first 3 and last 3 to keep logs readable
            first_three = "\n".join([f"  {i+1}. {msg}" for i, msg in enumerate(self.stored_messages[:3])])
            last_three = "\n".join([f"  {msg_count-2+i}. {msg}" for i, msg in enumerate(self.stored_messages[-3:])])
            formatted = f"{first_three}\n  ... ({msg_count-6} more messages) ...\n{last_three}"

        return f"Full-context retrieved (all {msg_count} messages) for '{query}':\n{formatted}"

    async def chat(self, message: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Chat using ALL messages as context (no limit)."""
        if self.stored_messages:
            # Preview last 5 messages to keep logs readable
            context_preview = " | ".join([msg[:50] for msg in self.stored_messages[-5:]])
            response = f"Full-context response to '{message}' (using all {len(self.stored_messages)} messages as context): Based on full context [{context_preview}...], here is the response."
        else:
            response = f"Full-context response to '{message}': No prior context available."

        # Update conversation history (store ALL)
        self.conversation_history.append({"role": "user", "content": message})
        self.conversation_history.append({"role": "assistant", "content": response})

        # Apply safety limit if configured
        if self.max_messages and len(self.conversation_history) > self.max_messages * 2:
            self.conversation_history = self.conversation_history[-(self.max_messages * 2):]

        return response

    async def clear_memory(self, session_id: Optional[str] = None) -> str:
        """Clear memory between workloads."""
        self.stored_messages = []
        self.conversation_history = []
        return "Full-context memory cleared"
```

**Pattern to Follow**: Nearly identical to `NoMemoryTool` (lines 12-73) but:
- Remove k parameter and trimming logic (lines 19, 32-33, 64-65)
- Add optional max_messages safety limit
- Add preview logic for large message counts (avoid huge logs)
- Update response strings to say "Full-context" instead of "Baseline"

---

### 2. Register Tool in Comparator

**File**: `llmemory_meter/comparator.py`

**Changes**:

1. **Update import** (line 8):
   ```python
   from llmemory_meter.memory_tools import MemoryTool, Mem0Tool, OpenAIMemoryTool, MemGPTTool, ClaudeMemoryTool, ZepTool, NoMemoryTool, FullContextTool
   ```

2. **Add tool registration** in `_get_tool_instance()` method (after line 87):
   ```python
   elif tool_name == "full_context":
       self._tool_instances[tool_name] = FullContextTool(self.config.get("full_context", {}))
   ```

3. **Update error message** (line 90):
   ```python
   raise ValueError(f"Unknown tool: {tool_name}. Supported tools: mem0, openai_memory, memgpt, claude_memory, zep, baseline, full_context")
   ```

---

### 3. Export Tool in Package Init

**File**: `llmemory_meter/memory_tools/__init__.py`

**Changes**:

1. **Update import** (modify existing baseline_tool import):
   ```python
   from llmemory_meter.memory_tools.baseline_tool import NoMemoryTool, FullContextTool
   ```

2. **Update __all__** (add to exports list):
   ```python
   __all__ = [
       "MemoryTool",
       "Mem0Tool",
       "OpenAIMemoryTool",
       "MemGPTTool",
       "ClaudeMemoryTool",
       "ZepTool",
       "NoMemoryTool",
       "FullContextTool"  # Add this
   ]
   ```

---

### 4. Create Configuration Files

#### 4.1 Create full-context-only.yml

**File**: `configs/full-context-only.yml` (NEW)

```yaml
# Full-Context Baseline Configuration
# Tests "stuff everything into prompt" strategy
# No API keys required

memory_tools:
- name: full_context
  enabled: true
  api_key_env: null
  model: null
  settings:
    max_messages: null  # null = unlimited

benchmarks:
- name: Conversational AI Memory
  enabled: true
  settings: null

metrics:
  latency: true
  success_rate: true
  token_usage: true
  accuracy: false
  memory_quality: false

output:
  save_results: true
  output_file: full_context_results.json
  print_summary: true
  detailed_logs: true

general:
  timeout: 60
  max_retries: 2
  concurrent_tools: false
  debug: false
```

---

#### 4.2 Create baseline-comparison.yml

**File**: `configs/baseline-comparison.yml` (NEW)

```yaml
# Baseline Strategies Comparison
# Compares "last k messages" vs "full context" strategies
# No API keys required

memory_tools:
- name: baseline
  enabled: true
  api_key_env: null
  model: null
  settings:
    k: 5  # Last 5 messages
- name: full_context
  enabled: true
  api_key_env: null
  model: null
  settings:
    max_messages: null  # Unlimited

benchmarks:
- name: Conversational AI Memory
  enabled: true
  settings: null
- name: Long Context Memory
  enabled: true
  settings: null

metrics:
  latency: true
  success_rate: true
  token_usage: true
  accuracy: false
  memory_quality: false

output:
  save_results: true
  output_file: baseline_comparison_results.json
  print_summary: true
  detailed_logs: false

general:
  timeout: 60
  max_retries: 2
  concurrent_tools: false
  debug: false
```

---

#### 4.3 Update starter.yml

**File**: `configs/starter.yml`

**Change**: Add full_context tool entry after baseline (after line 30)

```yaml
- name: baseline
  enabled: true
  api_key_env: null
  model: null
  settings:
    k: 5
- name: full_context  # ADD THIS
  enabled: true
  api_key_env: null
  model: null
  settings:
    max_messages: null
```

---

#### 4.4 Update comprehensive.yml

**File**: `configs/comprehensive.yml`

**Change**: Add full_context tool with safety limit for stress tests

```yaml
- name: baseline
  enabled: true
  api_key_env: null
  model: null
  settings:
    k: 10
- name: full_context  # ADD THIS
  enabled: true
  api_key_env: null
  model: null
  settings:
    max_messages: 1000  # Safety limit for stress tests
```

---

### 5. Update Documentation

#### 5.1 Update CLAUDE.md

**File**: `CLAUDE.md`

**Section**: "Core Architecture" → "Baseline Tool" (expand to "Baseline Tools")

Replace the existing "Baseline Tool" section with expanded version covering both tools:

```markdown
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
    max_messages: null  # unlimited
```

**Use Cases**:
- Smoke testing without API keys
- Baseline comparisons ("is Mem0 better than full context?")
- Validating framework changes without dependencies
- Understanding memory vs context trade-offs
- Comparing context management strategies

**Testing**:
```bash
# Test individual baselines
./run_overnight.sh configs/baseline-only.yml
./run_overnight.sh configs/full-context-only.yml

# Compare both strategies
python llmemory run --config baseline-comparison.yml
```
```

---

#### 5.2 Update README.md

**File**: `README.md`

**Changes**:

1. **Update "Supported Memory Tools" list** - add after Baseline:
   ```markdown
   - **Baseline** - Simple no-memory baseline (keeps last k messages, no API keys required)
   - **Full-Context** - Stores all messages without limit (simulates "stuff everything into prompt", no API keys required)
   ```

2. **Add to "Configuration Tiers"** section after "Baseline-Only Configuration":
   ```markdown
   ### 📊 **Baseline Comparison**
   - **Tools**: Baseline (last k) + Full-Context (all messages)
   - **Benchmarks**: Conversational AI Memory + Long Context Memory
   - **Runtime**: < 2 seconds
   - **Use Case**: Compare context management strategies
   - **Command**: `llmemory run --config baseline-comparison.yml`
   - **Files**: `configs/baseline-comparison.yml`, `configs/full-context-only.yml`
   ```

---

#### 5.3 Update roadmap.md

**File**: `docs/roadmap.md`

**Section**: Feature 1.1 table (lines 19-26)

**Change**: Mark Full-Context baseline as complete

```markdown
| Baseline | Description | Implementation Complexity | Status |
|----------|-------------|--------------------------|---------|
| **No-Memory** | Only last-k messages, discard rest | Trivial - mock store/retrieve | ✅ Complete |
| **Full-Context** | Stuff everything into prompt until limit | Simple - list storage, no retrieval | ✅ Complete |
| **Summarize-then-Append** | Rolling LLM summary + recent turns | Medium - LLM call on store | 📋 Planned |
| **RAG** | Vector store retrieval of prior turns | Medium - local embeddings + chromadb | 📋 Planned |
| **Hybrid** | Summary + retrieval | Medium - combines above | 📋 Planned |
```

---

## Verification & Testing

### Testing Approach

**1. Smoke Test Full-Context Only**:
```bash
./run_overnight.sh configs/full-context-only.yml
```

**Expected Results**:
- 100% success rate
- Zero latency (<1ms)
- Zero token usage
- Message count grows: "total 1 messages", "total 2 messages", etc.
- Logs show "Full-context stored", "Full-context retrieved", "Full-context response"

---

**2. Compare Both Baseline Strategies**:
```bash
python llmemory run --config baseline-comparison.yml
```

**Expected Results**:
- Both tools show 100% success rate
- baseline shows "last 5 messages" in logs
- full_context shows "all N messages" in logs
- Both have zero latency and zero tokens
- Results JSON contains entries for both tools

---

**3. Integration with Real Tools (starter.yml)**:
```bash
python llmemory run --config starter.yml
```

**Expected Results**:
- full_context runs alongside mem0, openai_memory, baseline
- No interference between tools
- full_context completes successfully
- Output shows 4 tools in results

---

**4. Stress Test with Safety Limit**:
```bash
python llmemory run --config comprehensive.yml
```

**Expected Results**:
- Memory Stress Test with 50 stores should show 50 messages
- If max_messages=1000 set, should never exceed 1000
- No memory errors or crashes

---

### Success Criteria

**Functional**:
- ✅ FullContextTool implements all 4 required methods
- ✅ Stores all messages when max_messages=null
- ✅ Respects max_messages safety limit when set
- ✅ 100% success rate in benchmarks
- ✅ Zero latency and zero token usage
- ✅ clear_memory() resets state properly

**Integration**:
- ✅ Tool registered in comparator
- ✅ Tool exported in __init__.py
- ✅ Works in full-context-only.yml
- ✅ Works in baseline-comparison.yml
- ✅ Works in starter.yml and comprehensive.yml

**Documentation**:
- ✅ CLAUDE.md updated with baseline tools section
- ✅ README.md lists full_context in tools
- ✅ README.md includes baseline-comparison.yml
- ✅ roadmap.md marked complete

**Validation**:
- ✅ `./run_overnight.sh configs/full-context-only.yml` succeeds
- ✅ `python llmemory run --config baseline-comparison.yml` shows both tools
- ✅ No errors in logs
- ✅ Message counts increase correctly

---

## Critical Files to Modify

| File | Type | Purpose |
|------|------|---------|
| `llmemory_meter/memory_tools/baseline_tool.py` | Edit | Add FullContextTool class (~80 lines) |
| `llmemory_meter/comparator.py` | Edit | Register tool (3 lines) |
| `llmemory_meter/memory_tools/__init__.py` | Edit | Export tool (2 lines) |
| `configs/full-context-only.yml` | New | Standalone test config |
| `configs/baseline-comparison.yml` | New | Comparison config |
| `configs/starter.yml` | Edit | Add full_context entry |
| `configs/comprehensive.yml` | Edit | Add full_context with safety limit |
| `CLAUDE.md` | Edit | Update baseline section |
| `README.md` | Edit | Add tool and config tier |
| `docs/roadmap.md` | Edit | Mark feature complete |

---

## Implementation Notes

**Design Philosophy**: "Minimal diff" from NoMemoryTool - only remove k-trimming logic and add optional safety limit.

**Why This Matters** (from roadmap):
- HIGH IMPACT: Answers practitioner question "Is memory better than full context?"
- LOW EFFORT: ~80 lines of code, mostly copy-paste from NoMemoryTool
- Enables data-driven comparison between strategies

**Future Extensions** (out of scope):
- Add token limit simulation (e.g., max_tokens to simulate LLM constraints)
- Add message compression strategies
- Add context relevance scoring
