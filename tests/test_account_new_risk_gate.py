"""Account NEW_RISK gate: health + capital envelope ⇒ NEW_RISK_PROHIBITED."""

from __future__ import annotations

import unittest

from quant_platform_kit.risk.account_new_risk_gate import (
    AccountNewRiskGateError,
    InjectedReconciliationSnapshot,
    NewRiskDisposition,
    evaluate_new_risk_admission,
    evaluate_new_risk_from_reader,
)
from quant_platform_kit.risk.contracts import RuntimeRiskLimits


def _healthy(*, equity_usd: float | None = 40_000.0, **kwargs) -> InjectedReconciliationSnapshot:
    return InjectedReconciliationSnapshot(
        observation_status="COMPLETE",
        reconciliation_status="VERIFIED",
        circuit_breaker_state="CLOSED",
        equity_usd=equity_usd,
        **kwargs,
    )


def _runtime_limits(*, max_daily_loss_usd: float | None) -> RuntimeRiskLimits:
    return RuntimeRiskLimits(
        allowed_symbols=("SPY",),
        product_leverage_factors={"SPY": 1},
        nominal_caps={"SPY": 1.0},
        total_nominal_exposure_cap=1.0,
        total_effective_exposure_cap=1.0,
        max_positions=1,
        max_daily_loss_usd=max_daily_loss_usd,
    )


class EvaluateNewRiskAdmissionTests(unittest.TestCase):
    def test_healthy_with_equity_allows_new_risk_without_side_effects(self) -> None:
        result = evaluate_new_risk_admission(_healthy())
        self.assertEqual(result.disposition, NewRiskDisposition.ALLOW_NEW_RISK)
        self.assertEqual(result.reason_codes, ())
        self.assertEqual(result.combined_scale, 1.0)
        self.assertFalse(result.live_authority_granted)
        self.assertFalse(result.circuit_breaker_reset)
        self.assertFalse(result.account_enablement_changed)

    def test_allowing_capital_envelope_exposes_combined_scale(self) -> None:
        result = evaluate_new_risk_admission(_healthy(equity_usd=100_000.0))
        self.assertEqual(result.disposition, NewRiskDisposition.ALLOW_NEW_RISK)
        self.assertEqual(result.combined_scale, 0.85)

    def test_equity_unknown_prohibits_fail_closed(self) -> None:
        result = evaluate_new_risk_admission(_healthy(equity_usd=None))
        self.assertEqual(result.disposition, NewRiskDisposition.NEW_RISK_PROHIBITED)
        self.assertIn("EQUITY_UNKNOWN_FAIL_CLOSED", result.reason_codes)
        self.assertFalse(result.circuit_breaker_reset)
        self.assertFalse(result.live_authority_granted)
        self.assertFalse(result.account_enablement_changed)

    def test_drawdown_brake_prohibits_new_risk_only(self) -> None:
        # mid band brake 0.10 → trip at 0.10
        snap = _healthy(equity_usd=100_000.0, drawdown_from_peak=0.10)
        result = evaluate_new_risk_admission(snap)
        self.assertEqual(result.disposition, NewRiskDisposition.NEW_RISK_PROHIBITED)
        self.assertIn("DRAWDOWN_BRAKE_TRIPPED", result.reason_codes)
        self.assertFalse(result.circuit_breaker_reset)
        self.assertFalse(result.account_enablement_changed)
        self.assertFalse(result.live_authority_granted)

    def test_peak_equity_derived_drawdown_can_prohibit(self) -> None:
        # peak 100k, equity 85k → DD 0.15 > mid-band brake 0.10
        snap = _healthy(equity_usd=85_000.0, peak_equity_usd=100_000.0)
        result = evaluate_new_risk_admission(snap)
        self.assertEqual(result.disposition, NewRiskDisposition.NEW_RISK_PROHIBITED)
        self.assertIn("DRAWDOWN_BRAKE_TRIPPED", result.reason_codes)

    def test_invalid_equity_prohibits(self) -> None:
        result = evaluate_new_risk_admission(_healthy(equity_usd=float("nan")))
        self.assertEqual(result.disposition, NewRiskDisposition.NEW_RISK_PROHIBITED)
        self.assertIn("INVALID_EQUITY_FAIL_CLOSED", result.reason_codes)

    def test_unverified_reconciliation_prohibits_new_risk(self) -> None:
        snap = InjectedReconciliationSnapshot(
            observation_status="COMPLETE",
            reconciliation_status="UNVERIFIED",
            circuit_breaker_state="CLOSED",
            equity_usd=40_000.0,
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
            equity_usd=40_000.0,
        )
        result = evaluate_new_risk_admission(snap)
        self.assertEqual(result.disposition, NewRiskDisposition.NEW_RISK_PROHIBITED)
        self.assertIn("RECONCILIATION_NOT_VERIFIED", result.reason_codes)

    def test_stale_observation_prohibits_new_risk(self) -> None:
        snap = InjectedReconciliationSnapshot(
            observation_status="STALE",
            reconciliation_status="VERIFIED",
            circuit_breaker_state="CLOSED",
            equity_usd=40_000.0,
        )
        result = evaluate_new_risk_admission(snap)
        self.assertEqual(result.disposition, NewRiskDisposition.NEW_RISK_PROHIBITED)
        self.assertIn("OBSERVATION_NOT_COMPLETE", result.reason_codes)

    def test_open_breaker_prohibits_without_reset(self) -> None:
        snap = InjectedReconciliationSnapshot(
            observation_status="COMPLETE",
            reconciliation_status="VERIFIED",
            circuit_breaker_state="OPEN",
            equity_usd=40_000.0,
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
            equity_usd=40_000.0,
        )
        with self.assertRaises(AccountNewRiskGateError):
            evaluate_new_risk_admission(snap)

    def test_absent_production_drift_does_not_invent_prohibit(self) -> None:
        result = evaluate_new_risk_admission(_healthy())
        self.assertEqual(result.disposition, NewRiskDisposition.ALLOW_NEW_RISK)
        self.assertEqual(result.reason_codes, ())

    def test_healthy_or_watch_production_drift_allows_when_other_axes_ok(self) -> None:
        for status in ("healthy", "watch", "HEALTHY", "WATCH"):
            with self.subTest(status=status):
                result = evaluate_new_risk_admission(
                    _healthy(production_drift_status=status)
                )
                self.assertEqual(result.disposition, NewRiskDisposition.ALLOW_NEW_RISK)
                self.assertEqual(result.reason_codes, ())

    def test_review_production_drift_prohibits_without_side_effects(self) -> None:
        result = evaluate_new_risk_admission(
            _healthy(production_drift_status="review")
        )
        self.assertEqual(result.disposition, NewRiskDisposition.NEW_RISK_PROHIBITED)
        self.assertIn("PRODUCTION_DRIFT_REVIEW", result.reason_codes)
        self.assertFalse(result.live_authority_granted)
        self.assertFalse(result.circuit_breaker_reset)
        self.assertFalse(result.account_enablement_changed)

    def test_critical_production_drift_prohibits_without_side_effects(self) -> None:
        result = evaluate_new_risk_admission(
            _healthy(production_drift_status="critical")
        )
        self.assertEqual(result.disposition, NewRiskDisposition.NEW_RISK_PROHIBITED)
        self.assertIn("PRODUCTION_DRIFT_CRITICAL", result.reason_codes)
        self.assertFalse(result.live_authority_granted)
        self.assertFalse(result.circuit_breaker_reset)
        self.assertFalse(result.account_enablement_changed)

    def test_invalid_production_drift_status_fails_closed(self) -> None:
        result = evaluate_new_risk_admission(
            _healthy(production_drift_status="maybe")
        )
        self.assertEqual(result.disposition, NewRiskDisposition.NEW_RISK_PROHIBITED)
        self.assertIn("PRODUCTION_DRIFT_STATUS_INVALID_FAIL_CLOSED", result.reason_codes)

    def test_daily_loss_below_limit_allows_new_risk(self) -> None:
        result = evaluate_new_risk_admission(
            _healthy(daily_loss_usd=99.99),
            runtime_risk_limits=_runtime_limits(max_daily_loss_usd=100.0),
        )
        self.assertEqual(result.disposition, NewRiskDisposition.ALLOW_NEW_RISK)
        self.assertEqual(result.reason_codes, ())

    def test_daily_loss_at_or_above_limit_prohibits(self) -> None:
        limits = _runtime_limits(max_daily_loss_usd=100.0)
        for daily_loss_usd in (100.0, 100.01):
            with self.subTest(daily_loss_usd=daily_loss_usd):
                result = evaluate_new_risk_admission(
                    _healthy(daily_loss_usd=daily_loss_usd),
                    runtime_risk_limits=limits,
                )
                self.assertEqual(
                    result.disposition,
                    NewRiskDisposition.NEW_RISK_PROHIBITED,
                )
                self.assertIn("DAILY_LOSS_LIMIT_EXCEEDED", result.reason_codes)

    def test_missing_or_invalid_daily_loss_fails_closed_when_configured(self) -> None:
        limits = _runtime_limits(max_daily_loss_usd=100.0)
        for daily_loss_usd in (None, -1.0, float("nan"), float("inf"), True):
            with self.subTest(daily_loss_usd=daily_loss_usd):
                result = evaluate_new_risk_admission(
                    _healthy(daily_loss_usd=daily_loss_usd),
                    runtime_risk_limits=limits,
                )
                self.assertEqual(
                    result.disposition,
                    NewRiskDisposition.NEW_RISK_PROHIBITED,
                )
                self.assertIn(
                    "DAILY_LOSS_UNKNOWN_FAIL_CLOSED",
                    result.reason_codes,
                )

    def test_unconfigured_daily_loss_axis_is_omitted(self) -> None:
        for limits in (None, _runtime_limits(max_daily_loss_usd=None)):
            with self.subTest(limits=limits):
                result = evaluate_new_risk_admission(
                    _healthy(daily_loss_usd=float("nan")),
                    runtime_risk_limits=limits,
                )
                self.assertEqual(result.disposition, NewRiskDisposition.ALLOW_NEW_RISK)
                self.assertNotIn(
                    "DAILY_LOSS_UNKNOWN_FAIL_CLOSED",
                    result.reason_codes,
                )
                self.assertNotIn("DAILY_LOSS_LIMIT_EXCEEDED", result.reason_codes)

    def test_daily_loss_reason_coexists_with_other_axes(self) -> None:
        result = evaluate_new_risk_admission(
            _healthy(
                daily_loss_usd=100.0,
                production_drift_status="critical",
            ),
            runtime_risk_limits=_runtime_limits(max_daily_loss_usd=100.0),
        )
        self.assertEqual(
            result.reason_codes,
            ("DAILY_LOSS_LIMIT_EXCEEDED", "PRODUCTION_DRIFT_CRITICAL"),
        )


class RuntimeRiskLimitsDailyLossTests(unittest.TestCase):
    def test_max_daily_loss_must_be_finite_positive_when_configured(self) -> None:
        for value in (0.0, -1.0, float("nan"), float("inf"), True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                _runtime_limits(max_daily_loss_usd=value)


class ReaderInjectionTests(unittest.TestCase):
    def test_reader_unhealthy_snapshot_prohibits(self) -> None:
        class _Reader:
            def read_snapshot(self) -> InjectedReconciliationSnapshot:
                return InjectedReconciliationSnapshot(
                    observation_status="UNAVAILABLE",
                    reconciliation_status="FAILED",
                    circuit_breaker_state="OPEN",
                    equity_usd=40_000.0,
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
