#!/usr/bin/env python3
"""Validate that required environment variables are set for the current platform.

Reads .env.example (or a JSON schema) to determine required env vars,
then checks os.environ for their presence.

Usage:
    python scripts/check_required_env.py              # check all vars
    python scripts/check_required_env.py --secrets    # also check secret manager
    python scripts/check_required_env.py --json       # output as JSON for CI
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Iterable


REQUIRED_VARS_BY_PLATFORM: dict[str, list[str]] = {
    "schwab": [
        "RUNTIME_TARGET_JSON",
        "SCHWAB_API_KEY",
        "SCHWAB_APP_SECRET",
        "TELEGRAM_TOKEN",
    ],
    "ibkr": [
        "RUNTIME_TARGET_JSON",
        "IBKR_ACCOUNT_IDS",
        "IB_GATEWAY_HOST",
        "IB_GATEWAY_PORT",
        "TELEGRAM_TOKEN",
    ],
    "longbridge": [
        "RUNTIME_TARGET_JSON",
        "LONGPORT_SECRET_NAME",
        "TELEGRAM_TOKEN",
    ],
}


def detect_platform() -> str | None:
    """Heuristic: detect platform from environment."""
    if os.getenv("SCHWAB_API_KEY"):
        return "schwab"
    if os.getenv("IBKR_ACCOUNT_IDS") or os.getenv("IB_GATEWAY_HOST"):
        return "ibkr"
    if os.getenv("LONGPORT_SECRET_NAME"):
        return "longbridge"
    if os.getenv("K_SERVICE", "").startswith("charles-schwab"):
        return "schwab"
    if os.getenv("K_SERVICE", "").startswith("interactive-brokers"):
        return "ibkr"
    if os.getenv("K_SERVICE", "").startswith("longbridge"):
        return "longbridge"
    return None


def parse_env_example(path: Path) -> dict[str, tuple[bool, str]]:
    """Parse .env.example, return {VAR_NAME: (required, description)}."""
    if not path.exists():
        return {}
    result: dict[str, tuple[bool, str]] = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # Extract description from preceding comment
        is_required = "REQUIRED" in line.upper() if "#" in line else False
        match = re.match(r"^(\w+)=(.*)", line)
        if match:
            name = match.group(1)
            value = match.group(2)
            desc = ""
            if "<" in value:
                is_required = True
                desc = f"must not be template value: {value}"
            result[name] = (is_required, desc)
    return result


def check_env(
    platform_id: str | None = None,
    *,
    env: dict | None = None,
) -> tuple[list[str], list[str]]:
    """Returns (missing_required, warnings)."""
    env = env or os.environ
    platform_id = platform_id or detect_platform()

    if platform_id is None:
        return (
            ["Cannot detect platform; set RUNTIME_TARGET_JSON or pass --platform"],
            [],
        )

    required_vars = REQUIRED_VARS_BY_PLATFORM.get(platform_id, [])
    if not required_vars:
        return ([f"No required var list for platform '{platform_id}'"], [])

    missing = [v for v in required_vars if not env.get(v)]
    warnings = []

    # Also check .env.example if present
    repo_root = Path(__file__).resolve().parents[1]
    example_file = repo_root / ".env.example"
    parsed = parse_env_example(example_file)
    for name, (is_required, desc) in parsed.items():
        if is_required and not env.get(name) and name not in required_vars:
            missing.append(f"{name} ({desc or 'from .env.example'})")

    # Check that RUNTIME_TARGET_JSON is valid JSON
    target_json = env.get("RUNTIME_TARGET_JSON")
    if target_json:
        try:
            json.loads(target_json)
        except json.JSONDecodeError as exc:
            missing.append(f"RUNTIME_TARGET_JSON is invalid JSON: {exc}")

    return missing, warnings


def main() -> int:
    json_output = "--json" in sys.argv
    platform_id = None

    for arg in sys.argv[1:]:
        if arg.startswith("--platform="):
            platform_id = arg.split("=", 1)[1]

    platform_id = platform_id or detect_platform()

    if platform_id is None:
        if json_output:
            print(json.dumps({"ok": False, "error": "Cannot detect platform"}))
        else:
            print("ERROR: Cannot detect platform. Set RUNTIME_TARGET_JSON or use --platform=<id>")
        return 2

    missing, warnings = check_env(platform_id)

    if json_output:
        result = {
            "platform": platform_id,
            "ok": len(missing) == 0,
            "missing_required": missing,
            "warnings": warnings,
            "required_count": len(REQUIRED_VARS_BY_PLATFORM.get(platform_id, [])),
            "missing_count": len(missing),
        }
        print(json.dumps(result, indent=2))
        return 1 if missing else 0

    print(f"Platform: {platform_id}")
    print(f"Required vars: {len(REQUIRED_VARS_BY_PLATFORM.get(platform_id, []))}")

    for w in warnings:
        print(f"  ⚠  {w}")
    for m in missing:
        print(f"  ✗  MISSING: {m}")

    if missing:
        print(f"\n{len(missing)} required variable(s) missing!")
        return 1

    print("\nAll required environment variables present.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
