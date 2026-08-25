"""Tests for strategy_lifecycle.contracts — data model creation & serialization."""

from __future__ import annotations

from datetime import date
import unittest

from quant_platform_kit.strategy_lifecycle.contracts import (
    BacktestResult,
    DriftDimension,
    DriftResult,
    DriftStatus,
    OptimizationProposal,
    ParamDimension,
    ParamSearchSpace,
    StrategyHealthScore,
    StrategyPerformanceSnapshot,
    UpdateLogEntry,
    UpdateStage,
    WindowPerformance,
)
from quant_platform_kit.strategy_lifecycle.performance_store import _drift_from_dict


class ContractsTests(unittest.TestCase):
    maxDiff = None

    def test_window_performance_defaults(self) -> None:
        wp = WindowPerformance(
            window_name="test_6m", window_days=126,
            start_date=date(2025, 1, 1), end_date=date(2025, 6, 30),
            observation_count=126, total_return=0.12, cagr=0.25,
            volatility=0.20, sharpe_ratio=1.5, sortino_ratio=2.0,
            calmar_ratio=1.2, max_drawdown=-0.10, win_rate=0.6,
        )
        self.assertEqual(wp.window_name, "test_6m")
        self.assertEqual(wp.sharpe_ratio, 1.5)
        self.assertEqual(wp.benchmark_symbol, "")

    def test_window_performance_with_benchmark(self) -> None:
        wp = WindowPerformance(
            window_name="test", window_days=63,
            start_date=date(2025, 1, 1), end_date=date(2025, 3, 31),
            observation_count=63, total_return=0.05, cagr=0.10,
            volatility=0.15, sharpe_ratio=0.8, sortino_ratio=1.2,
            calmar_ratio=0.6, max_drawdown=-0.08, win_rate=0.55,
            benchmark_symbol="SPY", excess_cagr=0.03, alpha=0.02,
        )
        self.assertEqual(wp.benchmark_symbol, "SPY")
        self.assertEqual(wp.excess_cagr, 0.03)

    def test_window_performance_to_dict(self) -> None:
        wp = WindowPerformance(
            window_name="t", window_days=21,
            start_date=date(2025, 1, 1), end_date=date(2025, 1, 31),
            observation_count=21, total_return=0.02, cagr=0.05,
            volatility=0.10, sharpe_ratio=0.5, sortino_ratio=1.0,
            calmar_ratio=0.3, max_drawdown=-0.05, win_rate=0.6,
        )
        d = wp.to_dict()
        self.assertEqual(d["window_name"], "t")
        self.assertEqual(d["window_days"], 21)
        self.assertEqual(d["start_date"], "2025-01-01")

    def test_snapshot_minimal(self) -> None:
        snap = StrategyPerformanceSnapshot(
            strategy_profile="test_strat", domain="us_equity",
            platform="schwab", as_of=date(2026, 6, 1),
        )
        self.assertEqual(snap.strategy_profile, "test_strat")
        self.assertEqual(snap.as_of, date(2026, 6, 1))
        self.assertIsNone(snap.latest_return)

    def test_snapshot_with_windows(self) -> None:
        wp = WindowPerformance(
            window_name="t", window_days=126, start_date=date(2025, 1, 1),
            end_date=date(2026, 6, 1), observation_count=250, total_return=0.15,
            cagr=0.20, volatility=0.22, sharpe_ratio=1.2, sortino_ratio=1.8,
            calmar_ratio=0.9, max_drawdown=-0.12, win_rate=0.58,
        )
        snap = StrategyPerformanceSnapshot(
            strategy_profile="p", domain="us", platform="t", as_of=date(2026, 6, 1),
            windows={126: wp},
        )
        self.assertIn(126, snap.windows)
        self.assertEqual(snap.windows[126].sharpe_ratio, 1.2)

    def test_snapshot_to_dict(self) -> None:
        snap = StrategyPerformanceSnapshot(
            strategy_profile="p", domain="us", platform="t",
            as_of=date(2026, 6, 1), computed_at="2026-06-29T12:00:00+00:00",
        )
        d = snap.to_dict()
        self.assertEqual(d["strategy_profile"], "p")
        self.assertEqual(d["as_of"], "2026-06-01")
        self.assertEqual(d["domain"], "us")

    def test_drift_status_enum(self) -> None:
        self.assertEqual(DriftStatus.HEALTHY.value, "healthy")
        self.assertEqual(DriftStatus.WATCH.value, "watch")
        self.assertEqual(DriftStatus.REVIEW.value, "review")
        self.assertEqual(DriftStatus.CRITICAL.value, "critical")
        self.assertEqual(DriftStatus.from_score(0.1), DriftStatus.HEALTHY)
        self.assertEqual(DriftStatus.from_score(0.35), DriftStatus.WATCH)
        self.assertEqual(DriftStatus.from_score(0.55), DriftStatus.REVIEW)
        self.assertEqual(DriftStatus.from_score(0.85), DriftStatus.CRITICAL)

    def test_drift_dimension(self) -> None:
        dim = DriftDimension(
            metric_name="sharpe_ratio", actual=0.8, expected=1.5,
            deviation=0.7, deviation_pct=0.467, threshold=0.5, breached=True,
        )
        self.assertTrue(dim.breached)
        self.assertEqual(dim.metric_name, "sharpe_ratio")
        self.assertEqual(dim.deviation, 0.7)

    def test_drift_result(self) -> None:
        dim = DriftDimension(
            metric_name="cagr", actual=0.05, expected=0.18,
            deviation=0.13, deviation_pct=0.72, threshold=0.5, breached=True,
        )
        drift = DriftResult(
            strategy_profile="t", domain="us", as_of=date(2026, 6, 1),
            drift_score=0.65, status=DriftStatus.REVIEW,
            dimensions={"cagr_drift": dim},
        )
        self.assertEqual(drift.status, DriftStatus.REVIEW)
        self.assertEqual(len(drift.breached_dimensions), 1)
        d = drift.to_dict()
        self.assertEqual(d["status"], "review")

    def test_drift_result_escalated(self) -> None:
        drift = DriftResult(
            strategy_profile="t", domain="us", as_of=date(2026, 6, 1),
            drift_score=0.6, status=DriftStatus.REVIEW,
            previous_status=DriftStatus.WATCH, escalated=True,
        )
        self.assertTrue(drift.escalated)

    def test_drift_result_preserves_legacy_positional_flags(self) -> None:
        drift = DriftResult(
            "t",
            "us",
            date(2026, 6, 1),
            0.6,
            DriftStatus.REVIEW,
            {},
            DriftStatus.WATCH,
            True,
            True,
            True,
        )

        self.assertTrue(drift.escalated)
        self.assertTrue(drift.cooldown_active)
        self.assertTrue(drift.alert_suppressed)
        self.assertIsNone(drift.baseline_param_set_id)
        self.assertTrue(drift.baseline_available)
        self.assertTrue(drift.to_dict()["baseline_available"])

    def test_drift_result_round_trips_baseline_availability(self) -> None:
        drift = DriftResult(
            strategy_profile="t",
            domain="us",
            as_of=date(2026, 6, 1),
            drift_score=0.6,
            status=DriftStatus.REVIEW,
            baseline_param_set_id="accepted-v1",
            baseline_param_version=2,
            baseline_artifact_id="accepted-run-2",
            baseline_available=False,
        )

        restored = _drift_from_dict(drift.to_dict())

        self.assertIsNotNone(restored)
        assert restored is not None
        self.assertEqual(restored.baseline_param_set_id, "accepted-v1")
        self.assertEqual(restored.baseline_param_version, 2)
        self.assertEqual(restored.baseline_artifact_id, "accepted-run-2")
        self.assertFalse(restored.baseline_available)

    def test_backtest_result(self) -> None:
        bt = BacktestResult(
            strategy_profile="p", domain="us", param_set_id="default",
            params={"trend_pool_size": 5}, param_version=1,
            sharpe_ratio=1.2, calmar_ratio=0.8, max_drawdown=-0.15,
            cagr=0.18, observation_count=1500,
            oos_sharpe=1.0, walk_forward_stability=0.7,
        )
        self.assertEqual(bt.param_version, 1)
        self.assertEqual(bt.params, {"trend_pool_size": 5})
        d = bt.to_dict()
        self.assertEqual(d["param_version"], 1)
        self.assertIn("oos_sharpe", d)

    def test_backtest_result_minimal(self) -> None:
        bt = BacktestResult(
            strategy_profile="p", domain="us", param_set_id="p1",
            params={},
        )
        self.assertEqual(bt.sharpe_ratio, None)
        self.assertEqual(bt.observation_count, 0)

    def test_param_domain_dimension(self) -> None:
        dim = ParamDimension(
            name="rotation_top_n", param_type="int",
            bounds=(2, 8), step=1, current_value=4,
        )
        self.assertEqual(ParamDimension, type(dim))
        d = dim.to_dict()
        self.assertEqual(d["param_type"], "int")
        self.assertEqual(d["bounds"], [2, 8])

    def test_param_search_space(self) -> None:
        dim = ParamDimension(name="a", param_type="int", bounds=(1, 10))
        space = ParamSearchSpace(strategy_profile="p", domain="us", dimensions={"a": dim})
        self.assertEqual(space.dimensions["a"].bounds, (1, 10))

    def test_optimization_proposal(self) -> None:
        bt = BacktestResult(
            strategy_profile="p", domain="us", param_set_id="proposed",
            params={"top_n": 5},
            sharpe_ratio=1.5, calmar_ratio=1.0, max_drawdown=-0.10,
        )
        proposal = OptimizationProposal(
            strategy_profile="p", domain="us",
            current_params={"top_n": 3}, proposed_params={"top_n": 5},
            proposed_metrics=bt,
            improvement_score=0.15, confidence=0.8,
            recommendation="promote",
            walk_forward_passed=True,
        )
        self.assertEqual(proposal.recommendation, "promote")
        self.assertTrue(proposal.walk_forward_passed)
        d = proposal.to_dict()
        self.assertEqual(d["improvement_score"], 0.15)

    def test_update_log_entry(self) -> None:
        entry = UpdateLogEntry(
            strategy_profile="p", domain="us", entry_id="abc123",
            stage=UpdateStage.DEPLOYED,
            timestamp="2026-06-29T12:00:00+00:00",
            operator="auto_optimizer",
            param_version_from=1, param_version_to=2,
            reason="Auto-optimized",
        )
        self.assertEqual(entry.operator, "auto_optimizer")
        self.assertIn("abc123", entry.entry_id)

    def test_update_stages(self) -> None:
        self.assertEqual(UpdateStage.OPTIMIZED.value, "optimized")
        self.assertEqual(UpdateStage.SHADOW_VALIDATING.value, "shadow_validating")
        self.assertEqual(UpdateStage.PATCH_CREATED.value, "patch_created")
        self.assertEqual(UpdateStage.DEPLOYED.value, "deployed")
        self.assertEqual(UpdateStage.RUNTIME_CONFIRMED.value, "runtime_confirmed")
        self.assertEqual(UpdateStage.ROLLBACK_PROPOSED.value, "rollback_proposed")
        self.assertEqual(UpdateStage.ROLLED_BACK.value, "rolled_back")

    def test_health_score(self) -> None:
        score = StrategyHealthScore(
            strategy_profile="p", domain="us", as_of=date(2026, 6, 1),
            overall_score=72.5, performance_score=80.0, risk_score=70.0,
            decay_score=65.0, stability_score=75.0, operational_score=90.0,
            status="healthy",
        )
        self.assertEqual(score.overall_score, 72.5)
        d = score.to_dict()
        self.assertEqual(d["status"], "healthy")


if __name__ == "__main__":
    unittest.main()
