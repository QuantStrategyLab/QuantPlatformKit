from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path

import pandas as pd

from quant_platform_kit.strategy_lifecycle.contracts import ReturnObservationContract
from quant_platform_kit.strategy_lifecycle.live_equity import (
    cash_flow_adjusted_return,
    consecutive_losses_from_live_run_records,
    count_consecutive_losses,
    extract_equity_value,
    extract_external_cash_flow,
    live_interval_records_to_return_series,
    live_run_records_to_return_series,
    live_run_records_to_return_series_result,
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
                {"recorded_at": "2026-07-07T10:00:00+00:00", "total_equity": 100.0, "external_cash_flow": 0.0},
                {"recorded_at": "2026-07-08T10:00:00+00:00", "total_equity": 101.0, "external_cash_flow": 0.0},
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
        self.assertIsNone(extract_external_cash_flow({"cash_balance": 500.0}))
        self.assertIsNone(extract_external_cash_flow({"total_equity": 200.0}))
        self.assertEqual(extract_external_cash_flow({"external_cash_flow": 0}), 0.0)
        self.assertEqual(extract_external_cash_flow({"net_external_cash_flow": "0.0"}), 0.0)
        self.assertIsNone(extract_external_cash_flow({"net_external_cash_flow": "invalid"}))

    def test_math_helper_default_remains_explicit_zero_flow_assumption(self) -> None:
        self.assertAlmostEqual(cash_flow_adjusted_return(100.0, 200.0), 1.0)

    def test_missing_cash_flow_from_100_to_200_is_not_a_trusted_return(self) -> None:
        result = live_run_records_to_return_series_result(
            [
                {"recorded_at": "2026-09-08T20:00:00Z", "total_equity": 100.0},
                {"recorded_at": "2026-09-09T20:00:00Z", "total_equity": 200.0},
            ]
        )
        self.assertEqual(result.status, "insufficient_observations")
        self.assertNotEqual(result.status, "ok")
        self.assertTrue(result.series.empty)

    def test_confirmed_zero_flow_reports_the_equity_change(self) -> None:
        result = live_run_records_to_return_series_result(
            [
                {
                    "recorded_at": "2026-09-08T20:00:00Z",
                    "total_equity": 100.0,
                    "external_cash_flow": 0.0,
                },
                {
                    "recorded_at": "2026-09-09T20:00:00Z",
                    "total_equity": 200.0,
                    "external_cash_flow": 0.0,
                },
            ]
        )
        self.assertEqual(result.status, "ok")
        self.assertAlmostEqual(float(result.series.iloc[0]), 1.0)

    def test_live_deposit_and_withdrawal_are_not_profit_or_loss(self) -> None:
        deposit = live_run_records_to_return_series_result(
            [
                {
                    "recorded_at": "2026-09-08T20:00:00Z",
                    "total_equity": 100.0,
                    "external_cash_flow": 0.0,
                },
                {
                    "recorded_at": "2026-09-09T20:00:00Z",
                    "total_equity": 200.0,
                    "external_cash_flow": 100.0,
                },
            ]
        )
        withdrawal = live_run_records_to_return_series_result(
            [
                {
                    "recorded_at": "2026-09-08T20:00:00Z",
                    "total_equity": 200.0,
                    "external_cash_flow": 0.0,
                },
                {
                    "recorded_at": "2026-09-09T20:00:00Z",
                    "total_equity": 100.0,
                    "external_cash_flow": -100.0,
                },
            ]
        )
        self.assertEqual(deposit.status, "ok")
        self.assertAlmostEqual(float(deposit.series.iloc[0]), 0.0)
        self.assertEqual(withdrawal.status, "ok")
        self.assertAlmostEqual(float(withdrawal.series.iloc[0]), 0.0)

    def test_missing_flow_positions_do_not_bridge_or_look_complete(self) -> None:
        def row(day: str, equity: float, flow: float | None = 0.0, omit: bool = False) -> dict:
            payload: dict = {"recorded_at": day, "total_equity": equity}
            if not omit:
                payload["external_cash_flow"] = flow
            return payload

        first_missing = live_run_records_to_return_series_result(
            [
                row("2026-09-08T20:00:00Z", 100.0, omit=True),
                row("2026-09-09T20:00:00Z", 110.0, 0.0),
                row("2026-09-10T20:00:00Z", 121.0, 0.0),
            ]
        )
        self.assertEqual(first_missing.status, "truncated_after_invalid_cash_flow")
        self.assertEqual(list(first_missing.series.index), [pd.Timestamp("2026-09-10")])
        self.assertAlmostEqual(float(first_missing.series.iloc[0]), 121.0 / 110.0 - 1.0)

        mixed = live_run_records_to_return_series_result(
            [
                row("2026-09-07T20:00:00Z", 100.0, 0.0),
                row("2026-09-08T09:00:00Z", 150.0, 50.0),
                row("2026-09-08T20:00:00Z", 200.0, omit=True),
                row("2026-09-09T20:00:00Z", 200.0, 0.0),
                row("2026-09-10T20:00:00Z", 202.0, 0.0),
            ]
        )
        self.assertEqual(mixed.status, "truncated_after_invalid_cash_flow")
        self.assertEqual(list(mixed.series.index), [pd.Timestamp("2026-09-10")])
        self.assertAlmostEqual(float(mixed.series.iloc[0]), 0.01)

        middle = live_run_records_to_return_series_result(
            [
                row("2026-09-07T20:00:00Z", 100.0, 0.0),
                row("2026-09-08T20:00:00Z", 200.0, omit=True),
                row("2026-09-09T20:00:00Z", 200.0, 0.0),
                row("2026-09-10T20:00:00Z", 202.0, 0.0),
            ]
        )
        self.assertEqual(middle.status, "truncated_after_invalid_cash_flow")
        self.assertEqual(list(middle.series.index), [pd.Timestamp("2026-09-10")])
        self.assertAlmostEqual(float(middle.series.iloc[0]), 0.01)

        trailing = live_run_records_to_return_series_result(
            [
                row("2026-09-08T20:00:00Z", 100.0, 0.0),
                row("2026-09-09T20:00:00Z", 110.0, 0.0),
                row("2026-09-10T20:00:00Z", 200.0, omit=True),
            ]
        )
        self.assertEqual(trailing.status, "insufficient_observations")
        self.assertTrue(trailing.series.empty)

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
                {"recorded_at": "2026-07-07T10:00:00+00:00", "total_equity": 100.0, "external_cash_flow": 0.0},
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
                    "external_cash_flow": 0.0,
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
                {"recorded_at": "2026-07-01T10:00:00+00:00", "total_equity": 100.0, "external_cash_flow": 0.0},
                {"recorded_at": "2026-07-02T10:00:00+00:00", "total_equity": 99.0, "external_cash_flow": 0.0},
                {"recorded_at": "2026-07-03T10:00:00+00:00", "total_equity": 97.0, "external_cash_flow": 0.0},
                {"recorded_at": "2026-07-04T10:00:00+00:00", "total_equity": 98.0, "external_cash_flow": 0.0},
                {"recorded_at": "2026-07-05T10:00:00+00:00", "total_equity": 96.0, "external_cash_flow": 0.0},
                {"recorded_at": "2026-07-06T10:00:00+00:00", "total_equity": 95.0, "external_cash_flow": 0.0},
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
                ("2026-07-06T10:00:00+00:00", 96.0),
            ):
                store.save_live_run_record(
                    "global_etf_rotation",
                    "us_equity",
                    {
                        "strategy_profile": "global_etf_rotation",
                        "domain": "us_equity",
                        "recorded_at": day,
                        "record_kind": "execution",
                        "execution_result": {"total_equity": equity, "external_cash_flow": 0.0},
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
                ("2026-07-06T10:00:00+00:00", 96.0),
            ):
                store.save_live_run_record(
                    "global_etf_rotation",
                    "us_equity",
                    {
                        "strategy_profile": "global_etf_rotation",
                        "domain": "us_equity",
                        "recorded_at": day,
                        "record_kind": "execution",
                        "execution_result": {"total_equity": equity, "external_cash_flow": 0.0},
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
    def test_collect_rejects_mixed_valid_and_invalid_return_matrices(self) -> None:
        """A bad matrix in the same domain must not silently leave only valid columns."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            alpha_dir = root / "alpha"
            beta_dir = root / "beta"
            alpha_dir.mkdir()
            beta_dir.mkdir()
            pd.DataFrame(
                {"as_of": ["2026-09-08", "2026-09-09"], "alpha": [0.01, -0.02]}
            ).to_csv(alpha_dir / "portfolio_and_tracker_returns.csv", index=False)
            pd.DataFrame(
                {"as_of": ["2026-09-08", "2026-09-09"], "beta": [0.01, float("inf")]}
            ).to_csv(beta_dir / "portfolio_and_tracker_returns.csv", index=False)

            store = PerformanceStore(local_root=root / "store")
            collector = ReturnCollector(
                artifact_roots={"us_equity": root},
                projects_root=root,
                store=store,
            )

            with self.assertRaisesRegex(ValueError, r"invalid return matrix") as ctx:
                collector.collect("us_equity")
            self.assertIsInstance(ctx.exception.__cause__, ValueError)
            self.assertRegex(str(ctx.exception.__cause__), r"infinite|NaN")

    def test_collect_benchmark_rejects_invalid_return_matrix(self) -> None:
        """Valid-before-invalid sort order must not early-return past a bad matrix."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # Sorted discovery: a_valid before z_invalid.
            a_valid = root / "a_valid"
            z_invalid = root / "z_invalid"
            a_valid.mkdir()
            z_invalid.mkdir()
            pd.DataFrame(
                {"as_of": ["2026-09-08", "2026-09-09"], "SPY": [0.01, -0.02]}
            ).to_csv(a_valid / "portfolio_and_tracker_returns.csv", index=False)
            pd.DataFrame(
                {"as_of": ["2026-09-08", "2026-09-09"], "SPY": [0.01, float("inf")]}
            ).to_csv(z_invalid / "portfolio_and_tracker_returns.csv", index=False)

            collector = ReturnCollector(
                artifact_roots={"us_equity": root},
                projects_root=root,
                store=PerformanceStore(local_root=root / "store"),
            )
            discovered = collector.discover_return_matrices("us_equity")
            self.assertEqual(
                [p.parent.name for p in discovered],
                ["a_valid", "z_invalid"],
            )
            with self.assertRaisesRegex(ValueError, r"invalid return matrix") as ctx:
                collector.collect_benchmark("us_equity", "SPY")
            self.assertIsInstance(ctx.exception.__cause__, ValueError)
            self.assertRegex(str(ctx.exception.__cause__), r"infinite|NaN")
            self.assertIn("z_invalid", str(ctx.exception))

    def test_collect_benchmark_returns_none_when_symbol_absent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pd.DataFrame(
                {"as_of": ["2026-09-08", "2026-09-09"], "alpha": [0.01, -0.02]}
            ).to_csv(root / "portfolio_and_tracker_returns.csv", index=False)
            collector = ReturnCollector(
                artifact_roots={"us_equity": root},
                projects_root=root,
                store=PerformanceStore(local_root=root / "store"),
            )
            self.assertIsNone(collector.collect_benchmark("us_equity", "SPY"))

    def test_collect_preserves_single_valid_return_matrix(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pd.DataFrame(
                {"as_of": ["2026-09-08", "2026-09-09"], "alpha": [0.01, -0.02]}
            ).to_csv(root / "portfolio_and_tracker_returns.csv", index=False)
            collector = ReturnCollector(
                artifact_roots={"us_equity": root},
                projects_root=root,
                store=PerformanceStore(local_root=root / "store"),
            )
            series_map = collector.collect("us_equity")
            self.assertEqual(list(series_map), ["alpha"])
            self.assertEqual(len(series_map["alpha"]), 2)
            self.assertAlmostEqual(float(series_map["alpha"].iloc[0]), 0.01)

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
            for day, equity in (
                ("2026-09-14T10:00:00+00:00", 100.0),
                ("2026-09-15T10:00:00+00:00", 102.0),
            ):
                store.save_live_run_record(
                    "global_etf_rotation",
                    "us_equity",
                    {
                        "strategy_profile": "global_etf_rotation",
                        "domain": "us_equity",
                        "recorded_at": day,
                        "record_kind": "execution",
                        "execution_result": {"total_equity": equity, "external_cash_flow": 0.0},
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

        with tempfile.TemporaryDirectory() as tmp:
            collector = ReturnCollector(store=Store(), projects_root=Path(tmp))
            outcome = collector.collect_from_live_runs_result(
                "us_equity",
                stream_id="offline-account",
            )
            series = outcome.series_by_profile["audit_case"]
            self.assertIn(
                "truncated_after_invalid_cash_flow",
                outcome.incomplete_by_profile["audit_case"],
            )
            collected = collector.collect(
                "us_equity",
                live_stream_id="offline-account",
            )["audit_case"]
            self.assertEqual(
                collected.attrs["observation_status"],
                "truncated_after_invalid_cash_flow",
            )

            self.assertEqual(list(series.index), [pd.Timestamp("2026-09-10")])
            self.assertAlmostEqual(float(series.iloc[0]), 0.01)
            self.assertAlmostEqual(compute_window_metrics(series).total_return, 0.01)

    def test_collect_missing_cash_flow_is_not_ok(self) -> None:
        rows = [
            {
                "recorded_at": "2026-09-08T20:00:00Z",
                "total_equity": 100.0,
                "strategy_profile": "missing_flow",
                "lifecycle_stream_id": "offline-account",
            },
            {
                "recorded_at": "2026-09-09T20:00:00Z",
                "total_equity": 200.0,
                "strategy_profile": "missing_flow",
                "lifecycle_stream_id": "offline-account",
            },
        ]

        class Store:
            def list_live_run_records(self, domain: str) -> list[dict[str, object]]:
                return rows

        with tempfile.TemporaryDirectory() as tmp:
            outcome = ReturnCollector(store=Store(), projects_root=Path(tmp)).collect_from_live_runs_result(
                "us_equity",
                stream_id="offline-account",
            )
        self.assertNotIn("missing_flow", outcome.series_by_profile)
        self.assertIn("missing_flow", outcome.incomplete_by_profile)
        self.assertNotIn("ok", outcome.incomplete_by_profile["missing_flow"])
        self.assertIn("insufficient_observations", outcome.incomplete_by_profile["missing_flow"])
        self.assertIn("invalid_cash_flow", outcome.incomplete_by_profile["missing_flow"])

    def test_csv_cannot_bridge_or_relabel_unknown_live_cash_flow(self) -> None:
        bridge = "bridge_case"
        empty = "empty_case"
        stream = "offline-account"
        rows = [
            {
                "recorded_at": "2026-09-07T20:00:00Z",
                "total_equity": 100.0,
                "external_cash_flow": 0.0,
                "strategy_profile": bridge,
                "lifecycle_stream_id": stream,
            },
            {
                "recorded_at": "2026-09-08T20:00:00Z",
                "total_equity": 200.0,
                "strategy_profile": bridge,
                "lifecycle_stream_id": stream,
            },
            {
                "recorded_at": "2026-09-09T20:00:00Z",
                "total_equity": 200.0,
                "external_cash_flow": 0.0,
                "strategy_profile": bridge,
                "lifecycle_stream_id": stream,
            },
            {
                "recorded_at": "2026-09-10T20:00:00Z",
                "total_equity": 202.0,
                "external_cash_flow": 0.0,
                "strategy_profile": bridge,
                "lifecycle_stream_id": stream,
            },
            {
                "recorded_at": "2026-09-08T20:00:00Z",
                "total_equity": 100.0,
                "strategy_profile": empty,
                "lifecycle_stream_id": stream,
            },
            {
                "recorded_at": "2026-09-09T20:00:00Z",
                "total_equity": 200.0,
                "strategy_profile": empty,
                "lifecycle_stream_id": stream,
            },
        ]

        class Store:
            def list_live_run_records(self, domain: str) -> list[dict[str, object]]:
                return rows

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pd.DataFrame(
                {"as_of": ["2026-09-07"], bridge: [0.01], empty: [0.01]}
            ).to_csv(root / "portfolio_and_tracker_returns.csv", index=False)
            collector = ReturnCollector(
                artifact_roots={"crypto": root},
                projects_root=root,
                store=Store(),
            )
            outcome = collector.collect_from_live_runs_result("crypto", stream_id=stream)
            collected = collector.collect("crypto", live_stream_id=stream)

        self.assertIn("truncated_after_invalid_cash_flow", outcome.incomplete_by_profile[bridge])
        self.assertEqual(list(outcome.series_by_profile[bridge].index), [pd.Timestamp("2026-09-10")])
        self.assertNotIn(empty, outcome.series_by_profile)
        self.assertIn("invalid_cash_flow", outcome.incomplete_by_profile[empty])

        bridge_series = collected[bridge]
        self.assertEqual(list(bridge_series.index), [pd.Timestamp("2026-09-10")])
        self.assertNotIn(pd.Timestamp("2026-09-07"), list(bridge_series.index))
        self.assertAlmostEqual(float(bridge_series.iloc[0]), 202.0 / 200.0 - 1.0)
        self.assertEqual(bridge_series.attrs["observation_status"], "truncated_after_invalid_cash_flow")

        empty_series = collected[empty]
        self.assertEqual(list(empty_series.index), [pd.Timestamp("2026-09-07")])
        self.assertAlmostEqual(float(empty_series.iloc[0]), 0.01)
        self.assertEqual(empty_series.attrs["observation_status"], "truncated_after_invalid_cash_flow")
        self.assertNotEqual(empty_series.attrs["observation_status"], "ok")

    def test_unknown_cash_flow_survives_gap_and_calendar_rejection(self) -> None:
        gap_profile = "gap_after_unknown"
        calendar_profile = "calendar_after_unknown"
        stream = "offline-account"

        def live_row(day: str, equity: float, profile: str, flow: float | None) -> dict[str, object]:
            row: dict[str, object] = {
                "recorded_at": day,
                "total_equity": equity,
                "strategy_profile": profile,
                "lifecycle_stream_id": stream,
            }
            if flow is not None:
                row["external_cash_flow"] = flow
            return row

        rows = [
            live_row("2026-09-07T20:00:00Z", 100.0, gap_profile, None),
            live_row("2026-09-08T20:00:00Z", 200.0, gap_profile, 0.0),
            live_row("2026-09-10T20:00:00Z", 202.0, gap_profile, 0.0),
            live_row("2025-12-29T20:00:00Z", 100.0, calendar_profile, None),
            live_row("2025-12-30T20:00:00Z", 200.0, calendar_profile, 0.0),
            live_row("2025-12-31T20:00:00Z", 202.0, calendar_profile, 0.0),
        ]

        class SplitStore:
            def list_live_run_records(self, domain: str) -> list[dict[str, object]]:
                profile = gap_profile if domain == "crypto" else calendar_profile
                return [row for row in rows if row["strategy_profile"] == profile]

        gap_result = live_run_records_to_return_series_result(
            [row for row in rows if row["strategy_profile"] == gap_profile],
            domain="crypto",
        )
        self.assertEqual(gap_result.status, "incomplete_observation_gap")
        self.assertIn("no_contiguous_session_pair", gap_result.detail)
        self.assertIn("invalid_cash_flow", gap_result.detail)
        self.assertTrue(gap_result.series.empty)

        calendar_result = live_run_records_to_return_series_result(
            [row for row in rows if row["strategy_profile"] == calendar_profile],
            domain="us_equity",
        )
        self.assertEqual(calendar_result.status, "incomplete_calendar")
        self.assertIn("coverage_exceeded", calendar_result.detail)
        self.assertIn("invalid_cash_flow", calendar_result.detail)
        self.assertTrue(calendar_result.series.empty)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            crypto_root = root / "crypto"
            us_root = root / "us"
            crypto_root.mkdir()
            us_root.mkdir()
            pd.DataFrame({"as_of": ["2026-09-06"], gap_profile: [0.01]}).to_csv(
                crypto_root / "portfolio_and_tracker_returns.csv", index=False
            )
            pd.DataFrame({"as_of": ["2025-12-28"], calendar_profile: [0.01]}).to_csv(
                us_root / "portfolio_and_tracker_returns.csv", index=False
            )
            collector = ReturnCollector(
                artifact_roots={"crypto": crypto_root, "us_equity": us_root},
                projects_root=root,
                store=SplitStore(),
            )
            crypto_outcome = collector.collect_from_live_runs_result("crypto", stream_id=stream)
            us_outcome = collector.collect_from_live_runs_result("us_equity", stream_id=stream)
            crypto_collected = collector.collect("crypto", live_stream_id=stream)
            us_collected = collector.collect("us_equity", live_stream_id=stream)

        self.assertIn("no_contiguous_session_pair", crypto_outcome.incomplete_by_profile[gap_profile])
        self.assertIn("invalid_cash_flow", crypto_outcome.incomplete_by_profile[gap_profile])
        self.assertNotIn(gap_profile, crypto_outcome.series_by_profile)
        gap_series = crypto_collected[gap_profile]
        self.assertEqual(list(gap_series.index), [pd.Timestamp("2026-09-06")])
        self.assertEqual(gap_series.attrs["observation_status"], "truncated_after_invalid_cash_flow")

        self.assertIn("coverage_exceeded", us_outcome.incomplete_by_profile[calendar_profile])
        self.assertIn("invalid_cash_flow", us_outcome.incomplete_by_profile[calendar_profile])
        self.assertNotIn(calendar_profile, us_outcome.series_by_profile)
        calendar_series = us_collected[calendar_profile]
        self.assertEqual(list(calendar_series.index), [pd.Timestamp("2025-12-28")])
        self.assertEqual(
            calendar_series.attrs["observation_status"],
            "truncated_after_invalid_cash_flow",
        )

    def test_missing_us_trading_day_does_not_become_single_day_return(self) -> None:
        result = live_run_records_to_return_series_result(
            [
                {"recorded_at": "2026-09-14T20:00:00Z", "total_equity": 100.0, "external_cash_flow": 0.0},
                {"recorded_at": "2026-09-16T20:00:00Z", "total_equity": 102.0, "external_cash_flow": 0.0},
            ],
            domain="us_equity",
        )
        self.assertEqual(result.status, "incomplete_observation_gap")
        self.assertTrue(result.series.empty)
        metrics = compute_window_metrics(result.series, window_days=1, window_label="gap")
        self.assertEqual(metrics.observation_count, 0)

    def test_published_2026_calendars_weekend_holiday_halfday_and_bounds(self) -> None:
        weekend = live_run_records_to_return_series_result(
            [
                {"recorded_at": "2026-09-11T20:00:00Z", "total_equity": 100.0, "external_cash_flow": 0.0},  # Fri
                {"recorded_at": "2026-09-14T20:00:00Z", "total_equity": 101.0, "external_cash_flow": 0.0},  # Mon
            ],
            domain="us_equity",
        )
        self.assertEqual(weekend.status, "ok")
        self.assertAlmostEqual(float(weekend.series.iloc[0]), 0.01)

        # Labor Day 2026-09-07 is a published full-day closure, not a gap.
        labor = live_run_records_to_return_series_result(
            [
                {"recorded_at": "2026-09-04T20:00:00Z", "total_equity": 100.0, "external_cash_flow": 0.0},
                {"recorded_at": "2026-09-08T20:00:00Z", "total_equity": 102.0, "external_cash_flow": 0.0},
            ],
            domain="us_equity",
        )
        self.assertEqual(labor.status, "ok")
        self.assertAlmostEqual(float(labor.series.iloc[0]), 0.02)

        # Half-day 2026-11-27 remains an expected session after Thanksgiving.
        half_day_gap = live_run_records_to_return_series_result(
            [
                {"recorded_at": "2026-11-25T20:00:00Z", "total_equity": 100.0, "external_cash_flow": 0.0},
                {"recorded_at": "2026-11-30T20:00:00Z", "total_equity": 101.0, "external_cash_flow": 0.0},
            ],
            domain="us_equity",
        )
        self.assertEqual(half_day_gap.status, "incomplete_observation_gap")
        self.assertTrue(half_day_gap.series.empty)

        half_day_ok = live_run_records_to_return_series_result(
            [
                {"recorded_at": "2026-11-25T20:00:00Z", "total_equity": 100.0, "external_cash_flow": 0.0},
                {"recorded_at": "2026-11-27T20:00:00Z", "total_equity": 101.0, "external_cash_flow": 0.0},
            ],
            domain="us_equity",
        )
        self.assertEqual(half_day_ok.status, "ok")

        # HKEX Lunar New Year full closures; 2026-02-16 half-day still required.
        hk_holiday = live_run_records_to_return_series_result(
            [
                {"recorded_at": "2026-02-16T20:00:00Z", "total_equity": 100.0, "external_cash_flow": 0.0},
                {"recorded_at": "2026-02-20T20:00:00Z", "total_equity": 101.0, "external_cash_flow": 0.0},
            ],
            domain="hk_equity",
        )
        self.assertEqual(hk_holiday.status, "ok")

        out_of_range = live_run_records_to_return_series_result(
            [
                {"recorded_at": "2025-12-30T20:00:00Z", "total_equity": 100.0, "external_cash_flow": 0.0},
                {"recorded_at": "2025-12-31T20:00:00Z", "total_equity": 101.0, "external_cash_flow": 0.0},
            ],
            domain="us_equity",
        )
        self.assertEqual(out_of_range.status, "incomplete_calendar")
        self.assertIn("coverage_exceeded", out_of_range.detail)

        future = live_run_records_to_return_series_result(
            [
                {"recorded_at": "2027-01-04T20:00:00Z", "total_equity": 100.0, "external_cash_flow": 0.0},
                {"recorded_at": "2027-01-05T20:00:00Z", "total_equity": 101.0, "external_cash_flow": 0.0},
            ],
            domain="us_equity",
        )
        self.assertEqual(future.status, "incomplete_calendar")

        synthetic = live_run_records_to_return_series_result(
            [
                {"recorded_at": "2026-09-04T20:00:00Z", "total_equity": 100.0, "external_cash_flow": 0.0},
                {"recorded_at": "2026-09-08T20:00:00Z", "total_equity": 102.0, "external_cash_flow": 0.0},
            ],
            observation_contract=ReturnObservationContract(
                calendar_id="XNYS",
                periods_per_year=252.0,
                domain="us_equity",
                session_holidays=frozenset({"2026-09-07"}),
                holiday_source="synthetic_fixture_only",
                holiday_coverage_start=date(2026, 9, 4),
                holiday_coverage_end=date(2026, 9, 8),
            ),
        )
        self.assertEqual(synthetic.status, "incomplete_calendar")

    def test_crypto_weekend_gap_does_not_bridge_natural_days(self) -> None:
        result = live_run_records_to_return_series_result(
            [
                {"recorded_at": "2026-09-12T20:00:00Z", "total_equity": 100.0, "external_cash_flow": 0.0},  # Sat
                {"recorded_at": "2026-09-14T20:00:00Z", "total_equity": 102.0, "external_cash_flow": 0.0},  # Mon, missing Sun
            ],
            domain="crypto",
        )
        self.assertEqual(result.status, "incomplete_observation_gap")
        self.assertTrue(result.series.empty)

    def test_gap_keeps_only_latest_contiguous_segment(self) -> None:
        result = live_run_records_to_return_series_result(
            [
                {"recorded_at": "2026-09-14T20:00:00Z", "total_equity": 100.0, "external_cash_flow": 0.0},
                {"recorded_at": "2026-09-16T20:00:00Z", "total_equity": 102.0, "external_cash_flow": 0.0},
                {"recorded_at": "2026-09-17T20:00:00Z", "total_equity": 103.0, "external_cash_flow": 0.0},
            ],
            domain="us_equity",
        )
        self.assertEqual(result.status, "truncated_after_observation_gap")
        self.assertEqual(list(result.series.index), [pd.Timestamp("2026-09-17")])
        self.assertAlmostEqual(float(result.series.iloc[0]), 103 / 102 - 1)

    def test_collect_from_live_runs_refuses_us_trading_day_gap(self) -> None:
        rows = [
            {
                "recorded_at": "2026-09-14T20:00:00Z",
                "total_equity": 100.0,
                "external_cash_flow": 0.0,
                "strategy_profile": "gap_case",
                "lifecycle_stream_id": "offline-account",
            },
            {
                "recorded_at": "2026-09-16T20:00:00Z",
                "total_equity": 102.0,
                "external_cash_flow": 0.0,
                "strategy_profile": "gap_case",
                "lifecycle_stream_id": "offline-account",
            },
        ]

        class Store:
            def list_live_run_records(self, domain: str) -> list[dict[str, object]]:
                self.domain = domain
                return rows

        outcome = ReturnCollector(store=Store()).collect_from_live_runs_result(
            "us_equity",
            stream_id="offline-account",
        )
        self.assertNotIn("gap_case", outcome.series_by_profile)
        self.assertIn("gap_case", outcome.incomplete_by_profile)
        self.assertIn("incomplete_observation_gap", outcome.incomplete_by_profile["gap_case"])

    def test_collect_rejects_synthetic_holiday_source_as_real(self) -> None:
        rows = [
            {
                "recorded_at": "2026-09-04T20:00:00Z",
                "total_equity": 100.0,
                "external_cash_flow": 0.0,
                "strategy_profile": "holiday_case",
                "lifecycle_stream_id": "offline-account",
            },
            {
                "recorded_at": "2026-09-08T20:00:00Z",
                "total_equity": 102.0,
                "external_cash_flow": 0.0,
                "strategy_profile": "holiday_case",
                "lifecycle_stream_id": "offline-account",
            },
        ]

        class Store:
            def list_live_run_records(self, domain: str) -> list[dict[str, object]]:
                return rows

        outcome = ReturnCollector(store=Store()).collect_from_live_runs_result(
            "us_equity",
            stream_id="offline-account",
            holiday_source="synthetic_fixture_only",
            holiday_coverage_start=date(2026, 9, 4),
            holiday_coverage_end=date(2026, 9, 8),
            session_holidays=frozenset({"2026-09-07"}),
        )
        self.assertEqual(outcome.series_by_profile, {})
        self.assertIn("incomplete_calendar", outcome.incomplete_by_profile["holiday_case"])

    def test_collect_default_uses_published_2026_labor_day(self) -> None:
        rows = [
            {
                "recorded_at": "2026-09-04T20:00:00Z",
                "total_equity": 100.0,
                "external_cash_flow": 0.0,
                "strategy_profile": "holiday_case",
                "lifecycle_stream_id": "offline-account",
            },
            {
                "recorded_at": "2026-09-08T20:00:00Z",
                "total_equity": 102.0,
                "external_cash_flow": 0.0,
                "strategy_profile": "holiday_case",
                "lifecycle_stream_id": "offline-account",
            },
        ]

        class Store:
            def list_live_run_records(self, domain: str) -> list[dict[str, object]]:
                return rows

        outcome = ReturnCollector(store=Store()).collect_from_live_runs_result(
            "us_equity",
            stream_id="offline-account",
        )
        self.assertIn("holiday_case", outcome.series_by_profile)
        self.assertAlmostEqual(float(outcome.series_by_profile["holiday_case"].iloc[0]), 0.02)
        self.assertEqual(outcome.incomplete_by_profile, {})

    def test_custom_coverage_overlay_is_not_swallowed_by_defaults(self) -> None:
        rows = [
            {
                "recorded_at": "2026-09-04T20:00:00Z",
                "total_equity": 100.0,
                "external_cash_flow": 0.0,
                "strategy_profile": "holiday_case",
                "lifecycle_stream_id": "offline-account",
            },
            {
                "recorded_at": "2026-09-08T20:00:00Z",
                "total_equity": 102.0,
                "external_cash_flow": 0.0,
                "strategy_profile": "holiday_case",
                "lifecycle_stream_id": "offline-account",
            },
        ]

        class Store:
            def list_live_run_records(self, domain: str) -> list[dict[str, object]]:
                return rows

        # Explicit narrow coverage must win over the published full-year default.
        outcome = ReturnCollector(store=Store()).collect_from_live_runs_result(
            "us_equity",
            stream_id="offline-account",
            holiday_source="caller_attested",
            holiday_coverage_start=date(2026, 9, 4),
            holiday_coverage_end=date(2026, 9, 5),
            session_holidays=frozenset({"2026-09-07"}),
        )
        self.assertEqual(outcome.series_by_profile, {})
        self.assertIn("coverage_exceeded", outcome.incomplete_by_profile["holiday_case"])

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
                            "execution_result": {"total_equity": equity, "external_cash_flow": 0.0},
                        },
                        stream_id=stream_id,
                    )

            collector = ReturnCollector(store=store, projects_root=Path(tmp))
            self.assertNotIn(
                "soxl_soxx_trend_income",
                collector.collect_from_live_runs("us_equity"),
            )

            account_a = collector.collect_from_live_runs(
                "us_equity", stream_id="account-a"
            )
            self.assertAlmostEqual(float(account_a["soxl_soxx_trend_income"].iloc[0]), 0.02)


if __name__ == "__main__":
    unittest.main()
