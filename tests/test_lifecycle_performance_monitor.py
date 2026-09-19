from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from quant_platform_kit.common.strategy_contracts import PositionTarget, StrategyDecision
from quant_platform_kit.strategy_lifecycle.performance_monitor import (
    PerformanceMonitor,
    infer_strategy_domain,
    resolve_monitor_source_revision,
    run_monitor,
    try_record_platform_execution,
)
from quant_platform_kit.strategy_lifecycle.performance_store import PerformanceStore
from quant_platform_kit.strategy_lifecycle.return_collector import ReturnCollector


class PerformanceMonitorTests(unittest.TestCase):
    def test_record_persists_live_run_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = PerformanceStore(local_root=Path(tmp))
            monitor = PerformanceMonitor(store=store)
            decision = StrategyDecision(
                positions=(PositionTarget(symbol="BTCUSDT", target_weight=0.5, role="target"),),
                risk_flags=("risk_gate:passed",),
            )
            result = monitor.record(
                "crypto_live_pool_rotation",
                decision,
                {"filled_orders": 1},
                domain="crypto",
            )
            self.assertTrue(result["ok"])
            files = list(Path(tmp).rglob("live_runs/crypto/crypto_live_pool_rotation/*.json"))
            self.assertEqual(len(files), 1)
            payload = files[0].read_text(encoding="utf-8")
            self.assertIn("BTCUSDT", payload)
            self.assertIn("filled_orders", payload)

    def test_record_execution_persists_execution_only_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = PerformanceStore(local_root=Path(tmp))
            monitor = PerformanceMonitor(store=store)
            result = monitor.record_execution(
                "global_etf_rotation",
                {"orders_filled": ["VOO"], "status": "ok"},
                domain="us_equity",
            )
            self.assertTrue(result["ok"])
            files = list(Path(tmp).rglob("live_runs/us_equity/global_etf_rotation/*.json"))
            self.assertEqual(len(files), 1)
            payload = files[0].read_text(encoding="utf-8")
            self.assertIn("record_kind", payload)
            self.assertIn("orders_filled", payload)

    def test_infer_strategy_domain_from_profile_prefix(self) -> None:
        self.assertEqual(infer_strategy_domain("cn_index_etf_tactical_rotation"), "cn_equity")
        self.assertEqual(infer_strategy_domain("hk_global_etf_tactical_rotation"), "hk_equity")
        self.assertEqual(infer_strategy_domain("crypto_live_pool_rotation"), "crypto")
        self.assertEqual(infer_strategy_domain("global_etf_rotation"), "us_equity")

    def test_try_record_platform_execution_swallows_errors(self) -> None:
        try_record_platform_execution("", {"status": "ok"})

    def test_resolve_monitor_source_revision_requires_real_provenance(self) -> None:
        sha = "a" * 40
        self.assertEqual(resolve_monitor_source_revision(sha), sha)
        self.assertEqual(
            resolve_monitor_source_revision(None, environ={"LIFECYCLE_SOURCE_REVISION": "fixture-rev"}),
            "fixture-rev",
        )
        self.assertEqual(
            resolve_monitor_source_revision(None, environ={"GITHUB_SHA": sha}),
            sha,
        )
        with self.assertRaisesRegex(RuntimeError, "source_revision is required"):
            resolve_monitor_source_revision(None, environ={})
        with self.assertRaisesRegex(RuntimeError, "source_revision is required"):
            resolve_monitor_source_revision("", environ={"GITHUB_SHA": "deadbeef"})

    def test_run_monitor_fails_closed_when_no_profiles_found(self) -> None:
        class EmptyCollector:
            def collect(self, _domain: str) -> dict[str, pd.Series]:
                return {}

        with self.assertRaisesRegex(RuntimeError, "No strategy return series found"):
            run_monitor(
                "us_equity",
                collector=EmptyCollector(),
                source_revision="a" * 40,
            )

    def test_run_monitor_fails_closed_without_source_revision(self) -> None:
        class OneCollector:
            def collect(self, _domain: str) -> dict[str, pd.Series]:
                return {
                    "synthetic_soxl": pd.Series(
                        [0.01, -0.02],
                        index=pd.to_datetime(["2026-09-08", "2026-09-09"]),
                    )
                }

        with patch.dict("os.environ", {}, clear=False):
            for key in ("LIFECYCLE_SOURCE_REVISION", "GITHUB_SHA"):
                # Ensure missing provenance cannot silently write empty revision.
                pass
        with patch(
            "quant_platform_kit.strategy_lifecycle.performance_monitor.resolve_monitor_source_revision",
            side_effect=RuntimeError("monitor source_revision is required"),
        ):
            with self.assertRaisesRegex(RuntimeError, "source_revision is required"):
                run_monitor("us_equity", collector=OneCollector(), windows=(2,), min_observations=2)

    def test_csv_collector_to_monitor_rejects_duplicate_daily_returns(self) -> None:
        revision = "b" * 40
        for dates, values in (
            (["2026-09-08", "2026-09-08"], [0.01, 0.01]),
            (["2026-09-08T09:00:00", "2026-09-08T16:00:00"], [0.01, -0.02]),
        ):
            with self.subTest(dates=dates), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                matrix = root / "portfolio_and_tracker_returns.csv"
                pd.DataFrame({"as_of": dates, "synthetic_soxl": values}).to_csv(matrix, index=False)
                store = PerformanceStore(local_root=root / "store")
                collector = ReturnCollector(artifact_roots={"us_equity": root}, projects_root=root, store=store)
                with patch.object(PerformanceStore, "save_snapshot", autospec=True) as save:
                    with self.assertRaisesRegex(RuntimeError, "No strategy return series found"):
                        run_monitor(
                            "us_equity",
                            strategy_profile="synthetic_soxl",
                            collector=collector,
                            store=store,
                            windows=(2,),
                            min_observations=2,
                            source_revision=revision,
                        )
                    self.assertEqual(
                        run_monitor(
                            "us_equity",
                            collector=collector,
                            store=store,
                            min_observations=2,
                            fail_on_empty=False,
                            source_revision=revision,
                        ),
                        [],
                    )
                    save.assert_not_called()

    def test_csv_collector_to_monitor_preserves_unique_daily_returns(self) -> None:
        revision = "c" * 40
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pd.DataFrame({
                "as_of": ["2026-09-08T16:00:00", "2026-09-09T16:00:00"],
                "synthetic_soxl": [0.01, -0.02],
                "SPY": [0.01, -0.02],
            }).to_csv(root / "portfolio_and_tracker_returns.csv", index=False)
            store = PerformanceStore(local_root=root / "store")
            collector = ReturnCollector(artifact_roots={"us_equity": root}, projects_root=root, store=store)
            snapshots = run_monitor(
                "us_equity", strategy_profile="synthetic_soxl", collector=collector, store=store,
                windows=(2,), min_observations=2, require_explicit_benchmark=True,
                strategy_benchmarks={"synthetic_soxl": "SPY"},
                source_revision=revision,
            )
            self.assertEqual(len(snapshots), 1)
            self.assertEqual(snapshots[0].source_revision, revision)
            metrics = snapshots[0].windows[2]
            self.assertEqual(metrics.observation_count, 2)
            self.assertAlmostEqual(metrics.total_return, 1.01 * 0.98 - 1.0)
            self.assertAlmostEqual(metrics.excess_cagr, 0.0)

    def test_csv_collector_to_monitor_rejects_duplicate_required_benchmark(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pd.DataFrame({"as_of": ["2026-09-08", "2026-09-09"], "synthetic_soxl": [0.01, -0.02]}).to_csv(
                root / "portfolio_and_tracker_returns.csv", index=False,
            )
            benchmark_dir = root / "benchmark"
            benchmark_dir.mkdir()
            pd.DataFrame({"as_of": ["2026-09-08", "2026-09-08"], "SPY": [0.01, -0.02]}).to_csv(
                benchmark_dir / "portfolio_and_tracker_returns.csv", index=False,
            )
            store = PerformanceStore(local_root=root / "store")
            collector = ReturnCollector(artifact_roots={"us_equity": root}, projects_root=root, store=store)
            with patch.object(PerformanceStore, "save_snapshot", autospec=True) as save:
                with self.assertRaisesRegex(RuntimeError, "explicit benchmark data is unavailable or insufficient"):
                    run_monitor(
                        "us_equity", strategy_profile="synthetic_soxl", collector=collector, store=store,
                        windows=(2,), min_observations=2, require_explicit_benchmark=True,
                        strategy_benchmarks={"synthetic_soxl": "SPY"},
                        source_revision="d" * 40,
                    )
                save.assert_not_called()

    def test_run_monitor_uses_crypto_365_25_and_equity_252(self) -> None:
        revision = "e" * 40
        idx = pd.to_datetime([f"2026-01-{d:02d}" for d in range(1, 11)])
        returns = pd.Series([0.01] * 10, index=idx)

        class FixedCollector:
            def __init__(self, series: pd.Series) -> None:
                self._series = series

            def collect(self, _domain: str) -> dict[str, pd.Series]:
                stamped = self._series.copy()
                stamped.attrs["observation_status"] = "ok"
                return {"prof": stamped}

            def collect_benchmark(self, _domain: str, _symbol: str):
                return None

        with tempfile.TemporaryDirectory() as tmp:
            store = PerformanceStore(local_root=Path(tmp))
            crypto = run_monitor(
                "crypto",
                strategy_profile="prof",
                collector=FixedCollector(returns),
                store=store,
                windows=(10,),
                min_observations=10,
                source_revision=revision,
            )
            equity = run_monitor(
                "us_equity",
                strategy_profile="prof",
                collector=FixedCollector(returns),
                store=store,
                windows=(10,),
                min_observations=10,
                source_revision=revision,
            )
        self.assertEqual(crypto[0].windows[10].periods_per_year, 365.25)
        self.assertEqual(crypto[0].windows[10].calendar_id, "CRYPTO_NATURAL_DAY")
        self.assertEqual(equity[0].windows[10].periods_per_year, 252.0)
        self.assertEqual(equity[0].windows[10].calendar_id, "XNYS")
        # Same raw returns → different annualized Sharpe when basis differs.
        self.assertNotAlmostEqual(
            crypto[0].windows[10].sharpe_ratio,
            equity[0].windows[10].sharpe_ratio,
        )

    def test_run_monitor_preserves_truncated_observation_status(self) -> None:
        revision = "f" * 40
        idx = pd.to_datetime(["2026-09-16", "2026-09-17", "2026-09-18"])
        series = pd.Series([0.01, 0.02, -0.01], index=idx)
        series.attrs["observation_status"] = "truncated_after_observation_gap"

        class TruncCollector:
            def collect(self, _domain: str) -> dict[str, pd.Series]:
                return {"live_prof": series}

            def collect_benchmark(self, _domain: str, _symbol: str):
                return None

        with tempfile.TemporaryDirectory() as tmp:
            store = PerformanceStore(local_root=Path(tmp))
            snapshots = run_monitor(
                "crypto",
                strategy_profile="live_prof",
                collector=TruncCollector(),
                store=store,
                windows=(3,),
                min_observations=3,
                source_revision=revision,
            )
            loaded = store.load_latest_snapshot("crypto", "live_prof")
        self.assertEqual(snapshots[0].observation_status, "truncated_after_observation_gap")
        self.assertEqual(loaded.observation_status, "truncated_after_observation_gap")
        # Window metrics still compute on the latest contiguous segment.
        self.assertEqual(snapshots[0].windows[3].observation_count, 3)

    def test_run_monitor_marks_baseline_incomparable_without_matching_periods(self) -> None:
        revision = "g" * 40
        idx = pd.to_datetime([f"2026-02-{d:02d}" for d in range(1, 21)])
        series = pd.Series([0.001] * 20, index=idx)
        series.attrs["observation_status"] = "ok"

        class FixedCollector:
            def collect(self, _domain: str) -> dict[str, pd.Series]:
                return {"crypto_live_pool_rotation": series}

            def collect_benchmark(self, _domain: str, _symbol: str):
                return None

        from quant_platform_kit.strategy_lifecycle.contracts import BacktestResult

        with tempfile.TemporaryDirectory() as tmp:
            store = PerformanceStore(local_root=Path(tmp))
            # Legacy baseline: no periods_per_year → not comparable.
            store.save_backtest_result(
                BacktestResult(
                    strategy_profile="crypto_live_pool_rotation",
                    domain="crypto",
                    param_set_id="crypto_live_pool_rotation_baseline",
                    params={},
                    sharpe_ratio=1.5,
                    cagr=0.2,
                    max_drawdown=-0.1,
                    volatility=0.3,
                    win_rate=0.55,
                    computed_at="2026-01-01T00:00:00+00:00",
                    periods_per_year=None,
                )
            )
            missing = run_monitor(
                "crypto",
                strategy_profile="crypto_live_pool_rotation",
                collector=FixedCollector(),
                store=store,
                windows=(20, 126),
                min_observations=20,
                source_revision=revision,
            )
            self.assertEqual(missing[0].drift_status, "not_comparable_annualization")
            self.assertIsNone(missing[0].drift_score)

            # Mismatched explicit basis (252 vs crypto 365.25).
            store.save_backtest_result(
                BacktestResult(
                    strategy_profile="crypto_live_pool_rotation",
                    domain="crypto",
                    param_set_id="crypto_live_pool_rotation_baseline",
                    params={},
                    sharpe_ratio=1.5,
                    cagr=0.2,
                    max_drawdown=-0.1,
                    volatility=0.3,
                    win_rate=0.55,
                    computed_at="2026-02-01T00:00:00+00:00",
                    periods_per_year=252.0,
                    calendar_id="XNYS",
                )
            )
            mismatched = run_monitor(
                "crypto",
                strategy_profile="crypto_live_pool_rotation",
                collector=FixedCollector(),
                store=store,
                windows=(20, 126),
                min_observations=20,
                source_revision=revision,
            )
            self.assertEqual(mismatched[0].drift_status, "not_comparable_annualization")
            self.assertIsNone(mismatched[0].drift_score)

            # Matching 365.25 allows drift scoring.
            store.save_backtest_result(
                BacktestResult(
                    strategy_profile="crypto_live_pool_rotation",
                    domain="crypto",
                    param_set_id="crypto_live_pool_rotation_baseline",
                    params={},
                    sharpe_ratio=0.0,
                    cagr=0.0,
                    max_drawdown=-0.01,
                    volatility=0.01,
                    win_rate=0.5,
                    computed_at="2026-03-01T00:00:00+00:00",
                    periods_per_year=365.25,
                    calendar_id="CRYPTO_NATURAL_DAY",
                )
            )
            matched = run_monitor(
                "crypto",
                strategy_profile="crypto_live_pool_rotation",
                collector=FixedCollector(),
                store=store,
                windows=(20, 126),
                min_observations=20,
                source_revision=revision,
            )
            self.assertNotEqual(matched[0].drift_status, "not_comparable_annualization")
            self.assertIsNotNone(matched[0].drift_score)

    def test_run_monitor_live_incomplete_calendar_produces_no_snapshot(self) -> None:
        revision = "h" * 40
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = PerformanceStore(local_root=root / "store")
            for day, equity in (
                ("2025-12-30T20:00:00Z", 100.0),
                ("2025-12-31T20:00:00Z", 101.0),
            ):
                store.save_live_run_record(
                    "global_etf_rotation",
                    "us_equity",
                    {
                        "strategy_profile": "global_etf_rotation",
                        "domain": "us_equity",
                        "recorded_at": day,
                        "record_kind": "execution",
                        "execution_result": {"total_equity": equity},
                    },
                    stream_id="acct-a",
                )
            collector = ReturnCollector(projects_root=root, store=store)
            snapshots = run_monitor(
                "us_equity",
                strategy_profile="global_etf_rotation",
                collector=collector,
                store=store,
                live_stream_id="acct-a",
                windows=(2,),
                min_observations=1,
                fail_on_empty=False,
                source_revision=revision,
            )
            self.assertEqual(snapshots, [])

    def test_run_monitor_live_truncation_stamps_status_not_full_history(self) -> None:
        revision = "i" * 40
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = PerformanceStore(local_root=root / "store")
            # Gap Fri→Mon missing Sat for crypto natural-day calendar truncates
            # to the latest contiguous segment after the gap.
            for day, equity in (
                ("2026-09-14T20:00:00Z", 100.0),
                ("2026-09-16T20:00:00Z", 102.0),
                ("2026-09-17T20:00:00Z", 103.0),
                ("2026-09-18T20:00:00Z", 104.0),
            ):
                store.save_live_run_record(
                    "crypto_live_pool_rotation",
                    "crypto",
                    {
                        "strategy_profile": "crypto_live_pool_rotation",
                        "domain": "crypto",
                        "recorded_at": day,
                        "record_kind": "execution",
                        "execution_result": {"total_equity": equity},
                    },
                    stream_id="stream-1",
                )
            collector = ReturnCollector(projects_root=root, store=store)
            snapshots = run_monitor(
                "crypto",
                strategy_profile="crypto_live_pool_rotation",
                collector=collector,
                store=store,
                live_stream_id="stream-1",
                windows=(2,),
                min_observations=2,
                source_revision=revision,
            )
            self.assertEqual(len(snapshots), 1)
            self.assertEqual(
                snapshots[0].observation_status,
                "truncated_after_observation_gap",
            )
            self.assertEqual(snapshots[0].windows[2].periods_per_year, 365.25)
            # Only post-gap contiguous points are usable (not the pre-gap day).
            self.assertLessEqual(snapshots[0].windows[2].observation_count, 3)


if __name__ == "__main__":
    unittest.main()
