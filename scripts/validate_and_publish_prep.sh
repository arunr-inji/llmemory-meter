#!/bin/bash
set -euo pipefail

RESULTS_FILE="${1:-scripts/fixtures/industry_fixture.json}"
PYTHON_BIN="${PYTHON_BIN:-.venv/bin/python}"

if [ ! -x "$PYTHON_BIN" ]; then
  if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
  else
    echo "Python runtime not found at $PYTHON_BIN and python3 is unavailable."
    echo "Create a venv first: python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
    exit 1
  fi
fi

if [ ! -f "$RESULTS_FILE" ]; then
  echo "Results file not found: $RESULTS_FILE"
  exit 1
fi

echo "[0/8] Baseline snapshot"
"$PYTHON_BIN" scripts/record_baseline.py --config configs/industry-benchmarks.yml

echo "[1/8] CLI sanity check"
"$PYTHON_BIN" -m llmemory_meter.cli --help > /dev/null

echo "[2/8] Results schema validation"
"$PYTHON_BIN" scripts/check_results_schema.py \
  "$RESULTS_FILE" \
  --require-benchmarks LongMemEval MemBench

echo "[3/8] Judge model guard validation"
set +e
"$PYTHON_BIN" -c "from llmemory_meter.hybrid_evaluator import LongMemEvalEvaluator; LongMemEvalEvaluator._validate_judge_model('bad-model')" 2>/dev/null
STATUS=$?
set -e
if [ $STATUS -eq 0 ]; then
  echo "Expected invalid judge model to fail but it passed."
  exit 1
fi

echo "[4/8] Deterministic metric fixture checks"
"$PYTHON_BIN" scripts/check_metric_fixtures.py

echo "[5/8] Reconciliation checks"
"$PYTHON_BIN" scripts/check_metrics_reconciliation.py \
  "$RESULTS_FILE" \
  --report-file results/validation_runs/reconciliation_report.json

echo "[6/8] Reconciliation fixture checks"
"$PYTHON_BIN" scripts/check_metrics_reconciliation.py \
  scripts/fixtures/reconciliation_fixture.json \
  --report-file results/validation_runs/reconciliation_fixture_report.json

echo "[7/8] MemBench deterministic eval fixture"
"$PYTHON_BIN" scripts/membench_eval.py scripts/fixtures/membench_hypothesis_fixture.jsonl

echo "[8/8] Publication bundle generation"
"$PYTHON_BIN" scripts/prepare_publication_bundle.py --results-file "$RESULTS_FILE"

echo "Validation and publication-prep pipeline completed."
