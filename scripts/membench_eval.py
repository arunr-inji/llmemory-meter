#!/usr/bin/env python3
"""Deterministic MemBench evaluator with MCQ-aware primary scoring."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional


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


def _safe_metadata(row: Dict[str, Any]) -> Dict[str, Any]:
    metadata = row.get("metadata")
    return metadata if isinstance(metadata, dict) else {}


def _extract_choices(row: Dict[str, Any]) -> Optional[Dict[str, str]]:
    for source in (row, _safe_metadata(row)):
        choices = source.get("choices")
        if isinstance(choices, dict) and choices:
            normalized: Dict[str, str] = {}
            for key, value in choices.items():
                label = str(key).strip().upper()
                text = str(value).strip()
                if label and text:
                    normalized[label] = text
            if normalized:
                return normalized
    return None


def _extract_ground_truth_label(row: Dict[str, Any]) -> Optional[str]:
    for source in (row, _safe_metadata(row)):
        value = source.get("ground_truth_label")
        if value is None:
            continue
        label = str(value).strip().upper()
        if label:
            return label
    return None


def _derive_ground_truth_text(
    row: Dict[str, Any],
    choices: Optional[Dict[str, str]],
    ground_truth_label: Optional[str],
) -> Optional[str]:
    ground_truth = row.get("ground_truth")
    if ground_truth is not None and str(ground_truth).strip() != "":
        return str(ground_truth)
    if choices and ground_truth_label and ground_truth_label in choices:
        return choices[ground_truth_label]
    return None


def _extract_predicted_label(hypothesis: str, choices: Dict[str, str]) -> Optional[str]:
    if not hypothesis:
        return None

    hyp_norm = _normalize(hypothesis)

    # First pass: explicit label declarations (e.g., "Answer: C", "Option B").
    label_patterns = [
        r"\b(?:answer|option|choice)\s*[:\-]?\s*\(?([A-Z])\)?\b",
        r"^\s*\(?([A-Z])\)?\s*$",
    ]
    for pattern in label_patterns:
        match = re.search(pattern, hypothesis, flags=re.IGNORECASE)
        if match:
            candidate = match.group(1).upper()
            if candidate in choices:
                return candidate

    # Second pass: option text appears in hypothesis.
    text_hits: List[str] = []
    for label, option_text in choices.items():
        option_norm = _normalize(option_text)
        if option_norm and option_norm in hyp_norm:
            text_hits.append(label)
    if len(text_hits) == 1:
        return text_hits[0]

    return None


def evaluate_rows(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    eval_rows: List[Dict[str, Any]] = []
    scored = 0
    unscorable = 0
    scored_mcq = 0
    scored_text = 0
    primary_correct = 0
    mcq_correct = 0
    contains_correct = 0
    exact_correct = 0
    by_category: Dict[str, Dict[str, int]] = {}

    for idx, row in enumerate(rows, start=1):
        hypothesis = _require_hypothesis(row, idx)
        category = _safe_category(row)
        workload_id = row.get("workload_id", f"row::{idx}")

        category_bucket = by_category.setdefault(
            category,
            {
                "scored_count": 0,
                "unscorable_count": 0,
                "scored_mcq_count": 0,
                "scored_text_count": 0,
                "primary_correct": 0,
                "mcq_correct": 0,
                "contains_correct": 0,
                "exact_correct": 0,
            },
        )

        choices = _extract_choices(row)
        ground_truth_label = _extract_ground_truth_label(row)
        ground_truth_text = _derive_ground_truth_text(row, choices, ground_truth_label)
        predicted_label = _extract_predicted_label(hypothesis, choices) if choices else None

        row_result: Dict[str, Any] = {
            "workload_id": workload_id,
            "category": category,
            "match_type": row.get("match_type", "contains"),
            "hypothesis": hypothesis,
            "ground_truth": ground_truth_text,
            "ground_truth_label": ground_truth_label,
            "predicted_label": predicted_label,
            "choices": choices,
            "scored": False,
            "scoring_mode": None,
            "unscorable_reason": None,
            "primary_match": False,
            "mcq_match": False,
            "contains_match": False,
            "exact_match": False,
        }

        if ground_truth_text is None or str(ground_truth_text).strip() == "":
            unscorable += 1
            category_bucket["unscorable_count"] += 1
            row_result["unscorable_reason"] = "missing_ground_truth"
            eval_rows.append(row_result)
            continue

        gt_norm = _normalize(str(ground_truth_text))
        hyp_norm = _normalize(hypothesis)
        is_mcq_scorable = bool(choices and ground_truth_label and ground_truth_label in choices)

        scored += 1
        category_bucket["scored_count"] += 1
        row_result["scored"] = True
        row_result["contains_match"] = gt_norm in hyp_norm if gt_norm else False
        row_result["exact_match"] = gt_norm == hyp_norm
        row_result["mcq_match"] = (
            predicted_label == ground_truth_label if is_mcq_scorable else False
        )

        if is_mcq_scorable:
            scored_mcq += 1
            category_bucket["scored_mcq_count"] += 1
            row_result["scoring_mode"] = "mcq"
            row_result["primary_match"] = row_result["mcq_match"]
        else:
            scored_text += 1
            category_bucket["scored_text_count"] += 1
            row_result["scoring_mode"] = "text"
            row_result["primary_match"] = row_result["contains_match"]

        if row_result["primary_match"]:
            primary_correct += 1
            category_bucket["primary_correct"] += 1
        if row_result["mcq_match"]:
            mcq_correct += 1
            category_bucket["mcq_correct"] += 1

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
            "scored_mcq_count": bucket["scored_mcq_count"],
            "scored_text_count": bucket["scored_text_count"],
            "accuracy": (bucket["primary_correct"] / scored_count) if scored_count else None,
            "accuracy_mcq": (
                bucket["mcq_correct"] / bucket["scored_mcq_count"]
                if bucket["scored_mcq_count"]
                else None
            ),
            "accuracy_contains": contains_acc,
            "accuracy_exact": exact_acc,
        }

    summary = {
        "total_rows": len(rows),
        "scored_count": scored,
        "unscorable_count": unscorable,
        "scored_mcq_count": scored_mcq,
        "scored_text_count": scored_text,
        "accuracy": (primary_correct / scored) if scored else None,
        "accuracy_mcq": (mcq_correct / scored_mcq) if scored_mcq else None,
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
