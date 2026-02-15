#!/usr/bin/env python3
"""Validate LLMemoryMeter results JSON schema for publication readiness."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import List


def _fail(errors: List[str]) -> int:
    print("Schema validation failed:")
    for error in errors:
        print(f"- {error}")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate benchmark results schema.")
    parser.add_argument("results_file", type=Path, help="Path to results JSON file")
    parser.add_argument(
        "--require-benchmarks",
        nargs="*",
        default=[],
        help="Benchmark names that must be present in results",
    )
    args = parser.parse_args()

    if not args.results_file.exists():
        print(f"Results file not found: {args.results_file}")
        return 1

    with args.results_file.open("r", encoding="utf-8") as f:
        data = json.load(f)

    errors: List[str] = []
    if not isinstance(data, dict):
        errors.append("Top-level JSON must be an object.")
        return _fail(errors)

    config = data.get("config")
    results = data.get("results")

    if not isinstance(config, dict):
        errors.append("Missing or invalid top-level key: config")
    if not isinstance(results, dict):
        errors.append("Missing or invalid top-level key: results")
        return _fail(errors)

    for benchmark in args.require_benchmarks:
        if benchmark not in results:
            errors.append(f"Required benchmark missing: {benchmark}")

    for benchmark_name, benchmark_data in results.items():
        if not isinstance(benchmark_data, dict):
            errors.append(f"{benchmark_name}: benchmark payload must be an object")
            continue
        standard_results = benchmark_data.get("standard_results")
        if not isinstance(standard_results, dict):
            errors.append(f"{benchmark_name}: missing standard_results object")
            continue
        workload_results = standard_results.get("workload_results")
        if not isinstance(workload_results, dict):
            errors.append(f"{benchmark_name}: missing workload_results object")

    if errors:
        return _fail(errors)

    print(f"Schema validation passed: {args.results_file}")
    print(f"Benchmarks found: {', '.join(sorted(results.keys()))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
