#!/usr/bin/env python3
"""Validate hybrid evaluation artifacts exist and are parseable."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List, Optional
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from llmemory_meter.benchmark_loader import BenchmarkLoader


def _load_tools(results_file: Path, benchmark_name: str) -> List[str]:
    with results_file.open("r", encoding="utf-8") as f:
        data = json.load(f)

    benchmark = data.get("results", {}).get(benchmark_name)
    if not isinstance(benchmark, dict):
        return []

    workload_results = benchmark.get("standard_results", {}).get("workload_results", {})
    if not isinstance(workload_results, dict):
        return []

    tools = set()
    for payload in workload_results.values():
        if isinstance(payload, dict):
            tools.update(t for t in payload.keys() if isinstance(t, str))
    return sorted(tools)


def _check_longmemeval(tool_name: str, output_dir: Path, subset: str, judge: str) -> List[str]:
    issues: List[str] = []
    hypothesis = output_dir / f"{tool_name}_longmemeval_{subset.lower()}_hypothesis.jsonl"
    eval_log = Path(f"{hypothesis}.eval-results-{judge}")

    if not hypothesis.exists() or hypothesis.stat().st_size == 0:
        issues.append(f"{tool_name}: missing or empty LongMemEval hypothesis file: {hypothesis}")
    if not eval_log.exists() or eval_log.stat().st_size == 0:
        issues.append(f"{tool_name}: missing or empty LongMemEval eval log: {eval_log}")

    return issues


def _check_membench(tool_name: str, output_dir: Path, required_summary_keys: Optional[List[str]]) -> List[str]:
    issues: List[str] = []
    hypothesis = output_dir / f"{tool_name}_membench_hypothesis.jsonl"
    row_eval = Path(f"{hypothesis}.eval.jsonl")
    summary = Path(f"{hypothesis}.summary.json")

    if not hypothesis.exists() or hypothesis.stat().st_size == 0:
        issues.append(f"{tool_name}: missing or empty MemBench hypothesis file: {hypothesis}")
    if not row_eval.exists() or row_eval.stat().st_size == 0:
        issues.append(f"{tool_name}: missing or empty MemBench row eval file: {row_eval}")
    if not summary.exists() or summary.stat().st_size == 0:
        issues.append(f"{tool_name}: missing or empty MemBench summary file: {summary}")
        return issues

    try:
        with summary.open("r", encoding="utf-8") as f:
            parsed = json.load(f)
        if not isinstance(parsed, dict):
            issues.append(f"{tool_name}: MemBench summary is not an object: {summary}")
            return issues
        for key in required_summary_keys or []:
            if key not in parsed:
                issues.append(f"{tool_name}: MemBench summary missing required key '{key}': {summary}")
    except Exception as exc:
        issues.append(f"{tool_name}: failed to parse MemBench summary {summary}: {exc}")
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description="Check hybrid evaluation artifacts.")
    parser.add_argument("--results-file", type=Path, required=True, help="Benchmark results JSON")
    parser.add_argument(
        "--benchmark",
        required=True,
        choices=["LongMemEval", "MemBench"],
        help="Benchmark to validate artifacts for",
    )
    parser.add_argument("--subset", default="S", help="LongMemEval subset (default: S)")
    parser.add_argument("--judge", default="gpt-4o", help="LongMemEval judge (default: gpt-4o)")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=BenchmarkLoader.data_dir() / "hybrid_eval",
        help="Hybrid eval output directory (default: benchmarks_data/hybrid_eval)",
    )
    parser.add_argument(
        "--summary-required-keys",
        nargs="*",
        default=[],
        help="Optional required keys for MemBench summary JSON",
    )
    args = parser.parse_args()

    if not args.results_file.exists():
        print(f"Results file not found: {args.results_file}")
        return 1

    tools = _load_tools(args.results_file, args.benchmark)
    if not tools:
        print(f"No tools found for benchmark '{args.benchmark}' in {args.results_file}")
        return 1

    issues: List[str] = []
    for tool_name in tools:
        if args.benchmark == "LongMemEval":
            issues.extend(_check_longmemeval(tool_name, args.output_dir, args.subset, args.judge))
        else:
            issues.extend(_check_membench(tool_name, args.output_dir, args.summary_required_keys))

    if issues:
        print("Eval artifact check failed:")
        for issue in issues:
            print(f"- {issue}")
        return 1

    print(
        f"Eval artifact check passed for {args.benchmark} "
        f"({', '.join(tools)}) in {args.output_dir}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
