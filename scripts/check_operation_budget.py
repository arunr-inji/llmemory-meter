#!/usr/bin/env python3
"""Estimate benchmark operation counts before spend-heavy runs."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict, List, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from llmemory_meter.benchmark_loader import BenchmarkLoader
from llmemory_meter.config_parser import ConfigManager


def _load_workloads(config, benchmark_name: str):
    benchmark_config = ConfigManager.get_benchmark_config(config, benchmark_name)
    settings = benchmark_config.settings if benchmark_config and benchmark_config.settings else {}

    if benchmark_name == "LongMemEval":
        subset = settings.get("subset", "S")
        limit = settings.get("limit")
        return BenchmarkLoader.load_longmemeval(subset=subset, limit=limit), settings
    if benchmark_name == "MemBench":
        categories = settings.get("categories")
        limit = settings.get("limit")
        return BenchmarkLoader.load_membench(categories=categories, limit=limit), settings
    return [], settings


def _count_steps(workloads, store_retrieve_only: bool) -> int:
    total = 0
    for workload in workloads:
        for step in workload.steps:
            if store_retrieve_only and step.action == "chat":
                continue
            total += 1
    return total


def main() -> int:
    parser = argparse.ArgumentParser(description="Estimate operation budget for enabled benchmarks/tools.")
    parser.add_argument("--config", default="configs/industry-benchmarks.yml", help="Config path")
    parser.add_argument(
        "--max-ops-per-tool",
        type=int,
        default=None,
        help="Fail if estimated ops per tool exceeds this value",
    )
    parser.add_argument(
        "--max-total-ops",
        type=int,
        default=None,
        help="Fail if estimated total ops across all tools exceeds this value",
    )
    args = parser.parse_args()

    config = ConfigManager.load_config(args.config)
    enabled_tools = ConfigManager.get_enabled_tools(config)
    enabled_benchmarks = ConfigManager.get_enabled_benchmarks(config)
    store_retrieve_only = bool(config.general.get("store_retrieve_only", False))

    if not enabled_tools:
        print("No enabled tools found in config.")
        return 1
    if not enabled_benchmarks:
        print("No enabled benchmarks found in config.")
        return 1

    issues: List[str] = []
    benchmark_op_counts: Dict[str, int] = {}

    for benchmark_name in enabled_benchmarks:
        workloads, settings = _load_workloads(config, benchmark_name)
        if not workloads:
            issues.append(f"{benchmark_name}: no workloads loaded")
            continue
        step_count = _count_steps(workloads, store_retrieve_only=store_retrieve_only)
        benchmark_op_counts[benchmark_name] = step_count
        print(
            f"{benchmark_name}: workloads={len(workloads)} estimated_steps_per_tool={step_count} "
            f"(settings={settings})"
        )

    if issues:
        print("Operation budget validation failed:")
        for issue in issues:
            print(f"- {issue}")
        return 1

    ops_per_tool = sum(benchmark_op_counts.values())
    total_ops = ops_per_tool * len(enabled_tools)

    print(f"Enabled tools: {', '.join(enabled_tools)}")
    print(f"Estimated operations per tool: {ops_per_tool}")
    print(f"Estimated total operations (all tools): {total_ops}")

    if args.max_ops_per_tool is not None and ops_per_tool > args.max_ops_per_tool:
        print(
            f"Operation budget exceeded: ops_per_tool={ops_per_tool} "
            f"> max_ops_per_tool={args.max_ops_per_tool}"
        )
        return 1

    if args.max_total_ops is not None and total_ops > args.max_total_ops:
        print(
            f"Operation budget exceeded: total_ops={total_ops} "
            f"> max_total_ops={args.max_total_ops}"
        )
        return 1

    print(f"Operation budget check passed for config: {args.config}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
