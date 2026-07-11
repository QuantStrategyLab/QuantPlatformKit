from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("review_validator", ROOT / "scripts/validate_strategy_review.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def _review(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": "strategy_review.v1",
        "profile": "crypto_live_pool_rotation",
        "decision": "insufficient_evidence",
        "promotion_allowed": False,
        "score": 0,
        "hard_gates": [
            {"id": f"H{i}", "status": "insufficient_evidence", "reason_codes": ["INSUFFICIENT_DATA"], "evidence_refs": []}
            for i in range(1, 13)
        ],
        "scorecard": {"total": 0},
        "blocking_reason_codes": ["INSUFFICIENT_DATA"],
        "evidence": {
            "metrics_kind": "performance",
            "data_source": "not_available",
            "sample_count": 0,
            "oos_folds": 0,
            "placeholder_metrics": False,
            "provenance": {
                "snapshot": {"source_revision": "fixture-rev", "cost_model": "not_available", "data_timestamp": "2026-07-11T00:00:00Z", "status": "unavailable"},
                "backtest": {"source_revision": "fixture-rev", "cost_model": "not_available", "data_timestamp": "2026-07-11T00:00:00Z", "status": "unavailable"},
            },
        },
        "decision_packet": {
            "strategy_what": "策略做什么尚待真实证据确认",
            "return_source": "真实 performance artifacts 未提供",
            "loss_scenarios": "未完成回测，主要亏损场景不可确认",
            "max_risk": "最大风险不可确认",
            "evidence_sufficiency": "insufficient_evidence",
            "version_change": "仅生成 fail-closed 评审结果",
            "system_recommendation": "insufficient_evidence",
            "technical_evidence_refs": [],
            "automation_boundary": {
                "research_auto_after_hard_gates": True,
                "shadow_auto_after_hard_gates": True,
                "canary_mode": "bounded_preapproved_only",
                "canary_limits": {"max_capital": 1000.0, "capital_currency": "USD", "max_duration_days": 14, "max_drawdown_fraction": 0.05, "max_leverage": 1.0, "max_concurrency": 1},
                "auto_scale_allowed": False,
                "normal_live_requires_human": True,
                "funding_leverage_risk_override_requires_human": True,
                "hard_risk_auto_pause_rollback": True,
            },
            "allowed_human_decisions": ["approve_research", "reject_rollback"],
        },
    }
    payload.update(overrides)
    return payload


class StrategyReviewValidatorTests(unittest.TestCase):
    def test_insufficient_evidence_is_valid_and_fail_closed(self) -> None:
        self.assertEqual(MODULE.validate_review(_review()), [])

    def test_operational_metrics_are_rejected(self) -> None:
        payload = _review(evidence={**_review()["evidence"], "metrics_kind": "operational"})
        self.assertTrue(any("metrics_kind" in issue for issue in MODULE.validate_review(payload)))

    def test_placeholder_metrics_are_rejected(self) -> None:
        payload = _review(evidence={**_review()["evidence"], "placeholder_metrics": True})
        self.assertTrue(any("placeholder" in issue for issue in MODULE.validate_review(payload)))

    def test_pass_cannot_override_failed_gate(self) -> None:
        payload = _review(decision="pass")
        self.assertTrue(any("cannot be pass" in issue for issue in MODULE.validate_review(payload)))

    def test_unknown_decision_is_rejected(self) -> None:
        self.assertTrue(any("decision must be" in issue for issue in MODULE.validate_review(_review(decision="unknown"))))

    def test_empty_provenance_is_rejected(self) -> None:
        evidence = {**_review()["evidence"], "data_source": ""}
        evidence["provenance"] = {**evidence["provenance"], "snapshot": {**evidence["provenance"]["snapshot"], "cost_model": " "}}
        payload = _review(evidence=evidence)
        issues = MODULE.validate_review(payload)
        self.assertTrue(any("data_source" in issue for issue in issues))
        self.assertTrue(any("cost_model" in issue for issue in issues))

    def test_missing_scorecard_and_boolean_counts_are_rejected(self) -> None:
        payload = _review()
        payload.pop("scorecard")
        payload["evidence"] = {**_review()["evidence"], "sample_count": True, "oos_folds": False}
        issues = MODULE.validate_review(payload)
        self.assertTrue(any("scorecard" in issue for issue in issues))
        self.assertTrue(any("sample_count" in issue for issue in issues))
        self.assertTrue(any("oos_folds" in issue for issue in issues))

    def test_reason_code_arrays_must_contain_strings(self) -> None:
        payload = _review()
        payload["hard_gates"][0]["reason_codes"] = [123]  # type: ignore[index]
        payload["blocking_reason_codes"] = [False]
        issues = MODULE.validate_review(payload)
        self.assertTrue(any("must contain strings" in issue for issue in issues))

    def test_approval_recommendation_requires_all_gates(self) -> None:
        payload = _review()
        payload["decision_packet"]["system_recommendation"] = "approve_research"  # type: ignore[index]
        self.assertTrue(any("every hard gate" in issue for issue in MODULE.validate_review(payload)))

    def test_pass_requires_real_samples_folds_and_evidence_refs(self) -> None:
        payload = _review(decision="pass")
        payload["hard_gates"] = [{**gate, "status": "pass"} for gate in payload["hard_gates"]]
        payload["decision_packet"]["system_recommendation"] = "approve_research"  # type: ignore[index]
        issues = MODULE.validate_review(payload)
        self.assertTrue(any("positive sample_count" in issue for issue in issues))

    def test_duplicate_human_actions_are_rejected(self) -> None:
        payload = _review()
        payload["decision_packet"]["allowed_human_decisions"] = ["approve_research", "approve_research"]  # type: ignore[index]
        self.assertTrue(any("must be unique" in issue for issue in MODULE.validate_review(payload)))

    def test_verified_provenance_rejects_sentinel(self) -> None:
        payload = _review()
        payload["decision_packet"]["evidence_sufficiency"] = "sufficient"  # type: ignore[index]
        payload["decision"] = "pass"
        payload["evidence"]["sample_count"] = 10  # type: ignore[index]
        payload["evidence"]["oos_folds"] = 3  # type: ignore[index]
        for gate in payload["hard_gates"]:
            gate["status"] = "pass"
            gate["evidence_refs"] = ["artifact"]
        payload["decision_packet"]["system_recommendation"] = "approve_research"  # type: ignore[index]
        payload["decision_packet"]["technical_evidence_refs"] = ["artifact"]  # type: ignore[index]
        payload["evidence"]["provenance"]["backtest"]["status"] = "verified"  # type: ignore[index]
        payload["evidence"]["provenance"]["backtest"]["source_revision"] = "legacy_missing"  # type: ignore[index]
        self.assertTrue(any("verified" in issue for issue in MODULE.validate_review(payload)))


if __name__ == "__main__":
    unittest.main()
