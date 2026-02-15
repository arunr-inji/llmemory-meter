"""Benchmark dataset loader and conversion utilities."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
import json
import zipfile
import tarfile
import re
from urllib.parse import urljoin

import httpx
from tqdm import tqdm

from llmemory_meter.workload import Workload, WorkloadStep


@dataclass(frozen=True)
class BenchmarkDatasetInfo:
    """Metadata describing a benchmark dataset source."""
    name: str
    file_name: str
    url: str


class BenchmarkLoader:
    """Load and convert external benchmark datasets to Workload format."""

    _LONGMEMEVAL_DATASETS: Dict[str, BenchmarkDatasetInfo] = {
        "S": BenchmarkDatasetInfo(
            name="LongMemEvalS",
            file_name="longmemeval_s_cleaned.json",
            url=(
                "https://huggingface.co/datasets/xiaowu0162/longmemeval-cleaned/"
                "resolve/main/longmemeval_s_cleaned.json"
            ),
        ),
        "M": BenchmarkDatasetInfo(
            name="LongMemEvalM",
            file_name="longmemeval_m_cleaned.json",
            url=(
                "https://huggingface.co/datasets/xiaowu0162/longmemeval-cleaned/"
                "resolve/main/longmemeval_m_cleaned.json"
            ),
        ),
        "oracle": BenchmarkDatasetInfo(
            name="LongMemEvalOracle",
            file_name="longmemeval_oracle.json",
            url=(
                "https://huggingface.co/datasets/xiaowu0162/longmemeval-cleaned/"
                "resolve/main/longmemeval_oracle.json"
            ),
        ),
    }
    _MEMBENCH_DRIVE_FILE_ID = "112Zraj4pTPH4Idph6i1uMOLA_LPFdGr0"
    _MEMBENCH_ARCHIVE_NAME = "membench_data.zip"

    @classmethod
    def data_dir(cls) -> Path:
        return Path(__file__).resolve().parent.parent / "benchmarks_data"

    @classmethod
    def longmemeval_dir(cls) -> Path:
        return cls.data_dir() / "longmemeval"

    @classmethod
    def membench_dir(cls) -> Path:
        return cls.data_dir() / "membench"

    @classmethod
    def validate_datasets(cls) -> Dict[str, bool]:
        """Check local availability of benchmark datasets."""
        longmemeval_ready = all(
            (cls.longmemeval_dir() / info.file_name).exists()
            for info in cls._LONGMEMEVAL_DATASETS.values()
        )
        membench_ready = cls.membench_dir().exists() and any(
            cls.membench_dir().rglob("*.json")
        )
        return {
            "longmemeval": longmemeval_ready,
            "membench": membench_ready,
        }

    @classmethod
    def load_longmemeval(
        cls,
        subset: str = "S",
        limit: Optional[int] = None,
        data_dir: Optional[Path] = None,
    ) -> List[Workload]:
        """Load LongMemEval dataset and convert to workloads.

        Args:
            subset: "S" (115K tokens), "M" (1.5M tokens), or "oracle".
            limit: Optional limit of question count.
            data_dir: Override default data directory.
        """
        dataset_info = cls._LONGMEMEVAL_DATASETS.get(subset)
        if not dataset_info:
            raise ValueError("LongMemEval subset must be one of: S, M, oracle")

        target_dir = data_dir or cls.longmemeval_dir()
        target_dir.mkdir(parents=True, exist_ok=True)
        data_path = target_dir / dataset_info.file_name

        if not data_path.exists():
            cls._download_file(dataset_info.url, data_path)

        with data_path.open("r", encoding="utf-8") as f:
            entries = json.load(f)

        if limit:
            entries = entries[:limit]

        workloads = []
        for entry in entries:
            workloads.append(cls._convert_longmemeval_entry(entry))

        return workloads

    @classmethod
    def get_longmemeval_path(
        cls,
        subset: str = "S",
        data_dir: Optional[Path] = None,
    ) -> Path:
        """Ensure LongMemEval dataset file is available and return path."""
        dataset_info = cls._LONGMEMEVAL_DATASETS.get(subset)
        if not dataset_info:
            raise ValueError("LongMemEval subset must be one of: S, M, oracle")

        target_dir = data_dir or cls.longmemeval_dir()
        target_dir.mkdir(parents=True, exist_ok=True)
        data_path = target_dir / dataset_info.file_name

        if not data_path.exists():
            cls._download_file(dataset_info.url, data_path)

        return data_path

    @classmethod
    def load_membench(
        cls,
        categories: Optional[List[str]] = None,
        limit: Optional[int] = None,
        data_dir: Optional[Path] = None,
        auto_download: bool = True,
    ) -> List[Workload]:
        """Load MemBench dataset and convert to workloads.

        Args:
            categories: Optional list of category names to include.
            limit: Optional limit of total workloads to create.
            data_dir: Override default data directory.
            auto_download: Download dataset archive if missing.
        """
        target_dir = data_dir or cls.membench_dir()
        target_dir.mkdir(parents=True, exist_ok=True)

        if not any(target_dir.rglob("*.json")):
            if auto_download:
                cls._download_membench_archive(target_dir)
            else:
                raise FileNotFoundError(
                    "MemBench dataset not found. Download the dataset and place it under "
                    f"{target_dir}."
                )

        json_files = sorted(target_dir.rglob("*.json"))
        if categories:
            lowered = {c.lower() for c in categories}
            json_files = [
                path for path in json_files
                if path.stem.lower() in lowered or path.parent.name.lower() in lowered
            ]

        if not json_files:
            raise FileNotFoundError(
                "No MemBench JSON files found after filtering. "
                "Check dataset placement and category names."
            )

        workloads: List[Workload] = []
        for json_file in json_files:
            with json_file.open("r", encoding="utf-8") as f:
                data = json.load(f)

            items = cls._extract_membench_items(data)
            if not items:
                # Some MemBench files contain auxiliary/noise data only.
                continue

            for idx, item in enumerate(items):
                workload = cls._convert_membench_entry(item, json_file.stem, idx)
                if workload:
                    workloads.append(workload)
                if limit and len(workloads) >= limit:
                    return workloads

        return workloads

    @classmethod
    def _extract_membench_items(cls, payload: Any) -> List[Dict[str, Any]]:
        """Extract QA-style MemBench entries from varied dataset layouts."""
        extracted: List[Dict[str, Any]] = []

        def walk(node: Any) -> None:
            if isinstance(node, dict):
                direct = cls._normalize_membench_raw_entry(node)
                if direct:
                    extracted.append(direct)
                    if "QA" in node and "message_list" in node:
                        return

                for value in node.values():
                    if isinstance(value, (list, dict)):
                        walk(value)
                return

            if isinstance(node, list):
                for item in node:
                    walk(item)

        walk(payload)
        return extracted

    @staticmethod
    def _normalize_membench_raw_entry(entry: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Normalize MemBench raw records into question/answer/history shape."""
        qa = entry.get("QA")
        message_list = entry.get("message_list")
        if isinstance(qa, dict) and message_list is not None:
            question = qa.get("question")
            if not question:
                return None

            answer = qa.get("answer")
            if answer is None:
                ground_truth = qa.get("ground_truth")
                choices = qa.get("choices")
                if isinstance(ground_truth, str) and isinstance(choices, dict):
                    answer = choices.get(ground_truth, ground_truth)
                else:
                    answer = ground_truth

            return {
                "question": question,
                "answer": answer,
                "history": message_list,
            }

        # Already normalized shape from previously supported format.
        has_question = any(key in entry for key in ("question", "query", "prompt", "instruction"))
        if has_question:
            return entry

        return None

    @classmethod
    def get_membench_root(cls, data_dir: Optional[Path] = None) -> Path:
        """Return MemBench dataset root directory."""
        target_dir = data_dir or cls.membench_dir()
        target_dir.mkdir(parents=True, exist_ok=True)
        return target_dir

    @classmethod
    def _convert_longmemeval_entry(cls, entry: Dict[str, Any]) -> Workload:
        question_id = entry.get("question_id", "unknown")
        question = entry.get("question", "")
        answer = entry.get("answer", "")
        question_type = entry.get("question_type", "unknown")
        question_date = entry.get("question_date")
        session_ids = entry.get("haystack_session_ids", [])
        session_dates = entry.get("haystack_dates", [])
        sessions = entry.get("haystack_sessions", [])
        answer_sessions = set(entry.get("answer_session_ids", []))

        steps: List[WorkloadStep] = []
        for idx, session in enumerate(sessions):
            session_id = session_ids[idx] if idx < len(session_ids) else None
            session_date = session_dates[idx] if idx < len(session_dates) else None
            content = cls._format_longmemeval_session(session, session_date)
            metadata = {
                "benchmark": "longmemeval",
                "question_id": question_id,
                "question_type": question_type,
                "session_id": session_id,
                "session_index": idx,
                "has_answer_session": session_id in answer_sessions if session_id is not None else None,
            }
            if session_date:
                metadata["session_date"] = session_date
            steps.append(
                WorkloadStep(
                    action="store",
                    content=content,
                    metadata=metadata,
                )
            )

        steps.append(
            WorkloadStep(
                action="retrieve",
                content=question,
                ground_truth=str(answer),
                metadata={
                    "benchmark": "longmemeval",
                    "question_id": question_id,
                    "question_type": question_type,
                    "question_date": question_date,
                },
            )
        )

        return Workload(
            name=f"LongMemEval {question_id}",
            description=f"LongMemEval question ({question_type})",
            steps=steps,
            expected_outcomes={"question_id": question_id},
        )

    @classmethod
    def _convert_membench_entry(
        cls,
        entry: Dict[str, Any],
        category: str,
        index: int,
    ) -> Optional[Workload]:
        question = cls._first_present(entry, ["question", "query", "prompt", "instruction"])
        answer = cls._first_present(entry, ["answer", "ground_truth", "gold", "target"])
        history = cls._first_present(entry, ["history", "conversation", "dialogue", "context", "memory", "messages", "sessions"])

        if not question:
            return None

        steps: List[WorkloadStep] = []
        for content, metadata in cls._normalize_history(history):
            steps.append(
                WorkloadStep(
                    action="store",
                    content=content,
                    metadata=metadata,
                )
            )

        steps.append(
            WorkloadStep(
                action="retrieve",
                content=question,
                ground_truth=str(answer) if answer is not None else None,
                metadata={
                    "benchmark": "membench",
                    "category": category,
                    "workload_id": f"membench::{category}::{index + 1}",
                    "ground_truth": str(answer) if answer is not None else None,
                    "match_type": "contains",
                },
                match_type="contains",
            )
        )

        return Workload(
            name=f"MemBench {category} #{index + 1}",
            description="MemBench memory evaluation task",
            steps=steps,
        )

    @staticmethod
    def _first_present(entry: Dict[str, Any], keys: Iterable[str]) -> Any:
        for key in keys:
            if key in entry and entry[key] is not None:
                return entry[key]
        return None

    @classmethod
    def _normalize_history(cls, history: Any) -> List[Tuple[str, Dict[str, Any]]]:
        if history is None:
            return []

        normalized: List[Tuple[str, Dict[str, Any]]] = []

        if isinstance(history, list):
            if all(isinstance(item, str) for item in history):
                for idx, text in enumerate(history):
                    normalized.append((text, {"history_index": idx}))
            elif all(isinstance(item, dict) for item in history):
                for idx, item in enumerate(history):
                    role = item.get("role", "unknown")
                    content = item.get("content", "")
                    normalized.append((f"{role}: {content}", {"history_index": idx, "role": role}))
            elif all(isinstance(item, list) for item in history):
                for idx, session in enumerate(history):
                    session_text = cls._format_session(session, idx)
                    normalized.append((session_text, {"session_index": idx}))
            else:
                normalized.append((json.dumps(history, ensure_ascii=True), {}))
        elif isinstance(history, dict):
            if "sessions" in history and isinstance(history["sessions"], list):
                return cls._normalize_history(history["sessions"])
            normalized.append((json.dumps(history, ensure_ascii=True), {}))
        else:
            normalized.append((str(history), {}))

        return normalized

    @staticmethod
    def _format_session(session: Any, session_index: int) -> str:
        if isinstance(session, list):
            lines = []
            for turn in session:
                if isinstance(turn, dict):
                    if "user_message" in turn or "assistant_message" in turn:
                        user_message = turn.get("user_message")
                        assistant_message = turn.get("assistant_message")
                        if user_message:
                            lines.append(f"user: {user_message}")
                        if assistant_message:
                            lines.append(f"assistant: {assistant_message}")

                        # Preserve structured memory hints when available.
                        rel = turn.get("rel")
                        attr = turn.get("attr")
                        value = turn.get("value")
                        if rel and attr and value is not None:
                            lines.append(f"memory_fact: {rel}.{attr}={value}")
                        continue

                    role = turn.get("role", "unknown")
                    content = turn.get("content", "")
                    lines.append(f"{role}: {content}")
                else:
                    lines.append(str(turn))
            return "\n".join(lines)
        return f"Session {session_index}: {session}"

    @staticmethod
    def _format_longmemeval_session(session: Any, session_date: Optional[str]) -> str:
        lines = []
        if session_date:
            lines.append(f"[Session date: {session_date}]")

        if isinstance(session, list):
            for turn in session:
                if isinstance(turn, dict):
                    role = turn.get("role", "unknown")
                    content = turn.get("content", "")
                    marker = " (evidence)" if turn.get("has_answer") else ""
                    lines.append(f"{role}{marker}: {content}")
                else:
                    lines.append(str(turn))
        else:
            lines.append(str(session))

        return "\n".join(lines)

    @classmethod
    def _download_file(cls, url: str, target_path: Path) -> None:
        target_path.parent.mkdir(parents=True, exist_ok=True)

        with httpx.stream("GET", url, follow_redirects=True, timeout=120) as response:
            response.raise_for_status()
            total = int(response.headers.get("content-length", 0))
            with target_path.open("wb") as f, tqdm(
                total=total,
                unit="B",
                unit_scale=True,
                desc=f"Downloading {target_path.name}",
            ) as pbar:
                for chunk in response.iter_bytes():
                    if chunk:
                        f.write(chunk)
                        pbar.update(len(chunk))

    @classmethod
    def _download_membench_archive(cls, target_dir: Path) -> None:
        archive_path = target_dir / cls._MEMBENCH_ARCHIVE_NAME
        file_id = cls._MEMBENCH_DRIVE_FILE_ID
        download_url = f"https://drive.google.com/uc?export=download&id={file_id}"

        with httpx.Client(follow_redirects=True, timeout=120) as client:
            response = client.get(download_url)
            content_type = response.headers.get("content-type", "").lower()
            if "text/html" in content_type and "download-form" in response.text:
                action_url, params = cls._extract_drive_download_form(response.text)
                if action_url and params:
                    response = client.get(action_url, params=params)
                else:
                    confirm_token = cls._extract_confirm_token(response.text)
                    if confirm_token:
                        response = client.get(
                            "https://drive.google.com/uc",
                            params={"export": "download", "confirm": confirm_token, "id": file_id},
                        )

            response.raise_for_status()
            with archive_path.open("wb") as f:
                for chunk in response.iter_bytes():
                    if chunk:
                        f.write(chunk)

        if not zipfile.is_zipfile(archive_path) and not tarfile.is_tarfile(archive_path):
            with archive_path.open("r", encoding="utf-8", errors="ignore") as f:
                preview = f.read(400)
            raise ValueError(
                f"MemBench download did not produce a valid archive: {archive_path}. "
                f"File preview: {preview!r}"
            )

        cls._extract_archive(archive_path, target_dir)

    @staticmethod
    def _extract_confirm_token(html_text: str) -> Optional[str]:
        marker = "confirm="
        if marker not in html_text:
            return None
        start = html_text.find(marker) + len(marker)
        end = html_text.find("&", start)
        if end == -1:
            end = start + 100
        return html_text[start:end]

    @staticmethod
    def _extract_drive_download_form(html_text: str) -> Tuple[Optional[str], Dict[str, str]]:
        form_match = re.search(
            r'<form[^>]*id=["\']download-form["\'][^>]*action=["\']([^"\']+)["\']',
            html_text,
            flags=re.IGNORECASE,
        )
        action_url: Optional[str] = None
        if form_match:
            action_url = urljoin("https://drive.google.com", form_match.group(1))

        params: Dict[str, str] = {}
        input_pattern = re.compile(r"<input[^>]+>", flags=re.IGNORECASE)
        for tag in input_pattern.findall(html_text):
            name_match = re.search(r'name=["\']([^"\']+)["\']', tag, flags=re.IGNORECASE)
            value_match = re.search(r'value=["\']([^"\']*)["\']', tag, flags=re.IGNORECASE)
            type_match = re.search(r'type=["\']([^"\']+)["\']', tag, flags=re.IGNORECASE)
            if not name_match or not value_match:
                continue
            if type_match and type_match.group(1).lower() != "hidden":
                continue
            params[name_match.group(1)] = value_match.group(1)

        if not action_url and params:
            action_url = "https://drive.google.com/uc"

        return action_url, params

    @staticmethod
    def _extract_archive(archive_path: Path, target_dir: Path) -> None:
        if zipfile.is_zipfile(archive_path):
            with zipfile.ZipFile(archive_path, "r") as zip_ref:
                zip_ref.extractall(target_dir)
            return

        if tarfile.is_tarfile(archive_path):
            with tarfile.open(archive_path, "r:*") as tar_ref:
                tar_ref.extractall(target_dir)
            return

        raise ValueError(f"Unsupported archive format: {archive_path}")
