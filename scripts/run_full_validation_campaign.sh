#!/bin/bash
set -euo pipefail

CONFIG_FILE="${1:-configs/industry-benchmarks.yml}"
RUN_COUNT="${2:-3}"
CAMPAIGN_DIR="${3:-results/validation_runs/campaign_$(date '+%Y%m%d_%H%M%S')}"
PYTHON_BIN="${PYTHON_BIN:-.venv/bin/python}"
JUDGE_MODEL="${JUDGE_MODEL:-gpt-4o}"
MEMBENCH_OFFICIAL_EVAL_SCRIPT="${MEMBENCH_OFFICIAL_EVAL_SCRIPT:-}"

log_phase() {
  local label="$1"
  printf "[%s] %s\n" "$(date '+%Y-%m-%d %H:%M:%S')" "$label"
}

if [ ! -x "$PYTHON_BIN" ]; then
  if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
  else
    echo "Python runtime not found: $PYTHON_BIN"
    exit 1
  fi
fi

if [ ! -f "$CONFIG_FILE" ]; then
  echo "Config file not found: $CONFIG_FILE"
  exit 1
fi

if ! [[ "$RUN_COUNT" =~ ^[0-9]+$ ]] || [ "$RUN_COUNT" -lt 1 ]; then
  echo "RUN_COUNT must be a positive integer (got: $RUN_COUNT)"
  exit 1
fi

resolve_results_file() {
  "$PYTHON_BIN" - "$CONFIG_FILE" <<'PY'
import sys
import yaml
from pathlib import Path
cfg = Path(sys.argv[1])
with cfg.open() as f:
    data = yaml.safe_load(f) or {}
print(data.get("output", {}).get("output_file", "industry_benchmarks_results.json"))
PY
}

resolve_enabled_tools() {
  "$PYTHON_BIN" - "$CONFIG_FILE" <<'PY'
import sys
import yaml
from pathlib import Path
cfg = Path(sys.argv[1])
with cfg.open() as f:
    data = yaml.safe_load(f) or {}
tools = [t.get("name") for t in data.get("memory_tools", []) if t.get("enabled") and t.get("name")]
print(" ".join(tools))
PY
}

resolve_longmemeval_subset() {
  "$PYTHON_BIN" - "$CONFIG_FILE" <<'PY'
import sys
import yaml
from pathlib import Path
cfg = Path(sys.argv[1])
with cfg.open() as f:
    data = yaml.safe_load(f) or {}
subset = "S"
for benchmark in data.get("benchmarks", []):
    if benchmark.get("name") == "LongMemEval":
        settings = benchmark.get("settings") or {}
        subset = str(settings.get("subset", "S"))
        break
print(subset)
PY
}

RESULTS_FILE="$(resolve_results_file)"
REQUIRED_TOOLS="$(resolve_enabled_tools)"
LONGMEMEVAL_SUBSET="$(resolve_longmemeval_subset)"
HYBRID_EVAL_DIR="benchmarks_data/hybrid_eval"

if [ -z "${MEMBENCH_OFFICIAL_EVAL_SCRIPT:-}" ]; then
  echo "MEMBENCH_OFFICIAL_EVAL_SCRIPT is not set. Export an official MemBench eval script path."
  exit 1
fi
if [ ! -f "$MEMBENCH_OFFICIAL_EVAL_SCRIPT" ]; then
  echo "Official MemBench eval script not found: $MEMBENCH_OFFICIAL_EVAL_SCRIPT"
  exit 1
fi

mkdir -p "$CAMPAIGN_DIR"
log_phase "Campaign directory: $CAMPAIGN_DIR"

log_phase "[Phase 0] Environment + baseline snapshots"
git rev-parse HEAD > "$CAMPAIGN_DIR/frozen_sha.txt" 2>/dev/null || echo "unknown" > "$CAMPAIGN_DIR/frozen_sha.txt"
"$PYTHON_BIN" --version > "$CAMPAIGN_DIR/python_version.txt" 2>&1 || true
"$PYTHON_BIN" -m pip freeze > "$CAMPAIGN_DIR/dependency_snapshot.txt" 2>/dev/null || true
"$PYTHON_BIN" scripts/record_baseline.py --config "$CONFIG_FILE" --output "$CAMPAIGN_DIR/baseline_snapshot.json"
"$PYTHON_BIN" scripts/check_tool_setup.py --config "$CONFIG_FILE"
"$PYTHON_BIN" scripts/check_benchmark_setup.py --config "$CONFIG_FILE" --sample-limit 1
"$PYTHON_BIN" scripts/check_operation_budget.py --config "$CONFIG_FILE"
"$PYTHON_BIN" scripts/check_membench_eval_setup.py --eval-script "$MEMBENCH_OFFICIAL_EVAL_SCRIPT" --require-official

for run_idx in $(seq 1 "$RUN_COUNT"); do
  run_dir="$CAMPAIGN_DIR/run_${run_idx}"
  mkdir -p "$run_dir"

  log_phase "[Phase 6] Run $run_idx/$RUN_COUNT benchmark execution"
  "$PYTHON_BIN" -u -m llmemory_meter.cli run --config "$CONFIG_FILE" | tee "$run_dir/run.log"

  if [ ! -f "$RESULTS_FILE" ]; then
    echo "Expected results file missing after run $run_idx: $RESULTS_FILE"
    exit 1
  fi
  cp "$RESULTS_FILE" "$run_dir/results.json"

  log_phase "[Phase 6] Run $run_idx schema check"
  "$PYTHON_BIN" scripts/check_results_schema.py "$run_dir/results.json" --require-benchmarks LongMemEval MemBench | tee "$run_dir/schema_check.log"

  log_phase "[Phase 6] Run $run_idx benchmark/tool coverage check"
  "$PYTHON_BIN" scripts/check_run_expectations.py "$run_dir/results.json" \
    --require-benchmarks LongMemEval MemBench \
    --require-tools $REQUIRED_TOOLS | tee "$run_dir/run_expectations.log"

  log_phase "[Phase 6] Run $run_idx reconciliation check"
  "$PYTHON_BIN" scripts/check_metrics_reconciliation.py \
    "$run_dir/results.json" \
    --report-file "$run_dir/reconciliation_report.json" | tee "$run_dir/reconciliation_check.log"

  mkdir -p "$HYBRID_EVAL_DIR"
  find "$HYBRID_EVAL_DIR" -maxdepth 1 -type f \
    \( -name '*_longmemeval_*_hypothesis.jsonl*' -o -name '*_membench_hypothesis.jsonl*' \) \
    -delete

  log_phase "[Phase 6] Run $run_idx LongMemEval eval"
  "$PYTHON_BIN" llmemory evaluate --benchmark LongMemEval --judge "$JUDGE_MODEL" --results "$run_dir/results.json" --config "$CONFIG_FILE" \
    | tee "$run_dir/longmemeval_eval.log"
  "$PYTHON_BIN" scripts/check_eval_artifacts.py \
    --results-file "$run_dir/results.json" \
    --benchmark LongMemEval \
    --subset "$LONGMEMEVAL_SUBSET" \
    --judge "$JUDGE_MODEL" | tee "$run_dir/longmemeval_artifacts_check.log"

  log_phase "[Phase 6] Run $run_idx MemBench eval"
  "$PYTHON_BIN" llmemory evaluate --benchmark MemBench --results "$run_dir/results.json" --eval-script "$MEMBENCH_OFFICIAL_EVAL_SCRIPT" \
    | tee "$run_dir/membench_eval.log"
  "$PYTHON_BIN" scripts/check_eval_artifacts.py \
    --results-file "$run_dir/results.json" \
    --benchmark MemBench | tee "$run_dir/membench_artifacts_check.log"

  if [ -d "$HYBRID_EVAL_DIR" ]; then
    rm -rf "$run_dir/hybrid_eval"
    mkdir -p "$run_dir/hybrid_eval"
    cp -R "$HYBRID_EVAL_DIR/." "$run_dir/hybrid_eval/"
  fi
done

log_phase "[Phase 7] Repeatability analysis"
"$PYTHON_BIN" scripts/build_repeatability_summary.py --campaign-dir "$CAMPAIGN_DIR"

RELEASE_ID="$(basename "$CAMPAIGN_DIR")"
RELEASE_DIR="results/final/${RELEASE_ID}"
log_phase "[Phase 7] Publication package assembly"
"$PYTHON_BIN" scripts/assemble_publication_release.py \
  --campaign-dir "$CAMPAIGN_DIR" \
  --output-dir "$RELEASE_DIR" \
  --config "$CONFIG_FILE"

log_phase "Campaign complete."
echo "Campaign artifacts: $CAMPAIGN_DIR"
echo "Release package: $RELEASE_DIR"
