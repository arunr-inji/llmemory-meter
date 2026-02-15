#!/bin/bash
set -euo pipefail

CONFIG_FILE="${1:-configs/industry-benchmarks-pilot.yml}"
PYTHON_BIN="${PYTHON_BIN:-.venv/bin/python}"
MEMBENCH_OFFICIAL_EVAL_SCRIPT="${MEMBENCH_OFFICIAL_EVAL_SCRIPT:-third_party/membench/official_eval.py}"
MEMBENCH_OFFICIAL_EVAL_METADATA="${MEMBENCH_OFFICIAL_EVAL_METADATA:-third_party/membench/official_eval.metadata.json}"
RUN_ID="$(date '+%Y%m%d_%H%M%S')"
RUN_CONTEXT_DIR="results/validation_runs/context_${RUN_ID}"

log_phase() {
  local label="$1"
  printf "[%s] %s\n" "$(date '+%Y-%m-%d %H:%M:%S')" "$label"
}

resolve_enabled_tools() {
"$PYTHON_BIN" - "$1" <<'PY'
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
"$PYTHON_BIN" - "$1" <<'PY'
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

if [ ! -x "$PYTHON_BIN" ]; then
  if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
  else
    echo "Python runtime not found: $PYTHON_BIN"
    exit 1
  fi
fi

if [ ! -f "$CONFIG_FILE" ]; then
  echo "Pilot config file not found: $CONFIG_FILE"
  exit 1
fi

if ! "$PYTHON_BIN" - <<'PY' >/dev/null 2>&1
import yaml
PY
then
  echo "PyYAML is not available in $PYTHON_BIN environment."
  echo "Install dependencies first (for example: pip install -r requirements.txt)."
  exit 1
fi

mkdir -p "$RUN_CONTEXT_DIR"
git rev-parse HEAD > "$RUN_CONTEXT_DIR/frozen_sha.txt" 2>/dev/null || echo "unknown" > "$RUN_CONTEXT_DIR/frozen_sha.txt"
"$PYTHON_BIN" --version > "$RUN_CONTEXT_DIR/python_version.txt" 2>&1 || true
"$PYTHON_BIN" -m pip freeze > "$RUN_CONTEXT_DIR/dependency_snapshot.txt" 2>/dev/null || true
rm -f scripts/fixtures/*.eval.jsonl scripts/fixtures/*.summary.json

REQUIRED_TOOLS="$(resolve_enabled_tools "$CONFIG_FILE")"
LONGMEMEVAL_SUBSET="$(resolve_longmemeval_subset "$CONFIG_FILE")"

if [ ! -f "$MEMBENCH_OFFICIAL_EVAL_SCRIPT" ]; then
  echo "Official MemBench eval script not found: $MEMBENCH_OFFICIAL_EVAL_SCRIPT"
  echo "Pin it first with scripts/pin_membench_official_eval.py or export MEMBENCH_OFFICIAL_EVAL_SCRIPT."
  exit 1
fi

log_phase "[1/8] Tool setup validation"
"$PYTHON_BIN" scripts/check_tool_setup.py --config "$CONFIG_FILE"

log_phase "[2/8] Benchmark setup validation"
"$PYTHON_BIN" scripts/check_benchmark_setup.py --config "$CONFIG_FILE" --sample-limit 1

log_phase "[3/8] Operation budget validation"
"$PYTHON_BIN" scripts/check_operation_budget.py --config "$CONFIG_FILE" --max-ops-per-tool 400 --max-total-ops 1200

log_phase "[4/8] MemBench official eval setup validation"
"$PYTHON_BIN" scripts/check_membench_eval_setup.py \
  --eval-script "$MEMBENCH_OFFICIAL_EVAL_SCRIPT" \
  --metadata-file "$MEMBENCH_OFFICIAL_EVAL_METADATA" \
  --require-official \
  --require-pinned-metadata

log_phase "[5/8] Pilot benchmark run"
"$PYTHON_BIN" -u -m llmemory_meter.cli run --config "$CONFIG_FILE"

RESULTS_FILE=$(
"$PYTHON_BIN" - "$CONFIG_FILE" <<'PY'
import sys
import yaml
from pathlib import Path
cfg = Path(sys.argv[1])
try:
    with cfg.open() as f:
        data = yaml.safe_load(f) or {}
except Exception as exc:
    print(f"ERROR: failed to parse config '{cfg}': {exc}", file=sys.stderr)
    raise SystemExit(2)
print(data.get("output", {}).get("output_file", "industry_benchmarks_pilot_results.json"))
PY
)

if [ -z "${RESULTS_FILE:-}" ]; then
  echo "Failed to resolve results file path from config: $CONFIG_FILE"
  exit 1
fi

if [ ! -f "$RESULTS_FILE" ]; then
  echo "Pilot results file not found: $RESULTS_FILE"
  exit 1
fi

log_phase "[6/8] Results schema validation"
"$PYTHON_BIN" scripts/check_results_schema.py "$RESULTS_FILE" --require-benchmarks LongMemEval MemBench

log_phase "[7/8] Metrics reconciliation"
"$PYTHON_BIN" scripts/check_metrics_reconciliation.py "$RESULTS_FILE" --report-file results/validation_runs/pilot_reconciliation_report.json

log_phase "[7b/8] Benchmark/tool coverage validation"
"$PYTHON_BIN" scripts/check_run_expectations.py "$RESULTS_FILE" \
  --require-benchmarks LongMemEval MemBench \
  --require-tools $REQUIRED_TOOLS

log_phase "[8/8] LongMemEval official eval"
"$PYTHON_BIN" llmemory evaluate --benchmark LongMemEval --judge gpt-4o --results "$RESULTS_FILE" --config "$CONFIG_FILE"
"$PYTHON_BIN" scripts/check_eval_artifacts.py --results-file "$RESULTS_FILE" --benchmark LongMemEval --subset "$LONGMEMEVAL_SUBSET" --judge gpt-4o

log_phase "[8b/8] MemBench official eval"
"$PYTHON_BIN" llmemory evaluate --benchmark MemBench --results "$RESULTS_FILE" --eval-script "$MEMBENCH_OFFICIAL_EVAL_SCRIPT"
"$PYTHON_BIN" scripts/check_eval_artifacts.py --results-file "$RESULTS_FILE" --benchmark MemBench

log_phase "[8c/8] Pilot publication bundle"
"$PYTHON_BIN" scripts/prepare_publication_bundle.py --results-file "$RESULTS_FILE" --output-dir results/final/pilot_bundle

log_phase "Pilot gate completed successfully."
