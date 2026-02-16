#!/usr/bin/env python3
"""Validate benchmark/tool coverage and benchmark-level fatal errors."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List, Set


def _tools_seen_in_benchmark(benchmark_payload: Dict[str, object]) -> Set[str]:
    standard_results = benchmark_payload.get("standard_results", {})
    if not isinstance(standard_results, dict):
        return set()

    workload_results = standard_results.get("workload_results", {})
    if not isinstance(workload_results, dict):
        return set()

    seen: Set[str] = set()
    for _, tools_payload in workload_results.items():
        if not isinstance(tools_payload, dict):
            continue
        seen.update(tool for tool in tools_payload.keys() if isinstance(tool, str))
    return seen


def main() -> int:
    parser = argparse.ArgumentParser(description="Check run-level benchmark/tool expectations.")
    parser.add_argument("results_file", type=Path, help="Path to benchmark results JSON")
    parser.add_argument(
        "--require-benchmarks",
        nargs="*",
        default=[],
        help="Benchmarks that must exist in results",
    )
    parser.add_argument(
        "--require-tools",
        nargs="*",
        default=[],
        help="Tools that must appear in each required benchmark",
    )
    args = parser.parse_args()

    if not args.results_file.exists():
        print(f"Results file not found: {args.results_file}")
        return 1

    with args.results_file.open("r", encoding="utf-8") as f:
        data = json.load(f)

    results = data.get("results")
    if not isinstance(results, dict):
        print("Invalid results file: top-level 'results' object missing.")
        return 1

    issues: List[str] = []
    required_benchmarks = args.require_benchmarks or list(results.keys())
    required_tools = sorted(set(args.require_tools))

    for benchmark_name in required_benchmarks:
        benchmark_payload = results.get(benchmark_name)
        if benchmark_payload is None:
            issues.append(f"missing benchmark: {benchmark_name}")
            continue
        if not isinstance(benchmark_payload, dict):
            issues.append(f"{benchmark_name}: benchmark payload must be an object")
            continue
        if "error" in benchmark_payload:
            issues.append(f"{benchmark_name}: benchmark-level error present: {benchmark_payload.get('error')}")
            continue

        tools_seen = _tools_seen_in_benchmark(benchmark_payload)
        if not tools_seen:
            issues.append(f"{benchmark_name}: no tools found in workload_results")
            continue

        for tool in required_tools:
            if tool not in tools_seen:
                issues.append(f"{benchmark_name}: required tool missing: {tool}")

        print(f"{benchmark_name}: tools seen -> {', '.join(sorted(tools_seen))}")

    if issues:
        print("Run expectation check failed:")
        for issue in issues:
            print(f"- {issue}")
        return 1

    print(f"Run expectation check passed: {args.results_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
