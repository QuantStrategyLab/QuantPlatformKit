#!/usr/bin/env python3
"""Validate a strategy evidence package JSON file."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ALLOWED_REQUESTED_STAGES = {
    "research_backtest_only",
    "ai_monitored_candidate",
    "shadow_candidate",
    "live_candidate",
    "runtime_enabled",
}
ALLOWED_KELLY_LEVELS = {"K0", "K1", "K2", "K3", "K4"}
REQUIRED_ARTIFACTS = (
    "returns",
    "trades",
    "positions",
    "config",
    "data_manifest",
    "candidate_registry",
    "benchmark_registry",
    "cost_model",
    "risk_report",
    "kelly_readiness_report",
)
SHA256_RE = re.compile(r"^[A-Fa-f0-9]{64}$")


def validate_payload(payload: Any) -> list[str]:
    issues: list[str] = []

    if not isinstance(payload, dict):
        return ["top-level JSON must be an object"]

    for field in (
        "schema_version",
        "profile",
        "market",
        "requested_stage",
        "generated_at",
        "evidence_package_id",
        "artifacts",
        "validation",
        "risk",
        "kelly_readiness",
        "ai_optimization",
    ):
        if field not in payload:
            issues.append(f"missing required field: {field}")

    _check_non_empty_string(payload, "schema_version", issues)
    _check_non_empty_string(payload, "profile", issues)
    _check_non_empty_string(payload, "market", issues)
    _check_non_empty_string(payload, "evidence_package_id", issues)

    requested_stage = payload.get("requested_stage")
    if not isinstance(requested_stage, str) or not requested_stage.strip():
        issues.append("requested_stage must be a non-empty string")
    elif requested_stage not in ALLOWED_REQUESTED_STAGES:
        issues.append(f"unsupported requested_stage: {requested_stage!r}")

    generated_at = payload.get("generated_at")
    if not isinstance(generated_at, str) or not generated_at.strip():
        issues.append("generated_at must be a non-empty string")
    elif not _is_datetime_string(generated_at):
        issues.append(f"generated_at is not a valid date-time: {generated_at!r}")

    artifacts = payload.get("artifacts")
    if not isinstance(artifacts, dict):
        issues.append("artifacts must be an object")
    else:
        for name in REQUIRED_ARTIFACTS:
            artifact = artifacts.get(name)
            if not isinstance(artifact, dict):
                issues.append(f"artifacts.{name} must be an object")
                continue
            _check_non_empty_string(artifact, "path", issues, prefix=f"artifacts.{name}")
            sha256 = artifact.get("sha256")
            if not isinstance(sha256, str) or not SHA256_RE.fullmatch(sha256):
                issues.append(f"artifacts.{name}.sha256 must be a 64-character hex string")

    validation = payload.get("validation")
    if not isinstance(validation, dict):
        issues.append("validation must be an object")
    else:
        if not isinstance(validation.get("oos_passed"), bool):
            issues.append("validation.oos_passed must be a boolean")
        if not isinstance(validation.get("overfit_report_present"), bool):
            issues.append("validation.overfit_report_present must be a boolean")
        if requested_stage in {"live_candidate", "runtime_enabled"}:
            if validation.get("oos_passed") is not True:
                issues.append(f"{requested_stage} requires validation.oos_passed=true")
            if validation.get("overfit_report_present") is not True:
                issues.append(f"{requested_stage} requires validation.overfit_report_present=true")

    risk = payload.get("risk")
    if not isinstance(risk, dict):
        issues.append("risk must be an object")

    kelly_readiness = payload.get("kelly_readiness")
    if not isinstance(kelly_readiness, dict):
        issues.append("kelly_readiness must be an object")
    else:
        level = kelly_readiness.get("level")
        if not isinstance(level, str) or level not in ALLOWED_KELLY_LEVELS:
            issues.append("kelly_readiness.level must be one of K0, K1, K2, K3, K4")
        if kelly_readiness.get("full_kelly_allowed") is not False:
            issues.append("kelly_readiness.full_kelly_allowed must be false")

    ai_optimization = payload.get("ai_optimization")
    if not isinstance(ai_optimization, dict):
        issues.append("ai_optimization must be an object")

    return issues


def validate_file(path: str | Path) -> list[str]:
    evidence_path = Path(path)
    try:
        payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return [f"file not found: {evidence_path}"]
    except json.JSONDecodeError as exc:
        return [f"invalid JSON: {exc.msg} (line {exc.lineno}, column {exc.colno})"]
    except OSError as exc:
        return [f"failed to read file: {exc}"]
    return validate_payload(payload)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="validate_strategy_evidence_package")
    parser.add_argument("path", help="path to evidence package JSON")
    args = parser.parse_args(argv)

    issues = validate_file(args.path)
    if issues:
        for issue in issues:
            print(issue, file=sys.stderr)
        return 1
    return 0


def _check_non_empty_string(
    payload: dict[str, Any],
    field: str,
    issues: list[str],
    *,
    prefix: str | None = None,
) -> None:
    value = payload.get(field)
    label = f"{prefix}.{field}" if prefix else field
    if not isinstance(value, str) or not value.strip():
        issues.append(f"{label} must be a non-empty string")


def _is_datetime_string(value: str) -> bool:
    candidate = value.strip()
    if candidate.endswith("Z"):
        candidate = f"{candidate[:-1]}+00:00"
    try:
        datetime.fromisoformat(candidate)
    except ValueError:
        return False
    return True


if __name__ == "__main__":
    raise SystemExit(main())
