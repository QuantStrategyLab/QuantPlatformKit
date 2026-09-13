from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from quant_platform_kit.strategy_lifecycle.live_equity import (
    cash_flow_adjusted_return,
    consecutive_losses_from_live_run_records,
    count_consecutive_losses,
    extract_equity_value,
    extract_external_cash_flow,
    live_interval_records_to_return_series,
    live_run_records_to_return_series,
    resolve_consecutive_losses,
    stamp_consecutive_losses_on_snapshot,
)
from quant_platform_kit.strategy_lifecycle.performance_metrics import compute_window_metrics
from quant_platform_kit.strategy_lifecycle.performance_monitor import PerformanceMonitor, resolve_lifecycle_stream_id
from quant_platform_kit.strategy_lifecycle.performance_store import PerformanceStore
from quant_platform_kit.strategy_lifecycle.return_collector import ReturnCollector


class LiveEquityTests(unittest.TestCase):
    @staticmethod
    def _interval(start: str, end: str, equity: float, flow: float = 0.0, scope: str = "a" * 64):
        return {
            "account_scope_sha256": scope,
            "start_at": start,
            "end_at": end,
            "end_equity_usdt": str(equity),
            "net_external_cash_flow": str(flow),
            "currency": "USDT",
            "valuation_basis": "checkpoint_quantities_sampled_prices",
        }

    def test_interval_deposit_is_baseline_and_later_day_return_uses_no_double_subtraction(self) -> None:
        intervals = [
            self._interval("2026-09-07T00:00:00Z", "2026-09-08T00:00:00Z", 200, 100),
            self._interval("2026-09-08T00:00:00Z", "2026-09-08T12:00:00Z", 200),
            self._interval("2026-09-08T12:00:00Z", "2026-09-09T00:00:00Z", 202),
        ]
        series = live_interval_records_to_return_series(intervals)
        self.assertEqual(list(series.index), [pd.Timestamp("2026-09-09")])
        self.assertAlmostEqual(float(series.iloc[0]), 0.01)

    def test_interval_records_are_sorted_by_end_and_timezone_equivalent(self) -> None:
        intervals = [
            self._interval("2026-09-08T08:00:00+08:00", "2026-09-09T08:00:00+08:00", 202),
            self._interval("2026-09-07T00:00:00Z", "2026-09-08T00:00:00Z", 200, 100),
        ]
        series = live_interval_records_to_return_series(intervals)
        self.assertAlmostEqual(float(series.iloc[0]), 0.01)

    def test_interval_conflicting_duplicate_and_mixed_accounts_fail_closed(self) -> None:
        first = self._interval("2026-09-07T00:00:00Z", "2026-09-08T00:00:00Z", 200, 100)
        conflict = dict(first, end_equity_usdt="201")
        second = self._interval("2026-09-08T00:00:00Z", "2026-09-09T00:00:00Z", 202)
        self.assertTrue(live_interval_records_to_return_series([first, conflict, second]).empty)
        other = self._interval("2026-09-09T00:00:00Z", "2026-09-10T00:00:00Z", 203, scope="b" * 64)
        self.assertTrue(live_interval_records_to_return_series([first, second, other]).empty)

    def test_interval_gap_overlap_and_missing_full_day_do_not_bridge(self) -> None:
        first = self._interval("2026-09-07T00:00:00Z", "2026-09-08T00:00:00Z", 200, 100)
        gap = self._interval("2026-09-08T01:00:00Z", "2026-09-09T00:00:00Z", 202)
        later = self._interval("2026-09-09T00:00:00Z", "2026-09-10T00:00:00Z", 204)
        series = live_interval_records_to_return_series([first, gap, later])
        self.assertEqual(list(series.index), [pd.Timestamp("2026-09-10")])
        self.assertAlmostEqual(float(series.iloc[0]), 204 / 202 - 1)
        too_long = self._interval("2026-09-08T00:00:00Z", "2026-09-10T00:00:00Z", 204)
        self.assertTrue(live_interval_records_to_return_series([first, too_long]).empty)

    def test_interval_schema_and_bad_day_fail_closed(self) -> None:
        good = self._interval("2026-09-07T00:00:00Z", "2026-09-08T00:00:00Z", 200, 100)
        malformed = dict(good, valuation_basis="close_only")
        self.assertTrue(live_interval_records_to_return_series([good, malformed]).empty)

    def test_interval_branch_is_selected_from_persisted_execution_payload(self) -> None:
        rows = [
            {"recorded_at": "2026-09-09T10:00:00Z", "execution_result": {"external_cash_flow_interval": self._interval("2026-09-08T00:00:00Z", "2026-09-09T00:00:00Z", 202)}},
            {"recorded_at": "2026-09-08T10:00:00Z", "execution_result": {"external_cash_flow_interval": self._interval("2026-09-07T00:00:00Z", "2026-09-08T00:00:00Z", 200, 100)}},
        ]
        series = live_run_records_to_return_series(rows)
        self.assertAlmostEqual(float(series.iloc[0]), 0.01)

    def test_interval_none_failure_record_is_a_bad_day_barrier(self) -> None:
        def row(recorded_at, interval):
            return {
                "recorded_at": recorded_at,
                "execution_result": {"external_cash_flow_interval": interval},
            }

        rows = [
            row("2026-09-08T20:00:00Z", self._interval("2026-09-07T20:00:00Z", "2026-09-08T20:00:00Z", 110, 10)),
            row("2026-09-08T22:00:00Z", None),
            row("2026-09-09T20:00:00Z", self._interval("2026-09-08T20:00:00Z", "2026-09-09T20:00:00Z", 111)),
            row("2026-09-10T20:00:00Z", self._interval("2026-09-09T20:00:00Z", "2026-09-10T20:00:00Z", 112)),
        ]
        series = live_run_records_to_return_series(rows)
        self.assertEqual(list(series.index), [pd.Timestamp("2026-09-10")])
        self.assertAlmostEqual(float(series.iloc[0]), 112 / 111 - 1)

    def test_legacy_record_after_interval_mode_is_an_unknown_barrier(self) -> None:
        def interval_row(recorded_at, interval):
            return {
                "recorded_at": recorded_at,
                "execution_result": {"external_cash_flow_interval": interval},
            }

        rows = [
            interval_row("2026-09-08T20:00:00Z", self._interval("2026-09-07T20:00:00Z", "2026-09-08T20:00:00Z", 110, 10)),
            {"recorded_at": "2026-09-08T22:00:00Z", "execution_result": {"external_cash_flow": None}},
            interval_row("2026-09-09T20:00:00Z", self._interval("2026-09-08T20:00:00Z", "2026-09-09T20:00:00Z", 111)),
            interval_row("2026-09-10T20:00:00Z", self._interval("2026-09-09T20:00:00Z", "2026-09-10T20:00:00Z", 112)),
        ]
        series = live_run_records_to_return_series(rows)
        self.assertEqual(list(series.index), [pd.Timestamp("2026-09-10")])
        self.assertAlmostEqual(float(series.iloc[0]), 112 / 111 - 1)

    def test_interval_conflict_barrier_keeps_only_latest_clean_segment(self) -> None:
        def row(interval):
            return {"recorded_at": interval["end_at"], "execution_result": {"external_cash_flow_interval": interval}}

        first = self._interval("2026-09-07T20:00:00Z", "2026-09-08T20:00:00Z", 110, 10)
        conflict = dict(first, end_equity_usdt="1000")
        rows = [
            row(first), row(conflict),
            row(self._interval("2026-09-08T20:00:00Z", "2026-09-09T20:00:00Z", 111)),
            row(self._interval("2026-09-09T20:00:00Z", "2026-09-10T20:00:00Z", 112)),
        ]
        series = live_run_records_to_return_series(rows)
        self.assertEqual(list(series.index), [pd.Timestamp("2026-09-10")])
        self.assertAlmostEqual(float(series.iloc[0]), 112 / 111 - 1)

    def test_interval_same_end_different_start_invalidates_that_day(self) -> None:
        def row(interval):
            return {"recorded_at": interval["end_at"], "execution_result": {"external_cash_flow_interval": interval}}

        rows = [
            row(self._interval("2026-09-07T20:00:00Z", "2026-09-08T20:00:00Z", 110, 10)),
            row(self._interval("2026-09-07T21:00:00Z", "2026-09-08T20:00:00Z", 1000)),
            row(self._interval("2026-09-08T20:00:00Z", "2026-09-09T20:00:00Z", 111)),
            row(self._interval("2026-09-09T20:00:00Z", "2026-09-10T20:00:00Z", 112)),
        ]
        series = live_run_records_to_return_series(rows)
        self.assertEqual(list(series.index), [pd.Timestamp("2026-09-10")])
        self.assertAlmostEqual(float(series.iloc[0]), 112 / 111 - 1)

    def test_extract_equity_from_nested_execution_result(self) -> None:
        value = extract_equity_value(
            {
                "execution_result": {
                    "portfolio": {"total_strategy_equity": 1_250_000.0},
                }
            }
        )
        self.assertEqual(value, 1_250_000.0)

    def test_live_run_records_to_return_series(self) -> None:
        series = live_run_records_to_return_series(
            [
                {"recorded_at": "2026-07-07T10:00:00+00:00", "total_equity": 100.0},
                {"recorded_at": "2026-07-08T10:00:00+00:00", "total_equity": 101.0},
            ]
        )
        self.assertEqual(len(series), 1)
        self.assertAlmostEqual(float(series.iloc[0]), 0.01)

    def test_external_cash_flow_extraction_is_signed_and_does_not_use_cash_balances(self) -> None:
        self.assertEqual(
            extract_external_cash_flow(
                {"execution_result": {"external_cash_flow": -50.0, "cash_balance": 500.0}}
            ),
            -50.0,
        )
        self.assertEqual(extract_external_cash_flow({"cash_balance": 500.0}), 0.0)
        self.assertIsNone(extract_external_cash_flow({"net_external_cash_flow": "invalid"}))

    def test_cash_flow_adjusted_return_is_invariant_to_pure_deposits_and_withdrawals(self) -> None:
        self.assertAlmostEqual(
            cash_flow_adjusted_return(100.0, 200.0, net_external_cash_flow=100.0) or 0.0,
            0.0,
        )
        self.assertAlmostEqual(
            cash_flow_adjusted_return(200.0, 100.0, net_external_cash_flow=-100.0) or 0.0,
            0.0,
        )
        self.assertAlmostEqual(
            cash_flow_adjusted_return(100.0, 210.0, net_external_cash_flow=100.0) or 0.0,
            0.10,
        )
        self.assertIsNone(cash_flow_adjusted_return(0.0, 100.0, net_external_cash_flow=100.0))

    def test_live_returns_aggregate_same_day_cash_flows_before_adjustment(self) -> None:
        series = live_run_records_to_return_series(
            [
                {"recorded_at": "2026-07-07T10:00:00+00:00", "total_equity": 100.0},
                {
                    "recorded_at": "2026-07-08T09:00:00+00:00",
                    "total_equity": 150.0,
                    "external_cash_flow": 50.0,
                },
                {
                    "recorded_at": "2026-07-08T16:00:00+00:00",
                    "total_equity": 200.0,
                    "external_cash_flow": 50.0,
                },
                {
                    "recorded_at": "2026-07-09T10:00:00+00:00",
                    "total_equity": 220.0,
                },
            ]
        )

        self.assertEqual(len(series), 2)
        self.assertAlmostEqual(float(series.iloc[0]), 0.0)
        self.assertAlmostEqual(float(series.iloc[1]), 0.10)

    def test_live_returns_restart_after_invalid_cash_flow_gap(self) -> None:
        for invalid_flow in ("invalid", float("nan")):
            with self.subTest(invalid_flow=invalid_flow):
                series = live_run_records_to_return_series(
                    [
                        {
                            "recorded_at": "2026-09-07T20:00:00Z",
                            "total_equity": 100.0,
                            "external_cash_flow": 0.0,
                        },
                        {
                            "recorded_at": "2026-09-08T20:00:00Z",
                            "total_equity": 200.0,
                            "external_cash_flow": invalid_flow,
                        },
                        {
                            "recorded_at": "2026-09-09T20:00:00Z",
                            "total_equity": 200.0,
                            "external_cash_flow": 0.0,
                        },
                        {
                            "recorded_at": "2026-09-10T20:00:00Z",
                            "total_equity": 202.0,
                            "external_cash_flow": 0.0,
                        },
                    ]
                )

                self.assertEqual(list(series.index), [pd.Timestamp("2026-09-10")])
                self.assertAlmostEqual(float(series.iloc[0]), 0.01)

    def test_same_day_invalid_cash_flow_discards_the_whole_daily_observation(self) -> None:
        series = live_run_records_to_return_series(
            [
                {
                    "recorded_at": "2026-09-06T20:00:00Z",
                    "total_equity": 99.0,
                    "external_cash_flow": 0.0,
                },
                {
                    "recorded_at": "2026-09-07T20:00:00Z",
                    "total_equity": 100.0,
                    "external_cash_flow": 0.0,
                },
                {
                    "recorded_at": "2026-09-08T09:00:00Z",
                    "total_equity": 200.0,
                    "external_cash_flow": 100.0,
                },
                {
                    "recorded_at": "2026-09-08T20:00:00Z",
                    "total_equity": 200.0,
                    "external_cash_flow": "invalid",
                },
                {
                    "recorded_at": "2026-09-09T20:00:00Z",
                    "total_equity": 200.0,
                    "external_cash_flow": 0.0,
                },
                {
                    "recorded_at": "2026-09-10T20:00:00Z",
                    "total_equity": 202.0,
                    "external_cash_flow": 0.0,
                },
            ]
        )

        self.assertEqual(list(series.index), [pd.Timestamp("2026-09-10")])
        self.assertAlmostEqual(float(series.iloc[0]), 0.01)

    def test_count_consecutive_losses_trailing_only(self) -> None:
        self.assertEqual(count_consecutive_losses(pd.Series([-0.01, 0.02, -0.01, -0.03])), 2)
        self.assertEqual(count_consecutive_losses(pd.Series([-0.01, -0.02, 0.0])), 0)
        self.assertEqual(count_consecutive_losses(pd.Series(dtype=float)), 0)

    def test_consecutive_losses_from_live_run_records(self) -> None:
        streak = consecutive_losses_from_live_run_records(
            [
                {"recorded_at": "2026-07-01T10:00:00+00:00", "total_equity": 100.0},
                {"recorded_at": "2026-07-02T10:00:00+00:00", "total_equity": 99.0},
                {"recorded_at": "2026-07-03T10:00:00+00:00", "total_equity": 97.0},
                {"recorded_at": "2026-07-04T10:00:00+00:00", "total_equity": 98.0},
                {"recorded_at": "2026-07-05T10:00:00+00:00", "total_equity": 96.0},
                {"recorded_at": "2026-07-06T10:00:00+00:00", "total_equity": 95.0},
            ]
        )
        # returns: -1%, -2.02%, +1.03%, -2.04%, -1.04% → trailing streak 2
        self.assertEqual(streak, 2)

    def test_resolve_consecutive_losses_from_store(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = PerformanceStore(local_root=Path(tmp))
            for day, equity in (
                ("2026-07-01T10:00:00+00:00", 100.0),
                ("2026-07-02T10:00:00+00:00", 98.0),
                ("2026-07-03T10:00:00+00:00", 96.0),
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
                )
            self.assertEqual(
                resolve_consecutive_losses(
                    domain="us_equity",
                    strategy_profile="global_etf_rotation",
                    store=store,
                ),
                2,
            )
            self.assertIsNone(
                resolve_consecutive_losses(
                    domain="us_equity",
                    strategy_profile="missing_profile",
                    store=store,
                )
            )

    def test_stamp_consecutive_losses_on_snapshot(self) -> None:
        from datetime import datetime, timezone

        from quant_platform_kit.common.models import PortfolioSnapshot

        with tempfile.TemporaryDirectory() as tmp:
            store = PerformanceStore(local_root=Path(tmp))
            for day, equity in (
                ("2026-07-01T10:00:00+00:00", 100.0),
                ("2026-07-02T10:00:00+00:00", 98.0),
                ("2026-07-03T10:00:00+00:00", 96.0),
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
                )
            snapshot = PortfolioSnapshot(
                as_of=datetime.now(timezone.utc),
                total_equity=96.0,
                positions=(),
                metadata={},
            )
            stamped = stamp_consecutive_losses_on_snapshot(
                snapshot,
                strategy_profile="global_etf_rotation",
                domain="us_equity",
                store=store,
            )
            self.assertIsNot(stamped, snapshot)
            self.assertEqual(stamped.metadata["consecutive_losses"], 2)

            preserved = stamp_consecutive_losses_on_snapshot(
                stamped,
                strategy_profile="global_etf_rotation",
                domain="us_equity",
                store=store,
            )
            self.assertIs(preserved, stamped)


class ReturnCollectorLiveRunTests(unittest.TestCase):
    def test_interval_survives_recorder_store_and_return_collector(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = PerformanceStore(local_root=Path(tmp))
            monitor = PerformanceMonitor(store=store)
            stream_id = "binance-interval"
            monitor.record_execution(
                "crypto_live_pool_rotation",
                {
                    "platform": "binance",
                    "status": "ok",
                    "external_cash_flow_interval": LiveEquityTests._interval(
                        "2026-09-07T00:00:00Z", "2026-09-08T00:00:00Z", 200, 100
                    ),
                },
                domain="crypto",
                stream_id=stream_id,
            )
            monitor.record_execution(
                "crypto_live_pool_rotation",
                {
                    "platform": "binance",
                    "status": "ok",
                    "external_cash_flow_interval": LiveEquityTests._interval(
                        "2026-09-08T00:00:00Z", "2026-09-09T00:00:00Z", 202
                    ),
                },
                domain="crypto",
                stream_id=stream_id,
            )

            series = ReturnCollector(store=store).collect_from_live_runs(
                "crypto", stream_id=stream_id
            )["crypto_live_pool_rotation"]
            self.assertEqual(list(series.index), [pd.Timestamp("2026-09-09")])
            self.assertAlmostEqual(float(series.iloc[0]), 0.01)

    def test_stream_identity_prefers_explicit_value_and_then_platform(self) -> None:
        self.assertEqual(
            resolve_lifecycle_stream_id("account-a", execution_result={"platform": "schwab"}),
            "account-a",
        )
        self.assertEqual(
            resolve_lifecycle_stream_id(execution_result={"platform": "schwab", "account_scope": "u1"}),
            "schwab:u1",
        )

    def test_collect_merges_live_run_returns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = PerformanceStore(local_root=Path(tmp))
            monitor = PerformanceMonitor(store=store)
            monitor.record_execution(
                "global_etf_rotation",
                {"platform": "schwab", "total_equity": 100.0},
                domain="us_equity",
            )
            first_record = store.list_live_run_records("us_equity", strategy_profile="global_etf_rotation")[0]
            second_recorded_at = (
                pd.Timestamp(first_record["recorded_at"]).normalize() + pd.Timedelta(days=1, hours=10)
            ).isoformat()
            # Second record on a later day in the same account-safe stream.
            store.save_live_run_record(
                "global_etf_rotation",
                "us_equity",
                {
                    "strategy_profile": "global_etf_rotation",
                    "domain": "us_equity",
                    "recorded_at": second_recorded_at,
                    "record_kind": "execution",
                    "execution_result": {"total_equity": 102.0},
                },
                stream_id="schwab",
            )

            collector = ReturnCollector(store=store, projects_root=Path(tmp))
            returns = collector.collect_from_live_runs("us_equity")
            self.assertIn("global_etf_rotation", returns)
            self.assertEqual(len(returns["global_etf_rotation"]), 1)
            self.assertAlmostEqual(float(returns["global_etf_rotation"].iloc[0]), 0.02)

            merged = collector.collect("us_equity")
            self.assertIn("global_etf_rotation", merged)
            self.assertIsInstance(merged["global_etf_rotation"], pd.Series)

    def test_collect_does_not_compound_across_invalid_cash_flow_gap(self) -> None:
        rows = [
            {
                "recorded_at": "2026-09-07T20:00:00Z",
                "total_equity": 100.0,
                "external_cash_flow": 0.0,
            },
            {
                "recorded_at": "2026-09-08T20:00:00Z",
                "total_equity": 200.0,
                "external_cash_flow": "invalid",
            },
            {
                "recorded_at": "2026-09-09T20:00:00Z",
                "total_equity": 200.0,
                "external_cash_flow": 0.0,
            },
            {
                "recorded_at": "2026-09-10T20:00:00Z",
                "total_equity": 202.0,
                "external_cash_flow": 0.0,
            },
        ]
        for row in rows:
            row.update(strategy_profile="audit_case", lifecycle_stream_id="offline-account")

        class Store:
            def list_live_run_records(self, domain: str) -> list[dict[str, object]]:
                self.domain = domain
                return rows

        series = ReturnCollector(store=Store()).collect_from_live_runs(
            "us_equity", stream_id="offline-account"
        )["audit_case"]

        self.assertEqual(list(series.index), [pd.Timestamp("2026-09-10")])
        self.assertAlmostEqual(float(series.iloc[0]), 0.01)
        self.assertAlmostEqual(compute_window_metrics(series).total_return, 0.01)

    def test_collect_refuses_to_merge_multiple_account_streams(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = PerformanceStore(local_root=Path(tmp))
            for stream_id, first_equity, second_equity in (
                ("account-a", 100.0, 102.0),
                ("account-b", 250.0, 230.0),
            ):
                for day, equity in (("2026-07-01T10:00:00+00:00", first_equity), ("2026-07-02T10:00:00+00:00", second_equity)):
                    store.save_live_run_record(
                        "soxl_soxx_trend_income",
                        "us_equity",
                        {
                            "strategy_profile": "soxl_soxx_trend_income",
                            "domain": "us_equity",
                            "recorded_at": day,
                            "record_kind": "execution",
                            "execution_result": {"total_equity": equity},
                        },
                        stream_id=stream_id,
                    )

            collector = ReturnCollector(store=store, projects_root=Path(tmp))
            self.assertNotIn("soxl_soxx_trend_income", collector.collect_from_live_runs("us_equity"))

            account_a = collector.collect_from_live_runs("us_equity", stream_id="account-a")
            self.assertAlmostEqual(float(account_a["soxl_soxx_trend_income"].iloc[0]), 0.02)


if __name__ == "__main__":
    unittest.main()
