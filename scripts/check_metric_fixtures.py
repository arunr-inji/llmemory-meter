#!/usr/bin/env python3
"""Run deterministic fixture checks for MetricsCalculator behavior."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from llmemory_meter.metrics import MetricsCalculator
from llmemory_meter.workload import StepResult, WorkloadResult


DEFAULT_FIXTURE = Path("scripts/fixtures/metric_cases.json")


def _assert_equal(case: str, key: str, actual: Any, expected: Any, errors: List[str]) -> None:
    if isinstance(expected, float):
        if abs(float(actual) - expected) > 1e-9:
            errors.append(f"{case}: {key} expected={expected} actual={actual}")
        return
    if actual != expected:
        errors.append(f"{case}: {key} expected={expected} actual={actual}")


def _build_workload_result(case_name: str, tool_name: str, payload: Dict[str, Any]) -> WorkloadResult:
    steps: List[StepResult] = []
    for idx, step in enumerate(payload.get("steps", [])):
        steps.append(
            StepResult(
                step_index=idx,
                action=step.get("action", "retrieve"),
                response=step.get("response", ""),
                latency_ms=float(step.get("latency_ms", 0.0)),
                tokens_used=step.get("tokens_used"),
                input_tokens=step.get("input_tokens"),
                output_tokens=step.get("output_tokens"),
                model=step.get("model"),
                success=bool(step.get("success", False)),
                metadata=step.get("metadata"),
            )
        )

    return WorkloadResult(
        tool_name=tool_name,
        workload_name=f"fixture::{case_name}",
        step_results=steps,
        total_latency_ms=sum(s.latency_ms for s in steps),
        total_tokens_used=sum((s.tokens_used or 0) for s in steps),
        success_rate=(sum(1 for s in steps if s.success) / len(steps)) if steps else 0.0,
        timestamp=datetime.now(timezone.utc),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate deterministic metric fixtures.")
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    args = parser.parse_args()

    if not args.fixture.exists():
        print(f"Fixture file not found: {args.fixture}")
        return 1

    with args.fixture.open("r", encoding="utf-8") as f:
        data = json.load(f)

    cases = data.get("cases", [])
    if not cases:
        print("No fixture cases found.")
        return 1

    errors: List[str] = []

    for case in cases:
        case_name = case["name"]
        tool_name = case.get("tool_name", "fixture_tool")
        config = case.get("config", {})
        wr = _build_workload_result(case_name, tool_name, case)
        metrics = MetricsCalculator.calculate_metrics([wr], config=config).to_dict()
        expected = case.get("expected", {})

        for key, expected_value in expected.items():
            actual_value = metrics.get(key)
            _assert_equal(case_name, key, actual_value, expected_value, errors)

    if errors:
        print(f"Metric fixture checks failed ({len(errors)} error(s)):")
        for err in errors:
            print(f"- {err}")
        return 1

    print(f"Metric fixture checks passed for {len(cases)} case(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
