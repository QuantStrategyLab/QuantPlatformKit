"""Tests for strategy_lifecycle.drift_detector — drift calculation logic."""

from __future__ import annotations

from dataclasses import replace
from datetime import date
import unittest
from unittest import mock

import pandas as pd

from quant_platform_kit.strategy_lifecycle.contracts import (
    BacktestResult,
    DriftStatus,
    StrategyPerformanceSnapshot,
    WindowPerformance,
)
from quant_platform_kit.strategy_lifecycle.drift_detector import detect_drift, run_drift_detection


def _make_snapshot(sharpe: float = 1.5, cagr: float = 0.18, dd: float = -0.12,
                   vol: float = 0.20, wr: float = 0.58) -> StrategyPerformanceSnapshot:
    wp126 = WindowPerformance(
        window_name="trailing_6m", window_days=126,
        start_date=date(2026, 1, 1), end_date=date(2026, 6, 1),
        observation_count=126, total_return=cagr, cagr=cagr,
        volatility=vol, sharpe_ratio=sharpe, sortino_ratio=sharpe * 1.2,
        calmar_ratio=abs(cagr / dd) if dd else 0,
        max_drawdown=dd, win_rate=wr,
    )
    return StrategyPerformanceSnapshot(
        strategy_profile="test_strat", domain="us_equity",
        platform="test", as_of=date(2026, 6, 1),
        windows={126: wp126},
    )


def _make_backtest(sharpe: float = 1.5, cagr: float = 0.18, dd: float = -0.12,
                   vol: float = 0.20, wr: float = 0.58) -> BacktestResult:
    return BacktestResult(
        strategy_profile="test_strat", domain="us_equity",
        param_set_id="baseline", params={}, param_version=1,
        sharpe_ratio=sharpe, cagr=cagr, max_drawdown=dd,
        volatility=vol, win_rate=wr,
        observation_count=1500,
    )


class DriftDetectorTests(unittest.TestCase):

    def test_no_drift_when_matches(self) -> None:
        snap = _make_snapshot(sharpe=1.5, cagr=0.18, dd=-0.12, vol=0.20, wr=0.58)
        bt = _make_backtest(sharpe=1.5, cagr=0.18, dd=-0.12, vol=0.20, wr=0.58)
        result = detect_drift(snap, backtest=bt)
        self.assertEqual(result.status, DriftStatus.HEALTHY)
        self.assertLess(result.drift_score, 0.25)

    def test_sharpe_drift_detected(self) -> None:
        snap = _make_snapshot(sharpe=0.6, cagr=0.18, dd=-0.12)
        bt = _make_backtest(sharpe=1.5)
        result = detect_drift(snap, backtest=bt)
        self.assertNotEqual(result.status, DriftStatus.HEALTHY)
        dims = result.dimensions
        self.assertIn("sharpe_drift", dims)
        self.assertTrue(dims["sharpe_drift"].breached)

    def test_cagr_drift_detected(self) -> None:
        snap = _make_snapshot(sharpe=1.5, cagr=0.01, dd=-0.12)
        bt = _make_backtest(sharpe=1.5, cagr=0.18)
        result = detect_drift(snap, backtest=bt)
        self.assertNotEqual(result.status, DriftStatus.HEALTHY)
        self.assertIn("cagr_drift", result.dimensions)
        self.assertTrue(result.dimensions["cagr_drift"].breached)

    def test_drawdown_breach_detected(self) -> None:
        snap = _make_snapshot(sharpe=1.5, cagr=0.18, dd=-0.40)
        bt = _make_backtest(sharpe=1.5, cagr=0.18, dd=-0.12)
        result = detect_drift(snap, backtest=bt)
        self.assertIn("max_drawdown_breach", result.dimensions)
        self.assertTrue(result.dimensions["max_drawdown_breach"].breached)

    def test_no_backtest_returns_healthy(self) -> None:
        snap = _make_snapshot(sharpe=0.6, cagr=0.01)
        result = detect_drift(snap, backtest=None)
        self.assertEqual(result.status, DriftStatus.HEALTHY)

    def test_no_windows_returns_healthy(self) -> None:
        snap = StrategyPerformanceSnapshot(
            strategy_profile="t", domain="us", platform="t",
            as_of=date(2026, 6, 1),
        )
        result = detect_drift(snap)
        self.assertEqual(result.status, DriftStatus.HEALTHY)

    def test_escalation_detected(self) -> None:
        snap = _make_snapshot(sharpe=0.5)
        bt = _make_backtest(sharpe=1.5)
        result = detect_drift(snap, backtest=bt, previous_status=DriftStatus.HEALTHY)
        self.assertTrue(result.escalated)
        self.assertIsNotNone(result.previous_status)

    def test_volatility_drift_detected(self) -> None:
        snap = _make_snapshot(sharpe=1.5, cagr=0.18, vol=0.45)
        bt = _make_backtest(sharpe=1.5, cagr=0.18, vol=0.20)
        result = detect_drift(snap, backtest=bt)
        self.assertIn("volatility_drift", result.dimensions)

    def test_drift_score_range(self) -> None:
        snap = _make_snapshot(sharpe=1.5, cagr=0.18)
        bt = _make_backtest(sharpe=1.5, cagr=0.18)
        result = detect_drift(snap, backtest=bt)
        self.assertGreaterEqual(result.drift_score, 0.0)
        self.assertLessEqual(result.drift_score, 1.0)

    def test_to_dict_roundtrip(self) -> None:
        snap = _make_snapshot()
        bt = _make_backtest()
        result = detect_drift(snap, backtest=bt)
        d = result.to_dict()
        self.assertEqual(d["strategy_profile"], "test_strat")
        self.assertEqual(d["domain"], "us_equity")
        self.assertIn("dimensions", d)

    def test_run_drift_detection_fails_closed_when_no_profiles_found(self) -> None:
        class EmptyCollector:
            def collect(self, _domain: str) -> dict[str, pd.Series]:
                return {}

        with mock.patch(
            "quant_platform_kit.strategy_lifecycle.return_collector.ReturnCollector",
            return_value=EmptyCollector(),
        ):
            with self.assertRaisesRegex(RuntimeError, "No strategy return series found"):
                run_drift_detection("us_equity")

    def test_run_drift_detection_passes_supplied_store_to_return_collector(self) -> None:
        sentinel_store = object()

        class EmptyCollector:
            def collect(self, _domain: str) -> dict[str, pd.Series]:
                return {}

        with mock.patch(
            "quant_platform_kit.strategy_lifecycle.return_collector.ReturnCollector",
            return_value=EmptyCollector(),
        ) as collector_factory:
            with self.assertRaisesRegex(RuntimeError, "No strategy return series found"):
                run_drift_detection("us_equity", store=sentinel_store)  # type: ignore[arg-type]

        collector_factory.assert_called_once_with(store=sentinel_store)

    def test_baseline_lineage_policy_handles_legacy_history_explicitly(self) -> None:
        snapshot = _make_snapshot()
        backtest = _make_backtest()
        legacy_previous = replace(
            detect_drift(snapshot, backtest=backtest),
            baseline_param_set_id=None,
        )

        def run(
            policy: str,
            accepted_backtest: BacktestResult | None = backtest,
            previous=legacy_previous,
            *,
            external_baseline: bool = True,
        ):
            active_store = mock.Mock()
            active_store.load_latest_snapshot.return_value = snapshot
            active_store.load_latest_drift.return_value = previous
            active_store.load_latest_backtest.return_value = accepted_backtest
            baseline_store = mock.Mock()
            baseline_store.load_latest_backtest.return_value = accepted_backtest

            collector = mock.Mock()
            collector.collect.return_value = {snapshot.strategy_profile: pd.Series([0.01])}
            with mock.patch(
                "quant_platform_kit.strategy_lifecycle.return_collector.ReturnCollector",
                return_value=collector,
            ):
                result = run_drift_detection(
                    snapshot.domain,
                    strategy_profile=snapshot.strategy_profile,
                    store=active_store,
                    baseline_store=baseline_store if external_baseline else None,
                    baseline_lineage_policy=policy,
                )[0]
            return result

        self.assertEqual(
            run("auto", external_baseline=False).previous_status,
            legacy_previous.status,
        )
        self.assertIsNone(run("auto").previous_status)
        self.assertIsNone(run("strict").previous_status)
        self.assertIsNone(run("strict", accepted_backtest=None).previous_status)
        self.assertEqual(run("migration").previous_status, legacy_previous.status)
        lineage_previous = detect_drift(snapshot, backtest=backtest)
        rotated_backtest = replace(backtest, param_set_id="rotated-baseline")
        self.assertEqual(
            run(
                "auto",
                accepted_backtest=rotated_backtest,
                previous=lineage_previous,
                external_baseline=False,
            ).previous_status,
            lineage_previous.status,
        )
        self.assertIsNone(
            run(
                "auto",
                accepted_backtest=None,
                previous=lineage_previous,
            ).previous_status
        )
        self.assertIsNone(
            run(
                "migration",
                accepted_backtest=rotated_backtest,
                previous=lineage_previous,
            ).previous_status
        )

        with self.assertRaisesRegex(ValueError, "external baseline store"):
            run("compatible")

        with self.assertRaisesRegex(ValueError, "baseline_lineage_policy"):
            run("unknown")

    def test_missing_external_baseline_does_not_replace_lineage_history(self) -> None:
        snapshot = _make_snapshot()
        previous = detect_drift(snapshot, backtest=_make_backtest())
        active_store = mock.Mock()
        active_store.load_latest_snapshot.return_value = snapshot
        active_store.load_latest_drift.return_value = previous
        baseline_store = mock.Mock()
        baseline_store.load_latest_backtest.return_value = None
        collector = mock.Mock()
        collector.collect.return_value = {snapshot.strategy_profile: pd.Series([0.01])}

        with mock.patch(
            "quant_platform_kit.strategy_lifecycle.return_collector.ReturnCollector",
            return_value=collector,
        ):
            result = run_drift_detection(
                snapshot.domain,
                strategy_profile=snapshot.strategy_profile,
                store=active_store,
                baseline_store=baseline_store,
                baseline_lineage_policy="strict",
            )[0]

        self.assertIsNone(result.baseline_param_set_id)
        active_store.save_drift_result.assert_not_called()


if __name__ == "__main__":
    unittest.main()
