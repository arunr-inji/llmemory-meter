#!/bin/bash
set -euo pipefail

CONFIG_FILE="${1:-configs/industry-benchmarks-pilot.yml}"
PYTHON_BIN="${PYTHON_BIN:-.venv/bin/python}"

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

echo "[1/7] Tool setup validation"
"$PYTHON_BIN" scripts/check_tool_setup.py --config "$CONFIG_FILE"

echo "[2/7] Pilot benchmark run"
"$PYTHON_BIN" -m llmemory_meter.cli run --config "$CONFIG_FILE"

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

echo "[3/7] Results schema validation"
"$PYTHON_BIN" scripts/check_results_schema.py "$RESULTS_FILE" --require-benchmarks LongMemEval MemBench

echo "[4/7] Metrics reconciliation"
"$PYTHON_BIN" scripts/check_metrics_reconciliation.py "$RESULTS_FILE" --report-file results/validation_runs/pilot_reconciliation_report.json

echo "[5/7] LongMemEval official eval"
"$PYTHON_BIN" llmemory evaluate --benchmark LongMemEval --judge gpt-4o --results "$RESULTS_FILE" --config "$CONFIG_FILE"

echo "[6/7] MemBench deterministic eval"
"$PYTHON_BIN" llmemory evaluate --benchmark MemBench --results "$RESULTS_FILE" --eval-script scripts/membench_eval.py

echo "[7/7] Pilot publication bundle"
"$PYTHON_BIN" scripts/prepare_publication_bundle.py --results-file "$RESULTS_FILE" --output-dir results/final/pilot_bundle

echo "Pilot gate completed successfully."
