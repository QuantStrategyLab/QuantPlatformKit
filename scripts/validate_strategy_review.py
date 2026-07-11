#!/usr/bin/env python3
"""Fail-closed validator for strategy_review.v1 results."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

STATUSES = {"pass", "fail", "insufficient_evidence", "not_applicable"}
DECISIONS = {"pass", "fail", "insufficient_evidence"}


def validate_review(payload: Any) -> list[str]:
    issues: list[str] = []
    if not isinstance(payload, dict):
        return ["top-level JSON must be an object"]
    if payload.get("schema_version") != "strategy_review.v1":
        issues.append("schema_version must be strategy_review.v1")
    if payload.get("decision") not in DECISIONS:
        issues.append("decision must be pass, fail, or insufficient_evidence")
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
            elif any(not isinstance(item, str) for item in gate[field]):
                issues.append(f"{gate.get('id', '<unknown>')}.{field} must contain strings")

    score = payload.get("score")
    if not isinstance(score, (int, float)) or isinstance(score, bool) or not 0 <= score <= 100:
        issues.append("score must be a number in [0, 100]")
    if not isinstance(payload.get("scorecard"), dict):
        issues.append("scorecard must be an object")
    evidence = payload.get("evidence")
    if not isinstance(evidence, dict):
        issues.append("evidence must be an object")
    else:
        if evidence.get("metrics_kind") != "performance":
            issues.append("evidence.metrics_kind must be performance")
        for field in ("data_source",):
            if not isinstance(evidence.get(field), str) or not evidence[field].strip():
                issues.append(f"evidence.{field} must be a non-empty string")
        provenance = evidence.get("provenance")
        if not isinstance(provenance, dict):
            issues.append("evidence.provenance must be an object")
            provenance = {}
        for source in ("snapshot", "backtest"):
            item = provenance.get(source)
            if not isinstance(item, dict):
                issues.append(f"evidence.provenance.{source} must be an object")
                continue
            for field in ("source_revision", "cost_model", "data_timestamp"):
                if not isinstance(item.get(field), str) or not item[field].strip():
                    issues.append(f"evidence.provenance.{source}.{field} must be non-empty")
            if item.get("status") not in {"verified", "legacy_missing", "unavailable"}:
                issues.append(f"evidence.provenance.{source}.status is invalid")
        if evidence.get("placeholder_metrics") is not False:
            issues.append("placeholder metrics are not admissible evidence")
        if not isinstance(evidence.get("sample_count"), int) or isinstance(evidence.get("sample_count"), bool) or evidence["sample_count"] < 0:
            issues.append("evidence.sample_count must be a non-negative integer")
        if not isinstance(evidence.get("oos_folds"), int) or isinstance(evidence.get("oos_folds"), bool) or evidence["oos_folds"] < 0:
            issues.append("evidence.oos_folds must be a non-negative integer")

    packet = payload.get("decision_packet")
    packet_fields = ("strategy_what", "return_source", "loss_scenarios", "max_risk", "version_change")
    if not isinstance(packet, dict):
        issues.append("decision_packet must be an object")
    else:
        for field in packet_fields:
            if not isinstance(packet.get(field), str) or not packet[field].strip():
                issues.append(f"decision_packet.{field} must be a non-empty string")
        if packet.get("evidence_sufficiency") not in {"sufficient", "insufficient_evidence"}:
            issues.append("decision_packet.evidence_sufficiency is invalid")
        recommendations = {"approve_research", "approve_shadow", "approve_canary", "approve_live", "reject_rollback", "insufficient_evidence"}
        if packet.get("system_recommendation") not in recommendations:
            issues.append("decision_packet.system_recommendation is invalid")
        if not isinstance(packet.get("technical_evidence_refs"), list) or any(not isinstance(item, str) for item in packet.get("technical_evidence_refs", [])):
            issues.append("decision_packet.technical_evidence_refs must be a string array")
        boundary = packet.get("automation_boundary")
        if not isinstance(boundary, dict):
            issues.append("decision_packet.automation_boundary must be an object")
        else:
            required_boundary = {
                "research_auto_after_hard_gates": True,
                "shadow_auto_after_hard_gates": True,
                "canary_mode": "bounded_preapproved_only",
                "auto_scale_allowed": False,
                "normal_live_requires_human": True,
                "funding_leverage_risk_override_requires_human": True,
                "hard_risk_auto_pause_rollback": True,
            }
            for field, expected in required_boundary.items():
                if boundary.get(field) != expected:
                    issues.append(f"decision_packet.automation_boundary.{field} is unsafe")
            if not isinstance(boundary.get("canary_limits"), dict):
                issues.append("decision_packet.automation_boundary.canary_limits must be an object")
        allowed = packet.get("allowed_human_decisions")
        if not isinstance(allowed, list) or not allowed or any(item not in {"approve_research", "approve_shadow", "approve_canary", "approve_live", "reject_rollback"} for item in allowed):
            issues.append("decision_packet.allowed_human_decisions is invalid")
        elif len(allowed) != len(set(allowed)):
            issues.append("decision_packet.allowed_human_decisions must be unique")
        if packet.get("evidence_sufficiency") == "insufficient_evidence" and packet.get("system_recommendation") != "insufficient_evidence":
            issues.append("insufficient evidence requires an insufficient_evidence recommendation")
        if packet.get("evidence_sufficiency") == "insufficient_evidence" and any(item != "approve_research" and item != "reject_rollback" for item in allowed or []):
            issues.append("insufficient evidence cannot allow shadow, canary, or live approval")
        promotive = {"approve_shadow", "approve_canary", "approve_live"}
        approval_recommendation = packet.get("system_recommendation") in {"approve_research", *promotive}
        if approval_recommendation and payload.get("decision") != "pass":
            issues.append("approval recommendation requires decision=pass")
        if payload.get("decision") != "pass" and any(item in promotive for item in allowed or []):
            issues.append("failed or insufficient review cannot allow shadow, canary, or live approval")
        if payload.get("decision") == "pass" and any(isinstance(gate, dict) and gate.get("status") != "pass" for gate in gates):
            issues.append("decision=pass requires every hard gate to pass")
        if payload.get("decision") == "pass" and packet.get("system_recommendation") == "insufficient_evidence":
            issues.append("decision=pass cannot recommend insufficient_evidence")
        if packet.get("system_recommendation") in {"approve_research", "approve_shadow", "approve_canary", "approve_live"} and any(
            isinstance(gate, dict) and gate.get("status") != "pass" for gate in gates
        ):
            issues.append("approval recommendation requires every hard gate to pass")
        promotive = packet.get("system_recommendation") in {"approve_shadow", "approve_canary", "approve_live"}
        if payload.get("decision") == "pass" or promotive:
            if not isinstance(evidence, dict) or evidence.get("sample_count", 0) <= 0 or evidence.get("oos_folds", 0) < 3:
                issues.append("passing review requires positive sample_count and at least 3 oos_folds")
            if not isinstance(packet.get("technical_evidence_refs"), list) or not packet["technical_evidence_refs"]:
                issues.append("passing review requires technical evidence references")
            for gate in gates:
                if isinstance(gate, dict) and gate.get("status") == "pass" and not gate.get("evidence_refs"):
                    issues.append(f"{gate.get('id', '<unknown>')} pass requires evidence_refs")
            if any(provenance.get(source, {}).get("status") != "verified" for source in ("snapshot", "backtest")):
                issues.append("passing review requires verified snapshot and backtest provenance")

    blocking = payload.get("blocking_reason_codes")
    if not isinstance(blocking, list):
        issues.append("blocking_reason_codes must be an array")
        blocking = []
    elif any(not isinstance(item, str) for item in blocking):
        issues.append("blocking_reason_codes must contain strings")
    failed = [gate for gate in gates if isinstance(gate, dict) and gate.get("status") in {"fail", "insufficient_evidence", "not_applicable"}]
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
