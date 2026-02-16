#!/usr/bin/env python3
"""Assemble final publication package from a validation campaign directory."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List


CAMPAIGN_ROOT_FILES = [
    "baseline_snapshot.json",
    "dependency_snapshot.txt",
    "frozen_sha.txt",
    "repeatability_summary.csv",
    "repeatability_notes.md",
]

RUN_FILES = [
    "results.json",
    "reconciliation_report.json",
    "run.log",
    "schema_check.log",
    "run_expectations.log",
    "longmemeval_eval.log",
    "membench_eval.log",
    "longmemeval_artifacts_check.log",
    "membench_artifacts_check.log",
]


def _sha256(file_path: Path) -> str:
    h = hashlib.sha256()
    with file_path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _copy_if_exists(src: Path, dst: Path, copied_files: List[Path]) -> None:
    if not src.exists():
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    copied_files.append(dst)


def _copy_tree_if_exists(src: Path, dst: Path, copied_files: List[Path]) -> None:
    if not src.exists() or not src.is_dir():
        return
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    for path in dst.rglob("*"):
        if path.is_file():
            copied_files.append(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Assemble publication package from campaign artifacts.")
    parser.add_argument("--campaign-dir", type=Path, required=True, help="Campaign directory with run_*/ artifacts")
    parser.add_argument("--output-dir", type=Path, required=True, help="Output release directory")
    parser.add_argument("--config", type=Path, default=None, help="Config used for campaign (for manifest metadata)")
    parser.add_argument(
        "--membench-eval-script",
        type=Path,
        default=Path("third_party/membench/official_eval.py"),
        help="Pinned MemBench official evaluator script to include in release package",
    )
    parser.add_argument(
        "--membench-eval-metadata",
        type=Path,
        default=Path("third_party/membench/official_eval.metadata.json"),
        help="Pinned MemBench evaluator metadata to include in release package",
    )
    args = parser.parse_args()

    campaign_dir = args.campaign_dir
    if not campaign_dir.exists():
        print(f"Campaign directory not found: {campaign_dir}")
        return 1

    run_dirs = sorted([p for p in campaign_dir.iterdir() if p.is_dir() and p.name.startswith("run_")])
    if not run_dirs:
        print(f"No run_* directories found under {campaign_dir}")
        return 1

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    copied_files: List[Path] = []

    for name in CAMPAIGN_ROOT_FILES:
        _copy_if_exists(campaign_dir / name, output_dir / name, copied_files)

    for run_dir in run_dirs:
        dst_run_dir = output_dir / run_dir.name
        dst_run_dir.mkdir(parents=True, exist_ok=True)
        for filename in RUN_FILES:
            _copy_if_exists(run_dir / filename, dst_run_dir / filename, copied_files)
        _copy_tree_if_exists(run_dir / "hybrid_eval", dst_run_dir / "hybrid_eval", copied_files)

    membench_dir = output_dir / "membench_official_eval"
    _copy_if_exists(args.membench_eval_script, membench_dir / "official_eval.py", copied_files)
    _copy_if_exists(args.membench_eval_metadata, membench_dir / "official_eval.metadata.json", copied_files)

    manifest_entries: List[Dict[str, object]] = []
    for file_path in sorted(copied_files):
        rel = file_path.relative_to(output_dir)
        manifest_entries.append(
            {
                "path": str(rel),
                "size_bytes": file_path.stat().st_size,
                "sha256": _sha256(file_path),
            }
        )

    manifest = {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "campaign_dir": str(campaign_dir),
        "config": str(args.config) if args.config else None,
        "run_directories": [run.name for run in run_dirs],
        "file_count": len(manifest_entries),
        "files": manifest_entries,
    }

    manifest_path = output_dir / "manifest.json"
    with manifest_path.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")

    print(f"Publication package assembled: {output_dir}")
    print(f"Manifest: {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
