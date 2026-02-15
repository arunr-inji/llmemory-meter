#!/usr/bin/env python3
"""Record pre-spend baseline metadata for reproducibility."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def _run(cmd):
    try:
        return subprocess.check_output(cmd, text=True).strip()
    except Exception:
        return "unknown"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Record baseline metadata")
    parser.add_argument(
        "--config",
        default="configs/industry-benchmarks.yml",
        help="Config path for upcoming runs",
    )
    parser.add_argument(
        "--output",
        default="results/validation_runs/baseline_snapshot.json",
        help="Output JSON path",
    )
    args = parser.parse_args()

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    default_eval_script = Path("third_party/membench/official_eval.py")
    eval_script = Path(os.getenv("MEMBENCH_OFFICIAL_EVAL_SCRIPT", str(default_eval_script)))
    metadata_file = Path(
        os.getenv("MEMBENCH_OFFICIAL_EVAL_METADATA", "third_party/membench/official_eval.metadata.json")
    )
    metadata_payload = None
    if metadata_file.exists():
        try:
            with metadata_file.open("r", encoding="utf-8") as f:
                metadata_payload = json.load(f)
        except Exception:
            metadata_payload = "unparseable"

    payload = {
        "captured_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "git_sha": _run(["git", "rev-parse", "HEAD"]),
        "git_branch": _run(["git", "branch", "--show-current"]),
        "python_version": _run(["python3", "--version"]),
        "platform": platform.platform(),
        "config_path": args.config,
        "required_env_vars": ["MEM0_API_KEY", "OPENAI_API_KEY", "MEMGPT_API_KEY", "ZEP_API_KEY"],
        "service_requirements": ["qdrant@localhost:6333"],
        "membench_official_eval": {
            "script_path": str(eval_script),
            "script_exists": eval_script.exists(),
            "script_sha256": _sha256(eval_script) if eval_script.exists() else None,
            "metadata_file": str(metadata_file),
            "metadata": metadata_payload,
        },
    }

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
        f.write("\n")

    print(f"Baseline snapshot written: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
