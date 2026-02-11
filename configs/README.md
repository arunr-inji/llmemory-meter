# Configuration Files

This directory contains YAML configuration files for LLMemoryMeter benchmarks.

## Available Configurations

### 🚀 **industry-benchmarks.yml** (Default - Phase 1)
- Store/retrieve-only comparison for Mem0, Zep, and MemGPT
- Runs LongMemEval + MemBench (industry datasets)
- Optimized for latency/cost measurement without chat steps

### 🧪 **longmemeval-only.yml**
- LongMemEval-only run (store/retrieve only)
- Useful for isolated LongMemEval evaluation + GPT-4o judging

Legacy configs are available in `configs/archived/` for reference.

## Creating Your Own Config

1. **Copy a template**:
```bash
cp configs/industry-benchmarks.yml my_config.yml
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
  - name: LongMemEval
  - name: MemBench
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
  store_retrieve_only: true
  debug: false   # false: clean responses | true: prefixed responses for debugging
```

**Debug Mode:**
- `debug: false` - Production mode with clean responses (recommended for benchmarks)
- `debug: true` - Development mode with `[tool_name]` prefixes for debugging

## Quick Commands

```bash
# Basic benchmarking (uses industry-benchmarks.yml by default)
llmemory run

# LongMemEval only
llmemory run --config longmemeval-only.yml

# Set your preferred default config  
export LLMEMORY_DEFAULT_CONFIG=configs/industry-benchmarks.yml
llmemory run  # Now uses industry-benchmarks.yml by default

# Create new config from default
llmemory create-config --output my_config.yml

# Run with specific config (auto-checks configs/ folder)
llmemory run --config industry-benchmarks
llmemory run --config my_config.yml

# Run with default config
python llmemory run
```
