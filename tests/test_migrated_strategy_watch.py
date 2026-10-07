from __future__ import annotations

import unittest
from copy import deepcopy
import json
from unittest.mock import patch

import quant_platform_kit.strategy_lifecycle.watch.strategy_watch as watch

from quant_platform_kit.strategy_lifecycle.watch.strategy_watch import (
    RESEARCH_INPUT_UNAVAILABLE_FINDING_TYPE,
    build_research_input_unavailable_finding,
    STRATEGY_WATCH_REGISTRY,
    build_strategy_monitoring_finding,
    evaluate_strategy_watch,
    finding_to_automation_task,
    issue_for_task,
    resolve_strategy_watch_repository,
    watcher_issue_key,
)
from quant_platform_kit.strategy_lifecycle.research_task import validate_strategy_diagnosis_task


# Captured from QPK main 23b381b4's real five-receipt -> four-return
# live_equity, performance_metrics and export code, using an offline store.
# The requested-window variant retains an earlier historical receipt gap.
_REAL_QPK_COVERAGE_EXPORT = json.loads(r'''
{
  "schema_version": "strategy_performance.coverage_envelope.v1",
  "metrics_kind": "performance",
  "repo": "QuantStrategyLab/CryptoStrategies",
  "domain": "crypto",
  "generated_at": "2026-09-13T00:00:00Z",
  "source": "strategy_lifecycle_performance_store",
  "snapshots": [
    {
      "schema_version": "strategy_performance.coverage_envelope.v1",
      "metrics_kind": "performance",
      "payload": {
        "repo": "QuantStrategyLab/CryptoStrategies",
        "strategy_profile": "coverage_case",
        "schema_version": "strategy_performance.v2",
        "metrics_kind": "performance",
        "current_metrics": {
          "sharpe": 6.370504951205463,
          "cagr": 3097.2220672130356,
          "calmar": 61944.44134426052,
          "win_rate": 0.5,
          "max_dd": -0.050000000000000155,
          "volatility": 1.4333636140212307,
          "total_return": 0.09202500000000002,
          "observation_count": 4,
          "benchmark_symbol": "",
          "benchmark_return": null,
          "benchmark_cagr": null,
          "benchmark_max_dd": null,
          "excess_cagr": null,
          "alpha": null,
          "information_ratio": null,
          "latest_return": null,
          "drift_score": null,
          "data_freshness_days": 0
        },
        "baseline_metrics": {
          "sharpe": 6.370504951205463,
          "cagr": 3097.2220672130356,
          "calmar": 61944.44134426052,
          "win_rate": 0.5,
          "max_dd": -0.050000000000000155,
          "volatility": 1.4333636140212307,
          "total_return": null,
          "observation_count": 4,
          "benchmark_symbol": "",
          "benchmark_cagr": null,
          "benchmark_max_dd": null,
          "excess_cagr": null,
          "param_version": 1,
          "oos_sharpe": null,
          "oos_calmar": null,
          "oos_max_dd": null,
          "walk_forward_stability": null
        },
        "source": "performance_store",
        "generated_at": "2026-09-13T00:00:00Z",
        "metadata": {
          "domain": "crypto",
          "as_of": "2026-09-12",
          "window_days": 4,
          "window_start": "2026-09-09",
          "window_end": "2026-09-12",
          "snapshot_computed_at": "",
          "backtest_computed_at": "",
          "snapshot_source_revision": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
          "backtest_source_revision": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
          "snapshot_cost_model": "fixture_cost_model",
          "backtest_cost_model": "fixture_cost_model",
          "provenance": {
            "snapshot": {
              "source_revision": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
              "cost_model": "fixture_cost_model",
              "data_timestamp": "2026-09-12T20:00:00+00:00",
              "status": "verified"
            },
            "backtest": {
              "source_revision": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
              "cost_model": "fixture_cost_model",
              "data_timestamp": "2026-09-12T00:00:00Z",
              "status": "verified"
            }
          },
          "snapshot_data_timestamp": "2026-09-12T20:00:00+00:00",
          "backtest_data_timestamp": "2026-09-12T00:00:00Z",
          "interval_return_coverage": {
            "method": "end_flow_checkpoint_daily_observations",
            "timezone": "UTC",
            "currency": "USDT",
            "valuation_basis": "checkpoint_quantities_sampled_prices",
            "source_segment_start_at": "2026-09-07T20:00:00+00:00",
            "source_segment_end_at": "2026-09-12T20:00:00+00:00",
            "available_return_start_at": "2026-09-08T20:00:00+00:00",
            "available_return_end_at": "2026-09-12T20:00:00+00:00",
            "return_start_at": "2026-09-08T20:00:00+00:00",
            "return_end_at": "2026-09-12T20:00:00+00:00",
            "requested_start_at": null,
            "requested_end_at": null,
            "requested_window_complete": null,
            "coverage_status": "complete_segment",
            "normalized_interval_count": 5,
            "segment_interval_count": 5,
            "return_count": 4,
            "truncation_reasons": []
          },
          "interval_comparison": {
            "comparable": true,
            "reason": "",
            "actual_start_date": "2026-09-09",
            "actual_end_date": "2026-09-12",
            "actual_observation_count": 4,
            "calendar_id": "CRYPTO_NATURAL_DAY",
            "periods_per_year": 365.25,
            "reference_coverage": {
              "method": "end_flow_checkpoint_daily_observations",
              "timezone": "UTC",
              "currency": "USDT",
              "valuation_basis": "checkpoint_quantities_sampled_prices",
              "source_segment_start_at": "2026-09-07T20:00:00+00:00",
              "source_segment_end_at": "2026-09-12T20:00:00+00:00",
              "available_return_start_at": "2026-09-08T20:00:00+00:00",
              "available_return_end_at": "2026-09-12T20:00:00+00:00",
              "return_start_at": "2026-09-08T20:00:00+00:00",
              "return_end_at": "2026-09-12T20:00:00+00:00",
              "requested_start_at": null,
              "requested_end_at": null,
              "requested_window_complete": null,
              "coverage_status": "complete_segment",
              "normalized_interval_count": 5,
              "segment_interval_count": 5,
              "return_count": 4,
              "truncation_reasons": []
            },
            "reference_start_date": "2026-09-09",
            "reference_end_date": "2026-09-12",
            "reference_observation_count": 4,
            "reference_calendar_id": "CRYPTO_NATURAL_DAY",
            "reference_periods_per_year": 365.25,
            "scope": "supplied_checkpoint_window"
          }
        }
      }
    }
  ]
}
''')

def coverage_export_fixture(*, gap: bool = False, requested: bool = False) -> dict:
    payload = deepcopy(_REAL_QPK_COVERAGE_EXPORT)
    metadata = payload["snapshots"][0]["payload"]["metadata"]
    for coverage in (metadata["interval_return_coverage"], metadata["interval_comparison"]["reference_coverage"]):
        if gap:
            coverage.update(normalized_interval_count=6, coverage_status="truncated_segment", truncation_reasons=["missing_interval"])
        if requested:
            coverage.update(requested_start_at=coverage["return_start_at"], requested_end_at=coverage["return_end_at"], requested_window_complete=True, coverage_status="complete_requested_window")
    return payload


class StrategyWatchTest(unittest.TestCase):

    def test_exact_soxl_v3_task_binds_the_fixed_learning_experiment(self) -> None:
        finding = evaluate_strategy_watch(
            {
                "repo": "QuantStrategyLab/UsEquitySnapshotPipelines",
                "strategy_profile": "soxl_soxx_core_only_p2_v3",
                "candidate_kind": "individual",
                "domain": "us_equity",
                "schema_version": "strategy_performance.v2",
                "metrics_kind": "performance",
                "generated_at": "2026-09-10T00:00:00Z",
                "current_metrics": {"sharpe": 0.5, "cagr": 0.1, "calmar": 0.7, "win_rate": 0.52, "max_dd": 0.12},
                "baseline_metrics": {"sharpe": 1.0, "cagr": 0.2, "calmar": 1.0, "win_rate": 0.58, "max_dd": 0.08},
                "research_task_evidence": {
                    "p1_input_digest": "a" * 64,
                    "p2_config_digest": "ff8fa0acf4f175a7c40c3e1e6a3304ea2748b6b81c3797342085a4df3810ab4d",
                    "p3_evidence_id": "c" * 64,
                    "strategy_revision": "7756fe32585e85cf1d09a163203a02e3eee39fe1",
                    "producer_revision": "e" * 40,
                },
            }
        )[0]

        task = validate_strategy_diagnosis_task(__import__("quant_platform_kit.strategy_lifecycle.watch.strategy_watch", fromlist=["finding_to_research_task"]).finding_to_research_task(finding))
        repeated = validate_strategy_diagnosis_task(__import__("quant_platform_kit.strategy_lifecycle.watch.strategy_watch", fromlist=["finding_to_research_task"]).finding_to_research_task(finding))
        self.assertIsNone(task["experiment"]["parameter_bounds_sha256"])
        bounded = watch.finding_to_research_task(finding, parameter_bounds_sha256="d" * 64)
        self.assertEqual(validate_strategy_diagnosis_task(bounded, allowed_parameter_bounds=frozenset({"d" * 64}))["experiment"]["parameter_bounds_sha256"], "d" * 64)
        with self.assertRaises(ValueError):
            validate_strategy_diagnosis_task(bounded)
        self.assertEqual(task["task_id"], repeated["task_id"])
        self.assertEqual(task["task_sha256"], repeated["task_sha256"])

    def test_old_null_bounds_soxl_task_remains_valid_but_non_executable(self) -> None:
        from quant_platform_kit.strategy_lifecycle.research_task import build_strategy_diagnosis_task, calculate_task_sha256

        task = build_strategy_diagnosis_task(
            event_key="123456789abc", created_at="2026-09-10T00:00:00Z",
            candidate_id="soxl_soxx_core_only_p2_v3", candidate_kind="individual",
            domain="us_equity", strategy_repository="QuantStrategyLab/UsEquityStrategies",
            evidence={"p1_input_digest": "a" * 64, "p2_config_digest": "ff8fa0acf4f175a7c40c3e1e6a3304ea2748b6b81c3797342085a4df3810ab4d", "p3_evidence_id": "c" * 64, "strategy_revision": "7756fe32585e85cf1d09a163203a02e3eee39fe1", "producer_revision": "e" * 40},
        )
        task["experiment"]["parameter_bounds_sha256"] = None
        task["task_sha256"] = calculate_task_sha256(task)
        self.assertIsNone(validate_strategy_diagnosis_task(task)["experiment"]["parameter_bounds_sha256"])

    def test_deferred_research_input_creates_issue_only_data_finding(self) -> None:
        finding = build_research_input_unavailable_finding(
            repo="QuantStrategyLab/UsEquitySnapshotPipelines",
            profile="soxl_soxx_trend_income",
            status="DEFERRED",
            reason_code="ALPACA_SIP_ACCESS_FORBIDDEN",
            candidate_id="soxl_soxx_core_only_p2_v3",
            date_cutoff="2026-08-21",
            source="artifact://p1-status.json",
        )

        task = finding_to_automation_task(finding)

        self.assertEqual(finding.finding_type, RESEARCH_INPUT_UNAVAILABLE_FINDING_TYPE)
        self.assertEqual(task.trigger.kind, "strategy_research_input_unavailable")
        self.assertTrue(task.gate_decision.metadata["issue_only"])
        self.assertFalse(task.gate_decision.metadata["live_impact_allowed"])
    def test_strategy_watch_registry_resolves_known_domains_and_fails_closed(self) -> None:
        self.assertEqual(
            {item.domain for item in STRATEGY_WATCH_REGISTRY},
            {"cn_equity", "hk_equity", "us_equity", "crypto"},
        )
        self.assertEqual(resolve_strategy_watch_repository("us_equity"), "QuantStrategyLab/UsEquityStrategies")
        self.assertEqual(resolve_strategy_watch_repository("unknown"), "")

    def test_monitoring_trigger_becomes_issue_only_optimization_record(self) -> None:
        finding = build_strategy_monitoring_finding(
            domain="us_equity",
            profile="global_etf_rotation",
            severity="high",
            metrics={"overall_score": 14.2, "performance_score": 0.0},
            signals=[
                {
                    "metric": "overall_score",
                    "reason": "overall_score=14.2 is below monitoring threshold 60.0",
                }
            ],
            source="quant-monitor/daily-briefing",
            generated_at="2026-07-31T00:00:00Z",
        )

        task = finding_to_automation_task(finding)
        payload = task.to_dict()

        self.assertEqual(finding.snapshot.repo, "QuantStrategyLab/UsEquityStrategies")
        self.assertEqual(finding.finding_type, "monitoring_trigger")
        self.assertEqual(payload["trigger"]["kind"], "strategy_monitoring_trigger")
        self.assertEqual(payload["proposed_action"]["action"], "open_issue")
        self.assertFalse(payload["gate_decision"]["metadata"]["live_impact_allowed"])
        self.assertIn("bounded, no-order", payload["proposed_action"]["rationale"])

    def test_degraded_snapshot_becomes_issue_only_task(self) -> None:
        findings = evaluate_strategy_watch(
            {
                "repo": "QuantStrategyLab/TestStrategies",
                "snapshots": [
                    {
                        "strategy_profile": "mean_reversion_live",
                        "plugin": "mean_reversion",
                        "schema_version": "strategy_performance.v2",
                        "metrics_kind": "performance",
                        "current_metrics": {"sharpe": 0.7, "cagr": 0.11, "calmar": 0.6, "win_rate": 0.52, "max_dd": 0.18},
                        "baseline_metrics": {"sharpe": 1.0, "cagr": 0.18, "calmar": 1.0, "win_rate": 0.58, "max_dd": 0.1},
                        "source": "data/output/strategy_metrics.json",
                    }
                ],
            }
        )

        self.assertEqual(len(findings), 1)
        task = finding_to_automation_task(findings[0])
        payload = task.to_dict()
        self.assertTrue(task.is_actionable)
        self.assertEqual(payload["proposed_action"]["action"], "open_issue")
        self.assertFalse(payload["proposed_action"]["requires_human_review"])
        self.assertFalse(payload["gate_decision"]["human_review_required"])
        self.assertFalse(payload["gate_decision"]["metadata"]["live_impact_allowed"])

    def test_malformed_metrics_snapshot_is_ignored_without_crashing(self) -> None:
        findings = evaluate_strategy_watch(
            {
                "repo": "QuantStrategyLab/TestStrategies",
                "snapshots": [
                    {"profile": "bad", "current_metrics": "oops", "baseline_metrics": {"sharpe": 1.0}},
                    {
                        "profile": "live",
                        "schema_version": "strategy_performance.v2",
                        "metrics_kind": "performance",
                        "current_metrics": {"sharpe": 0.5, "cagr": 0.1, "calmar": 0.7, "win_rate": 0.52, "max_dd": 0.12},
                        "baseline_metrics": {"sharpe": 1.0, "cagr": 0.2, "calmar": 1.0, "win_rate": 0.58, "max_dd": 0.08},
                    },
                ],
            }
        )

        self.assertEqual(len(findings), 2)
        self.assertEqual(findings[0].finding_type, "data_quality")
        self.assertEqual(findings[1].snapshot.profile, "live")

    def test_healthy_snapshot_creates_no_finding(self) -> None:
        findings = evaluate_strategy_watch(
            {
                "repo": "QuantStrategyLab/TestStrategies",
                "schema_version": "strategy_performance.v2",
                "metrics_kind": "performance",
                "current_metrics": {"sharpe": 1.01, "cagr": 0.2, "calmar": 1.0, "win_rate": 0.58, "max_dd": 0.10},
                "baseline_metrics": {"sharpe": 1.0, "cagr": 0.2, "calmar": 1.0, "win_rate": 0.58, "max_dd": 0.1},
            }
        )

        self.assertEqual(findings, [])

    def test_issue_body_states_safety_boundary(self) -> None:
        finding = evaluate_strategy_watch(
            {
                "repo": "QuantStrategyLab/TestStrategies",
                "profile": "live",
                "schema_version": "strategy_performance.v2",
                "metrics_kind": "performance",
                "current_metrics": {"sharpe": 0.8, "cagr": 0.1, "calmar": 0.8, "win_rate": 0.55, "max_dd": 0.12},
                "baseline_metrics": {"sharpe": 1.0, "cagr": 0.2, "calmar": 1.0, "win_rate": 0.55, "max_dd": 0.12},
            }
        )[0]

        issue = issue_for_task(finding_to_automation_task(finding))

        self.assertIn("AI strategy optimization proposal", issue["title"])
        self.assertNotRegex(issue["title"], r"\[[a-f0-9]{12}\]$")
        self.assertIn("Event key", issue["body"])
        self.assertIn("<!-- strategy-optimization-watcher:", issue["body"])
        self.assertIn("only opens an issue", issue["body"])
        self.assertIn("does not modify strategy code", issue["body"])
        self.assertIn("sandbox backtest", issue["body"])

    def test_operational_metrics_payload_becomes_data_quality_finding(self) -> None:
        findings = evaluate_strategy_watch(
            {
                "repo": "QuantStrategyLab/TestStrategies",
                "schema_version": "strategy_operational_metrics.v1",
                "metrics_kind": "operational_quality",
                "profile": "live",
                "current_metrics": {"pool_size": 12},
                "baseline_metrics": {"pool_size": 10},
            }
        )

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].finding_type, "data_quality")
        task = finding_to_automation_task(findings[0])
        payload = task.to_dict()
        self.assertEqual(payload["trigger"]["kind"], "strategy_metrics_contract_invalid")
        self.assertIn("strategy_performance.v2", payload["trigger"]["reason"])
        self.assertEqual(payload["metadata"]["finding_type"], "data_quality")

    def test_legacy_performance_payload_remains_compatible(self) -> None:
        findings = evaluate_strategy_watch(
            {
                "repo": "QuantStrategyLab/TestStrategies",
                "profile": "legacy",
                "current_metrics": {"sharpe": 0.5},
                "baseline_metrics": {"sharpe": 1.0},
            }
        )

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].finding_type, "metric_degradation")

    def test_single_performance_discriminator_remains_compatible(self) -> None:
        base = {
            "repo": "QuantStrategyLab/TestStrategies",
            "profile": "live",
            "current_metrics": {"sharpe": 0.5, "cagr": 0.1, "calmar": 0.7, "win_rate": 0.52, "max_dd": 0.12},
            "baseline_metrics": {"sharpe": 1.0, "cagr": 0.2, "calmar": 1.0, "win_rate": 0.58, "max_dd": 0.08},
        }

        for discriminator in ({"schema_version": "strategy_performance.v2"}, {"metrics_kind": "performance"}):
            findings = evaluate_strategy_watch({**base, **discriminator})
            self.assertEqual(len(findings), 1)
            self.assertEqual(findings[0].finding_type, "metric_degradation")

    def test_invalid_numeric_value_becomes_data_quality_finding(self) -> None:
        findings = evaluate_strategy_watch(
            {
                "repo": "QuantStrategyLab/TestStrategies",
                "schema_version": "strategy_performance.v2",
                "metrics_kind": "performance",
                "profile": "live",
                "current_metrics": {"sharpe": "oops", "cagr": 0.1, "calmar": 0.7, "win_rate": 0.52, "max_dd": 0.12},
                "baseline_metrics": {"sharpe": 1.0, "cagr": 0.2, "calmar": 1.0, "win_rate": 0.58, "max_dd": 0.08},
            }
        )

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].finding_type, "data_quality")

    def test_data_quality_issue_key_does_not_collide_with_metric_issue(self) -> None:
        metric_finding = evaluate_strategy_watch(
            {
                "repo": "QuantStrategyLab/TestStrategies",
                "profile": "live",
                "current_metrics": {"sharpe": 0.5},
                "baseline_metrics": {"sharpe": 1.0},
            }
        )[0]
        quality_finding = evaluate_strategy_watch(
            {
                "repo": "QuantStrategyLab/TestStrategies",
                "schema_version": "strategy_operational_metrics.v1",
                "metrics_kind": "operational_quality",
                "profile": "live",
                "current_metrics": {"pool_size": 10},
                "baseline_metrics": {"pool_size": 9},
            }
        )[0]

        self.assertNotEqual(
            watcher_issue_key(finding_to_automation_task(metric_finding)),
            watcher_issue_key(finding_to_automation_task(quality_finding)),
        )

    def test_malformed_snapshot_entry_becomes_data_quality_finding(self) -> None:
        findings = evaluate_strategy_watch(
            {
                "repo": "QuantStrategyLab/TestStrategies",
                "schema_version": "strategy_performance.v2",
                "metrics_kind": "performance",
                "snapshots": [None],
            }
        )

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].finding_type, "data_quality")


def guard_external_io(test_case):
    """Keep direct unittest/pytest runs offline, including regressed products."""
    mocks = []
    for target in ("socket.create_connection", "socket.socket.connect", "socket.socket.connect_ex", "subprocess.Popen"):
        guard = patch(target, side_effect=AssertionError("external I/O forbidden"))
        mocks.append(guard.start())
        test_case.addCleanup(guard.stop)
    def assert_no_attempts():
        for guarded in mocks:
            guarded.assert_not_called()
    test_case.addCleanup(assert_no_attempts)
    return mocks


class StrategyCoverageReaderTest(unittest.TestCase):
    def setUp(self):
        self.external_guards = guard_external_io(self)

    def test_real_public_window_is_read_but_cannot_authorize_optimization(self):
        payload = coverage_export_fixture()
        with patch.object(watch, "evaluate_strategy_metrics") as evaluator:
            self.assertEqual(watch.evaluate_strategy_watch(payload), [])
            evaluator.assert_not_called()
        status = watch.strategy_watch_coverage_status(payload)[0]
        self.assertEqual(status["read_status"], "valid")
        self.assertEqual(status["public_comparison_status"], "consistent")
        self.assertEqual(status["comparison_status"], "unknown")
        self.assertEqual(status["optimization_status"], "unavailable")
        self.assertEqual(status["reason"], "interval_scope_binding_unavailable")
        self.assertEqual(status["effective_window"], {"start_at": "2026-09-08T20:00:00+00:00", "end_at": "2026-09-12T20:00:00+00:00", "return_count": 4})
        snapshot = watch._snapshots_from_payload(payload)[0]
        self.assertEqual(snapshot.schema_version, "strategy_performance.coverage_envelope.v1")
        self.assertEqual(snapshot.coverage_context, status)
        self.assertNotIn("metadata", snapshot.to_dict())

    def test_complete_requested_window_survives_historical_gap(self):
        status = watch.strategy_watch_coverage_status(coverage_export_fixture(gap=True, requested=True))[0]
        self.assertEqual(status["read_status"], "valid")
        self.assertEqual(status["coverage_status"], "complete_requested_window")
        self.assertTrue(status["requested_window"]["complete"])
        self.assertEqual(status["effective_window"]["return_count"], 4)
        self.assertEqual(status["optimization_status"], "unavailable")

    def test_public_coverage_validation_is_bounded_and_fail_closed(self):
        mutations = [
            ("return_start_at", None), ("return_end_at", "2026-09-13T20:00:00Z"),
            ("source_segment_end_at", "2026-09-10T20:00:00Z"),
            ("return_count", 3), ("return_count", True), ("return_count", float("nan")),
            ("segment_interval_count", 4), ("normalized_interval_count", 3),
            ("method", "exact_twr"), ("timezone", "Asia/Shanghai"),
            ("coverage_status", "complete_native_archive"), ("requested_window_complete", True),
            ("truncation_reasons", ["unknown"]), ("account_scope_sha256", "a" * 64),
            ("path", "/private/account.json"),
        ]
        for key, value in mutations:
            with self.subTest(key=key, value=value):
                payload = coverage_export_fixture()
                payload["snapshots"][0]["payload"]["metadata"]["interval_return_coverage"][key] = value
                self.assertEqual(watch.evaluate_strategy_watch(payload), [])
                status = watch.strategy_watch_coverage_status(payload)[0]
                self.assertEqual(status["read_status"], "invalid")
                self.assertTrue(status["errors"])
                self.assertNotIn("/private/", json.dumps(status))
                self.assertNotIn("a" * 64, json.dumps(status))

    def test_actual_and_reference_bindings_cannot_be_invented_from_dates(self):
        for key, value in [("actual_start_date", "2026-09-08"), ("actual_end_date", None),
                           ("actual_observation_count", True), ("calendar_id", ""),
                           ("reference_calendar_id", "XNYS"), ("periods_per_year", float("nan")),
                           ("periods_per_year", True), ("reference_periods_per_year", 252),
                           ("reference_coverage", None), ("comparable", "true"), ("reason", "invented")]:
            with self.subTest(key=key):
                payload = coverage_export_fixture()
                payload["snapshots"][0]["payload"]["metadata"]["interval_comparison"][key] = value
                self.assertEqual(watch.evaluate_strategy_watch(payload), [])
                self.assertEqual(watch.strategy_watch_coverage_status(payload)[0]["read_status"], "invalid")
        for key in ["actual_start_date", "actual_observation_count", "calendar_id", "periods_per_year"]:
            payload = coverage_export_fixture()
            del payload["snapshots"][0]["payload"]["metadata"]["interval_comparison"][key]
            self.assertEqual(watch.strategy_watch_coverage_status(payload)[0]["read_status"], "invalid")

    def test_empty_new_container_has_explicit_invalid_coverage_status(self):
        payload=coverage_export_fixture()
        payload["snapshots"]=[]
        self.assertEqual(watch.evaluate_strategy_watch(payload),[])
        self.assertEqual(watch.strategy_watch_coverage_status(payload)[0]["read_status"],"invalid")

    def test_missing_reference_is_unknown_and_preserves_current_window(self):
        payload = coverage_export_fixture()
        payload["snapshots"][0]["payload"]["metadata"]["interval_comparison"].update(
            comparable=False, reason="interval_coverage_unavailable", reference_coverage=None)
        status = watch.strategy_watch_coverage_status(payload)[0]
        self.assertEqual(status["read_status"], "valid")
        self.assertEqual(status["public_comparison_status"], "unknown")
        self.assertEqual(status["effective_window"]["return_count"], 4)

    def test_envelope_mismatch_nesting_privacy_and_v2_relabel_cannot_downgrade(self):
        variants=[]
        p=coverage_export_fixture()
        p["schema_version"]="strategy_performance.coverage_envelope.v999"
        variants.append(p)
        p=coverage_export_fixture()
        p["snapshots"][0]["schema_version"]="strategy_performance.v2"
        variants.append(p)
        p=coverage_export_fixture()
        p["snapshots"][0]["payload"] = deepcopy(p["snapshots"][0])
        variants.append(p)
        p=coverage_export_fixture()
        p["snapshots"][0]["payload"]["metadata"]["account_scope_sha256"]="a"*64
        variants.append(p)
        p=coverage_export_fixture()
        p["snapshots"][0]["payload"]["metadata"]["provenance"]["snapshot"]["path"]="/private/account.json"
        variants.append(p)
        p=coverage_export_fixture()["snapshots"][0]["payload"]
        variants.append(p)
        for payload in variants:
            with self.subTest(payload=payload):
                with patch.object(watch, "evaluate_strategy_metrics") as evaluator:
                    self.assertEqual(watch.evaluate_strategy_watch(payload), [])
                    evaluator.assert_not_called()
                status=watch.strategy_watch_coverage_status(payload)[0]
                self.assertEqual(status["read_status"], "invalid")
                self.assertNotIn("/private/", json.dumps(status))

    def test_container_inner_identity_privacy_and_serialized_context_are_retained(self):
        variants=[]
        for location in ["container", "inner"]:
            for key in ["account_scope_sha256", "path"]:
                payload=coverage_export_fixture()
                target=payload if location == "container" else payload["snapshots"][0]["payload"]
                target[key]="/private/account.json"
                variants.append(payload)
        payload=coverage_export_fixture()
        payload["snapshots"][0]["payload"]["domain"]="us_equity"
        variants.append(payload)
        payload=coverage_export_fixture()
        payload["snapshots"][0]["payload"]["repository"]="QuantStrategyLab/Other"
        variants.append(payload)
        payload=coverage_export_fixture()["snapshots"][0]["payload"]
        snapshot=watch.StrategyWatchSnapshot.from_dict(payload)
        variants.append(snapshot.to_dict())
        payload=coverage_export_fixture()
        metadata=payload["snapshots"][0]["payload"].pop("metadata")
        payload["schema_version"]="strategy_performance.v2"
        payload["snapshots"]=[payload["snapshots"][0]["payload"]]
        payload["metadata"]=metadata
        variants.append(payload)
        for payload in variants:
            with self.subTest(payload=payload):
                self.assertEqual(watch.evaluate_strategy_watch(payload),[])
                status=watch.strategy_watch_coverage_status(payload)[0]
                self.assertEqual(status["read_status"],"invalid")
                self.assertNotIn("/private/",json.dumps(status))

    def test_missing_reference_does_not_hide_invalid_current_binding(self):
        for key,value in [("actual_observation_count",True),("actual_start_date",None),("calendar_id",""),("periods_per_year",float("nan"))]:
            payload=coverage_export_fixture()
            comparison=payload["snapshots"][0]["payload"]["metadata"]["interval_comparison"]
            comparison.update(comparable=False,reason="interval_coverage_unavailable",reference_coverage=None)
            comparison[key]=value
            self.assertEqual(watch.strategy_watch_coverage_status(payload)[0]["read_status"],"invalid")

    def test_root_missing_reference_repro_checks_each_current_input_independently(self):
        for location,key,value in [("current_metrics","observation_count",99),("current_metrics","sharpe",float("nan")),("metadata","window_start","1900-01-01"),("metadata","window_end","1900-01-01")]:
            payload=coverage_export_fixture()
            inner=payload["snapshots"][0]["payload"]
            inner["metadata"]["interval_comparison"].update(comparable=False,reason="interval_coverage_unavailable",reference_coverage=None)
            inner[location][key]=value
            with self.subTest(key=key):
                self.assertEqual(watch.strategy_watch_coverage_status(payload)[0]["read_status"],"invalid")

    def test_forged_p3_evidence_cannot_promote_coverage_to_research(self):
        payload=coverage_export_fixture()
        inner=payload["snapshots"][0]["payload"]
        inner.update(domain="crypto", candidate_kind="individual", research_task_evidence={
            "p1_input_digest":"a"*64,"p2_config_digest":"b"*64,"p3_evidence_id":"c"*64,
            "strategy_revision":"d"*40,"producer_revision":"e"*40})
        snapshot=watch.StrategyWatchSnapshot.from_dict(inner)
        finding=watch.StrategyWatchFinding(snapshot,"high",[],finding_type="metric_degradation")
        with patch.object(watch,"build_strategy_diagnosis_task") as builder:
            self.assertIsNone(watch.finding_to_research_task(finding))
            builder.assert_not_called()
        self.assertFalse(watch.research_task_context_available(inner))

    def test_mixed_envelope_preserves_legacy_contract_and_event_key(self):
        legacy={"repo":"QuantStrategyLab/CryptoStrategies","profile":"legacy",
            "schema_version":"strategy_performance.v2","metrics_kind":"performance",
            "current_metrics":{"sharpe":0.5,"cagr":0.1,"calmar":0.7,"win_rate":0.52,"max_dd":0.12},
            "baseline_metrics":{"sharpe":1.0,"cagr":0.2,"calmar":1.0,"win_rate":0.58,"max_dd":0.08}}
        baseline=watch.evaluate_strategy_watch(legacy)[0]
        payload=coverage_export_fixture()
        payload["snapshots"].append({"schema_version":payload["schema_version"],"metrics_kind":"performance","payload":legacy})
        findings=watch.evaluate_strategy_watch(payload)
        self.assertEqual(len(findings),1)
        self.assertEqual(findings[0].snapshot.to_dict(),baseline.snapshot.to_dict())
        self.assertEqual(watch.finding_event_key(findings[0]),watch.finding_event_key(baseline))
        self.assertEqual(len(baseline.snapshot.to_dict()),12)
        self.assertEqual(watch.finding_event_key(baseline), "f20b8d24ad51")
        self.assertEqual(json.dumps(baseline.snapshot.to_dict(), separators=(",", ":")),
            '{"repo":"QuantStrategyLab/CryptoStrategies","profile":"legacy","plugin":"","candidate_kind":"individual","domain":"","schema_version":"strategy_performance.v2","metrics_kind":"performance","current_metrics":{"sharpe":0.5,"cagr":0.1,"calmar":0.7,"win_rate":0.52,"max_dd":0.12},"baseline_metrics":{"sharpe":1.0,"cagr":0.2,"calmar":1.0,"win_rate":0.58,"max_dd":0.08},"research_task_evidence":{},"source":"","generated_at":""}')
        bad=deepcopy(payload)
        del bad["snapshots"][1]["payload"]["baseline_metrics"]["cagr"]
        self.assertEqual(watch.evaluate_strategy_watch(bad)[0].finding_type,"data_quality")


if __name__ == "__main__":
    unittest.main()
