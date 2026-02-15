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

## Fast Path Automation

Run the offline validation + publication-prep pipeline:

```bash
./scripts/validate_and_publish_prep.sh scripts/fixtures/industry_fixture.json
```

This validates CLI wiring, results schema, judge-model hardening, and generates a publication bundle with checksums.
It also runs deterministic metric fixtures, reconciliation checks, and MemBench deterministic eval fixture checks.

## Staged Validation Automation

Use staged gates before expensive runs:

```bash
./scripts/run_incremental_validation.sh preflight
./scripts/run_incremental_validation.sh smoke-mem0
./scripts/run_incremental_validation.sh smoke-memgpt
./scripts/run_incremental_validation.sh smoke-zep
./scripts/run_incremental_validation.sh smoke-all
python3 scripts/pin_membench_official_eval.py \
  --source-script /absolute/path/to/official_membench_eval.py \
  --repo-url https://github.com/<official-org>/<official-membench-repo> \
  --commit <pinned_commit_sha>
export MEMBENCH_OFFICIAL_EVAL_SCRIPT=third_party/membench/official_eval.py
export MEMBENCH_OFFICIAL_EVAL_METADATA=third_party/membench/official_eval.metadata.json
./scripts/run_incremental_validation.sh pilot
./scripts/run_incremental_validation.sh final-readiness configs/industry-benchmarks-pilot.yml
```

For full publication campaign (3-run validation + repeatability + release package):

```bash
./scripts/run_full_validation_campaign.sh configs/industry-benchmarks.yml 3
```

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
| VM-10 | Metric invariant reconciliation | `python3 scripts/check_metrics_reconciliation.py <results_file> --report-file <report_path>` | Zero mismatches between raw step data and reported metrics | `reconciliation_report.json` |
| VM-11 | Deterministic metric fixture checks | `python3 scripts/check_metric_fixtures.py` | Percentile/token/success/cost fixture cases pass | fixture check output |
| VM-12 | MemBench canary evaluator (diagnostic only) | `python3 scripts/membench_eval.py <hypothesis_file.jsonl>` | Produces `.eval.jsonl` + `.summary.json` and exits 0 | `<hypothesis>.eval.jsonl`, `<hypothesis>.summary.json` |
| VM-12b | MemBench official eval pinning | `python3 scripts/pin_membench_official_eval.py --source-script <official_script.py> --repo-url <official_repo> --commit <sha>` | Pinned script and metadata are written under `third_party/membench/` with commit + sha256 | `third_party/membench/official_eval.py`, `third_party/membench/official_eval.metadata.json` |
| VM-12c | MemBench official eval readiness | `python3 scripts/check_membench_eval_setup.py --eval-script "$MEMBENCH_OFFICIAL_EVAL_SCRIPT" --metadata-file "$MEMBENCH_OFFICIAL_EVAL_METADATA" --require-official --require-pinned-metadata` | Script executes on fixture, metadata is valid, and script sha256 matches pinned metadata | fixture `.eval.jsonl` + `.summary.json` |
| VM-13 | Tool setup validation | `python3 scripts/check_tool_setup.py --config configs/industry-benchmarks-pilot.yml` | Enabled tools have required env vars; Mem0 qdrant endpoint reachable | command output |
| VM-14 | Pilot gate | `./scripts/run_pilot_gate.sh configs/industry-benchmarks-pilot.yml` | Pilot run + eval + reconciliation + bundle all pass | `results/validation_runs/pilot_reconciliation_report.json`, `results/final/pilot_bundle/` |
| VM-15 | Per-tool smoke gates | `./scripts/run_incremental_validation.sh smoke-mem0|smoke-memgpt|smoke-zep` | Each tool passes isolated run + schema + coverage + reconciliation + MemBench eval | `results/validation_runs/smoke_*` |
| VM-16 | Multi-tool smoke | `./scripts/run_incremental_validation.sh smoke-all` | All required tools appear in both benchmark outputs; no benchmark-level fatal errors | `results/validation_runs/smoke_all_tools_*` |
| VM-17 | Final readiness checklist | `./scripts/run_incremental_validation.sh final-readiness <config>` | Checklist shows `Final Readiness Result: PASS` with no failed checks | `results/validation_runs/final_readiness_*/final_readiness_checklist.md` |
| VM-18 | Full campaign and repeatability | `./scripts/run_full_validation_campaign.sh configs/industry-benchmarks.yml 3` | 3 runs pass strict gates; repeatability summary + release package produced | `results/validation_runs/campaign_*/`, `results/final/campaign_*/` |
| VM-19 | Benchmark dataset setup fail-fast | `python3 scripts/check_benchmark_setup.py --config <config> --sample-limit 1` | MemBench + LongMemEval datasets load at least one workload before long benchmark execution | command output |
| VM-20 | Operation budget precheck | `python3 scripts/check_operation_budget.py --config <config> [--max-ops-per-tool N --max-total-ops M]` | Estimated operation counts are visible and within configured budget gates before paid execution | command output |

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
- MemBench official evaluation outputs are generated and reproducible.
- Publication package includes pinned MemBench evaluator script and metadata (repo + commit + sha256).
