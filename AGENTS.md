# Repository Guidelines

## Project Structure & Module Organization
- `llmemory_meter/`: core Python package (CLI, comparator, workloads, metrics, tool adapters).
- `llmemory_meter/memory_tools/`: integrations for Mem0, OpenAI Memory, MemGPT, Claude, Zep; copy `template_tool.py` when adding a new tool.
- `configs/`: YAML configs for benchmark runs (starter, comprehensive, single-tool variants).
- `examples/` and root scripts (`simple_example.py`, `benchmark_demo.py`, `benchmark_example.py`): usage demos.
- `docs/` and `KNOWN_ISSUES.md`: architecture notes and known limitations.
- `results/`, `logs/`, `quick-test/`, `comprehensive/`: generated outputs from runs.

## Build, Test, and Development Commands
- `pip install -r requirements.txt`: install dependencies.
- `python llmemory run`: run default benchmarks (`configs/starter.yml`).
- `python llmemory run --config comprehensive`: full suite (longer runtime).
- `python llmemory run --config quick-test.yml`: fast smoke test.
- `python llmemory create-config --output my_experiment.yml`: generate a new config in `configs/`.
- `python benchmark_demo.py`: run the demo script.
- `docker run -d --name qdrant -p 6333:6333 qdrant/qdrant`: required for Mem0 local vector store.

## Coding Style & Naming Conventions
- Python, 4-space indentation, follow existing module patterns in `llmemory_meter/`.
- Use `snake_case` for functions/variables, `PascalCase` for classes.
- Keep async APIs consistent with existing tools (`store_memory`, `retrieve_memory`, `chat`).
- Avoid introducing new formatting tools unless agreed; match surrounding style.

## Testing Guidelines
- No formal test suite is present. Validate changes with:
  - `python llmemory run --config quick-test.yml`
  - `python llmemory run --config comprehensive.yml`
- Name custom configs with `.yml` and store in `configs/`.

## Commit & Pull Request Guidelines
- Commit messages follow short, imperative summaries (e.g., "Fix MemGPT clear memory output").
- PRs should include: summary of changes, runtime impact (if any), and relevant config or command used.
- Attach sample output or screenshots when changes affect reporting or CLI UX.

## Configuration & Secrets
- Copy `.env.example` to `.env` and set API keys (tool-dependent).
- Keep keys out of commits; prefer environment variables for CI and local runs.
