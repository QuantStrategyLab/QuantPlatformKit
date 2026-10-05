from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from quant_platform_kit.strategy_lifecycle import live_equity
from quant_platform_kit.strategy_lifecycle.contracts import LiveReturnCollectionResult, LiveReturnSeriesResult
from quant_platform_kit.strategy_lifecycle.live_equity import (
    consecutive_losses_from_live_run_records,
    live_interval_records_to_return_series,
    live_run_records_to_return_series_result,
)
from quant_platform_kit.strategy_lifecycle.return_collector import ReturnCollector


def interval(start, end, equity, flow=0, scope="a" * 64):
    return dict(account_scope_sha256=scope, start_at=start, end_at=end,
                end_equity_usdt=str(equity), net_external_cash_flow=str(flow),
                currency="USDT", valuation_basis="checkpoint_quantities_sampled_prices")


def row(value, *, recorded_at=None):
    return dict(recorded_at=recorded_at or value["end_at"],
                strategy_profile="coverage_case", lifecycle_stream_id="offline-account",
                execution_result={"external_cash_flow_interval": value})


def clean_intervals():
    return [interval("2026-09-07T20:00:00Z", "2026-09-08T20:00:00Z", 100),
            interval("2026-09-08T20:00:00Z", "2026-09-09T20:00:00Z", 99),
            interval("2026-09-09T20:00:00Z", "2026-09-10T20:00:00Z", 98)]


class IntervalCoverageTests(unittest.TestCase):
    def derive(self, values, **kwargs):
        return live_run_records_to_return_series_result([row(value) for value in values], **kwargs)

    def test_explicit_coverage_keeps_source_start_separate_from_return_baseline(self):
        result = self.derive(clean_intervals())
        self.assertEqual(result.status, "ok")
        coverage = result.coverage
        self.assertEqual(coverage["source_segment_start_at"], "2026-09-07T20:00:00+00:00")
        self.assertEqual(coverage["source_segment_end_at"], "2026-09-10T20:00:00+00:00")
        self.assertEqual(coverage["return_start_at"], "2026-09-08T20:00:00+00:00")
        self.assertEqual(coverage["return_end_at"], "2026-09-10T20:00:00+00:00")
        self.assertEqual(coverage["method"], "end_flow_checkpoint_daily_observations")
        self.assertEqual(coverage["timezone"], "UTC")
        self.assertEqual(coverage["currency"], "USDT")
        self.assertEqual(coverage["truncation_reasons"], [])
        self.assertIsNone(coverage["requested_window_complete"])
        self.assertEqual(result.series.attrs["interval_coverage"], coverage)
        self.assertEqual(len(result.series), 2)

    def test_order_duplicates_and_timezone_normalization_are_deterministic(self):
        values = clean_intervals()
        equivalent = dict(values[0], start_at="2026-09-08T04:00:00+08:00",
                          end_at="2026-09-09T04:00:00+08:00")
        expected = self.derive(values)
        result = self.derive([values[2], equivalent, values[1], values[0], values[1]])
        pd.testing.assert_series_equal(result.series, expected.series)
        self.assertEqual(result.coverage, expected.coverage)

    def test_gap_preserves_later_segment_and_discloses_reason(self):
        values = clean_intervals()
        values[1] = dict(values[1], start_at="2026-09-08T21:00:00Z")
        result = self.derive(values)
        self.assertEqual(result.status, "truncated_after_interval_gap")
        self.assertIn("missing_interval", result.coverage["truncation_reasons"])
        self.assertEqual(result.coverage["return_start_at"], "2026-09-09T20:00:00+00:00")
        self.assertEqual(list(result.series.index), [pd.Timestamp("2026-09-10")])
        self.assertAlmostEqual(result.series.iloc[0], 98 / 99 - 1)
        self.assertEqual(consecutive_losses_from_live_run_records([row(value) for value in values]), 1)

    def test_overlap_is_distinct_from_missing_interval(self):
        values = clean_intervals()
        values[1] = dict(values[1], start_at="2026-09-08T19:00:00Z")
        result = self.derive(values)
        self.assertIn("overlapping_interval", result.coverage["truncation_reasons"])
        self.assertNotIn("missing_interval", result.coverage["truncation_reasons"])
        self.assertEqual(len(result.series), 1)

    def test_null_and_missing_interval_barriers_are_distinct(self):
        values = clean_intervals()
        for explicit, reason in [(True, "null_interval"), (False, "missing_interval_record")]:
            with self.subTest(reason=reason):
                barrier = row(None, recorded_at="2026-09-08T22:00:00Z")
                if not explicit:
                    barrier["execution_result"] = {"external_cash_flow": None}
                result = live_run_records_to_return_series_result([row(values[0]), barrier,
                                                                   row(values[1]), row(values[2])])
                self.assertEqual(result.status, "truncated_after_interval_gap")
                self.assertIn(reason, result.coverage["truncation_reasons"])
                self.assertEqual(len(result.series), 1)

    def test_conflict_and_same_end_different_start_recover_without_reusing_bad_day(self):
        values = clean_intervals()
        for conflict, reason in [(dict(values[0], end_equity_usdt="500"), "interval_conflict"),
                                 (dict(values[0], start_at="2026-09-07T21:00:00Z"),
                                  "same_end_different_start")]:
            with self.subTest(reason=reason):
                result = self.derive([values[0], conflict, values[1], values[2]])
                self.assertEqual(result.status, "truncated_after_interval_gap")
                self.assertIn(reason, result.coverage["truncation_reasons"])
                self.assertEqual(len(result.series), 1)
                self.assertEqual(result.coverage["return_start_at"], "2026-09-09T20:00:00+00:00")

    def test_unlocated_invalid_record_and_mixed_scope_are_unavailable(self):
        values = clean_intervals()
        result = live_run_records_to_return_series_result([row(values[0]), row(values[1]),
                                                           row(None, recorded_at="invalid")])
        self.assertEqual(result.status, "incomplete_interval_coverage")
        self.assertIn("unlocated_invalid_interval", result.coverage["truncation_reasons"])
        self.assertTrue(result.series.empty)
        mixed = self.derive([values[0], dict(values[1], account_scope_sha256="b" * 64)])
        self.assertEqual(mixed.status, "incomplete_interval_coverage")
        self.assertIn("mixed_account_scope", mixed.coverage["truncation_reasons"])
        self.assertIsNone(mixed.coverage["account_scope_sha256"])
        self.assertTrue(mixed.series.empty)

    def test_invalid_schema_barrier_reason_is_retained(self):
        values = clean_intervals()
        result = self.derive([dict(values[0], valuation_basis="unsupported"), values[1], values[2]])
        self.assertIn("invalid_interval", result.coverage["truncation_reasons"])
        self.assertEqual(len(result.series), 1)

    def test_insufficient_baseline_has_no_fabricated_return_coverage(self):
        result = self.derive(clean_intervals()[:1])
        self.assertEqual(result.status, "insufficient_observations")
        self.assertTrue(result.series.empty)
        self.assertIsNone(result.coverage["return_start_at"])
        self.assertIsNone(result.coverage["return_end_at"])

    def test_impossible_adjusted_nav_is_unavailable(self):
        values = clean_intervals()
        values[1] = dict(values[1], net_external_cash_flow="1000")
        result = self.derive(values)
        self.assertEqual(result.status, "incomplete_interval_coverage")
        self.assertIn("invalid_adjusted_return", result.coverage["truncation_reasons"])
        self.assertTrue(result.series.empty)

    def test_requested_checkpoint_window_is_complete_and_sliced(self):
        result = self.derive(clean_intervals(), required_start_at="2026-09-09T20:00:00Z",
                             required_end_at="2026-09-10T20:00:00Z")
        self.assertEqual(result.status, "ok")
        self.assertTrue(result.coverage["requested_window_complete"])
        self.assertEqual(result.coverage["return_start_at"], "2026-09-09T20:00:00+00:00")
        self.assertEqual(len(result.series), 1)
        self.assertAlmostEqual(result.series.iloc[0], 98 / 99 - 1)

    def test_source_start_is_not_a_qualified_return_start(self):
        result = self.derive(clean_intervals(), required_start_at="2026-09-07T20:00:00Z",
                             required_end_at="2026-09-10T20:00:00Z")
        self.assertEqual(result.status, "incomplete_requested_window")
        self.assertFalse(result.coverage["requested_window_complete"])
        self.assertIn("requested_checkpoint_unavailable", result.coverage["truncation_reasons"])
        self.assertTrue(result.series.empty)

    def test_incomplete_or_unaligned_requested_windows_never_return_partial_success(self):
        cases = [("2026-09-08T20:00:00Z", "2026-09-11T20:00:00Z"),
                 ("2026-09-08T20:00:01Z", "2026-09-10T20:00:00Z"),
                 ("2026-09-08T00:00:00Z", "2026-09-10T00:00:00Z")]
        for start, end in cases:
            with self.subTest(start=start, end=end):
                result = self.derive(clean_intervals(), required_start_at=start, required_end_at=end)
                self.assertEqual(result.status, "incomplete_requested_window")
                self.assertTrue(result.series.empty)

    def test_invalid_requested_window_is_explicitly_unavailable(self):
        for start, end in [(None, "2026-09-10T20:00:00Z"),
                           ("2026-09-08T20:00:00", "2026-09-10T20:00:00Z"),
                           ("2026-09-10T20:00:00Z", "2026-09-08T20:00:00Z")]:
            with self.subTest(start=start, end=end):
                result = self.derive(clean_intervals(), required_start_at=start, required_end_at=end)
                self.assertEqual(result.status, "invalid_requested_window")
                self.assertFalse(result.coverage["requested_window_complete"])
                self.assertTrue(result.series.empty)

    def test_requested_window_can_use_latest_clean_segment_only(self):
        values = clean_intervals()
        values[1] = dict(values[1], start_at="2026-09-08T21:00:00Z")
        complete = self.derive(values, required_start_at="2026-09-09T20:00:00Z",
                               required_end_at="2026-09-10T20:00:00Z")
        self.assertEqual(complete.status, "ok")
        self.assertTrue(complete.coverage["requested_window_complete"])
        self.assertIn("missing_interval", complete.coverage["truncation_reasons"])
        incomplete = self.derive(values, required_start_at="2026-09-08T20:00:00Z",
                                 required_end_at="2026-09-10T20:00:00Z")
        self.assertEqual(incomplete.status, "incomplete_requested_window")
        self.assertTrue(incomplete.series.empty)

    def test_legacy_series_values_match_explicit_result_and_input_is_unchanged(self):
        values = clean_intervals()
        before = [dict(value) for value in values]
        result = live_equity.live_interval_records_to_return_series_result(values)
        pd.testing.assert_series_equal(live_interval_records_to_return_series(values), result.series)
        self.assertEqual(values, before)

    def test_scalar_records_cannot_satisfy_an_interval_window(self):
        result = live_run_records_to_return_series_result(
            [dict(recorded_at="2026-09-08T20:00:00Z", total_equity=100, external_cash_flow=0),
             dict(recorded_at="2026-09-09T20:00:00Z", total_equity=99, external_cash_flow=0)],
            required_start_at="2026-09-08T20:00:00Z", required_end_at="2026-09-09T20:00:00Z")
        self.assertEqual(result.status, "incomplete_requested_window")
        self.assertTrue(result.series.empty)
        self.assertIn("interval_records_required", result.detail)


    def test_legacy_result_constructors_keep_optional_defaults(self):
        series = pd.Series([0.01])
        result = LiveReturnSeriesResult(series, "ok", "legacy")
        self.assertIsNone(result.coverage)
        collected = LiveReturnCollectionResult({"legacy": series}, {})
        self.assertEqual(collected.coverage_by_profile, {})
        collected.coverage_by_profile["changed"] = {}
        self.assertEqual(LiveReturnCollectionResult({}, {}).coverage_by_profile, {})
        self.assertEqual(asdict(result)["detail"], "legacy")

    def test_coverage_json_and_attrs_copy_do_not_replace_explicit_metadata(self):
        values = clean_intervals()
        values[1] = dict(values[1], start_at="2026-09-08T21:00:00Z")
        result = self.derive(values)
        self.assertEqual(json.loads(json.dumps(result.coverage)), result.coverage)
        result.series.attrs["interval_coverage"]["truncation_reasons"].append("discarded_copy")
        self.assertNotIn("discarded_copy", result.coverage["truncation_reasons"])
        result.series.attrs.clear()
        self.assertEqual(result.coverage["return_start_at"], "2026-09-09T20:00:00+00:00")

    def test_null_barrier_uses_utc_date_rather_than_text_date(self):
        values = clean_intervals()
        # This text date is Sep 9 locally but Sep 8 UTC: Sep 9 becomes the anchor.
        barrier = row(None, recorded_at="2026-09-09T06:00:00+08:00")
        result = live_run_records_to_return_series_result([row(values[0]), barrier,
                                                           row(values[1]), row(values[2])])
        self.assertEqual(len(result.series), 1)
        self.assertEqual(result.coverage["return_start_at"], "2026-09-09T20:00:00+00:00")

    def test_midnight_three_receipts_provide_only_two_returns(self):
        values = [interval("2026-09-07T00:00:00Z", "2026-09-08T00:00:00Z", 100),
                  interval("2026-09-08T00:00:00Z", "2026-09-09T00:00:00Z", 105),
                  interval("2026-09-09T00:00:00Z", "2026-09-10T00:00:00Z", 115.5)]
        result = self.derive(values, required_start_at="2026-09-08T08:00:00+08:00",
                             required_end_at="2026-09-10T08:00:00+08:00")
        self.assertEqual(result.status, "ok")
        self.assertEqual(len(result.series), 2)
        self.assertAlmostEqual(result.series.iloc[0], 0.05)
        self.assertAlmostEqual(result.series.iloc[1], 0.10)
        self.assertEqual(result.coverage["return_start_at"], "2026-09-08T00:00:00+00:00")

    def test_intraday_nonfinal_checkpoint_cannot_complete_a_daily_request(self):
        values = [interval("2026-09-07T20:00:00Z", "2026-09-08T12:00:00Z", 100),
                  interval("2026-09-08T12:00:00Z", "2026-09-08T20:00:00Z", 100),
                  interval("2026-09-08T20:00:00Z", "2026-09-09T20:00:00Z", 105)]
        result = self.derive(values, required_start_at="2026-09-08T12:00:00Z",
                             required_end_at="2026-09-09T20:00:00Z")
        self.assertEqual(result.status, "incomplete_requested_window")
        self.assertTrue(result.series.empty)
        self.assertEqual(result.coverage["available_return_start_at"], "2026-09-08T20:00:00+00:00")

    def test_conflicting_payload_order_has_no_effect_on_recovered_result(self):
        values = clean_intervals()
        conflict = dict(values[0], end_equity_usdt="1000")
        expected = self.derive([values[0], conflict, values[1], values[2]])
        result = self.derive([values[2], conflict, values[1], values[0], conflict])
        pd.testing.assert_series_equal(result.series, expected.series)
        self.assertEqual(result.coverage, expected.coverage)

    def test_end_conflict_without_later_pair_remains_unavailable(self):
        values = clean_intervals()
        result = self.derive([values[0], dict(values[1], end_equity_usdt="200"), values[1]])
        self.assertEqual(result.status, "insufficient_observations")
        self.assertIn("interval_conflict", result.coverage["truncation_reasons"])
        self.assertTrue(result.series.empty)

    def test_raw_internal_reason_cannot_inject_unbounded_metadata(self):
        wrapped = {"_interval_record_payload": None, "_interval_record_reason": "untrusted-secret-text",
                   "recorded_at": "2026-09-08T20:00:00Z"}
        result = live_equity.live_interval_records_to_return_series_result([wrapped] + clean_intervals()[1:])
        self.assertNotIn("untrusted-secret-text", result.detail)
        self.assertEqual(result.coverage["truncation_reasons"], ["null_interval"])

    def test_empty_direct_legacy_series_remains_unnamed(self):
        result = live_interval_records_to_return_series([])
        self.assertTrue(result.empty)
        self.assertIsNone(result.name)
        self.assertEqual(result.dtype, float)

    def test_scalar_default_result_has_no_interval_coverage(self):
        result = live_run_records_to_return_series_result(
            [dict(recorded_at="2026-09-08T20:00:00Z", total_equity=100, external_cash_flow=0),
             dict(recorded_at="2026-09-09T20:00:00Z", total_equity=99, external_cash_flow=0)])
        self.assertEqual(result.status, "ok")
        self.assertIsNone(result.coverage)
        self.assertNotIn("interval_coverage", result.series.attrs)


class IntervalCollectorCoverageTests(unittest.TestCase):
    def collector(self, root, values):
        class Store:
            def list_live_run_records(self, domain):
                return [row(value) for value in values]
        return ReturnCollector(store=Store(), projects_root=root, artifact_roots={"crypto": root})

    def test_collector_preserves_explicit_metadata_and_partial_status(self):
        values = clean_intervals()
        values[1] = dict(values[1], start_at="2026-09-08T21:00:00Z")
        with tempfile.TemporaryDirectory() as tmp:
            collector = self.collector(Path(tmp), values)
            result = collector.collect_from_live_runs_result("crypto", stream_id="offline-account")
            self.assertIn("truncated_after_interval_gap", result.incomplete_by_profile["coverage_case"])
            self.assertEqual(result.coverage_by_profile["coverage_case"],
                             result.series_by_profile["coverage_case"].attrs["interval_coverage"])
            self.assertEqual(len(collector.collect_from_live_runs("crypto")["coverage_case"]), 1)

    def test_csv_never_extends_an_interval_segment_or_relabels_it(self):
        for gap in [False, True]:
            with self.subTest(gap=gap), tempfile.TemporaryDirectory() as tmp:
                values = clean_intervals()
                if gap:
                    values[1] = dict(values[1], start_at="2026-09-08T21:00:00Z")
                root = Path(tmp)
                pd.DataFrame({"as_of": ["2026-09-07", "2026-09-08"],
                              "coverage_case": [-0.1, -0.1]}).to_csv(
                                  root / "portfolio_and_tracker_returns.csv", index=False)
                collector = self.collector(root, values)
                series = collector.collect("crypto", live_stream_id="offline-account")["coverage_case"]
                self.assertEqual(len(series), 1 if gap else 2)
                self.assertNotIn(pd.Timestamp("2026-09-07"), series.index)
                self.assertEqual(series.attrs["observation_status"],
                                 "truncated_after_interval_gap" if gap else "ok")
                self.assertIn("interval_coverage", series.attrs)

    def test_whole_window_unavailability_does_not_fall_back_to_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pd.DataFrame({"as_of": ["2026-09-07"], "coverage_case": [-0.1]}).to_csv(
                root / "portfolio_and_tracker_returns.csv", index=False)
            collector = self.collector(root, clean_intervals())
            kwargs = dict(required_start_at="2026-09-07T20:00:00Z",
                          required_end_at="2026-09-10T20:00:00Z")
            result = collector.collect_from_live_runs_result("crypto", **kwargs)
            self.assertNotIn("coverage_case", result.series_by_profile)
            self.assertIn("incomplete_requested_window", result.incomplete_by_profile["coverage_case"])
            self.assertFalse(result.coverage_by_profile["coverage_case"]["requested_window_complete"])
            self.assertNotIn("coverage_case", collector.collect("crypto", **kwargs))

    def test_empty_interval_history_does_not_promote_csv_as_live_coverage(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pd.DataFrame({"as_of": ["2026-09-07"], "coverage_case": [-0.1]}).to_csv(
                root / "portfolio_and_tracker_returns.csv", index=False)
            collector = self.collector(root, clean_intervals()[:1])
            self.assertNotIn("coverage_case", collector.collect("crypto"))


    def test_required_window_with_no_live_records_cannot_use_csv_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pd.DataFrame({"as_of": ["2026-09-07"], "coverage_case": [-0.1]}).to_csv(
                root / "portfolio_and_tracker_returns.csv", index=False)
            collector = self.collector(root, [])
            self.assertEqual(collector.collect("crypto", required_start_at="2026-09-08T20:00:00Z",
                                               required_end_at="2026-09-10T20:00:00Z"), {})


    def test_ambiguous_or_missing_interval_stream_is_explicit_and_cannot_fall_back(self):
        values = clean_intervals()
        rows = [dict(row(value), lifecycle_stream_id=stream)
                for stream in ["stream-a", "stream-b"] for value in values]

        class Store:
            def list_live_run_records(self, domain):
                return rows

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pd.DataFrame({"as_of": ["2026-09-07"], "coverage_case": [-0.1]}).to_csv(
                root / "portfolio_and_tracker_returns.csv", index=False)
            collector = ReturnCollector(store=Store(), projects_root=root, artifact_roots={"crypto": root})
            for stream, reason in [(None, "ambiguous_lifecycle_stream"),
                                   ("stream-c", "requested_stream_unavailable")]:
                with self.subTest(stream=stream):
                    outcome = collector.collect_from_live_runs_result("crypto", stream_id=stream)
                    self.assertNotIn("coverage_case", outcome.series_by_profile)
                    self.assertEqual(outcome.incomplete_by_profile["coverage_case"],
                                     "incomplete_interval_coverage:" + reason)
                    self.assertNotIn("coverage_case", collector.collect("crypto", live_stream_id=stream))
            selected = collector.collect("crypto", live_stream_id="stream-a")["coverage_case"]
            self.assertEqual(len(selected), 2)
            self.assertIn("interval_coverage", selected.attrs)


    def test_mixed_scope_has_authoritative_unavailable_coverage_and_no_csv_fallback(self):
        values = clean_intervals()
        values[1] = dict(values[1], account_scope_sha256="b" * 64)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pd.DataFrame({"as_of": ["2026-09-07"], "coverage_case": [-0.1]}).to_csv(
                root / "portfolio_and_tracker_returns.csv", index=False)
            collector = self.collector(root, values)
            outcome = collector.collect_from_live_runs_result("crypto", stream_id="offline-account")
            self.assertNotIn("coverage_case", outcome.series_by_profile)
            coverage = outcome.coverage_by_profile["coverage_case"]
            self.assertEqual(coverage["coverage_status"], "unavailable")
            self.assertIsNone(coverage["account_scope_sha256"])
            self.assertIn("mixed_account_scope", coverage["truncation_reasons"])
            self.assertNotIn("coverage_case", collector.collect("crypto", live_stream_id="offline-account"))

    def test_merge_uses_explicit_coverage_when_series_attrs_are_lost(self):
        values = clean_intervals()
        values[1] = dict(values[1], start_at="2026-09-08T21:00:00Z")
        with tempfile.TemporaryDirectory() as tmp:
            collector = self.collector(Path(tmp), values)
            result = collector.collect_from_live_runs_result("crypto")
            series = result.series_by_profile["coverage_case"]
            series.attrs.clear()
            csv = pd.Series([-0.1], index=pd.to_datetime(["2026-09-07"]))
            merged = collector._merge_return_series({"coverage_case": csv}, result.series_by_profile,
                                                    coverage_by_profile=result.coverage_by_profile,
                                                    incomplete_by_profile=result.incomplete_by_profile)
            self.assertEqual(len(merged["coverage_case"]), 1)
            self.assertNotIn(pd.Timestamp("2026-09-07"), merged["coverage_case"].index)


if __name__ == "__main__":
    unittest.main()
