import unittest
from datetime import datetime, timezone
from dataclasses import replace

from quant_platform_kit.common.strategy_contracts import PositionTarget, StrategyDecision
from quant_platform_kit.common.execution_receipts import build_execution_receipt
from quant_platform_kit.common.decision_consumption_receipts import (
    attach_decision_consumption_receipt, attach_decision_execution_link, build_decision_consumption_receipt,
    validate_decision_consumption_receipt,
)


class DecisionConsumptionReceiptTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 4, 17, 12, tzinfo=timezone.utc)
        self.before = StrategyDecision(positions=(PositionTarget("TQQQ", target_weight=0.2),))
        self.after = StrategyDecision(positions=(PositionTarget("TQQQ", target_weight=0.1),))
        self.kwargs = dict(run_id="run-1", strategy_profile="tqqq_growth_income", strategy_revision="a" * 40,
            config_sha256="b" * 64, decision_at=self.now, pre_risk_decision=self.before,
            post_risk_decision=self.after, observations=[dict(reference="signal", status="observed",
                artifact_sha256="c" * 64, digest_status="unverified", availability_at=None, authority="denied")])

    def test_binds_actual_targets_and_preserves_unknowns(self):
        receipt = build_decision_consumption_receipt(**self.kwargs)
        self.assertNotEqual(receipt["pre_risk_target_sha256"], receipt["post_risk_target_sha256"])
        self.assertEqual(receipt["observations"][0]["availability_status"], "unknown")
        self.assertEqual(receipt["observations"][0]["authority"], "denied")
        self.assertEqual(validate_decision_consumption_receipt(receipt), receipt)
        tampered = dict(receipt, post_risk_target_sha256="d" * 64)
        with self.assertRaises(ValueError):
            validate_decision_consumption_receipt(tampered)

    def test_attach_rejects_wrong_run_and_targets(self):
        receipt = build_decision_consumption_receipt(**self.kwargs)
        report = {"run_id": "run-1", "strategy_profile": "tqqq_growth_income",
                  "runtime_release_receipt": {"strategy_release": {"strategy_revision": "a" * 40}}}
        attach_decision_consumption_receipt(report, receipt, post_risk_decision=self.after)
        with self.assertRaises(ValueError):
            attach_decision_consumption_receipt({**report, "run_id": "run-2"}, receipt)
        with self.assertRaises(ValueError):
            attach_decision_consumption_receipt(report, receipt, post_risk_decision=self.before)
        bad_config = {**report, "runtime_release_receipt": {"strategy_release": {
            "strategy_revision": "a" * 40, "config_sha256": "f" * 64}}}
        with self.assertRaisesRegex(ValueError, "configuration mismatch"):
            attach_decision_consumption_receipt(bad_config, receipt)
        with self.assertRaisesRegex(ValueError, "decision clock mismatch"):
            attach_decision_consumption_receipt({**report, "decision_at": "2026-04-17T12:00:01Z"}, receipt)
        attach_decision_consumption_receipt({**report, "decision_at": "2026-04-17T08:00:00-04:00"}, receipt)

    def test_missing_and_execution_outcome_are_not_fabricated(self):
        execution = build_execution_receipt(platform="ibkr", strategy_profile="tqqq_growth_income",
            strategy_revision="a" * 40, execution_mode="paper", outcome="submitted", observed_at=self.now)
        receipt = build_decision_consumption_receipt(**{**self.kwargs, "observations": [dict(reference="x",
            status="unavailable", artifact_sha256=None, digest_status="unknown", availability_at=None,
            authority="unknown")], "pre_risk_decision": None, "execution_receipt": execution})
        self.assertIsNone(receipt["pre_risk_target_sha256"])
        self.assertEqual(receipt["execution_outcome"], "submitted")
        self.assertEqual(receipt["broker_confirmation"], "not_observed")
        self.assertNotIn("fill_id", receipt)
        with self.assertRaises(ValueError):
            build_decision_consumption_receipt(**{**self.kwargs, "observations": [dict(reference="x", status="missing",
                artifact_sha256="a" * 64, digest_status="verified", availability_at=None, authority="unknown")]})

    def test_fractional_future_availability_and_execution_binding(self):
        observation = {**self.kwargs["observations"][0], "availability_at": "2026-04-17T12:00:00.500000+00:00",
                       "observed_at": "2026-04-17T12:00:00.100000+00:00", "consumer": "market_regime_control",
                       "consumer_payload_sha256": "d" * 64}
        execution = build_execution_receipt(platform="ibkr", strategy_profile="tqqq_growth_income",
            strategy_revision="a" * 40, execution_mode="paper", outcome="submitted", observed_at=self.now)
        receipt = build_decision_consumption_receipt(**{**self.kwargs, "observations": [observation],
                                                       "execution_receipt": execution, "signal_session": "2026-04-17"})
        self.assertEqual(receipt["observations"][0]["availability_status"], "after_decision")
        self.assertEqual(receipt["observations"][0]["read_status"], "after_decision")
        report = {"run_id": "run-1", "strategy_profile": "tqqq_growth_income", "execution_receipt": execution,
                  "runtime_release_receipt": {"strategy_release": {"strategy_revision": "a" * 40}}}
        attach_decision_consumption_receipt(report, receipt, post_risk_decision=self.after)
        other = build_execution_receipt(platform="ibkr", strategy_profile="tqqq_growth_income",
            strategy_revision="a" * 40, execution_mode="paper", outcome="filled", observed_at=self.now)
        with self.assertRaises(ValueError):
            attach_decision_consumption_receipt({**report, "execution_receipt": other}, receipt)

    def test_later_execution_link_keeps_original_and_does_not_infer_fills(self):
        receipt = build_decision_consumption_receipt(**self.kwargs)
        execution = build_execution_receipt(platform="ibkr", strategy_profile="tqqq_growth_income",
            strategy_revision="a" * 40, execution_mode="paper", outcome="submitted", observed_at=self.now)
        report = {"run_id": "run-1", "strategy_profile": "tqqq_growth_income", "execution_receipt": execution,
                  "runtime_release_receipt": {"strategy_release": {"strategy_revision": "a" * 40}}}
        attach_decision_consumption_receipt(report, receipt, post_risk_decision=self.after)
        attach_decision_execution_link(report, receipt, order_records=[{"id": "observed"}])
        self.assertEqual(report["decision_consumption_receipt"], receipt)
        self.assertIsNone(report["decision_execution_link"]["fill_records_sha256"])
        self.assertEqual(report["decision_execution_link"]["provenance_status"], "partial")
        with self.assertRaises(ValueError):
            attach_decision_execution_link({**report, "run_id": "run-2"}, receipt)


if __name__ == "__main__":
    unittest.main()
