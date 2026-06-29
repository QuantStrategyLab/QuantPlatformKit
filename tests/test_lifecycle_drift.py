"""Tests for strategy_lifecycle.drift_detector — drift calculation logic."""

from __future__ import annotations

from datetime import date
import unittest

from quant_platform_kit.strategy_lifecycle.contracts import (
    BacktestResult,
    DriftStatus,
    StrategyPerformanceSnapshot,
    WindowPerformance,
)
from quant_platform_kit.strategy_lifecycle.drift_detector import detect_drift


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


if __name__ == "__main__":
    unittest.main()
