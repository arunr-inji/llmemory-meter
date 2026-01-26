# Configuration Files

This directory contains YAML configuration files for LLMemoryMeter benchmarks.

## Available Configurations

### 🚀 **starter.yml** (Default - Recommended for Beginners)
- **Production-ready** configuration with 100% success rate
- Both Mem0 (with Qdrant vector store) and OpenAI Memory enabled
- Optimized settings: sequential execution, proper timeouts
- Runs basic conversational and long-context benchmarks

### 🔬 **comprehensive.yml** (For Tech Articles & Research)
- **Complete evaluation** setup with all memory tools and benchmarks
- Memory Tools: Mem0, OpenAI Memory, MemGPT, Claude Memory (+ Zep optional)
- All 5 benchmarks enabled for thorough comparison
- Full quality analysis (accuracy, memory_quality metrics)
- Perfect for tech journal articles, research papers, vendor evaluation

### 📝 **example.yml**
- Alternative configuration showing different options
- OpenAI Memory only setup (for users with just OpenAI API key)
- Includes detailed comments explaining each option
- Shows how to enable/disable specific benchmarks

### 🔬 **gemini.yml**
- Mem0 with Google Gemini LLM instead of OpenAI
- Requires GOOGLE_API_KEY and MEM0_API_KEY
- Demonstrates multi-LLM provider setup

### ⚔️ **conflict-resolution.yml**
- Focused run for conflict-resolution workloads (overwrite + multi-hop + temporal updates)
- Runs only the conflict-resolution workloads in the Conversational AI suite
- Useful for validating latest-fact behavior and scenario metrics

## Creating Your Own Config

1. **Copy a template**:
```bash
cp configs/default.yml my_config.yml
```

2. **Edit settings**:
- Enable/disable memory tools
- Select benchmarks to run
- Configure tool-specific settings
- Set output preferences

3. **Run with your config**:
```bash
python llmemory run --config my_config.yml
```

## Configuration Structure

```yaml
memory_tools:    # Which tools to test
  - name: mem0
    enabled: true
    api_key_env: MEM0_API_KEY
    model: gpt-4o-mini
    settings: {...}

benchmarks:      # Which test suites to run
  - name: Conversational AI Memory
    enabled: true

metrics:         # What to measure
  latency: true
  success_rate: true
  token_usage: true
  accuracy: true

accuracy:        # Multi-provider accuracy evaluation
  providers:
    openai:
      - text-embedding-3-small
    local:
      - all-mpnet-base-v2

output:          # Results handling
  save_results: true
  output_file: results.json

general:         # Global settings
  timeout: 30
  debug: false   # false: clean responses | true: prefixed responses for debugging
```

**Debug Mode:**
- `debug: false` - Production mode with clean responses (recommended for benchmarks)
- `debug: true` - Development mode with `[tool_name]` prefixes for debugging

## Quick Commands

```bash
# Basic benchmarking (uses starter.yml by default)
llmemory run

# Comprehensive evaluation (for articles/research)
llmemory run --config comprehensive

# Set your preferred default config  
export LLMEMORY_DEFAULT_CONFIG=comprehensive.yml
llmemory run  # Now uses comprehensive.yml by default

# Create new config from default
llmemory create-config --output my_config.yml

# Run with specific config (auto-checks configs/ folder)
llmemory run --config example
llmemory run --config my_config.yml

# Run with default config
python llmemory run
```
