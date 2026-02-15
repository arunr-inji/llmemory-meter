#!/usr/bin/env python3
"""Record pre-spend baseline metadata for reproducibility."""

from __future__ import annotations

import argparse
import json
import platform
import subprocess
from datetime import datetime
from pathlib import Path


def _run(cmd):
    try:
        return subprocess.check_output(cmd, text=True).strip()
    except Exception:
        return "unknown"


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

    payload = {
        "captured_utc": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "git_sha": _run(["git", "rev-parse", "HEAD"]),
        "git_branch": _run(["git", "branch", "--show-current"]),
        "python_version": _run(["python3", "--version"]),
        "platform": platform.platform(),
        "config_path": args.config,
        "required_env_vars": ["MEM0_API_KEY", "OPENAI_API_KEY", "MEMGPT_API_KEY", "ZEP_API_KEY"],
        "service_requirements": ["qdrant@localhost:6333"],
    }

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
        f.write("\n")

    print(f"Baseline snapshot written: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
