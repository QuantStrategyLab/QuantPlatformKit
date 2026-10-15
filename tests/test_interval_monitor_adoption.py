from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import date
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

from quant_platform_kit.strategy_lifecycle import contracts
from quant_platform_kit.strategy_lifecycle.ai_reviewer import llm_enhanced_review, review_proposal
from quant_platform_kit.strategy_lifecycle.contracts import (
    BacktestResult, DriftStatus, OptimizationProposal, StrategyPerformanceSnapshot,
)
from quant_platform_kit.strategy_lifecycle.drift_detector import detect_drift
from quant_platform_kit.strategy_lifecycle.drift_policy import DriftPolicy
from quant_platform_kit.strategy_lifecycle.live_equity import live_interval_records_to_return_series_result
from quant_platform_kit.strategy_lifecycle.performance_export import export_strategy_performance
from quant_platform_kit.strategy_lifecycle.performance_metrics import compute_window_metrics
from quant_platform_kit.strategy_lifecycle.performance_monitor import run_monitor
from quant_platform_kit.strategy_lifecycle.performance_store import PerformanceStore, _snapshot_from_dict
from quant_platform_kit.strategy_lifecycle.return_collector import ReturnCollector


SNAPSHOT_SCHEMA = "strategy_lifecycle.snapshot.coverage.v1"
EXPORT_SCHEMA = "strategy_performance.coverage_envelope.v1"
START = "2026-09-08T20:00:00+00:00"
END = "2026-09-12T20:00:00+00:00"


def receipts(gap=False):
    values = []
    equity = 100.0
    for day, factor in zip(range(8, 13), [1, 1.1, .95, 1.1, .95]):
        equity *= factor
        values.append(dict(account_scope_sha256="a" * 64,
                           start_at=f"2026-09-{day - 1:02d}T20:00:00Z",
                           end_at=f"2026-09-{day:02d}T20:00:00Z",
                           end_equity_usdt=str(equity), net_external_cash_flow="0",
                           currency="USDT", valuation_basis="checkpoint_quantities_sampled_prices"))
    if gap:
        values.insert(0, dict(values[0], start_at="2026-09-01T20:00:00Z",
                              end_at="2026-09-02T20:00:00Z"))
    return values


def coverage(gap=False, requested=False):
    kwargs = dict(required_start_at=START, required_end_at=END) if requested else {}
    return live_interval_records_to_return_series_result(receipts(gap), **kwargs).coverage


def window():
    values = pd.Series([.1, -.05, .1, -.05],
                       index=pd.date_range("2026-09-09", periods=4))
    return compute_window_metrics(values, window_days=4,
                                  periods_per_year=365.25, calendar_id="CRYPTO_NATURAL_DAY")


def snapshot(cov=None, status="ok"):
    kwargs = {} if cov is None else {"interval_return_coverage": cov}
    return StrategyPerformanceSnapshot(
        strategy_profile="coverage_case", domain="crypto", platform="offline-account",
        as_of=date(2026, 9, 12), windows={4: window()}, source_revision="a" * 40,
        cost_model="fixture_cost_model", observation_status=status, **kwargs)


def baseline():
    w = window()
    return BacktestResult(
        strategy_profile="coverage_case", domain="crypto", param_set_id="fixture", params={},
        start_date=w.start_date, end_date=w.end_date, observation_count=w.observation_count,
        sharpe_ratio=w.sharpe_ratio, calmar_ratio=w.calmar_ratio,
        max_drawdown=w.max_drawdown, cagr=w.cagr, win_rate=w.win_rate,
        volatility=w.volatility, periods_per_year=w.periods_per_year, calendar_id=w.calendar_id,
        source_revision="b" * 40, cost_model="fixture_cost_model")


def collector(root, values):
    rows = [dict(strategy_profile="coverage_case", lifecycle_stream_id="offline-account",
                 recorded_at=v["end_at"], external_cash_flow_interval=v) for v in values]

    class ReceiptStore:
        def list_live_run_records(self, domain):
            return rows

    return ReturnCollector(store=ReceiptStore(), projects_root=root,
                           artifact_roots={"crypto": root})


class IntervalMonitorAdoptionTests(unittest.TestCase):
    def test_none_coverage_preserves_exact_legacy_wire(self):
        s = snapshot()
        expected = {
            "strategy_profile", "domain", "platform", "as_of", "windows", "latest_return",
            "benchmark_symbol", "drift_score", "drift_status", "data_freshness_days",
            "source_artifact_path", "computed_at", "source_revision", "cost_model", "observation_status",
        }
        self.assertEqual(set(s.to_dict()), expected)
        self.assertIsInstance(s.to_dict()["windows"], dict)
        with tempfile.TemporaryDirectory() as tmp:
            store = PerformanceStore(local_root=Path(tmp))
            store.save_snapshot(s)
            wire = json.loads(next(Path(tmp).rglob("daily/**/*.json")).read_text())
            self.assertEqual(wire, dict(s.to_dict(), schema_version="strategy_lifecycle.v1"))
            self.assertIsNone(store.load_latest_snapshot("crypto", "coverage_case").interval_return_coverage)

    def test_new_snapshot_is_separate_envelope_and_roundtrips(self):
        cov = coverage(gap=True)
        s = snapshot(cov, "truncated_after_interval_gap")
        wire = s.to_dict()
        self.assertEqual(wire["schema_version"], SNAPSHOT_SCHEMA)
        self.assertEqual(set(wire), {"schema_version", "snapshot", "interval_return_coverage"})
        self.assertNotIn("as_of", wire)
        self.assertEqual(wire["interval_return_coverage"], cov)
        with tempfile.TemporaryDirectory() as tmp:
            store = PerformanceStore(local_root=Path(tmp))
            store.save_snapshot(s)
            restored = store.load_latest_snapshot("crypto", "coverage_case")
            self.assertEqual(restored.interval_return_coverage, cov)
            self.assertEqual(restored.windows[4], s.windows[4])
            self.assertEqual(restored.observation_status, "truncated_after_interval_gap")
            self.assertEqual(restored.to_dict(), wire)

    def test_unknown_schema_or_bad_coverage_cannot_downgrade(self):
        wire = snapshot(coverage()).to_dict()
        mutations = [dict(wire, schema_version="strategy_lifecycle.snapshot.coverage.v999"),
                     dict(wire, interval_return_coverage=None),
                     dict(wire, extra="must not silently ignore"),
                     dict(wire, interval_return_coverage=dict(coverage(), method="unknown")),
                     dict(wire, interval_return_coverage=dict(coverage(), return_count=True)),
                     dict(wire, interval_return_coverage=dict(coverage(), requested_window_complete=True)),
                     dict(wire, snapshot=dict(wire["snapshot"], unrecognized_metadata="ignored")),
                     dict(snapshot().to_dict(), schema_version="strategy_lifecycle.v1",
                          interval_return_coverage=coverage())]
        for raw in mutations:
            with self.subTest(raw=raw):
                self.assertIsNone(_snapshot_from_dict(raw))

    def test_count_cannot_disagree_with_contiguous_checkpoint_dates(self):
        with self.assertRaisesRegex(ValueError, "count|window"):
            snapshot(dict(coverage(), return_count=3)).to_dict()

    def test_collector_result_keeps_authoritative_coverage(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            c = collector(root, receipts(gap=True))
            result = c.collect_result("crypto", live_stream_id="offline-account")
            self.assertEqual(result.coverage_by_profile["coverage_case"]["return_count"], 4)
            self.assertIn("coverage_case", result.incomplete_by_profile)
            pd.testing.assert_series_equal(c.collect("crypto", live_stream_id="offline-account")["coverage_case"],
                                           result.series_by_profile["coverage_case"])

    def test_monitor_whole_window_after_historical_gap_is_legal_and_persisted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = PerformanceStore(local_root=root / "store")
            c = collector(root, receipts(gap=True))
            result = run_monitor("crypto", strategy_profile="coverage_case", collector=c, store=store,
                                 windows=(4,), min_observations=2, source_revision="a" * 40,
                                 live_stream_id="offline-account", required_start_at=START, required_end_at=END)
            self.assertEqual(len(result), 1)
            cov = result[0].interval_return_coverage
            self.assertTrue(cov["requested_window_complete"])
            self.assertEqual(cov["return_start_at"], START)
            self.assertIn("missing_interval", cov["truncation_reasons"])
            self.assertEqual(store.load_latest_snapshot("crypto", "coverage_case").interval_return_coverage, cov)

    def test_monitor_opt_in_segment_preserves_coverage_without_whole_window_claim(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = PerformanceStore(local_root=root / "store")
            result = run_monitor("crypto", collector=collector(root, receipts(gap=True)), store=store,
                                 windows=(4,), min_observations=2, source_revision="a" * 40,
                                 include_interval_coverage=True)
            self.assertEqual(result[0].interval_return_coverage["coverage_status"], "truncated_segment")
            self.assertIsNone(result[0].interval_return_coverage["requested_window_complete"])
            self.assertEqual(result[0].windows[4].observation_count, 4)

    def test_rejected_window_cannot_be_repaired_by_csv_or_write_any_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pd.DataFrame({"as_of": ["2026-09-07"], "coverage_case": [.1]}).to_csv(
                root / "portfolio_and_tracker_returns.csv", index=False)
            store = PerformanceStore(local_root=root / "store")
            c = collector(root, receipts())
            for start, end in [("2026-09-07T20:00:00Z", END), (START, "2026-09-13T20:00:00Z"),
                               (START, None), (END, START)]:
                with self.subTest(start=start, end=end), patch.object(PerformanceStore, "save_snapshot") as save:
                    with self.assertRaises((RuntimeError, ValueError)):
                        run_monitor("crypto", collector=c, store=store, windows=(4,), min_observations=2,
                                    source_revision="a" * 40, required_start_at=start, required_end_at=end)
                    save.assert_not_called()

    def test_requested_window_cannot_use_plain_collector_or_forged_attrs(self):
        class PlainCollector:
            def collect(self, domain):
                return {"coverage_case": pd.Series([.1, -.05])}

        with self.assertRaisesRegex((ValueError, RuntimeError), "coverage|result"):
            run_monitor("crypto", collector=PlainCollector(), required_start_at=START, required_end_at=END)

        series = pd.Series([.1, -.05, .1, -.05], index=pd.date_range("2026-09-09", periods=4))
        series.attrs.update(observation_status="ok", interval_coverage=coverage(requested=True))

        class ForgedAttrsCollector:
            def collect_result(self, domain, **kwargs):
                return contracts.LiveReturnCollectionResult({"coverage_case": series}, {})

        with self.assertRaisesRegex(RuntimeError, "incomplete_requested_window"):
            run_monitor("crypto", collector=ForgedAttrsCollector(), required_start_at=START, required_end_at=END)

    def test_requested_all_profiles_preflight_before_first_write(self):
        series = pd.Series([.1, -.05, .1, -.05], index=pd.date_range("2026-09-09", periods=4))

        class MixedResultCollector:
            def collect_result(self, domain, **kwargs):
                return contracts.LiveReturnCollectionResult(
                    {"a-good": series, "z-unqualified": series}, {},
                    {"a-good": coverage(requested=True)})

        with patch.object(PerformanceStore, "save_snapshot") as save:
            with self.assertRaisesRegex(RuntimeError, "incomplete_requested_window"):
                run_monitor("crypto", collector=MixedResultCollector(), required_start_at=START, required_end_at=END)
            save.assert_not_called()

    def test_mixed_scope_and_unavailable_stream_fail_before_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            mixed = receipts(); mixed[1] = dict(mixed[1], account_scope_sha256="b" * 64)
            for values, stream in [(mixed, "offline-account"), (receipts(), "missing-stream")]:
                with self.subTest(stream=stream), patch.object(PerformanceStore, "save_snapshot") as save:
                    with self.assertRaisesRegex(RuntimeError, "incomplete_requested_window"):
                        run_monitor("crypto", collector=collector(root, values), live_stream_id=stream,
                                    required_start_at=START, required_end_at=END)
                    save.assert_not_called()

    def test_lost_attrs_do_not_remove_explicit_monitor_qualification(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            c = collector(root, receipts())
            original = c.collect_result

            def cleared(*args, **kwargs):
                outcome = original(*args, **kwargs)
                for series in outcome.series_by_profile.values():
                    series.attrs.clear()
                return outcome

            c.collect_result = cleared
            result = run_monitor("crypto", collector=c, store=PerformanceStore(local_root=root / "store"),
                                 windows=(4,), min_observations=2, source_revision="a" * 40,
                                 required_start_at=START, required_end_at=END)
            self.assertTrue(result[0].interval_return_coverage["requested_window_complete"])

    def test_monitor_binds_normalized_date_set_before_any_write(self):
        indexes = {
            "shifted_same_length": pd.date_range("2026-08-01", periods=4),
            "missing_middle_date": pd.to_datetime(["2026-09-09", "2026-09-10", "2026-09-12", "2026-09-13"]),
            "timezone_shifted_labels": pd.date_range("2026-09-09", periods=4, tz="Asia/Shanghai"),
            "daily_duplicate": pd.to_datetime(["2026-09-09T10:00", "2026-09-09T20:00", "2026-09-11", "2026-09-12"], format="mixed"),
            "leading_nan": pd.date_range("2026-09-09", periods=4),
            "mid_nan": pd.date_range("2026-09-09", periods=4),
        }
        for label, index in indexes.items():
            with self.subTest(case=label), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                c = collector(root, receipts())
                outcome = c.collect_result("crypto", required_start_at=START, required_end_at=END)
                original = outcome.series_by_profile["coverage_case"].copy()
                changed = original.copy(); changed.index = index
                if label == "leading_nan":
                    changed.iloc[0] = float("nan")
                elif label == "mid_nan":
                    changed.iloc[1] = float("nan")
                # An earlier good target must not write before a later bad one.
                fake = contracts.LiveReturnCollectionResult(
                    {"a-good": original, "z-bad": changed}, {},
                    {"a-good": outcome.coverage_by_profile["coverage_case"],
                     "z-bad": outcome.coverage_by_profile["coverage_case"]})

                class FakeCollector:
                    def collect_result(self, domain, **kwargs):
                        return fake

                with patch.object(PerformanceStore, "save_snapshot") as save:
                    with self.assertRaises((ValueError, RuntimeError)):
                        run_monitor("crypto", collector=FakeCollector(), store=PerformanceStore(local_root=root / "store"),
                                    windows=(126,), min_observations=2, source_revision="a" * 40,
                                    required_start_at=START, required_end_at=END)
                    save.assert_not_called()

    def test_monitor_missing_or_mismatched_baseline_coverage_cannot_create_drift(self):
        for ref in [None, dict(coverage(), account_scope_sha256="b" * 64),
                    dict(coverage(), return_end_at="2026-09-11T20:00:00+00:00")]:
            with self.subTest(reference=ref), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp); store = PerformanceStore(local_root=root / "store")
                store.save_backtest_result(replace(baseline(), sharpe_ratio=.1, cagr=.01, max_drawdown=-.01))
                kwargs = {} if ref is None else {"baseline_coverage_by_profile": {"coverage_case": ref}}
                with patch("quant_platform_kit.strategy_lifecycle.performance_monitor.compare_with_backtest",
                           return_value={"sharpe_deviation": .6}) as compare:
                    result = run_monitor("crypto", collector=collector(root, receipts(gap=True)), store=store,
                                         windows=(126,), min_observations=2, source_revision="a" * 40,
                                         required_start_at=START, required_end_at=END, **kwargs)
                self.assertEqual(result[0].windows[126].observation_count, 4)
                self.assertEqual(result[0].drift_status, "not_comparable_interval_coverage")
                self.assertIsNone(result[0].drift_score)
                compare.assert_not_called()

    def test_monitor_matching_baseline_coverage_allows_bounded_drift_and_legacy_stays_same(self):
        for mode in ["coverage", "legacy"]:
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp); store = PerformanceStore(local_root=root / "store")
                store.save_backtest_result(replace(baseline(), sharpe_ratio=.1, cagr=.01, max_drawdown=-.01))
                kwargs = ({"include_interval_coverage": True,
                           "baseline_coverage_by_profile": {"coverage_case": coverage()}} if mode == "coverage" else {})
                result = run_monitor("crypto", collector=collector(root, receipts(gap=True)), store=store,
                                     windows=(126,), min_observations=2, source_revision="a" * 40, **kwargs)
                self.assertIsNotNone(result[0].drift_score)
                self.assertNotEqual(result[0].drift_status, "not_comparable_interval_coverage")
                self.assertEqual(result[0].as_of, date.today())

    def test_new_not_comparable_status_is_unevaluable_before_old_drift_fallbacks(self):
        s = replace(snapshot(coverage(requested=True)), windows={126: window()},
                    drift_status="not_comparable_interval_coverage")
        for current, ref, previous in [(s, baseline(), None), (s, None, None),
                                       (replace(s, windows={}), None, None),
                                       (replace(s, windows={}), baseline(), DriftStatus.CRITICAL)]:
            with self.subTest(window=current.windows, baseline=ref, previous=previous):
                result = detect_drift(current, backtest=ref, policy=DriftPolicy(), previous_status=previous)
                self.assertEqual(result.reason, "not_comparable_interval_coverage")
                self.assertFalse(result.baseline_available)
                self.assertTrue(result.alert_suppressed)
                self.assertEqual(result.dimensions, {})
                self.assertEqual(result.status, DriftStatus.CRITICAL if previous is DriftStatus.CRITICAL
                                 else DriftStatus.REVIEW)

    def test_actual_drift_entry_and_auto_dispatch_cannot_reopen_provider_for_unknown_coverage(self):
        from quant_platform_kit.strategy_lifecycle import codex_integration
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); store = PerformanceStore(local_root=root / "store")
            store.save_backtest_result(replace(baseline(), sharpe_ratio=.1, cagr=.01, max_drawdown=-.01))
            s = run_monitor("crypto", collector=collector(root, receipts(gap=True)), store=store,
                            windows=(126,), min_observations=2, source_revision="a" * 40,
                            required_start_at=START, required_end_at=END)[0]
            discovered = {"coverage_case": pd.Series([.1, -.05, .1, -.05],
                                                      index=pd.date_range("2026-09-09", periods=4))}
            # Preserve the completed opt-in monitor snapshot; exercise the real
            # store-backed drift entry, issue filtering and automatic dispatcher.
            with patch.object(ReturnCollector, "collect", return_value=discovered), \
                    patch.object(codex_integration, "_run_monitor_phase", return_value=[s]), \
                    patch.object(codex_integration, "_process_optimization_decision",
                                 side_effect=AssertionError("optimization/provider pipeline must not start")) as process, \
                    patch.object(codex_integration, "create_github_issue") as issue, \
                    patch("quant_platform_kit.strategy_lifecycle.ai_provider.AiServiceClient.execute") as execute:
                summary = codex_integration.run_auto_pilot_cycle("crypto", store=store, dry_run=False)
                self.assertEqual(summary["drifts_checked"], 1)
                self.assertEqual(summary["drifts_alerting"], 0)
                self.assertEqual(summary["issues_created"], 0)
                process.assert_not_called(); issue.assert_not_called(); execute.assert_not_called()
                retained = store.load_latest_drift("crypto", "coverage_case")
                self.assertFalse(retained.baseline_available)
                self.assertEqual(retained.reason, "not_comparable_interval_coverage")

    def test_default_monitor_still_writes_legacy_even_for_interval_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = run_monitor("crypto", collector=collector(root, receipts(gap=True)),
                                 store=PerformanceStore(local_root=root / "store"), windows=(4,),
                                 min_observations=2, source_revision="a" * 40)
            self.assertIsNone(result[0].interval_return_coverage)
            self.assertEqual(result[0].observation_status, "truncated_after_interval_gap")
            self.assertEqual(set(result[0].to_dict()), set(snapshot().to_dict()))

    def test_export_legacy_unchanged_and_new_coverage_is_not_ordinary_v2(self):
        for cov in [None, coverage(gap=True)]:
            with self.subTest(coverage=cov), tempfile.TemporaryDirectory() as tmp:
                store = PerformanceStore(local_root=Path(tmp))
                store.save_snapshot(snapshot(cov, "truncated_after_interval_gap" if cov else "ok"))
                store.save_backtest_result(baseline())
                payload = export_strategy_performance("crypto", repo="QuantStrategyLab/Offline", store=store)
                if cov is None:
                    self.assertEqual(payload["schema_version"], "strategy_performance.v2")
                    self.assertIn("current_metrics", payload["snapshots"][0])
                else:
                    self.assertEqual(payload["schema_version"], EXPORT_SCHEMA)
                    wrapper = payload["snapshots"][0]
                    self.assertEqual(wrapper["schema_version"], EXPORT_SCHEMA)
                    self.assertNotIn("current_metrics", wrapper)
                    inner = wrapper["payload"]
                    self.assertEqual(inner["schema_version"], "strategy_performance.v2")
                    meta = inner["metadata"]["interval_return_coverage"]
                    self.assertEqual(meta["return_start_at"], START)
                    self.assertEqual(meta["coverage_status"], "truncated_segment")
                    self.assertNotIn("account_scope_sha256", meta)
                    self.assertEqual(inner["metadata"]["snapshot_data_timestamp"], END)
                    self.assertEqual(inner["metadata"]["provenance"]["snapshot"]["data_timestamp"], END)
                    self.assertFalse(inner["metadata"]["interval_comparison"]["comparable"])

    def test_export_comparison_requires_actual_full_metric_window_and_method(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = PerformanceStore(local_root=Path(tmp))
            s = snapshot(coverage(gap=True))
            store.save_snapshot(s); store.save_backtest_result(baseline())
            for ref, expected in [(coverage(), True), (dict(coverage(), return_count=3), False),
                                  (dict(coverage(), method="unknown"), False)]:
                with self.subTest(reference=ref):
                    payload = export_strategy_performance("crypto", repo="QuantStrategyLab/Offline", store=store,
                                                          baseline_coverage_by_profile={"coverage_case": ref})
                    comp = payload["snapshots"][0]["payload"]["metadata"]["interval_comparison"]
                    self.assertEqual(comp["comparable"], expected)
                    if expected:
                        self.assertEqual(comp["reference_coverage"]["return_start_at"], START)
                        self.assertNotIn("account_scope_sha256", comp["reference_coverage"])
                        self.assertEqual(comp["reference_observation_count"], comp["actual_observation_count"])
                        self.assertEqual(comp["reference_start_date"], comp["actual_start_date"])
                        self.assertEqual(comp["reference_calendar_id"], comp["calendar_id"])
                        self.assertEqual(comp["reference_periods_per_year"], comp["periods_per_year"])

    def test_ai_does_not_turn_unknown_comparison_into_performance_conclusion(self):
        proposal = OptimizationProposal(strategy_profile="coverage_case", domain="crypto",
                                        current_metrics=baseline(), proposed_metrics=baseline(), confidence=.9)
        s = snapshot(coverage(gap=True), "truncated_after_interval_gap")
        verdict = review_proposal(proposal, snapshot=s)
        self.assertEqual(verdict.verdict, "escalate")
        self.assertEqual(verdict.confidence, 0)
        self.assertIn("coverage", verdict.summary)
        with patch("quant_platform_kit.strategy_lifecycle.ai_provider.AiServiceClient.review") as review:
            verdict = llm_enhanced_review(proposal, snapshot=s)
            self.assertEqual(verdict.verdict, "escalate")
            review.assert_not_called()

    def test_ai_legal_recovered_segment_uses_matching_window_comparison(self):
        proposal = OptimizationProposal(strategy_profile="coverage_case", domain="crypto",
                                        current_metrics=baseline(), proposed_metrics=baseline(), confidence=.9)
        s = snapshot(coverage(gap=True), "truncated_after_interval_gap")
        valid = {"current": coverage(), "proposed": coverage()}
        verdict = review_proposal(proposal, snapshot=s, comparison_coverage=valid)
        legacy = review_proposal(proposal)
        self.assertEqual(verdict.verdict, legacy.verdict)
        self.assertEqual(verdict.dimensions, legacy.dimensions)
        for key in ["current", "proposed"]:
            broken = deepcopy(valid); broken[key]["return_end_at"] = "2026-09-11T20:00:00+00:00"
            self.assertEqual(review_proposal(proposal, snapshot=s, comparison_coverage=broken).verdict, "escalate")

    def test_ai_current_values_must_match_actual_snapshot_not_just_dates(self):
        valid = {"current": coverage(), "proposed": coverage()}
        s = snapshot(coverage(gap=True), "truncated_after_interval_gap")
        for field, changed in [("sharpe_ratio", 50.0), ("volatility", .001),
                               ("max_drawdown", -.9), ("total_return", 8.0)]:
            with self.subTest(field=field):
                proposal = OptimizationProposal(
                    strategy_profile="coverage_case", domain="crypto",
                    current_metrics=replace(baseline(), **{field: changed}),
                    proposed_metrics=baseline(), confidence=.9)
                verdict = review_proposal(proposal, snapshot=s, comparison_coverage=valid)
                self.assertEqual(verdict.verdict, "escalate")
                self.assertEqual(verdict.confidence, 0)
                self.assertIn("current_metrics", verdict.summary)

    def test_comparison_rejects_inferred_subwindow_and_annualization(self):
        checker = contracts.interval_return_coverage_comparison_reason
        w, b = window(), baseline()
        args = dict(current_window=w, reference_metrics=b)
        self.assertEqual(checker(coverage(gap=True), coverage(), **args), "")
        self.assertNotEqual(checker(coverage(), coverage(), current_window=replace(w, observation_count=3),
                                   reference_metrics=b), "")
        self.assertNotEqual(checker(coverage(), coverage(), current_window=w,
                                   reference_metrics=replace(b, periods_per_year=252.0)), "")

    def test_comparison_cannot_qualify_undefined_performance_numbers(self):
        checker = contracts.interval_return_coverage_comparison_reason
        w, b = window(), baseline()
        for invalid in [replace(b, sharpe_ratio=float("nan")), replace(b, max_drawdown=float("inf"))]:
            with self.subTest(reference=invalid):
                self.assertNotEqual(checker(coverage(), coverage(), current_window=w, reference_metrics=invalid), "")


if __name__ == "__main__":
    unittest.main()
