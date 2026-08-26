"""Tests for strategy_lifecycle.cli."""

from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from quant_platform_kit.strategy_lifecycle import cli
from quant_platform_kit.strategy_lifecycle.performance_store import PerformanceStore


class LifecycleCliTests(unittest.TestCase):

    def test_autopilot_command_delegates_to_qpk_lifecycle(self) -> None:
        calls = []

        def fake_load_callable(module_name: str, function_name: str):
            calls.append((module_name, function_name))

            def fake_run_auto_pilot_cycle(domain: str, **kwargs):
                return {
                    "domain": domain,
                    "snapshots_count": 1,
                    "drifts_checked": 2,
                    "drifts_alerting": 0,
                    "issues_created": 0,
                    "actions": [],
                    "kwargs": kwargs,
                }

            return fake_run_auto_pilot_cycle

        with patch.object(cli, "_load_callable", fake_load_callable):
            result = cli.main(["autopilot", "--domain", "us_equity", "--dry-run", "--no-issues"])

        self.assertEqual(result, 0)
        self.assertEqual(
            calls,
            [
                (
                    "quant_platform_kit.strategy_lifecycle.codex_integration",
                    "run_auto_pilot_cycle",
                )
            ],
        )

    def test_monitor_command_passes_optional_filters(self) -> None:
        observed = {}

        def fake_load_callable(_module_name: str, _function_name: str):
            def fake_run_monitor(**kwargs):
                observed.update(kwargs)
                return [object()]

            return fake_run_monitor

        with patch.object(cli, "_load_callable", fake_load_callable):
            result = cli.main([
                "monitor",
                "--domain",
                "hk_equity",
                "--strategy",
                "hk_combo",
                "--output-dir",
                "out",
            ])

        self.assertEqual(result, 0)
        self.assertEqual(
            observed,
            {
                "domain": "hk_equity",
                "strategy_profile": "hk_combo",
                "output_dir": "out",
            },
        )

    def test_monitor_command_passes_live_stream_filter_only_when_requested(self) -> None:
        observed = {}

        def fake_load_callable(_module_name: str, _function_name: str):
            def fake_run_monitor(**kwargs):
                observed.update(kwargs)
                return [object()]

            return fake_run_monitor

        with patch.object(cli, "_load_callable", fake_load_callable):
            result = cli.main([
                "monitor",
                "--domain",
                "us_equity",
                "--strategy",
                "soxl_soxx_trend_income",
                "--live-stream-id",
                "longbridge-quant-sg-service",
            ])

        self.assertEqual(result, 0)
        self.assertEqual(observed["live_stream_id"], "longbridge-quant-sg-service")

    def test_drift_command_counts_status_values(self) -> None:
        statuses = [
            SimpleNamespace(status=SimpleNamespace(value="critical")),
            SimpleNamespace(status=SimpleNamespace(value="review")),
            SimpleNamespace(status=SimpleNamespace(value="healthy")),
        ]
        published = {}

        def fake_load_callable(_module_name: str, function_name: str):
            if function_name == "run_drift_detection":
                return lambda **_kwargs: statuses
            if function_name == "build_drift_alert":
                return lambda result: result if result.status.value != "healthy" else None
            if function_name == "publish_drift_alerts":
                def fake_publish(events, **kwargs):
                    published["events"] = list(events)
                    published["kwargs"] = kwargs
                    return {"telegram": len(published["events"])}

                return fake_publish
            raise AssertionError(function_name)

        with patch.object(cli, "_load_callable", fake_load_callable):
            result = cli.main(["drift", "--domain", "crypto"])

        self.assertEqual(result, 0)
        self.assertEqual(len(published["events"]), 2)

    def test_drift_command_allows_explicit_legacy_baseline_migration(self) -> None:
        observed = {}

        def fake_load_callable(_module_name: str, function_name: str):
            if function_name == "run_drift_detection":
                def fake_run_drift_detection(**kwargs):
                    observed.update(kwargs)
                    return []

                return fake_run_drift_detection
            if function_name == "build_drift_alert":
                return lambda _result: None
            if function_name == "publish_drift_alerts":
                return lambda _events, **_kwargs: {}
            raise AssertionError(function_name)

        environment_store = PerformanceStore(cloud_bucket="candidate-bucket", cloud_prefix="candidate")
        with (
            patch.object(cli, "_load_callable", fake_load_callable),
            patch.object(PerformanceStore, "from_env", return_value=environment_store),
        ):
            result = cli.main([
                "drift",
                "--baseline-local-root",
                "accepted-baselines",
                "--allow-legacy-baseline-history",
            ])

        self.assertEqual(result, 0)
        self.assertEqual(observed["baseline_lineage_policy"], "migration")
        self.assertEqual(observed["baseline_store"].local_root, Path("accepted-baselines"))
        self.assertEqual(observed["baseline_store"].cloud_bucket, "")
        self.assertEqual(observed["baseline_store"].cloud_prefix, "")

    def test_drift_command_uses_explicit_baseline_bucket(self) -> None:
        observed = {}

        def fake_load_callable(_module_name: str, function_name: str):
            if function_name == "run_drift_detection":
                def fake_run_drift_detection(**kwargs):
                    observed.update(kwargs)
                    return []

                return fake_run_drift_detection
            if function_name == "build_drift_alert":
                return lambda _result: None
            if function_name == "publish_drift_alerts":
                return lambda _events, **_kwargs: {}
            raise AssertionError(function_name)

        with patch.object(cli, "_load_callable", fake_load_callable):
            result = cli.main(["drift", "--baseline-bucket", "gs://accepted-bucket/lifecycle"])

        self.assertEqual(result, 0)
        self.assertEqual(observed["baseline_store"].cloud_bucket, "accepted-bucket")
        self.assertEqual(observed["baseline_store"].cloud_prefix, "lifecycle")
        self.assertIsNone(observed["baseline_store"].local_root)

    def test_update_returns_non_zero_for_error_stage(self) -> None:
        def fake_load_callable(_module_name: str, _function_name: str):
            return lambda **_kwargs: {"stage": "error", "reason": "missing proposal"}

        with patch.object(cli, "_load_callable", fake_load_callable):
            result = cli.main(["update", "--proposal", "gs://missing/proposal.json"])

        self.assertEqual(result, 1)

    def test_export_performance_command_passes_expected_args(self) -> None:
        observed = {}

        def fake_load_callable(_module_name: str, _function_name: str):
            def fake_export(domain: str, **kwargs):
                observed["domain"] = domain
                observed.update(kwargs)
                return {"snapshots": [object()]}

            return fake_export

        with patch.object(cli, "_load_callable", fake_load_callable):
            result = cli.main([
                "export-performance",
                "--domain",
                "crypto",
                "--repo",
                "QuantStrategyLab/CryptoLivePoolPipelines",
                "--profile",
                "crypto_live_pool_rotation",
                "--output",
                "data/output/strategy_metrics.json",
            ])

        self.assertEqual(result, 0)
        self.assertEqual(
            observed,
            {
                "domain": "crypto",
                "repo": "QuantStrategyLab/CryptoLivePoolPipelines",
                "strategy_profiles": ["crypto_live_pool_rotation"],
                "output_path": "data/output/strategy_metrics.json",
            },
        )

    def test_doctor_command_returns_non_zero_when_not_ok(self) -> None:
        def fake_load_callable(_module_name: str, _function_name: str):
            return lambda domain, **_kwargs: {
                "ok": False,
                "profiles_discovered": 1,
                "issues": ["missing lifecycle backtest"],
                "domain": domain,
            }

        with patch.object(cli, "_load_callable", fake_load_callable):
            result = cli.main(["doctor", "--domain", "us_equity", "--require-backtest"])

        self.assertEqual(result, 1)

    def test_lifecycle_command_runs_real_steps(self) -> None:
        calls = []
        drift_kwargs = {}

        def fake_load_callable(_module_name: str, function_name: str):
            if function_name == "run_monitor":
                def fake_monitor(**_kwargs):
                    calls.append("monitor")
                    return []

                return fake_monitor
            if function_name == "run_drift_detection":
                def fake_drift(**kwargs):
                    calls.append("drift")
                    drift_kwargs.update(kwargs)
                    return []

                return fake_drift
            if function_name == "publish_drift_alerts":
                return lambda events, **_kwargs: {}
            if function_name == "build_drift_alert":
                return lambda _result: None
            if function_name == "build_dashboard":
                def fake_dashboard(**_kwargs):
                    calls.append("dashboard")
                    return {"strategy_count": 0}

                return fake_dashboard
            raise AssertionError(function_name)

        with patch.object(cli, "_load_callable", fake_load_callable):
            result = cli.main([
                "lifecycle",
                "--domain",
                "cn_equity",
                "--skip-optimization",
                "--baseline-local-root",
                "accepted-baselines",
                "--strict-baseline-lineage",
            ])

        self.assertEqual(result, 0)
        self.assertEqual(calls, ["monitor", "drift", "dashboard"])
        self.assertEqual(drift_kwargs["baseline_store"].local_root, Path("accepted-baselines"))
        self.assertEqual(drift_kwargs["baseline_lineage_policy"], "strict")

    def test_lifecycle_command_stops_after_monitor_failure(self) -> None:
        calls = []

        def fake_load_callable(_module_name: str, function_name: str):
            if function_name == "run_monitor":
                def fake_monitor(**_kwargs):
                    calls.append("monitor")
                    raise RuntimeError("snapshot unavailable")

                return fake_monitor
            raise AssertionError(function_name)

        with patch.object(cli, "_load_callable", fake_load_callable):
            result = cli.main(["lifecycle", "--domain", "us_equity"])

        self.assertEqual(result, 1)
        self.assertEqual(calls, ["monitor"])

    def test_lifecycle_command_optimizes_only_explicit_strategy(self) -> None:
        calls = []

        def fake_load_callable(_module_name: str, function_name: str):
            if function_name == "run_monitor":
                return lambda **_kwargs: calls.append("monitor") or []
            if function_name == "run_drift_detection":
                return lambda **_kwargs: calls.append("drift") or []
            if function_name == "build_drift_alert":
                return lambda _result: None
            if function_name == "publish_drift_alerts":
                return lambda _events, **_kwargs: {}
            if function_name == "run_optimization":
                return lambda **kwargs: calls.append(("optimize", kwargs["strategy_profile"])) or SimpleNamespace(
                    recommendation="keep",
                    improvement_score=0.0,
                )
            if function_name == "build_dashboard":
                return lambda **_kwargs: calls.append("dashboard") or {"strategy_count": 0}
            raise AssertionError(function_name)

        with patch.object(cli, "_load_callable", fake_load_callable):
            result = cli.main(["lifecycle", "--domain", "us_equity", "--strategy", "tqqq_core_only_p2_v5"])

        self.assertEqual(result, 0)
        self.assertEqual(calls, ["monitor", "drift", ("optimize", "tqqq_core_only_p2_v5"), "dashboard"])

    def test_drift_rejects_conflicting_baseline_lineage_flags(self) -> None:
        with self.assertRaises(SystemExit):
            cli.main(["drift", "--strict-baseline-lineage", "--allow-legacy-baseline-history"])

    def test_error_returns_non_zero(self) -> None:
        def fake_load_callable(_module_name: str, _function_name: str):
            raise RuntimeError("boom")

        with patch.object(cli, "_load_callable", fake_load_callable):
            result = cli.main(["dashboard"])

        self.assertEqual(result, 1)


if __name__ == "__main__":
    unittest.main()
