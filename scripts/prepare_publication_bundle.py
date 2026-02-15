#!/usr/bin/env python3
"""Create a publication-ready bundle with manifest and checksums."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from typing import Dict


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True
        ).strip()
    except Exception:
        return "unknown"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build publication artifact bundle.")
    parser.add_argument("--results-file", required=True, type=Path, help="Results JSON path")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Bundle output directory. Defaults to results/final/<timestamp>",
    )
    parser.add_argument(
        "--report-template",
        type=Path,
        default=Path("docs/PUBLICATION_REPORT_TEMPLATE.md"),
        help="Report template file path",
    )
    args = parser.parse_args()

    if not args.results_file.exists():
        print(f"Results file not found: {args.results_file}")
        return 1
    if not args.report_template.exists():
        print(f"Report template not found: {args.report_template}")
        return 1

    stamp = dt.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    output_dir = args.output_dir or Path("results/final") / stamp
    output_dir.mkdir(parents=True, exist_ok=True)

    copied_results = output_dir / args.results_file.name
    copied_report = output_dir / "PUBLICATION_REPORT.md"
    shutil.copy2(args.results_file, copied_results)
    shutil.copy2(args.report_template, copied_report)

    files: Dict[str, str] = {
        copied_results.name: _sha256(copied_results),
        copied_report.name: _sha256(copied_report),
    }

    manifest = {
        "created_utc": dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "git_sha": _git_sha(),
        "source_results": str(args.results_file),
        "files": files,
    }

    manifest_path = output_dir / "manifest.json"
    with manifest_path.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")

    print(f"Publication bundle created: {output_dir}")
    print(f"Manifest: {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
