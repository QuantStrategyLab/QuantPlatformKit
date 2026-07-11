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
            "cost_model": "not_available",
            "placeholder_metrics": False,
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


if __name__ == "__main__":
    unittest.main()
