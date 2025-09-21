# Configuration Files

This directory contains YAML configuration files for LLMemoryMeter benchmarks.

## Available Configurations

### 📋 **default.yml**
- Default configuration with both Mem0 and OpenAI Memory enabled
- Runs basic conversational and long-context benchmarks
- Good starting point for most users

### 📝 **example.yml**
- Example custom configuration
- Shows how to configure specific tools and benchmarks
- Includes detailed comments explaining each option

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

output:          # Results handling
  save_results: true
  output_file: results.json

general:         # Global settings
  timeout: 30
  debug: false
```

## Quick Commands

```bash
# Create new config from default
python llmemory create-config --output my_config.yml

# Run with specific config
python llmemory run --config configs/example.yml

# Run with default config
python llmemory run
```
