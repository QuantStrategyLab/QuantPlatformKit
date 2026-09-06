"""Account NEW_RISK gate adapter: unhealthy snapshot ⇒ NEW_RISK_PROHIBITED."""

from __future__ import annotations

import unittest

from quant_platform_kit.risk.account_new_risk_gate import (
    AccountNewRiskGateError,
    InjectedReconciliationSnapshot,
    NewRiskDisposition,
    evaluate_new_risk_admission,
    evaluate_new_risk_from_reader,
)


def _healthy() -> InjectedReconciliationSnapshot:
    return InjectedReconciliationSnapshot(
        observation_status="COMPLETE",
        reconciliation_status="VERIFIED",
        circuit_breaker_state="CLOSED",
    )


class EvaluateNewRiskAdmissionTests(unittest.TestCase):
    def test_healthy_allows_new_risk_without_side_effects(self) -> None:
        result = evaluate_new_risk_admission(_healthy())
        self.assertEqual(result.disposition, NewRiskDisposition.ALLOW_NEW_RISK)
        self.assertEqual(result.reason_codes, ())
        self.assertFalse(result.live_authority_granted)
        self.assertFalse(result.circuit_breaker_reset)
        self.assertFalse(result.account_enablement_changed)

    def test_unverified_reconciliation_prohibits_new_risk(self) -> None:
        snap = InjectedReconciliationSnapshot(
            observation_status="COMPLETE",
            reconciliation_status="UNVERIFIED",
            circuit_breaker_state="CLOSED",
        )
        result = evaluate_new_risk_admission(snap)
        self.assertEqual(result.disposition, NewRiskDisposition.NEW_RISK_PROHIBITED)
        self.assertIn("RECONCILIATION_NOT_VERIFIED", result.reason_codes)
        self.assertFalse(result.circuit_breaker_reset)

    def test_failed_reconciliation_prohibits_new_risk(self) -> None:
        snap = InjectedReconciliationSnapshot(
            observation_status="COMPLETE",
            reconciliation_status="FAILED",
            circuit_breaker_state="CLOSED",
        )
        result = evaluate_new_risk_admission(snap)
        self.assertEqual(result.disposition, NewRiskDisposition.NEW_RISK_PROHIBITED)
        self.assertIn("RECONCILIATION_NOT_VERIFIED", result.reason_codes)

    def test_stale_observation_prohibits_new_risk(self) -> None:
        snap = InjectedReconciliationSnapshot(
            observation_status="STALE",
            reconciliation_status="VERIFIED",
            circuit_breaker_state="CLOSED",
        )
        result = evaluate_new_risk_admission(snap)
        self.assertEqual(result.disposition, NewRiskDisposition.NEW_RISK_PROHIBITED)
        self.assertIn("OBSERVATION_NOT_COMPLETE", result.reason_codes)

    def test_open_breaker_prohibits_without_reset(self) -> None:
        snap = InjectedReconciliationSnapshot(
            observation_status="COMPLETE",
            reconciliation_status="VERIFIED",
            circuit_breaker_state="OPEN",
        )
        result = evaluate_new_risk_admission(snap)
        self.assertEqual(result.disposition, NewRiskDisposition.NEW_RISK_PROHIBITED)
        self.assertIn("CIRCUIT_BREAKER_OPEN", result.reason_codes)
        self.assertFalse(result.circuit_breaker_reset)
        self.assertFalse(result.account_enablement_changed)
        self.assertFalse(result.live_authority_granted)

    def test_invalid_enum_fails_closed(self) -> None:
        snap = InjectedReconciliationSnapshot(
            observation_status="COMPLETE",
            reconciliation_status="MAYBE",
            circuit_breaker_state="CLOSED",
        )
        with self.assertRaises(AccountNewRiskGateError):
            evaluate_new_risk_admission(snap)


class ReaderInjectionTests(unittest.TestCase):
    def test_reader_unhealthy_snapshot_prohibits(self) -> None:
        class _Reader:
            def read_snapshot(self) -> InjectedReconciliationSnapshot:
                return InjectedReconciliationSnapshot(
                    observation_status="UNAVAILABLE",
                    reconciliation_status="FAILED",
                    circuit_breaker_state="OPEN",
                )

        result = evaluate_new_risk_from_reader(_Reader())
        self.assertEqual(result.disposition, NewRiskDisposition.NEW_RISK_PROHIBITED)
        self.assertIn("OBSERVATION_NOT_COMPLETE", result.reason_codes)
        self.assertIn("RECONCILIATION_NOT_VERIFIED", result.reason_codes)
        self.assertIn("CIRCUIT_BREAKER_OPEN", result.reason_codes)

    def test_reader_exception_is_gate_error(self) -> None:
        class _Boom:
            def read_snapshot(self) -> InjectedReconciliationSnapshot:
                raise RuntimeError("no account wired")

        with self.assertRaises(AccountNewRiskGateError):
            evaluate_new_risk_from_reader(_Boom())


if __name__ == "__main__":
    unittest.main()
