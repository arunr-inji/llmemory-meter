# Validation Matrix

This matrix defines what must pass before publishing benchmark results.

## Scope

- Framework: `llmemory_meter` CLI + benchmark loaders + hybrid evaluators
- Benchmarks: `LongMemEval` and `MemBench`
- Primary configs: `configs/industry-benchmarks.yml`, `configs/longmemeval-only.yml`
- Outputs: JSON results, log files, hybrid evaluation outputs

## Preflight (must pass first)

Run from repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # if needed
```

```bash
docker run -d --name qdrant -p 6333:6333 qdrant/qdrant
```

```bash
.venv/bin/python -m llmemory_meter.cli run --config configs/longmemeval-only.yml --verbose
```

Pass criteria:
- Config loads without missing required keys or missing required env vars.
- CLI exits `0` for smoke run.
- Results JSON is written.

## Validation Matrix

| ID | Area | Command | Pass Criteria | Artifact |
|---|---|---|---|---|
| VM-01 | CLI config resolution | `.venv/bin/python -m llmemory_meter.cli run --config configs/industry-benchmarks.yml --verbose` | Command starts benchmark execution and prints enabled tools/benchmarks | `logs/benchmark_*.log` |
| VM-02 | LongMemEval run | `./run_overnight.sh configs/longmemeval-only.yml` | Run completes with exit `0`; no benchmark-level error block for LongMemEval | `results/*longmemeval*.json` |
| VM-03 | Industry benchmarks run | `./run_overnight.sh configs/industry-benchmarks.yml` | Run completes with exit `0`; both LongMemEval and MemBench present in results | `results/*industry*.json` |
| VM-04 | LongMemEval hybrid eval | `.venv/bin/python llmemory evaluate --benchmark LongMemEval --judge gpt-4o --results <results_file> --config configs/industry-benchmarks.yml` | Per-tool evaluation prints success or accuracy and no traceback | `*_longmemeval_*_hypothesis.jsonl` |
| VM-05 | Judge model input hardening | `.venv/bin/python llmemory evaluate --benchmark LongMemEval --judge "bad-model" --results <results_file>` | Command fails fast with `Invalid judge model` | stderr/stdout message |
| VM-06 | Large dataset download UX | Trigger LongMemEval M dataset fetch | Download shows progress bar and continues writing chunks | terminal progress output |
| VM-07 | MemBench eval script path handling | `.venv/bin/python llmemory evaluate --benchmark MemBench --results <results_file> --eval-script <path>` | If script exists, command executes; if missing, returns actionable error | command output |
| VM-08 | Output schema integrity | Inspect final JSON keys for `config` and `results` plus per-benchmark `standard_results` | Required keys exist with parseable JSON | `results/*.json` |
| VM-09 | Reproducibility repeat run | Repeat VM-03 3 times on same commit/config | Runtime and success metrics are stable enough for reporting | `results/validation_runs/<date>/` |

## Execution Protocol

- Use one git commit SHA for all validation runs.
- Do not change `.env`, configs, or dataset files between repeated runs.
- Save each run log and JSON output into `results/validation_runs/<YYYYMMDD>/`.
- Record failures with root cause and rerun only after a code/config change.

## Exit Gates for Publishable Results

- All matrix rows pass at least once on release candidate commit.
- VM-03 and VM-09 pass on the same commit used for publication artifacts.
- No critical security issues remain open.
- Hybrid evaluation outputs are generated for LongMemEval with an approved judge model.
