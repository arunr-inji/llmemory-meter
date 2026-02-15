#!/usr/bin/env python3
"""Recompute benchmark metrics from raw step results and compare against reported output."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from llmemory_meter.metrics import MetricsCalculator
from llmemory_meter.workload import StepResult, WorkloadResult


def _is_close(a: Any, b: Any, tol: float = 1e-6) -> bool:
    if isinstance(a, float) or isinstance(b, float):
        try:
            return abs(float(a) - float(b)) <= tol
        except (TypeError, ValueError):
            return False
    return a == b


def _reconstruct_workload_result(tool_name: str, workload_name: str, payload: Dict[str, Any]) -> WorkloadResult:
    step_results = []
    for step in payload.get("step_results", []):
        step_results.append(
            StepResult(
                step_index=step.get("step_index", 0),
                action=step.get("action", "unknown"),
                response=step.get("response", ""),
                latency_ms=step.get("latency_ms", 0.0),
                tokens_used=step.get("tokens_used"),
                input_tokens=step.get("input_tokens"),
                output_tokens=step.get("output_tokens"),
                model=step.get("model"),
                success=step.get("success", False),
                error_message=step.get("error_message"),
                metadata=step.get("metadata"),
                accuracy=step.get("accuracy"),
                accuracy_by_provider=step.get("accuracy_by_provider"),
            )
        )

    timestamp_raw = payload.get("timestamp")
    if timestamp_raw:
        timestamp = datetime.fromisoformat(timestamp_raw)
    else:
        timestamp = datetime.utcnow()

    return WorkloadResult(
        tool_name=tool_name,
        workload_name=workload_name,
        step_results=step_results,
        total_latency_ms=payload.get("total_latency_ms", 0.0),
        total_tokens_used=payload.get("total_tokens_used", 0),
        success_rate=payload.get("success_rate", 0.0),
        timestamp=timestamp,
    )


def _validate_workload_invariants(result: WorkloadResult) -> List[str]:
    mismatches: List[str] = []

    total_tokens = sum(sr.tokens_used or 0 for sr in result.step_results)
    if total_tokens != result.total_tokens_used:
        mismatches.append(
            f"{result.tool_name}/{result.workload_name}: total_tokens_used={result.total_tokens_used} "
            f"but recomputed={total_tokens}"
        )

    total_steps = len(result.step_results)
    computed_success_rate = (
        sum(1 for sr in result.step_results if sr.success) / total_steps if total_steps else 0.0
    )
    if not _is_close(computed_success_rate, result.success_rate):
        mismatches.append(
            f"{result.tool_name}/{result.workload_name}: success_rate={result.success_rate} "
            f"but recomputed={computed_success_rate}"
        )

    for idx, sr in enumerate(result.step_results):
        if sr.latency_ms < 0:
            mismatches.append(
                f"{result.tool_name}/{result.workload_name}: step {idx} has negative latency {sr.latency_ms}"
            )
        if sr.tokens_used is not None and sr.tokens_used < 0:
            mismatches.append(
                f"{result.tool_name}/{result.workload_name}: step {idx} has negative tokens {sr.tokens_used}"
            )

    return mismatches


def _compare_reported_metrics(
    benchmark_name: str,
    reported: Dict[str, Any],
    recomputed: Dict[str, Any],
) -> List[str]:
    mismatches: List[str] = []
    for key, expected_value in recomputed.items():
        if key not in reported:
            mismatches.append(f"{benchmark_name}: missing metric key '{key}' in reported overall metrics")
            continue
        reported_value = reported[key]
        if isinstance(expected_value, dict) and isinstance(reported_value, dict):
            for sub_key, sub_expected in expected_value.items():
                if sub_key not in reported_value:
                    mismatches.append(f"{benchmark_name}: missing sub-key '{key}.{sub_key}'")
                    continue
                if not _is_close(sub_expected, reported_value[sub_key]):
                    mismatches.append(
                        f"{benchmark_name}: mismatch '{key}.{sub_key}' reported={reported_value[sub_key]} "
                        f"recomputed={sub_expected}"
                    )
        else:
            if not _is_close(expected_value, reported_value):
                mismatches.append(
                    f"{benchmark_name}: mismatch '{key}' reported={reported_value} recomputed={expected_value}"
                )
    return mismatches


def reconcile(results_file: Path, report_file: Path) -> Tuple[bool, Dict[str, Any]]:
    with results_file.open("r", encoding="utf-8") as f:
        data = json.load(f)

    config = data.get("config", {})
    benchmarks = data.get("results", {})

    output: Dict[str, Any] = {
        "results_file": str(results_file),
        "checked_at": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "benchmark_reports": {},
        "mismatches": [],
    }

    for benchmark_name, benchmark_payload in benchmarks.items():
        standard_results = benchmark_payload.get("standard_results", {})
        workload_results = standard_results.get("workload_results", {})
        reported_overall = standard_results.get("overall_metrics", {})

        by_tool: Dict[str, List[WorkloadResult]] = {}
        benchmark_mismatches: List[str] = []

        for workload_name, tool_results in workload_results.items():
            if not isinstance(tool_results, dict):
                benchmark_mismatches.append(
                    f"{benchmark_name}/{workload_name}: tool_results must be an object"
                )
                continue
            for tool_name, payload in tool_results.items():
                if not isinstance(payload, dict):
                    benchmark_mismatches.append(
                        f"{benchmark_name}/{workload_name}/{tool_name}: payload must be an object"
                    )
                    continue
                wr = _reconstruct_workload_result(tool_name, workload_name, payload)
                by_tool.setdefault(tool_name, []).append(wr)
                benchmark_mismatches.extend(_validate_workload_invariants(wr))

        recomputed_overall: Dict[str, Any] = {}
        metrics_config = config.get("metrics", {})
        pricing_config = config.get("pricing", {})
        calc_config = {"metrics": metrics_config, "pricing": pricing_config}

        for tool_name, tool_workloads in by_tool.items():
            step_count = sum(len(w.step_results) for w in tool_workloads)
            if step_count == 0:
                if reported_overall and tool_name in reported_overall:
                    benchmark_mismatches.append(
                        f"{benchmark_name}/{tool_name}: cannot recompute overall metrics with zero step results"
                    )
                continue
            metrics = MetricsCalculator.calculate_metrics(tool_workloads, config=calc_config)
            recomputed_overall[tool_name] = metrics.to_dict()

        if reported_overall:
            for tool_name, reported_tool_metrics in reported_overall.items():
                recomputed_tool_metrics = recomputed_overall.get(tool_name)
                if recomputed_tool_metrics is None:
                    benchmark_mismatches.append(
                        f"{benchmark_name}: reported tool '{tool_name}' missing from recomputed metrics"
                    )
                    continue
                benchmark_mismatches.extend(
                    _compare_reported_metrics(
                        f"{benchmark_name}/{tool_name}",
                        reported_tool_metrics,
                        recomputed_tool_metrics,
                    )
                )

        output["benchmark_reports"][benchmark_name] = {
            "tools_recomputed": sorted(recomputed_overall.keys()),
            "has_reported_overall_metrics": bool(reported_overall),
            "recomputed_overall_metrics": recomputed_overall,
            "mismatch_count": len(benchmark_mismatches),
            "mismatches": benchmark_mismatches,
        }
        output["mismatches"].extend(benchmark_mismatches)

    output["status"] = "pass" if not output["mismatches"] else "fail"

    report_file.parent.mkdir(parents=True, exist_ok=True)
    with report_file.open("w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)
        f.write("\n")

    return (not output["mismatches"]), output


def main() -> int:
    parser = argparse.ArgumentParser(description="Reconcile reported metrics with recomputed metrics.")
    parser.add_argument("results_file", type=Path, help="Results JSON file")
    parser.add_argument(
        "--report-file",
        type=Path,
        default=None,
        help="Output report path (default: <results_dir>/reconciliation_report.json)",
    )
    args = parser.parse_args()

    if not args.results_file.exists():
        print(f"Results file not found: {args.results_file}")
        return 1

    report_file = args.report_file or args.results_file.parent / "reconciliation_report.json"
    passed, output = reconcile(args.results_file, report_file)

    print(f"Reconciliation report written: {report_file}")
    if passed:
        print("Reconciliation passed with zero mismatches.")
        return 0

    print(f"Reconciliation failed with {len(output['mismatches'])} mismatch(es).")
    for mismatch in output["mismatches"][:20]:
        print(f"- {mismatch}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
