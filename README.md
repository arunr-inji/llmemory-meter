# LLMemoryMeter 🧠📊

A comprehensive Python tool for benchmarking and comparing AI memory systems like **Mem0**, **OpenAI Memory**, and more.

## Features

- 🔄 **Multi-Tool Comparison**: Compare Mem0, OpenAI Memory, and other AI memory systems
- 📊 **Industry-Standard Benchmarks**: Pre-configured test suites based on research datasets
- 📈 **Comprehensive Metrics**: Latency, accuracy, token usage, success rates, and more
- ⚙️ **Custom Workloads**: Create domain-specific test scenarios
- 🚀 **Easy Integration**: Simple API for adding new memory tools

## Supported Memory Tools

- **Mem0** - Multi-level memory system with semantic search
- **OpenAI Memory** - Built-in ChatGPT memory capabilities
- **Extensible Framework** - Easy to add MemGPT, Zep, and other memory tools

## Performance Metrics

LLMemoryMeter measures comprehensive performance across multiple dimensions:

### 🚀 **Performance Metrics**
- **Latency**: Response time for memory operations (avg, P95, P99)
- **Throughput**: Operations per second under load
- **Success Rate**: Percentage of operations that complete successfully
- **Token Usage**: API token consumption and cost efficiency

### 🎯 **Memory Quality Metrics**
- **Accuracy**: How well retrieved information matches queries
- **Consistency**: Reliability of responses across repeated queries  
- **Retention**: Information persistence across sessions
- **Context Relevance**: Appropriateness of retrieved memories

### 📊 **Benchmark Categories**
- **Conversational AI**: Multi-session chat, persona consistency (MSC, PersonaChat)
- **Long Context**: Document processing, needle-in-haystack tests (LongBench style)
- **Technical Performance**: Stress testing, capacity limits, concurrent access
- **Domain-Specific**: Customer service, research assistant, personal assistant scenarios

## Quick Start

### 🚀 **Option 1: CLI with YAML Configuration (Recommended)**

1. **Set up Python environment** (optional but recommended):
```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
# venv\Scripts\activate

# To deactivate when done:
# deactivate
```

2. **Install dependencies**:
```bash
pip install -r requirements.txt
```

3. **Start Qdrant vector database (required for Mem0)**:
```bash
# Using Docker (recommended)
docker run -d --name qdrant -p 6333:6333 -p 6334:6334 \
  -v $(pwd)/qdrant_storage:/qdrant/storage:z \
  qdrant/qdrant

# Or if you already have the container, just start it
docker start qdrant

# Verify Qdrant is running
curl http://localhost:6333
```

4. **Create default configuration**:
```bash
python llmemory create-config
```

5. **Set up API keys**:
```bash
cp .env.example .env
# Add your MEM0_API_KEY and OPENAI_API_KEY
```

6. **Run benchmarks**:
```bash
python llmemory run
```

### 🐍 **Option 2: Python API**

1. Install dependencies and set up API keys (steps 1-5 above)

2. Run the simple comparison:
```bash
python simple_example.py
```

## Basic Usage

### Custom Workload Testing
```python
from llmemory_meter import MemoryComparator

# Create comparator
comparator = MemoryComparator()

# Create a simple test
workload = comparator.create_simple_workload(
    name="Basic Test",
    memory_content="I am a Python developer from NYC",
    retrieval_query="What is my profession?"
)

# Compare tools
results = await comparator.compare_tools(workload, ["mem0", "openai_memory"])
print(results)
```

### Industry-Standard Benchmarks
```python
from llmemory_meter import MemoryComparator, StandardBenchmarks

# Initialize comparator
comparator = MemoryComparator()

# View available benchmarks
benchmarks = comparator.get_available_benchmarks()
print("Available benchmarks:", benchmarks)

# Run a specific benchmark suite
results = await comparator.run_benchmark_suite(
    "Conversational AI Memory", 
    ["mem0", "openai_memory"]
)

# Run all benchmarks
all_results = await comparator.run_all_benchmarks()
comparator.print_summary(all_results)
```

## YAML Configuration

### 📋 **Configuration Structure**

The YAML config has 4 main sections:

```yaml
memory_tools:    # Tools to compare
benchmarks:      # Test suites to run  
metrics:         # What to measure
output:          # Results handling
general:         # Global settings
```

### 🔧 **Memory Tools Configuration**

```yaml
memory_tools:
  - name: mem0
    enabled: true
    api_key_env: MEM0_API_KEY
    model: gpt-4o-mini
    settings:
      user_id: benchmark_user
      llm_provider: openai
      llm_api_key_env: OPENAI_API_KEY
      vector_store:
        provider: qdrant
        host: localhost
        port: 6333
        collection_name: test

  - name: openai_memory
    enabled: true
    api_key_env: OPENAI_API_KEY
    model: gpt-4o-mini
    settings:
      temperature: 0.3
      max_tokens: 300
```

### 📊 **Benchmarks Configuration**

```yaml
benchmarks:
  - name: Conversational AI Memory
    enabled: true
  - name: Long Context Memory  
    enabled: true
  - name: Persona Consistency
    enabled: false    # Skip this benchmark
```

### 📈 **CLI Commands**

```bash
# Create default config
python llmemory create-config

# Create custom config
python llmemory create-config --output my_config.yml

# Run with default config
python llmemory run

# Run with custom config
python llmemory run --config my_config.yml

# Verbose output
python llmemory run --verbose
```

## Example Results

```
🧠 LLMemoryMeter - Benchmark Results Summary
============================================================

📊 Overall Performance Metrics:
----------------------------------------

🔧 MEM0:
  • Avg Latency: 245.3ms
  • P95 Latency: 420.1ms
  • Success Rate: 95.2%
  • Avg Tokens/Query: 1,250

🔧 OPENAI_MEMORY:
  • Avg Latency: 189.7ms
  • P95 Latency: 312.4ms
  • Success Rate: 98.7%
  • Avg Tokens/Query: 890

🏆 Performance Rankings:
⚡ Speed (Latency): openai_memory > mem0
✅ Reliability: openai_memory > mem0
💰 Token Efficiency: openai_memory > mem0
```

## Available Benchmark Suites

### 🗣️ **Conversational AI Benchmarks**
- **Multi-Session Memory Retention**: Tests memory across conversation sessions
- **Persona Consistency**: Evaluates consistent character/role maintenance
- Based on MSC (Multi-Session Chat) and PersonaChat datasets

### 📚 **Long Context Benchmarks** 
- **Long Document Memory**: Information retention over extended text
- **Needle-in-Haystack**: Specific fact retrieval from large contexts
- Based on LongBench and InfiniteBench methodologies

### ⚡ **Technical Performance Benchmarks**
- **Memory Stress Testing**: High-frequency operations and capacity limits
- **Concurrent Access**: Multi-user scenarios and race conditions
- Based on AdaptMemBench and AISBench approaches

### 🏢 **Domain-Specific Benchmarks**
- **Customer Service**: Support ticket context and resolution tracking
- **Research Assistant**: Knowledge accumulation and synthesis
- **Personal Assistant**: Preference management and scheduling

## Current Status

⚠️ **Note**: The current implementation uses **mock APIs** for demonstration. To get real performance data:

1. **Set up API keys** in `.env` file:
   ```bash
   MEM0_API_KEY=your_mem0_api_key
   OPENAI_API_KEY=your_openai_api_key
   ```

2. **Replace mock implementations** with actual API calls in `memory_tools.py`

3. **Run benchmarks** to get real performance comparisons

## Quick Demo

Run the benchmark demo to see the framework in action:
```bash
python benchmark_demo.py
```

## Installation

```bash
git clone <repository>
cd llmemory_meter

# Optional: Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Start Qdrant for Mem0 (requires Docker)
docker run -d --name qdrant -p 6333:6333 qdrant/qdrant

# When done, you can clean up:
# deactivate  # Exit virtual environment
# docker stop qdrant  # Stop Qdrant container
# rm -rf venv  # Remove virtual environment (optional)
```

## Contributing

We welcome contributions! Areas where help is needed:
- Real API implementations for Mem0, OpenAI Memory
- Additional memory tools (MemGPT, Zep, LangMem)
- New benchmark scenarios
- Memory quality evaluation metrics

## License

MIT License
