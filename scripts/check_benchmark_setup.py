#!/usr/bin/env python3
"""Validate benchmark dataset readiness for enabled benchmarks."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from llmemory_meter.benchmark_loader import BenchmarkLoader
from llmemory_meter.config_parser import ConfigManager


def _prioritized_enabled_benchmarks(config) -> List:
    enabled = [b for b in config.benchmarks if b.enabled]
    # Validate MemBench first so dataset/archive failures surface immediately.
    priority = {"MemBench": 0, "LongMemEval": 1}
    return sorted(enabled, key=lambda b: priority.get(b.name, 99))


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate benchmark setup for enabled benchmarks.")
    parser.add_argument("--config", default="configs/industry-benchmarks.yml", help="Config path")
    parser.add_argument(
        "--sample-limit",
        type=int,
        default=1,
        help="Workload sample size per benchmark for readiness checks (default: 1)",
    )
    args = parser.parse_args()

    config = ConfigManager.load_config(args.config)
    enabled_benchmarks = _prioritized_enabled_benchmarks(config)
    if not enabled_benchmarks:
        print("No enabled benchmarks found in config.")
        return 1

    errors: List[str] = []
    checked: Dict[str, int] = {}

    for benchmark in enabled_benchmarks:
        settings = benchmark.settings or {}
        try:
            if benchmark.name == "LongMemEval":
                subset = settings.get("subset", "S")
                workloads = BenchmarkLoader.load_longmemeval(
                    subset=subset,
                    limit=args.sample_limit,
                )
                checked[benchmark.name] = len(workloads)
                if not workloads:
                    errors.append(f"LongMemEval readiness returned zero workloads (subset={subset}).")
            elif benchmark.name == "MemBench":
                categories = settings.get("categories")
                workloads = BenchmarkLoader.load_membench(
                    categories=categories,
                    limit=args.sample_limit,
                    auto_download=True,
                )
                checked[benchmark.name] = len(workloads)
                if not workloads:
                    errors.append("MemBench readiness returned zero workloads.")
            else:
                checked[benchmark.name] = 0
                print(f"Skipping benchmark setup check for unsupported benchmark: {benchmark.name}")
        except Exception as exc:
            errors.append(f"{benchmark.name} setup failed: {exc}")

    if errors:
        print("Benchmark setup validation failed:")
        for err in errors:
            print(f"- {err}")
        return 1

    for benchmark_name, count in checked.items():
        print(f"{benchmark_name} setup OK (sample workloads loaded: {count})")
    print(f"Benchmark setup validation passed for config: {args.config}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
