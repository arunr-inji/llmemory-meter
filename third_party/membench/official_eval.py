#!/usr/bin/env python3
"""MemBench evaluator with LLM-as-a-judge for MCQ label prediction."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


PROMPT_VERSION = "membench_llm_judge_v2"
SYSTEM_PROMPT = (
    "You are an evaluation judge for a multiple-choice memory benchmark. "
    "Given a question, choices, and a model response, pick exactly one best label "
    "(A/B/C/D) only if the response supports it; otherwise return null. "
    "You must infer answers from evidence in the response, not only explicit final answers. "
    "For counting questions (e.g., 'How many ...?'), count entities in the response and map to the closest option. "
    "Treat phrases like 'from <location>' and 'lives in <location>' as location evidence unless contradicted. "
    "If one option is clearly better supported than others, choose it (do not return null). "
    "Return strict JSON with keys: predicted_label, confidence, reason. "
    "predicted_label must be one of A,B,C,D,null. confidence is a float 0..1."
)

NUMBER_WORDS = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
}


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
                if label in {"A", "B", "C", "D"} and text:
                    normalized[label] = text
            if normalized:
                return normalized
    return None


def _extract_question(row: Dict[str, Any]) -> Optional[str]:
    for source in (row, _safe_metadata(row)):
        for key in ("question", "query", "prompt"):
            value = source.get(key)
            if value is not None and str(value).strip():
                return str(value)
    return None


def _extract_ground_truth_label(row: Dict[str, Any]) -> Optional[str]:
    for source in (row, _safe_metadata(row)):
        for key in ("ground_truth_label", "ground_truth", "answer_label"):
            value = source.get(key)
            if value is None:
                continue
            label = str(value).strip().upper()
            if label in {"A", "B", "C", "D"}:
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


def _require_hypothesis(row: Dict[str, Any], line_number: int) -> str:
    if "hypothesis" not in row:
        raise ValueError(f"line {line_number}: missing required field 'hypothesis'")
    hypothesis = row.get("hypothesis")
    if hypothesis is None:
        return ""
    return str(hypothesis)


def _extract_label_from_response(text: str, choices: Dict[str, str]) -> Optional[str]:
    if not text:
        return None
    for pattern in (
        r"\b(?:answer|option|choice)\s*[:\-]?\s*\(?([A-D])\)?\b",
        r"^\s*\(?([A-D])\)?\s*$",
    ):
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            label = match.group(1).upper()
            if label in choices:
                return label
    return None


def _match_choice_text(response: str, choices: Dict[str, str]) -> Optional[str]:
    response_norm = _normalize(response)
    hits: List[str] = []
    for label, option_text in choices.items():
        option_norm = _normalize(option_text)
        if option_norm and option_norm in response_norm:
            hits.append(label)
    if len(hits) == 1:
        return hits[0]
    return None


def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _extract_target_location(question: str) -> Optional[str]:
    match = re.search(
        r"how many\s+.*?(?:in|from)\s+([^?.,;]+)",
        question,
        flags=re.IGNORECASE,
    )
    if not match:
        return None
    return _normalize(match.group(1))


def _extract_count_from_text(text: str) -> Optional[int]:
    match = re.search(r"\b(\d+)\b", text)
    if match:
        return int(match.group(1))
    normalized = _normalize(text)
    for word, value in NUMBER_WORDS.items():
        if re.search(rf"\b{word}\b", normalized):
            return value
    return None


def _infer_count_label(question: str, hypothesis: str, choices: Dict[str, str]) -> Optional[str]:
    if "how many" not in _normalize(question):
        return None
    target_location = _extract_target_location(question)
    if not target_location:
        return None

    segments = [seg.strip() for seg in re.split(r"[|\n]", hypothesis) if seg.strip()]
    if not segments:
        segments = [seg.strip() for seg in re.split(r"[.!?]", hypothesis) if seg.strip()]

    count = 0
    for segment in segments:
        seg_norm = _normalize(segment)
        if target_location in seg_norm:
            count += len(re.findall(re.escape(target_location), seg_norm))

    if count <= 0:
        return None

    matching_labels: List[str] = []
    for label, option_text in choices.items():
        option_count = _extract_count_from_text(option_text)
        if option_count is not None and option_count == count:
            matching_labels.append(label)

    if len(matching_labels) == 1:
        return matching_labels[0]
    return None


def _extract_json_object(raw: str) -> Dict[str, Any]:
    raw = (raw or "").strip()
    if not raw:
        raise ValueError("empty LLM response")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError("LLM response is not JSON")
        payload = json.loads(raw[start : end + 1])
    if not isinstance(payload, dict):
        raise ValueError("LLM response JSON must be an object")
    return payload


class LLMJudge:
    def __init__(
        self,
        model: str,
        api_key: Optional[str],
        base_url: Optional[str],
        timeout_seconds: float,
        max_retries: int,
        cache_path: Path,
    ):
        self.model = model
        self.api_key = api_key
        self.base_url = base_url
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.cache_path = cache_path
        self._cache = self._load_cache(cache_path)
        self.cache_hits = 0
        self.calls = 0
        self._client = None

    @staticmethod
    def _load_cache(path: Path) -> Dict[str, Dict[str, Any]]:
        if not path.exists():
            return {}
        try:
            with path.open("r", encoding="utf-8") as f:
                payload = json.load(f)
            if isinstance(payload, dict):
                return payload
        except Exception:
            return {}
        return {}

    def _save_cache(self) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        with self.cache_path.open("w", encoding="utf-8") as f:
            json.dump(self._cache, f, indent=2)
            f.write("\n")

    def _cache_key(self, question: str, choices: Dict[str, str], hypothesis: str) -> str:
        payload = {
            "prompt_version": PROMPT_VERSION,
            "model": self.model,
            "question": question,
            "choices": choices,
            "hypothesis": hypothesis,
        }
        encoded = json.dumps(payload, sort_keys=True, ensure_ascii=True).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def _client_instance(self):
        if self._client is not None:
            return self._client
        if not self.api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is required for LLM MemBench judge (or set MEMBENCH_LLM_JUDGE_API_KEY)."
            )
        from openai import OpenAI

        kwargs: Dict[str, Any] = {"api_key": self.api_key, "timeout": self.timeout_seconds}
        if self.base_url:
            kwargs["base_url"] = self.base_url
        self._client = OpenAI(**kwargs)
        return self._client

    def judge(self, question: str, choices: Dict[str, str], hypothesis: str) -> Dict[str, Any]:
        key = self._cache_key(question, choices, hypothesis)
        cached = self._cache.get(key)
        if isinstance(cached, dict):
            self.cache_hits += 1
            out = dict(cached)
            out["cache_hit"] = True
            return out

        user_payload = {
            "question": question,
            "choices": choices,
            "response": hypothesis,
        }
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(user_payload, ensure_ascii=True)},
        ]

        last_error = None
        for attempt in range(1, self.max_retries + 1):
            try:
                self.calls += 1
                completion = self._client_instance().chat.completions.create(
                    model=self.model,
                    temperature=0,
                    response_format={"type": "json_object"},
                    messages=messages,
                )
                content = completion.choices[0].message.content or ""
                payload = _extract_json_object(content)
                label_raw = payload.get("predicted_label")
                if label_raw is None:
                    label = None
                else:
                    label_str = str(label_raw).strip().upper()
                    label = label_str if label_str in {"A", "B", "C", "D"} else None

                parsed = {
                    "predicted_label": label,
                    "confidence": _safe_float(payload.get("confidence")),
                    "reason": str(payload.get("reason", "")),
                    "cache_hit": False,
                }
                self._cache[key] = {
                    "predicted_label": parsed["predicted_label"],
                    "confidence": parsed["confidence"],
                    "reason": parsed["reason"],
                    "model": self.model,
                    "prompt_version": PROMPT_VERSION,
                    "cached_at": datetime.now(timezone.utc)
                    .replace(microsecond=0)
                    .isoformat()
                    .replace("+00:00", "Z"),
                }
                self._save_cache()
                return parsed
            except Exception as exc:  # pragma: no cover - network/runtime failures
                last_error = str(exc)
                if attempt < self.max_retries:
                    time.sleep(min(2 ** (attempt - 1), 8))
                continue

        raise RuntimeError(f"LLM judge failed after {self.max_retries} attempts: {last_error}")


def evaluate_rows(rows: List[Dict[str, Any]], judge: LLMJudge) -> Dict[str, Any]:
    eval_rows: List[Dict[str, Any]] = []
    scored = 0
    unscorable = 0
    scored_mcq = 0
    scored_text = 0
    scored_llm = 0
    unresolved = 0
    primary_correct = 0
    contains_correct = 0
    exact_correct = 0
    by_category: Dict[str, Dict[str, int]] = {}

    for idx, row in enumerate(rows, start=1):
        hypothesis = _require_hypothesis(row, idx)
        category = _safe_category(row)
        workload_id = row.get("workload_id", f"row::{idx}")
        choices = _extract_choices(row)
        question = _extract_question(row)
        ground_truth_label = _extract_ground_truth_label(row)
        ground_truth_text = _derive_ground_truth_text(row, choices, ground_truth_label)

        category_bucket = by_category.setdefault(
            category,
            {
                "scored_count": 0,
                "unscorable_count": 0,
                "scored_mcq_count": 0,
                "scored_text_count": 0,
                "scored_llm_count": 0,
                "unresolved_count": 0,
                "primary_correct": 0,
                "contains_correct": 0,
                "exact_correct": 0,
            },
        )

        row_result: Dict[str, Any] = {
            "workload_id": workload_id,
            "category": category,
            "question": question,
            "match_type": row.get("match_type", "contains"),
            "hypothesis": hypothesis,
            "ground_truth": ground_truth_text,
            "ground_truth_label": ground_truth_label,
            "predicted_label": None,
            "choices": choices,
            "scored": False,
            "scoring_mode": None,
            "unscorable_reason": None,
            "primary_match": False,
            "mcq_match": False,
            "contains_match": False,
            "exact_match": False,
            "judge_reason": None,
            "judge_confidence": None,
            "judge_cache_hit": None,
        }

        if ground_truth_text is None or str(ground_truth_text).strip() == "":
            unscorable += 1
            category_bucket["unscorable_count"] += 1
            row_result["unscorable_reason"] = "missing_ground_truth"
            eval_rows.append(row_result)
            continue

        gt_norm = _normalize(str(ground_truth_text))
        hyp_norm = _normalize(hypothesis)

        scored += 1
        category_bucket["scored_count"] += 1
        row_result["scored"] = True
        row_result["contains_match"] = gt_norm in hyp_norm if gt_norm else False
        row_result["exact_match"] = gt_norm == hyp_norm

        if choices and ground_truth_label and question:
            scored_mcq += 1
            category_bucket["scored_mcq_count"] += 1

            predicted = _extract_label_from_response(hypothesis, choices)
            if predicted:
                row_result["predicted_label"] = predicted
                row_result["scoring_mode"] = "explicit_label"
            else:
                predicted = _match_choice_text(hypothesis, choices)
                if predicted:
                    row_result["predicted_label"] = predicted
                    row_result["scoring_mode"] = "option_text_match"
                else:
                    predicted = _infer_count_label(question, hypothesis, choices)
                    if predicted:
                        row_result["predicted_label"] = predicted
                        row_result["scoring_mode"] = "count_adapter"
                    else:
                        scored_llm += 1
                        category_bucket["scored_llm_count"] += 1
                        verdict = judge.judge(question, choices, hypothesis)
                        row_result["predicted_label"] = verdict.get("predicted_label")
                        row_result["judge_reason"] = verdict.get("reason")
                        row_result["judge_confidence"] = verdict.get("confidence")
                        row_result["judge_cache_hit"] = verdict.get("cache_hit")
                        row_result["scoring_mode"] = "llm_judge"

            row_result["mcq_match"] = row_result["predicted_label"] == ground_truth_label
            row_result["primary_match"] = row_result["mcq_match"]
            if row_result["predicted_label"] is None:
                unresolved += 1
                category_bucket["unresolved_count"] += 1
        else:
            scored_text += 1
            category_bucket["scored_text_count"] += 1
            row_result["scoring_mode"] = "text_contains_fallback"
            row_result["primary_match"] = row_result["contains_match"]

        if row_result["primary_match"]:
            primary_correct += 1
            category_bucket["primary_correct"] += 1
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
        per_category[category] = {
            "scored_count": scored_count,
            "unscorable_count": bucket["unscorable_count"],
            "scored_mcq_count": bucket["scored_mcq_count"],
            "scored_text_count": bucket["scored_text_count"],
            "scored_llm_count": bucket["scored_llm_count"],
            "unresolved_count": bucket["unresolved_count"],
            "accuracy": (bucket["primary_correct"] / scored_count) if scored_count else None,
            "accuracy_contains": (bucket["contains_correct"] / scored_count) if scored_count else None,
            "accuracy_exact": (bucket["exact_correct"] / scored_count) if scored_count else None,
            "adjudication_rate": (
                bucket["scored_llm_count"] / bucket["scored_mcq_count"]
                if bucket["scored_mcq_count"]
                else None
            ),
        }

    summary = {
        "prompt_version": PROMPT_VERSION,
        "judge_model": judge.model,
        "total_rows": len(rows),
        "scored_count": scored,
        "unscorable_count": unscorable,
        "scored_mcq_count": scored_mcq,
        "scored_text_count": scored_text,
        "scored_llm_count": scored_llm,
        "unresolved_count": unresolved,
        "cache_hit_count": judge.cache_hits,
        "llm_call_count": judge.calls,
        "accuracy": (primary_correct / scored) if scored else None,
        "accuracy_mcq": (primary_correct / scored_mcq) if scored_mcq else None,
        "accuracy_contains": (contains_correct / scored) if scored else None,
        "accuracy_exact": (exact_correct / scored) if scored else None,
        "adjudication_rate": (scored_llm / scored_mcq) if scored_mcq else None,
        "per_category": per_category,
    }

    return {"rows": eval_rows, "summary": summary}


def main() -> int:
    parser = argparse.ArgumentParser(description="MemBench LLM-judge evaluator")
    parser.add_argument("hypothesis_file", type=Path, help="Input hypothesis JSONL")
    args = parser.parse_args()

    if not args.hypothesis_file.exists():
        print(f"Hypothesis file not found: {args.hypothesis_file}")
        return 1

    model = os.getenv("MEMBENCH_LLM_JUDGE_MODEL", "gpt-4o-mini")
    api_key = os.getenv("MEMBENCH_LLM_JUDGE_API_KEY") or os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("MEMBENCH_LLM_JUDGE_BASE_URL")
    timeout_seconds = float(os.getenv("MEMBENCH_LLM_JUDGE_TIMEOUT_SECONDS", "45"))
    max_retries = int(os.getenv("MEMBENCH_LLM_JUDGE_MAX_RETRIES", "3"))
    cache_path = Path(str(args.hypothesis_file) + ".llm_cache.json")

    judge = LLMJudge(
        model=model,
        api_key=api_key,
        base_url=base_url,
        timeout_seconds=timeout_seconds,
        max_retries=max_retries,
        cache_path=cache_path,
    )

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

        output = evaluate_rows(rows, judge)

        eval_path = Path(str(args.hypothesis_file) + ".eval.jsonl")
        summary_path = Path(str(args.hypothesis_file) + ".summary.json")

        with eval_path.open("w", encoding="utf-8") as f:
            for row in output["rows"]:
                f.write(json.dumps(row, ensure_ascii=True) + "\n")

        with summary_path.open("w", encoding="utf-8") as f:
            json.dump(output["summary"], f, indent=2)
            f.write("\n")

        print(f"MemBench LLM eval completed: {args.hypothesis_file}")
        print(f"Row-level output: {eval_path}")
        print(f"Summary output: {summary_path}")
        return 0

    except ValueError as exc:
        print(str(exc))
        return 1
    except Exception as exc:
        print(f"MemBench LLM eval failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
