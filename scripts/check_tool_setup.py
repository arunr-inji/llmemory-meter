#!/usr/bin/env python3
"""Validate enabled tool setup and required services for a config."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import List

import httpx
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from llmemory_meter.config_parser import ConfigManager


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate tool setup for a benchmark config")
    parser.add_argument("--config", default="configs/industry-benchmarks.yml", help="Config path")
    args = parser.parse_args()

    config = ConfigManager.load_config(args.config)
    issues: List[str] = []

    config_issues = ConfigManager.validate_config(config)
    issues.extend(config_issues)

    for tool in config.memory_tools:
        if not tool.enabled:
            continue

        if tool.api_key_env and not os.getenv(tool.api_key_env):
            issues.append(f"{tool.name}: missing env var {tool.api_key_env}")

        if tool.name == "mem0":
            settings = tool.settings or {}
            vector_store = settings.get("vector_store", {})
            provider = vector_store.get("provider")
            if provider == "qdrant":
                host = vector_store.get("host", "localhost")
                port = vector_store.get("port", 6333)
                url = f"http://{host}:{port}/collections"
                try:
                    response = httpx.get(url, timeout=5)
                    if response.status_code >= 400:
                        issues.append(f"mem0: qdrant check failed at {url} status={response.status_code}")
                except Exception as exc:
                    issues.append(f"mem0: qdrant not reachable at {url} ({exc})")

    if issues:
        print("Tool setup validation failed:")
        for issue in issues:
            print(f"- {issue}")
        return 1

    print(f"Tool setup validation passed for config: {args.config}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
