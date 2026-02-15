#!/usr/bin/env python3
"""Build repeatability summary artifacts across validation runs."""

from __future__ import annotations

import argparse
import csv
import json
import re
import statistics
from pathlib import Path
from typing import Dict, List, Tuple


METRIC_KEYS = [
    "success_rate",
    "avg_latency_ms",
    "p95_latency_ms",
    "p99_latency_ms",
    "total_tokens",
    "avg_tokens_per_query",
    "total_cost_usd",
    "cost_priced_queries",
]


def _safe_float(value):
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _extract_longmemeval_accuracy(log_file: Path) -> Dict[str, float]:
    """Parse `llmemory evaluate --benchmark LongMemEval` summary lines."""
    out: Dict[str, float] = {}
    if not log_file.exists():
        return out
    pattern = re.compile(r"•\s+([a-zA-Z0-9_]+):\s+([0-9]+(?:\.[0-9]+)?)% accuracy")
    for line in log_file.read_text(encoding="utf-8", errors="replace").splitlines():
        m = pattern.search(line)
        if not m:
            continue
        tool_name = m.group(1)
        pct = float(m.group(2))
        out[tool_name] = pct / 100.0
    return out


def _extract_membench_accuracy(hybrid_eval_dir: Path) -> Dict[str, Dict[str, float]]:
    out: Dict[str, Dict[str, float]] = {}
    if not hybrid_eval_dir.exists():
        return out
    for summary_file in hybrid_eval_dir.glob("*_membench_hypothesis.jsonl.summary.json"):
        name = summary_file.name
        tool_name = name.split("_membench_hypothesis.jsonl.summary.json", 1)[0]
        try:
            with summary_file.open("r", encoding="utf-8") as f:
                payload = json.load(f)
        except Exception:
            continue
        tool_entry: Dict[str, float] = {}
        contains = _safe_float(payload.get("accuracy_contains"))
        exact = _safe_float(payload.get("accuracy_exact"))
        if contains is not None:
            tool_entry["accuracy_contains"] = contains
        if exact is not None:
            tool_entry["accuracy_exact"] = exact
        if tool_entry:
            out[tool_name] = tool_entry
    return out


def _extract_recomputed_metrics(reconciliation_report: Path) -> Tuple[Dict[Tuple[str, str, str], float], Dict[str, int]]:
    metrics: Dict[Tuple[str, str, str], float] = {}
    mismatch_summary: Dict[str, int] = {}
    if not reconciliation_report.exists():
        return metrics, mismatch_summary
    with reconciliation_report.open("r", encoding="utf-8") as f:
        report = json.load(f)
    mismatch_summary = report.get("mismatch_summary", {}) if isinstance(report, dict) else {}
    benchmark_reports = report.get("benchmark_reports", {})
    if not isinstance(benchmark_reports, dict):
        return metrics, mismatch_summary

    for benchmark_name, benchmark_payload in benchmark_reports.items():
        if not isinstance(benchmark_payload, dict):
            continue
        recomputed = benchmark_payload.get("recomputed_overall_metrics", {})
        if not isinstance(recomputed, dict):
            continue
        for tool_name, tool_metrics in recomputed.items():
            if not isinstance(tool_metrics, dict):
                continue
            for metric_key in METRIC_KEYS:
                value = _safe_float(tool_metrics.get(metric_key))
                if value is None:
                    continue
                metrics[(benchmark_name, tool_name, metric_key)] = value
    return metrics, mismatch_summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Build repeatability summary across run directories.")
    parser.add_argument("--campaign-dir", type=Path, required=True, help="Directory containing run_*/ artifacts")
    parser.add_argument("--output-csv", type=Path, default=None, help="Output CSV path")
    parser.add_argument("--output-notes", type=Path, default=None, help="Output Markdown notes path")
    args = parser.parse_args()

    campaign_dir = args.campaign_dir
    if not campaign_dir.exists():
        print(f"Campaign directory not found: {campaign_dir}")
        return 1

    run_dirs = sorted([p for p in campaign_dir.iterdir() if p.is_dir() and p.name.startswith("run_")])
    if not run_dirs:
        print(f"No run directories found under: {campaign_dir}")
        return 1

    output_csv = args.output_csv or campaign_dir / "repeatability_summary.csv"
    output_notes = args.output_notes or campaign_dir / "repeatability_notes.md"
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    output_notes.parent.mkdir(parents=True, exist_ok=True)

    by_metric: Dict[Tuple[str, str, str], Dict[str, float]] = {}
    notes: List[str] = []
    mismatch_totals: Dict[str, int] = {}

    for run_dir in run_dirs:
        run_name = run_dir.name
        recon_file = run_dir / "reconciliation_report.json"
        run_metrics, mismatch_summary = _extract_recomputed_metrics(recon_file)
        for key, value in run_metrics.items():
            by_metric.setdefault(key, {})[run_name] = value

        for mtype, count in mismatch_summary.items():
            mismatch_totals[mtype] = mismatch_totals.get(mtype, 0) + int(count)

        long_eval_log = run_dir / "longmemeval_eval.log"
        long_scores = _extract_longmemeval_accuracy(long_eval_log)
        for tool_name, score in long_scores.items():
            key = ("LongMemEval", tool_name, "accuracy_longmemeval")
            by_metric.setdefault(key, {})[run_name] = score
        if not long_scores:
            notes.append(f"- {run_name}: no LongMemEval accuracy parsed from {long_eval_log}")

        membench_scores = _extract_membench_accuracy(run_dir / "hybrid_eval")
        for tool_name, metric_map in membench_scores.items():
            if "accuracy_contains" in metric_map:
                key = ("MemBench", tool_name, "accuracy_membench_contains")
                by_metric.setdefault(key, {})[run_name] = metric_map["accuracy_contains"]
            if "accuracy_exact" in metric_map:
                key = ("MemBench", tool_name, "accuracy_membench_exact")
                by_metric.setdefault(key, {})[run_name] = metric_map["accuracy_exact"]
        if not membench_scores:
            notes.append(f"- {run_name}: no MemBench summary files found under {run_dir / 'hybrid_eval'}")

    run_names = [p.name for p in run_dirs]
    headers = ["benchmark", "tool", "metric", *run_names, "mean", "std", "count"]

    with output_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        for key in sorted(by_metric.keys()):
            benchmark, tool_name, metric = key
            values = [by_metric[key].get(run_name) for run_name in run_names]
            numeric_values = [v for v in values if v is not None]
            row = {
                "benchmark": benchmark,
                "tool": tool_name,
                "metric": metric,
                "mean": f"{statistics.mean(numeric_values):.8f}" if numeric_values else "",
                "std": f"{statistics.pstdev(numeric_values):.8f}" if len(numeric_values) > 1 else "0.00000000" if len(numeric_values) == 1 else "",
                "count": len(numeric_values),
            }
            for run_name, value in zip(run_names, values):
                row[run_name] = "" if value is None else f"{value:.8f}"
            writer.writerow(row)

    with output_notes.open("w", encoding="utf-8") as f:
        f.write("# Repeatability Notes\n\n")
        f.write(f"- Campaign directory: `{campaign_dir}`\n")
        f.write(f"- Runs analyzed: {', '.join(run_names)}\n")
        f.write(f"- Summary CSV: `{output_csv}`\n\n")
        if mismatch_totals:
            f.write("## Reconciliation Mismatch Totals (all runs)\n\n")
            for key in sorted(mismatch_totals.keys()):
                f.write(f"- {key}: {mismatch_totals[key]}\n")
            f.write("\n")
        if notes:
            f.write("## Warnings\n\n")
            for note in notes:
                f.write(f"{note}\n")
            f.write("\n")
        else:
            f.write("## Warnings\n\n- None.\n")

    print(f"Repeatability summary written: {output_csv}")
    print(f"Repeatability notes written: {output_notes}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
