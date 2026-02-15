"""Hybrid evaluation utilities for industry benchmarks."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
import json
import subprocess
import sys

from llmemory_meter.benchmark_loader import BenchmarkLoader


@dataclass(frozen=True)
class HybridEvalResult:
    """Standardized hybrid evaluation result."""
    benchmark: str
    tool_name: str
    judge_model: str
    accuracy: Optional[float]
    per_question_type: Optional[Dict[str, float]]
    hypothesis_file: Path
    eval_log_file: Optional[Path] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "benchmark": self.benchmark,
            "tool_name": self.tool_name,
            "judge_model": self.judge_model,
            "accuracy": self.accuracy,
            "per_question_type": self.per_question_type,
            "hypothesis_file": str(self.hypothesis_file),
            "eval_log_file": str(self.eval_log_file) if self.eval_log_file else None,
            "error": self.error,
        }


class HybridEvaluator:
    """Dispatch hybrid evaluation for supported benchmarks."""

    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = data_dir

    def evaluate_longmemeval(
        self,
        tool_name: str,
        workload_results: Dict[str, Any],
        subset: str = "S",
        judge_model: str = "gpt-4o",
        output_dir: Optional[Path] = None,
    ) -> HybridEvalResult:
        evaluator = LongMemEvalEvaluator(data_dir=self.data_dir)
        return evaluator.evaluate(tool_name, workload_results, subset, judge_model, output_dir)

    def evaluate_membench(
        self,
        tool_name: str,
        workload_results: Dict[str, Any],
        eval_script: Optional[Path] = None,
        output_dir: Optional[Path] = None,
    ) -> HybridEvalResult:
        evaluator = MemBenchEvaluator()
        return evaluator.evaluate(tool_name, workload_results, eval_script, output_dir)


class LongMemEvalEvaluator:
    """Run LongMemEval official evaluation script."""

    _EVAL_SCRIPT_URL = (
        "https://raw.githubusercontent.com/xiaowu0162/LongMemEval/main/src/evaluation/evaluate_qa.py"
    )
    _ALLOWED_JUDGE_MODELS = {
        "gpt-4o",
        "gpt-4",
        "gpt-3.5-turbo",
        "claude-3-sonnet",
    }

    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = data_dir
        self.eval_dir = BenchmarkLoader.data_dir() / "longmemeval_eval"
        self.eval_dir.mkdir(parents=True, exist_ok=True)
        self.eval_script_path = self.eval_dir / "evaluate_qa.py"
        if not self.eval_script_path.exists():
            BenchmarkLoader._download_file(self._EVAL_SCRIPT_URL, self.eval_script_path)

    def evaluate(
        self,
        tool_name: str,
        workload_results: Dict[str, Any],
        subset: str,
        judge_model: str,
        output_dir: Optional[Path],
    ) -> HybridEvalResult:
        self._validate_judge_model(judge_model)
        output_path = output_dir or (BenchmarkLoader.data_dir() / "hybrid_eval")
        output_path.mkdir(parents=True, exist_ok=True)

        hypotheses = self._extract_hypotheses(workload_results, tool_name)
        if not hypotheses:
            return HybridEvalResult(
                benchmark="longmemeval",
                tool_name=tool_name,
                judge_model=judge_model,
                accuracy=None,
                per_question_type=None,
                hypothesis_file=output_path / f"{tool_name}_longmemeval_{subset}_hypothesis.jsonl",
                error="No LongMemEval hypotheses found in results.",
            )

        hypothesis_file = output_path / f"{tool_name}_longmemeval_{subset}_hypothesis.jsonl"
        with hypothesis_file.open("w", encoding="utf-8") as f:
            for entry in hypotheses:
                f.write(json.dumps(entry, ensure_ascii=True) + "\n")

        try:
            data_path = BenchmarkLoader.get_longmemeval_path(subset=subset, data_dir=self.data_dir)
            eval_log_path = Path(f"{hypothesis_file}.eval-results-{judge_model}")
            self._run_eval_script(judge_model, hypothesis_file, data_path)
            accuracy, per_type = self._parse_eval_results(eval_log_path, data_path)
            return HybridEvalResult(
                benchmark="longmemeval",
                tool_name=tool_name,
                judge_model=judge_model,
                accuracy=accuracy,
                per_question_type=per_type,
                hypothesis_file=hypothesis_file,
                eval_log_file=eval_log_path,
            )
        except Exception as exc:
            return HybridEvalResult(
                benchmark="longmemeval",
                tool_name=tool_name,
                judge_model=judge_model,
                accuracy=None,
                per_question_type=None,
                hypothesis_file=hypothesis_file,
                error=str(exc),
            )

    def _run_eval_script(self, judge_model: str, hypothesis_file: Path, ref_file: Path) -> None:
        self._validate_judge_model(judge_model)
        result = subprocess.run(
            [
                sys.executable,
                str(self.eval_script_path),
                judge_model,
                str(hypothesis_file),
                str(ref_file),
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(
                "LongMemEval evaluation failed: "
                f"{result.stderr.strip() or result.stdout.strip()}"
            )

    @classmethod
    def _validate_judge_model(cls, model: str) -> None:
        if model not in cls._ALLOWED_JUDGE_MODELS:
            allowed = ", ".join(sorted(cls._ALLOWED_JUDGE_MODELS))
            raise ValueError(f"Invalid judge model: {model}. Allowed: {allowed}")

    @staticmethod
    def _extract_hypotheses(workload_results: Dict[str, Any], tool_name: str) -> List[Dict[str, Any]]:
        hypotheses = {}
        for workload_name, tool_data in workload_results.items():
            if not isinstance(tool_data, dict):
                continue
            result = tool_data.get(tool_name)
            if not isinstance(result, dict):
                continue
            step_results = result.get("step_results", [])
            for step in step_results:
                if step.get("action") != "retrieve":
                    continue
                metadata = step.get("metadata") or {}
                question_id = metadata.get("question_id")
                if not question_id:
                    continue
                response = step.get("response", "").strip()
                hypotheses[question_id] = {
                    "question_id": question_id,
                    "hypothesis": response,
                }
        return list(hypotheses.values())

    @staticmethod
    def _parse_eval_results(
        eval_file: Path,
        reference_file: Path,
    ) -> tuple[float, Dict[str, float]]:
        if not eval_file.exists():
            raise FileNotFoundError(f"Missing evaluation file: {eval_file}")

        with eval_file.open("r", encoding="utf-8") as f:
            logs = [json.loads(line) for line in f if line.strip()]

        if not logs:
            return 0.0, {}

        labels = [1 if entry.get("autoeval_label", {}).get("label") else 0 for entry in logs]
        accuracy = sum(labels) / len(labels)

        with reference_file.open("r", encoding="utf-8") as f:
            references = json.load(f)
        qid2type = {entry["question_id"]: entry.get("question_type", "unknown") for entry in references}

        per_type: Dict[str, List[int]] = {}
        for entry, label in zip(logs, labels):
            qtype = qid2type.get(entry.get("question_id"), "unknown")
            per_type.setdefault(qtype, []).append(label)

        per_type_accuracy = {
            qtype: sum(scores) / len(scores) if scores else 0.0
            for qtype, scores in per_type.items()
        }

        return accuracy, per_type_accuracy


class MemBenchEvaluator:
    """Run MemBench official evaluation scripts when provided."""

    _REQUIRED_FIELDS = (
        "workload_id",
        "benchmark",
        "category",
        "hypothesis",
        "match_type",
        "metadata",
    )

    def evaluate(
        self,
        tool_name: str,
        workload_results: Dict[str, Any],
        eval_script: Optional[Path],
        output_dir: Optional[Path],
    ) -> HybridEvalResult:
        output_path = output_dir or (BenchmarkLoader.data_dir() / "hybrid_eval")
        output_path.mkdir(parents=True, exist_ok=True)
        hypothesis_file = output_path / f"{tool_name}_membench_hypothesis.jsonl"

        hypotheses = self._extract_hypotheses(workload_results, tool_name)
        if not hypotheses:
            return HybridEvalResult(
                benchmark="membench",
                tool_name=tool_name,
                judge_model="membench",
                accuracy=None,
                per_question_type=None,
                hypothesis_file=hypothesis_file,
                error="No MemBench hypotheses found in results.",
            )

        contract_issues = self._validate_hypothesis_contract(hypotheses)
        if contract_issues:
            return HybridEvalResult(
                benchmark="membench",
                tool_name=tool_name,
                judge_model="membench",
                accuracy=None,
                per_question_type=None,
                hypothesis_file=hypothesis_file,
                error=(
                    "MemBench hypothesis contract validation failed before eval script run: "
                    + "; ".join(contract_issues[:5])
                    + (" ..." if len(contract_issues) > 5 else "")
                ),
            )

        with hypothesis_file.open("w", encoding="utf-8") as f:
            for entry in hypotheses:
                f.write(json.dumps(entry, ensure_ascii=True) + "\n")

        if not eval_script:
            return HybridEvalResult(
                benchmark="membench",
                tool_name=tool_name,
                judge_model="membench",
                accuracy=None,
                per_question_type=None,
                hypothesis_file=hypothesis_file,
                error="MemBench eval_script not configured.",
            )

        eval_mode = self._resolve_eval_mode(eval_script)

        summary_path = Path(f"{hypothesis_file}.summary.json")
        row_eval_path = Path(f"{hypothesis_file}.eval.jsonl")
        for stale_path in (summary_path, row_eval_path):
            if stale_path.exists():
                stale_path.unlink()

        result = subprocess.run(
            [sys.executable, str(eval_script), str(hypothesis_file)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return HybridEvalResult(
                benchmark="membench",
                tool_name=tool_name,
                judge_model=eval_mode,
                accuracy=None,
                per_question_type=None,
                hypothesis_file=hypothesis_file,
                error=result.stderr.strip() or result.stdout.strip(),
            )

        if not summary_path.exists():
            output_snippet = (result.stdout.strip() or result.stderr.strip())
            if output_snippet:
                output_snippet = f" Script output: {output_snippet}"
            else:
                output_snippet = ""
            return HybridEvalResult(
                benchmark="membench",
                tool_name=tool_name,
                judge_model=eval_mode,
                accuracy=None,
                per_question_type=None,
                hypothesis_file=hypothesis_file,
                error=(
                    f"MemBench eval script succeeded but summary file was not created: {summary_path}."
                    f"{output_snippet}"
                ),
            )

        try:
            with summary_path.open("r", encoding="utf-8") as f:
                summary = json.load(f)
            if not isinstance(summary, dict):
                raise ValueError("summary JSON payload must be an object")
        except Exception as exc:
            return HybridEvalResult(
                benchmark="membench",
                tool_name=tool_name,
                judge_model=eval_mode,
                accuracy=None,
                per_question_type=None,
                hypothesis_file=hypothesis_file,
                error=f"Failed to parse MemBench summary file '{summary_path}': {exc}",
            )

        # Deterministic script is kept as a diagnostic canary only (not publication accuracy).
        if eval_mode == "deterministic_canary":
            return HybridEvalResult(
                benchmark="membench",
                tool_name=tool_name,
                judge_model=eval_mode,
                accuracy=None,
                per_question_type=None,
                hypothesis_file=hypothesis_file,
                eval_log_file=summary_path if summary_path.exists() else None,
            )

        accuracy, per_category = self._parse_official_summary(summary)

        return HybridEvalResult(
            benchmark="membench",
            tool_name=tool_name,
            judge_model=eval_mode,
            accuracy=accuracy,
            per_question_type=per_category,
            hypothesis_file=hypothesis_file,
            eval_log_file=summary_path if summary_path.exists() else None,
        )

    @staticmethod
    def _validate_hypothesis_contract(rows: List[Dict[str, Any]]) -> List[str]:
        issues: List[str] = []
        for idx, row in enumerate(rows, start=1):
            for field in MemBenchEvaluator._REQUIRED_FIELDS:
                if field not in row:
                    issues.append(f"row {idx}: missing field '{field}'")
            if row.get("benchmark") != "membench":
                issues.append(f"row {idx}: benchmark must be 'membench'")
            if not isinstance(row.get("workload_id"), str) or not row.get("workload_id", "").strip():
                issues.append(f"row {idx}: workload_id must be a non-empty string")
            if not isinstance(row.get("category"), str) or not row.get("category", "").strip():
                issues.append(f"row {idx}: category must be a non-empty string")
            if not isinstance(row.get("hypothesis"), str):
                issues.append(f"row {idx}: hypothesis must be a string")
            if not isinstance(row.get("match_type"), str):
                issues.append(f"row {idx}: match_type must be a string")
            if row.get("match_type") not in {"contains", "exact"}:
                issues.append(f"row {idx}: match_type must be one of ['contains', 'exact']")
            if not isinstance(row.get("metadata"), dict):
                issues.append(f"row {idx}: metadata must be an object")
        return issues

    @staticmethod
    def _resolve_eval_mode(eval_script: Path) -> str:
        deterministic_script = Path(__file__).resolve().parents[1] / "scripts" / "membench_eval.py"
        if eval_script.resolve() == deterministic_script.resolve():
            return "deterministic_canary"
        return "official"

    @staticmethod
    def _coerce_float(value: Any) -> Optional[float]:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @classmethod
    def _parse_official_summary(cls, summary: Dict[str, Any]) -> tuple[Optional[float], Optional[Dict[str, float]]]:
        accuracy: Optional[float] = None
        for key in ("accuracy", "overall_accuracy", "acc", "score", "accuracy_contains"):
            candidate = cls._coerce_float(summary.get(key))
            if candidate is not None:
                accuracy = candidate
                break

        per_category = None
        for key in ("per_category", "per_question_type", "by_category"):
            category_metrics = summary.get(key)
            if not isinstance(category_metrics, dict):
                continue
            parsed: Dict[str, float] = {}
            for category, metrics in category_metrics.items():
                if isinstance(metrics, dict):
                    score = None
                    for nested_key in ("accuracy", "overall_accuracy", "acc", "score", "accuracy_contains"):
                        score = cls._coerce_float(metrics.get(nested_key))
                        if score is not None:
                            break
                else:
                    score = cls._coerce_float(metrics)
                if score is not None:
                    parsed[category] = score
            if parsed:
                per_category = parsed
                break

        return accuracy, per_category

    @staticmethod
    def _extract_hypotheses(workload_results: Dict[str, Any], tool_name: str) -> List[Dict[str, Any]]:
        hypotheses = []
        for workload_name, tool_data in workload_results.items():
            if not isinstance(tool_data, dict):
                continue
            result = tool_data.get(tool_name)
            if not isinstance(result, dict):
                continue
            step_results = result.get("step_results", [])
            for step in step_results:
                if step.get("action") != "retrieve":
                    continue
                metadata = step.get("metadata") or {}
                category = str(metadata.get("category", "unknown") or "unknown")
                workload_id = metadata.get("workload_id") or f"membench::{workload_name}"
                match_type = str(metadata.get("match_type", "contains") or "contains").lower()
                if match_type not in {"contains", "exact"}:
                    match_type = "contains"
                choices = metadata.get("choices")
                normalized_choices = None
                if isinstance(choices, dict):
                    normalized_choices = {
                        str(key): str(value)
                        for key, value in choices.items()
                        if key is not None and value is not None
                    }
                ground_truth_label = metadata.get("ground_truth_label")
                hypotheses.append({
                    "workload_id": str(workload_id),
                    "benchmark": "membench",
                    "workload": workload_name,
                    "category": category,
                    "ground_truth": metadata.get("ground_truth"),
                    "ground_truth_label": (
                        str(ground_truth_label) if ground_truth_label is not None else None
                    ),
                    "choices": normalized_choices,
                    "hypothesis": step.get("response", "").strip(),
                    "match_type": match_type,
                    "metadata": metadata,
                })
        return hypotheses
