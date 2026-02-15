#!/bin/bash
set -euo pipefail

STAGE="${1:-all}"
FINAL_READINESS_CONFIG="${2:-configs/industry-benchmarks.yml}"
PYTHON_BIN="${PYTHON_BIN:-.venv/bin/python}"
MEMBENCH_CANARY_EVAL_SCRIPT="scripts/membench_eval.py"
MEMBENCH_OFFICIAL_EVAL_SCRIPT="${MEMBENCH_OFFICIAL_EVAL_SCRIPT:-}"
RUN_ID="$(date '+%Y%m%d_%H%M%S')"
RUN_CONTEXT_DIR="results/validation_runs/context_${RUN_ID}"

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

resolve_results_file() {
  local config_file="$1"
  "$PYTHON_BIN" - "$config_file" <<'PY'
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
  local config_file="$1"
  "$PYTHON_BIN" - "$config_file" <<'PY'
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
  local config_file="$1"
  "$PYTHON_BIN" - "$config_file" <<'PY'
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

resolve_membench_eval_script() {
  local mode="$1"
  if [ "$mode" = "canary" ]; then
    if [ ! -f "$MEMBENCH_CANARY_EVAL_SCRIPT" ]; then
      echo "MemBench canary eval script not found: $MEMBENCH_CANARY_EVAL_SCRIPT" >&2
      exit 1
    fi
    echo "$MEMBENCH_CANARY_EVAL_SCRIPT"
    return
  fi

  if [ -z "${MEMBENCH_OFFICIAL_EVAL_SCRIPT:-}" ]; then
    echo "MEMBENCH_OFFICIAL_EVAL_SCRIPT is not set. Export an official MemBench eval script path." >&2
    exit 1
  fi
  if [ ! -f "$MEMBENCH_OFFICIAL_EVAL_SCRIPT" ]; then
    echo "Official MemBench eval script not found: $MEMBENCH_OFFICIAL_EVAL_SCRIPT" >&2
    exit 1
  fi
  echo "$MEMBENCH_OFFICIAL_EVAL_SCRIPT"
}

run_phase0_hygiene() {
  local config_file="$1"
  local enabled_tools="$2"
  local max_ops_per_tool="${3:-}"
  local max_total_ops="${4:-}"
  local membench_eval_script="${5:-$MEMBENCH_CANARY_EVAL_SCRIPT}"
  local require_official_eval="${6:-false}"

  mkdir -p "$RUN_CONTEXT_DIR"
  git rev-parse HEAD > "$RUN_CONTEXT_DIR/frozen_sha.txt" 2>/dev/null || echo "unknown" > "$RUN_CONTEXT_DIR/frozen_sha.txt"
  "$PYTHON_BIN" --version > "$RUN_CONTEXT_DIR/python_version.txt" 2>&1 || true
  "$PYTHON_BIN" -m pip freeze > "$RUN_CONTEXT_DIR/dependency_snapshot.txt" 2>/dev/null || true
  "$PYTHON_BIN" scripts/record_baseline.py --config "$config_file" --output "$RUN_CONTEXT_DIR/baseline_snapshot.json" >/dev/null 2>&1 || true
  rm -f scripts/fixtures/*.eval.jsonl scripts/fixtures/*.summary.json

  log_phase "[phase-0] environment + hygiene checks"
  "$PYTHON_BIN" scripts/check_tool_setup.py --config "$config_file"
  "$PYTHON_BIN" scripts/check_benchmark_setup.py --config "$config_file" --sample-limit 1

  if [ -n "$max_ops_per_tool" ] && [ -n "$max_total_ops" ]; then
    "$PYTHON_BIN" scripts/check_operation_budget.py \
      --config "$config_file" \
      --max-ops-per-tool "$max_ops_per_tool" \
      --max-total-ops "$max_total_ops"
  else
    "$PYTHON_BIN" scripts/check_operation_budget.py --config "$config_file"
  fi

  if [ "$require_official_eval" = "true" ]; then
    "$PYTHON_BIN" scripts/check_membench_eval_setup.py \
      --eval-script "$membench_eval_script" \
      --require-official
  else
    "$PYTHON_BIN" scripts/check_membench_eval_setup.py \
      --eval-script "$membench_eval_script"
  fi
}

run_smoke_stage() {
  local config_file="$1"
  local label="$2"
  local required_tools="$3"
  local results_file
  results_file="$(resolve_results_file "$config_file")"
  local enabled_tools
  enabled_tools="$(resolve_enabled_tools "$config_file")"
  local membench_eval_script
  membench_eval_script="$(resolve_membench_eval_script canary)"

  run_phase0_hygiene "$config_file" "$enabled_tools" "${4:-}" "${5:-}" "$membench_eval_script" "false"

  log_phase "[$label] Tool setup validation"
  "$PYTHON_BIN" scripts/check_tool_setup.py --config "$config_file"

  log_phase "[$label] Benchmark run"
  "$PYTHON_BIN" -u -m llmemory_meter.cli run --config "$config_file"

  if [ ! -f "$results_file" ]; then
    echo "Expected results file not found: $results_file"
    exit 1
  fi

  log_phase "[$label] Results schema validation"
  "$PYTHON_BIN" scripts/check_results_schema.py "$results_file" --require-benchmarks LongMemEval MemBench

  log_phase "[$label] Benchmark/tool coverage validation"
  "$PYTHON_BIN" scripts/check_run_expectations.py "$results_file" \
    --require-benchmarks LongMemEval MemBench \
    --require-tools $required_tools

  log_phase "[$label] Metrics reconciliation"
  "$PYTHON_BIN" scripts/check_metrics_reconciliation.py "$results_file" --report-file "results/validation_runs/${label}_reconciliation_report.json"

  log_phase "[$label] MemBench canary eval (diagnostic only)"
  "$PYTHON_BIN" llmemory evaluate --benchmark MemBench --results "$results_file" --eval-script "$membench_eval_script"
  "$PYTHON_BIN" scripts/check_eval_artifacts.py \
    --results-file "$results_file" \
    --benchmark MemBench \
    --summary-required-keys scored_count unscorable_count
}

run_final_readiness_stage() {
  local config_file="$1"
  local run_id run_dir checklist_file
  local results_file reconciliation_report bundle_dir
  local overall_failed=0
  local -a check_rows=()
  local required_tools subset
  local membench_eval_script
  required_tools="$(resolve_enabled_tools "$config_file")"
  subset="$(resolve_longmemeval_subset "$config_file")"
  membench_eval_script="$(resolve_membench_eval_script official)"

  run_id="$(date '+%Y%m%d_%H%M%S')"
  run_dir="results/validation_runs/final_readiness_${run_id}"
  checklist_file="$run_dir/final_readiness_checklist.md"
  mkdir -p "$run_dir"

  results_file="$(resolve_results_file "$config_file")"
  reconciliation_report="$run_dir/reconciliation_report.json"
  bundle_dir="$run_dir/bundle"

  run_phase0_hygiene "$config_file" "$required_tools" "" "" "$membench_eval_script" "true"

  run_check() {
    local check_id="$1"
    shift
    local log_file="$run_dir/${check_id}.log"
    log_phase "[final-readiness] $check_id"
    {
      printf '$'
      for arg in "$@"; do
        printf ' %q' "$arg"
      done
      printf '\n'
    } > "$log_file"

    if "$@" >> "$log_file" 2>&1; then
      check_rows+=("$check_id|PASS|$log_file")
    else
      check_rows+=("$check_id|FAIL|$log_file")
      overall_failed=1
    fi
  }

  log_phase "[final-readiness] capturing environment snapshot"
  if git rev-parse HEAD > "$run_dir/frozen_sha.txt" 2>/dev/null; then
    :
  else
    echo "unknown" > "$run_dir/frozen_sha.txt"
  fi
  "$PYTHON_BIN" --version > "$run_dir/python_version.txt" 2>&1 || true
  if "$PYTHON_BIN" scripts/record_baseline.py --config "$config_file" --output "$run_dir/baseline_snapshot.json" > "$run_dir/record_baseline.log" 2>&1; then
    check_rows+=("record_baseline|PASS|$run_dir/record_baseline.log")
  else
    check_rows+=("record_baseline|FAIL|$run_dir/record_baseline.log")
    overall_failed=1
  fi

  run_check "tool_setup_validation" "$PYTHON_BIN" scripts/check_tool_setup.py --config "$config_file"
  run_check "benchmark_run" "$PYTHON_BIN" -u -m llmemory_meter.cli run --config "$config_file"

  if [ -f "$results_file" ]; then
    cp "$results_file" "$run_dir/"
    check_rows+=("results_file_present|PASS|$run_dir/benchmark_run.log")
    run_check "results_schema_validation" "$PYTHON_BIN" scripts/check_results_schema.py "$results_file" --require-benchmarks LongMemEval MemBench
    run_check "run_expectations" "$PYTHON_BIN" scripts/check_run_expectations.py "$results_file" --require-benchmarks LongMemEval MemBench --require-tools $required_tools
    run_check "metrics_reconciliation" "$PYTHON_BIN" scripts/check_metrics_reconciliation.py "$results_file" --report-file "$reconciliation_report"
    run_check "longmemeval_eval" "$PYTHON_BIN" llmemory evaluate --benchmark LongMemEval --judge gpt-4o --results "$results_file" --config "$config_file"
    run_check "longmemeval_eval_artifacts" "$PYTHON_BIN" scripts/check_eval_artifacts.py --results-file "$results_file" --benchmark LongMemEval --subset "$subset" --judge gpt-4o
    run_check "membench_eval_official" "$PYTHON_BIN" llmemory evaluate --benchmark MemBench --results "$results_file" --eval-script "$membench_eval_script"
    run_check "membench_eval_artifacts" "$PYTHON_BIN" scripts/check_eval_artifacts.py --results-file "$results_file" --benchmark MemBench
    run_check "publication_bundle" "$PYTHON_BIN" scripts/prepare_publication_bundle.py --results-file "$results_file" --output-dir "$bundle_dir"
  else
    check_rows+=("results_file_present|FAIL|$run_dir/benchmark_run.log")
    overall_failed=1
  fi

  {
    echo "# Final Readiness Checklist"
    echo
    echo "- Timestamp: $(date '+%Y-%m-%d %H:%M:%S')"
    echo "- Config: \`$config_file\`"
    echo "- Results file (expected): \`$results_file\`"
    echo "- Frozen SHA: \`$(cat "$run_dir/frozen_sha.txt")\`"
    echo
    echo "## Checks"
    echo
    echo "| Check | Status | Log |"
    echo "|---|---|---|"
    for row in "${check_rows[@]}"; do
      IFS='|' read -r check_id status log_file <<< "$row"
      echo "| $check_id | $status | \`$log_file\` |"
    done
    echo
    if [ "$overall_failed" -eq 0 ]; then
      echo "## Final Readiness Result: PASS"
    else
      echo "## Final Readiness Result: FAIL"
    fi
  } > "$checklist_file"

  log_phase "[final-readiness] checklist artifact: $checklist_file"

  if [ "$overall_failed" -ne 0 ]; then
    log_phase "[final-readiness] one or more gates failed."
    return 1
  fi

  log_phase "[final-readiness] all gates passed."
  return 0
}

case "$STAGE" in
  preflight)
    log_phase "[preflight] Validation fixture suite"
    ./scripts/validate_and_publish_prep.sh scripts/fixtures/industry_fixture.json
    ;;
  smoke-mem0)
    run_smoke_stage "configs/industry-benchmarks-smoke-mem0.yml" "smoke_mem0" "mem0" "120" "120"
    ;;
  smoke-memgpt)
    run_smoke_stage "configs/industry-benchmarks-smoke-memgpt.yml" "smoke_memgpt" "memgpt" "120" "120"
    ;;
  smoke-zep)
    run_smoke_stage "configs/industry-benchmarks-smoke-zep.yml" "smoke_zep" "zep" "120" "120"
    ;;
  smoke-all)
    run_smoke_stage "configs/industry-benchmarks-smoke-all-tools.yml" "smoke_all_tools" "mem0 memgpt zep" "120" "360"
    ;;
  pilot)
    log_phase "[pilot] Full pilot gate"
    run_phase0_hygiene "configs/industry-benchmarks-pilot.yml" "mem0 memgpt zep" "400" "1200" "$(resolve_membench_eval_script official)" "true"
    ./scripts/run_pilot_gate.sh configs/industry-benchmarks-pilot.yml
    ;;
  final-readiness)
    run_final_readiness_stage "$FINAL_READINESS_CONFIG"
    ;;
  all)
    log_phase "[preflight] Validation fixture suite"
    ./scripts/validate_and_publish_prep.sh scripts/fixtures/industry_fixture.json
    run_smoke_stage "configs/industry-benchmarks-smoke-mem0.yml" "smoke_mem0" "mem0" "120" "120"
    run_smoke_stage "configs/industry-benchmarks-smoke-memgpt.yml" "smoke_memgpt" "memgpt" "120" "120"
    run_smoke_stage "configs/industry-benchmarks-smoke-zep.yml" "smoke_zep" "zep" "120" "120"
    run_smoke_stage "configs/industry-benchmarks-smoke-all-tools.yml" "smoke_all_tools" "mem0 memgpt zep" "120" "360"
    log_phase "[pilot] Full pilot gate"
    run_phase0_hygiene "configs/industry-benchmarks-pilot.yml" "mem0 memgpt zep" "400" "1200" "$(resolve_membench_eval_script official)" "true"
    ./scripts/run_pilot_gate.sh configs/industry-benchmarks-pilot.yml
    run_final_readiness_stage "configs/industry-benchmarks-pilot.yml"
    ;;
  *)
    echo "Unknown stage: $STAGE"
    echo "Usage: $0 [preflight|smoke-mem0|smoke-memgpt|smoke-zep|smoke-all|pilot|final-readiness|all] [final-readiness-config]"
    exit 1
    ;;
esac

log_phase "Incremental validation stage '$STAGE' completed."
