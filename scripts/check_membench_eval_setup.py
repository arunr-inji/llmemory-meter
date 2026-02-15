#!/usr/bin/env python3
"""Fail-fast readiness checks for MemBench evaluation scripts."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import List


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _deterministic_script_path() -> Path:
    return _repo_root() / "scripts" / "membench_eval.py"


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate MemBench eval script readiness.")
    parser.add_argument(
        "--eval-script",
        type=Path,
        required=True,
        help="MemBench eval script path",
    )
    parser.add_argument(
        "--fixture",
        type=Path,
        default=Path("scripts/fixtures/membench_hypothesis_fixture.jsonl"),
        help="Hypothesis fixture JSONL",
    )
    parser.add_argument(
        "--require-official",
        action="store_true",
        help="Fail if eval script points to deterministic canary script",
    )
    args = parser.parse_args()

    eval_script = args.eval_script.resolve()
    fixture = args.fixture.resolve()
    deterministic_script = _deterministic_script_path().resolve()

    issues: List[str] = []
    if not eval_script.exists():
        issues.append(f"eval script not found: {eval_script}")
    if not fixture.exists():
        issues.append(f"fixture not found: {fixture}")
    if args.require_official and eval_script == deterministic_script:
        issues.append(
            "official MemBench eval required, but deterministic canary script was provided: "
            f"{eval_script}"
        )
    if issues:
        print("MemBench eval setup check failed:")
        for issue in issues:
            print(f"- {issue}")
        return 1

    summary_path = Path(f"{fixture}.summary.json")
    row_eval_path = Path(f"{fixture}.eval.jsonl")
    for p in (summary_path, row_eval_path):
        if p.exists():
            p.unlink()

    result = subprocess.run(
        [sys.executable, str(eval_script), str(fixture)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print("MemBench eval setup check failed:")
        print(
            "- eval script returned non-zero exit status: "
            f"{result.returncode} ({result.stderr.strip() or result.stdout.strip()})"
        )
        return 1

    if not summary_path.exists():
        print("MemBench eval setup check failed:")
        print(f"- summary artifact missing: {summary_path}")
        return 1
    if not row_eval_path.exists():
        print("MemBench eval setup check failed:")
        print(f"- row-level eval artifact missing: {row_eval_path}")
        return 1

    try:
        with summary_path.open("r", encoding="utf-8") as f:
            payload = json.load(f)
        if not isinstance(payload, dict):
            raise ValueError("summary JSON is not an object")
    except Exception as exc:
        print("MemBench eval setup check failed:")
        print(f"- summary artifact is not parseable JSON object: {summary_path} ({exc})")
        return 1

    print(
        f"MemBench eval setup check passed: script={eval_script} "
        f"(official_required={'yes' if args.require_official else 'no'})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
