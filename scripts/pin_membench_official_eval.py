#!/usr/bin/env python3
"""Pin a MemBench official evaluator script into the repo with metadata."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Pin MemBench official evaluator script and metadata.")
    parser.add_argument("--source-script", type=Path, required=True, help="Path to official MemBench evaluator script")
    parser.add_argument("--repo-url", required=True, help="Official repository URL used to source evaluator")
    parser.add_argument("--commit", required=True, help="Pinned source commit hash")
    parser.add_argument(
        "--output-script",
        type=Path,
        default=Path("third_party/membench/official_eval.py"),
        help="Repo-relative output path for pinned evaluator script",
    )
    parser.add_argument(
        "--metadata-file",
        type=Path,
        default=Path("third_party/membench/official_eval.metadata.json"),
        help="Repo-relative metadata JSON output path",
    )
    args = parser.parse_args()

    source_script = args.source_script.resolve()
    if not source_script.exists():
        print(f"Source script not found: {source_script}")
        return 1
    if source_script.is_dir():
        print(f"Source script must be a file, got directory: {source_script}")
        return 1

    output_script = args.output_script
    output_script.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_script, output_script)

    metadata = {
        "pinned_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "repo_url": args.repo_url,
        "commit": args.commit,
        "source_script": str(source_script),
        "pinned_script": str(output_script),
        "script_sha256": _sha256(output_script),
    }

    metadata_path = args.metadata_file
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    with metadata_path.open("w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
        f.write("\n")

    print(f"Pinned MemBench evaluator: {output_script}")
    print(f"Metadata written: {metadata_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
