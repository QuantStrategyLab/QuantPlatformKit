#!/usr/bin/env python3
"""Fail-closed validator for strategy_review.v1 results."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

STATUSES = {"pass", "fail", "insufficient_evidence", "not_applicable"}


def validate_review(payload: Any) -> list[str]:
    issues: list[str] = []
    if not isinstance(payload, dict):
        return ["top-level JSON must be an object"]
    if payload.get("schema_version") != "strategy_review.v1":
        issues.append("schema_version must be strategy_review.v1")
    if not isinstance(payload.get("profile"), str) or not payload["profile"].strip():
        issues.append("profile must be a non-empty string")
    gates = payload.get("hard_gates")
    if not isinstance(gates, list) or len(gates) != 12:
        issues.append("hard_gates must contain exactly H1-H12")
        gates = gates if isinstance(gates, list) else []
    ids = [gate.get("id") for gate in gates if isinstance(gate, dict)]
    if set(ids) != {f"H{i}" for i in range(1, 13)}:
        issues.append("hard_gates ids must be unique H1-H12")
    for gate in gates:
        if not isinstance(gate, dict):
            issues.append("each hard gate must be an object")
            continue
        if gate.get("status") not in STATUSES:
            issues.append(f"{gate.get('id', '<unknown>')} has invalid status")
        for field in ("reason_codes", "evidence_refs"):
            if not isinstance(gate.get(field), list):
                issues.append(f"{gate.get('id', '<unknown>')}.{field} must be an array")

    score = payload.get("score")
    if not isinstance(score, (int, float)) or isinstance(score, bool) or not 0 <= score <= 100:
        issues.append("score must be a number in [0, 100]")
    evidence = payload.get("evidence")
    if not isinstance(evidence, dict):
        issues.append("evidence must be an object")
    else:
        if evidence.get("metrics_kind") != "performance":
            issues.append("evidence.metrics_kind must be performance")
        if evidence.get("placeholder_metrics") is not False:
            issues.append("placeholder metrics are not admissible evidence")
        if not isinstance(evidence.get("sample_count"), int) or evidence["sample_count"] < 0:
            issues.append("evidence.sample_count must be a non-negative integer")
        if not isinstance(evidence.get("oos_folds"), int) or evidence["oos_folds"] < 0:
            issues.append("evidence.oos_folds must be a non-negative integer")

    blocking = payload.get("blocking_reason_codes")
    if not isinstance(blocking, list):
        issues.append("blocking_reason_codes must be an array")
        blocking = []
    failed = [gate for gate in gates if isinstance(gate, dict) and gate.get("status") in {"fail", "insufficient_evidence"}]
    if failed and not blocking:
        issues.append("failed or insufficient hard gates require blocking_reason_codes")
    if payload.get("promotion_allowed") is not False:
        issues.append("promotion_allowed must be false in v1 review output")
    if payload.get("decision") == "pass" and failed:
        issues.append("decision cannot be pass when a hard gate failed or lacks evidence")
    if payload.get("decision") == "pass" and blocking:
        issues.append("decision cannot be pass with blocking_reason_codes")
    return issues


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("review", type=Path)
    args = parser.parse_args(argv)
    issues = validate_review(json.loads(args.review.read_text(encoding="utf-8")))
    if issues:
        for issue in issues:
            print(f"ERROR: {issue}")
        return 1
    print("strategy_review.v1: valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
