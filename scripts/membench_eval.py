#!/usr/bin/env python3
"""Deterministic MemBench evaluator (exact + contains)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List


def _normalize(text: str) -> str:
    return " ".join(text.strip().lower().split())


def _safe_category(row: Dict[str, Any]) -> str:
    category = row.get("category")
    if category:
        return str(category)
    metadata = row.get("metadata")
    if isinstance(metadata, dict) and metadata.get("category"):
        return str(metadata["category"])
    return "unknown"


def _require_hypothesis(row: Dict[str, Any], line_number: int) -> str:
    if "hypothesis" not in row:
        raise ValueError(f"line {line_number}: missing required field 'hypothesis'")
    hypothesis = row.get("hypothesis")
    if hypothesis is None:
        return ""
    return str(hypothesis)


def evaluate_rows(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    eval_rows: List[Dict[str, Any]] = []
    scored = 0
    unscorable = 0
    contains_correct = 0
    exact_correct = 0
    by_category: Dict[str, Dict[str, int]] = {}

    for idx, row in enumerate(rows, start=1):
        hypothesis = _require_hypothesis(row, idx)
        category = _safe_category(row)
        ground_truth = row.get("ground_truth")
        workload_id = row.get("workload_id", f"row::{idx}")

        category_bucket = by_category.setdefault(
            category,
            {
                "scored_count": 0,
                "unscorable_count": 0,
                "contains_correct": 0,
                "exact_correct": 0,
            },
        )

        row_result: Dict[str, Any] = {
            "workload_id": workload_id,
            "category": category,
            "match_type": row.get("match_type", "contains"),
            "hypothesis": hypothesis,
            "ground_truth": ground_truth,
            "scored": False,
            "unscorable_reason": None,
            "contains_match": False,
            "exact_match": False,
        }

        if ground_truth is None or str(ground_truth).strip() == "":
            unscorable += 1
            category_bucket["unscorable_count"] += 1
            row_result["unscorable_reason"] = "missing_ground_truth"
            eval_rows.append(row_result)
            continue

        gt_norm = _normalize(str(ground_truth))
        hyp_norm = _normalize(hypothesis)

        scored += 1
        category_bucket["scored_count"] += 1
        row_result["scored"] = True
        row_result["contains_match"] = gt_norm in hyp_norm if gt_norm else False
        row_result["exact_match"] = gt_norm == hyp_norm

        if row_result["contains_match"]:
            contains_correct += 1
            category_bucket["contains_correct"] += 1
        if row_result["exact_match"]:
            exact_correct += 1
            category_bucket["exact_correct"] += 1

        eval_rows.append(row_result)

    per_category: Dict[str, Dict[str, Any]] = {}
    for category, bucket in by_category.items():
        scored_count = bucket["scored_count"]
        contains_acc = (bucket["contains_correct"] / scored_count) if scored_count else None
        exact_acc = (bucket["exact_correct"] / scored_count) if scored_count else None
        per_category[category] = {
            "scored_count": scored_count,
            "unscorable_count": bucket["unscorable_count"],
            "accuracy_contains": contains_acc,
            "accuracy_exact": exact_acc,
        }

    summary = {
        "total_rows": len(rows),
        "scored_count": scored,
        "unscorable_count": unscorable,
        "accuracy_contains": (contains_correct / scored) if scored else None,
        "accuracy_exact": (exact_correct / scored) if scored else None,
        "per_category": per_category,
    }

    return {
        "rows": eval_rows,
        "summary": summary,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Deterministic MemBench evaluator")
    parser.add_argument("hypothesis_file", type=Path, help="Input hypothesis JSONL")
    args = parser.parse_args()

    if not args.hypothesis_file.exists():
        print(f"Hypothesis file not found: {args.hypothesis_file}")
        return 1

    try:
        rows: List[Dict[str, Any]] = []
        with args.hypothesis_file.open("r", encoding="utf-8") as f:
            for i, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError as exc:
                    print(f"Invalid JSON on line {i}: {exc}")
                    return 1
                if not isinstance(payload, dict):
                    print(f"Invalid row on line {i}: expected object")
                    return 1
                rows.append(payload)

        output = evaluate_rows(rows)

        eval_path = Path(str(args.hypothesis_file) + ".eval.jsonl")
        summary_path = Path(str(args.hypothesis_file) + ".summary.json")

        with eval_path.open("w", encoding="utf-8") as f:
            for row in output["rows"]:
                f.write(json.dumps(row, ensure_ascii=True) + "\n")

        with summary_path.open("w", encoding="utf-8") as f:
            json.dump(output["summary"], f, indent=2)
            f.write("\n")

        print(f"MemBench eval completed: {args.hypothesis_file}")
        print(f"Row-level output: {eval_path}")
        print(f"Summary output: {summary_path}")
        return 0

    except ValueError as exc:
        print(str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
