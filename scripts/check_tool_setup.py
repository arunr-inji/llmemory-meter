#!/usr/bin/env python3
"""Validate enabled tool setup and required services for a config."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import List, Optional

import httpx
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from llmemory_meter.config_parser import ConfigManager


def _status_code_from_exception(exc: Exception) -> Optional[int]:
    for attr in ("status_code", "status"):
        value = getattr(exc, attr, None)
        if isinstance(value, int):
            return value
    response = getattr(exc, "response", None)
    if response is not None:
        code = getattr(response, "status_code", None)
        if isinstance(code, int):
            return code
    return None


def _probe_openai_auth(api_key: str, timeout_seconds: float) -> Optional[str]:
    try:
        response = httpx.get(
            "https://api.openai.com/v1/models",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout_seconds,
        )
        if response.status_code == 200:
            return None
        body_snippet = response.text[:180].replace("\n", " ")
        return f"openai: auth probe failed status={response.status_code} body={body_snippet!r}"
    except Exception as exc:
        return f"openai: auth probe request failed ({exc})"


def _probe_memgpt_auth(api_key: str) -> Optional[str]:
    try:
        from letta_client import Letta
    except Exception as exc:
        return f"memgpt: letta-client unavailable for auth probe ({exc})"

    try:
        client = Letta(api_key=api_key)
        list(client.agents.list())  # read-only call
        return None
    except Exception as exc:
        status = _status_code_from_exception(exc)
        if status in (401, 403):
            return f"memgpt: auth probe unauthorized status={status}"
        return f"memgpt: auth probe failed ({type(exc).__name__}: {str(exc)[:200]})"


def _probe_zep_auth(api_key: str, timeout_seconds: float) -> Optional[str]:
    try:
        from zep_cloud.client import Zep
    except Exception as exc:
        return f"zep: zep-cloud unavailable for auth probe ({exc})"

    try:
        client = Zep(api_key=api_key, timeout=timeout_seconds)
        # Read-only call. 404 means auth succeeded but user does not exist.
        client.user.get(user_id="llmemory-meter-auth-probe-user")
        return None
    except Exception as exc:
        status = _status_code_from_exception(exc)
        if status == 404:
            return None
        if status in (401, 403):
            return f"zep: auth probe unauthorized status={status}"
        return f"zep: auth probe failed ({type(exc).__name__}: {str(exc)[:200]})"


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate tool setup for a benchmark config")
    parser.add_argument("--config", default="configs/industry-benchmarks.yml", help="Config path")
    parser.add_argument(
        "--skip-auth-probes",
        action="store_true",
        help="Skip external credential probes (OpenAI/MemGPT/Zep)",
    )
    parser.add_argument(
        "--auth-timeout-seconds",
        type=float,
        default=8.0,
        help="Timeout for external auth probe HTTP requests",
    )
    args = parser.parse_args()

    config = ConfigManager.load_config(args.config)
    issues: List[str] = []

    config_issues = ConfigManager.validate_config(config)
    issues.extend(config_issues)
    enabled_tool_names = {tool.name for tool in config.memory_tools if tool.enabled}

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

    if not args.skip_auth_probes:
        # Probe OpenAI once if any enabled tool depends on it.
        if enabled_tool_names.intersection({"mem0", "memgpt"}) and os.getenv("OPENAI_API_KEY"):
            err = _probe_openai_auth(os.getenv("OPENAI_API_KEY", ""), timeout_seconds=args.auth_timeout_seconds)
            if err:
                issues.append(err)

        if "memgpt" in enabled_tool_names and os.getenv("MEMGPT_API_KEY"):
            err = _probe_memgpt_auth(os.getenv("MEMGPT_API_KEY", ""))
            if err:
                issues.append(err)

        if "zep" in enabled_tool_names and os.getenv("ZEP_API_KEY"):
            err = _probe_zep_auth(os.getenv("ZEP_API_KEY", ""), timeout_seconds=args.auth_timeout_seconds)
            if err:
                issues.append(err)

    if issues:
        print("Tool setup validation failed:")
        for issue in issues:
            print(f"- {issue}")
        return 1

    print(f"Tool setup validation passed for config: {args.config}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
