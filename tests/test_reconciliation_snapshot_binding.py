"""W2 reconciliation equity summary → injected snapshot binding."""

from __future__ import annotations

import unittest

from quant_platform_kit.risk.account_new_risk_gate import (
    AccountNewRiskGateError,
    InjectedReconciliationSnapshot,
)
from quant_platform_kit.risk.reconciliation_snapshot_binding import (
    ReconciliationEquitySummary,
    build_injected_snapshot_from_equity_summary,
)


class BuildInjectedSnapshotFromEquitySummaryTests(unittest.TestCase):
    def test_dict_maps_to_injected_snapshot(self) -> None:
        snap = build_injected_snapshot_from_equity_summary(
            {
                "equity_usd": 40_000.0,
                "peak_equity_usd": 50_000.0,
                "realized_vol": 0.15,
            }
        )
        self.assertIsInstance(snap, InjectedReconciliationSnapshot)
        self.assertEqual(snap.equity_usd, 40_000.0)
        self.assertEqual(snap.peak_equity_usd, 50_000.0)
        self.assertEqual(snap.realized_vol, 0.15)
        self.assertEqual(snap.observation_status, "COMPLETE")

    def test_dataclass_maps_to_injected_snapshot(self) -> None:
        snap = build_injected_snapshot_from_equity_summary(
            ReconciliationEquitySummary(equity_usd=25_000.0, drawdown_from_peak=0.05)
        )
        self.assertEqual(snap.equity_usd, 25_000.0)
        self.assertEqual(snap.drawdown_from_peak, 0.05)

    def test_health_axes_can_be_in_mapping(self) -> None:
        snap = build_injected_snapshot_from_equity_summary(
            {
                "equity_usd": 10_000.0,
                "observation_status": "STALE",
                "reconciliation_status": "UNVERIFIED",
                "circuit_breaker_state": "OPEN",
            }
        )
        self.assertEqual(snap.observation_status, "STALE")
        self.assertEqual(snap.reconciliation_status, "UNVERIFIED")
        self.assertEqual(snap.circuit_breaker_state, "OPEN")

    def test_unknown_dict_key_fails_closed(self) -> None:
        with self.assertRaises(AccountNewRiskGateError):
            build_injected_snapshot_from_equity_summary(
                {"equity_usd": 1.0, "account_id": "secret"}
            )

    def test_missing_equity_fails_closed(self) -> None:
        with self.assertRaises(AccountNewRiskGateError):
            build_injected_snapshot_from_equity_summary({})

    def test_invalid_equity_fails_closed(self) -> None:
        with self.assertRaises(AccountNewRiskGateError):
            build_injected_snapshot_from_equity_summary({"equity_usd": float("nan")})

    def test_negative_equity_fails_closed(self) -> None:
        with self.assertRaises(AccountNewRiskGateError):
            build_injected_snapshot_from_equity_summary({"equity_usd": -1.0})

    def test_bool_equity_fails_closed(self) -> None:
        with self.assertRaises(AccountNewRiskGateError):
            build_injected_snapshot_from_equity_summary({"equity_usd": True})


if __name__ == "__main__":
    unittest.main()
