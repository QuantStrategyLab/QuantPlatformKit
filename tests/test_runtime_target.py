from __future__ import annotations

import unittest
from types import SimpleNamespace

from quant_platform_kit.common.runtime_target import (
    RuntimeExecutionEnvironment,
    RuntimeTarget,
    build_runtime_context_fields,
    build_runtime_target,
    resolve_runtime_execution_environment,
    resolve_runtime_target_from_env,
)


class RuntimeTargetTests(unittest.TestCase):
    def test_runtime_target_preserves_existing_execution_windows_positional_slot(self) -> None:
        windows = {"execution": {"enabled": True, "mode": "paper"}}

        target = RuntimeTarget(
            "longbridge",
            "global_etf_rotation",
            True,
            "HK",
            ("HK",),
            "HK",
            "longbridge-quant-hk-service",
            windows,
        )

        self.assertEqual(target.execution_windows, windows)
        self.assertIsNone(target.market)

    def test_build_runtime_target_normalizes_selectors_and_mode(self) -> None:
        target = build_runtime_target(
            platform_id=" longbridge ",
            strategy_profile=" soxl_soxx_trend_income ",
            dry_run_only=True,
            deployment_selector=" HK ",
            account_selector=(" U123 ", "", None),
            account_scope=" hk ",
            service_name=" longbridge-quant-hk-service ",
            execution_windows={
                "precheck": {"enabled": True, "offset_minutes": 15, "mode": "notify_only"},
                "execution": {"enabled": True, "offset_minutes": 15, "mode": "paper"},
            },
        )

        self.assertEqual(target.platform_id, "longbridge")
        self.assertEqual(target.strategy_profile, "soxl_soxx_trend_income")
        self.assertEqual(target.execution_mode, "paper")
        self.assertEqual(target.execution_environment, RuntimeExecutionEnvironment.DRY_RUN)
        self.assertEqual(target.deployment_selector, "HK")
        self.assertEqual(target.account_selector, ("U123",))
        self.assertEqual(target.account_scope, "hk")
        self.assertEqual(target.service_name, "longbridge-quant-hk-service")
        self.assertEqual(target.execution_windows["precheck"]["offset_minutes"], 15)
        self.assertEqual(target.execution_windows["execution"]["mode"], "paper")

    def test_build_runtime_target_supports_live_mode_without_account_selector(self) -> None:
        target = build_runtime_target(
            platform_id="schwab",
            strategy_profile="tqqq_growth_income",
            dry_run_only=False,
            deployment_selector=None,
            account_selector=None,
            account_scope=None,
            service_name=None,
        )

        self.assertEqual(target.execution_mode, "live")
        self.assertEqual(target.execution_environment, RuntimeExecutionEnvironment.LIVE)
        self.assertEqual(target.account_selector, ())

    def test_runtime_target_carries_complete_strategy_release_identity(self) -> None:
        digest = "a" * 64
        target = build_runtime_target(
            platform_id="longbridge",
            strategy_profile="soxl_soxx_trend_income",
            dry_run_only=True,
            strategy_release={
                "release_id": "soxl-p2-v3.20260824",
                "manifest_sha256": digest,
                "strategy_revision": "2e3bb51",
                "config_sha256": digest,
                "risk_policy_sha256": digest,
                "evidence_sha256": digest,
                "plugin_bundle_sha256": digest,
                "effective_session": "2026-08-25",
            },
        )

        self.assertEqual(target.strategy_release.release_id, "soxl-p2-v3.20260824")
        self.assertEqual(target.to_dict()["strategy_release"]["effective_session"], "2026-08-25")

    def test_runtime_target_carries_redacted_account_identity_policy(self) -> None:
        target = build_runtime_target(
            platform_id="longbridge",
            strategy_profile="soxl_soxx_trend_income",
            dry_run_only=True,
            account_identity={
                "enforcement": "observe",
                "expected_account_types": ["cash"],
            },
        )

        self.assertEqual(target.account_identity["enforcement"], "observe")
        self.assertEqual(target.to_dict()["account_identity"]["expected_account_types"], ["cash"])

    def test_runtime_target_rejects_incomplete_strategy_release_identity(self) -> None:
        with self.assertRaisesRegex(ValueError, "strategy_release is missing required fields"):
            build_runtime_target(
                platform_id="longbridge",
                strategy_profile="soxl_soxx_trend_income",
                dry_run_only=True,
                strategy_release={"release_id": "soxl-p2-v3"},
            )

    def test_runtime_target_accepts_frozen_legacy_live_continuity_baseline(self) -> None:
        base_target = build_runtime_target(
            platform_id="schwab",
            strategy_profile="soxl_soxx_trend_income",
            dry_run_only=False,
            deployment_selector="default",
            account_selector=("default",),
            account_scope="default",
            service_name="charles-schwab-quant-service",
        )
        from quant_platform_kit.common.live_continuity import runtime_target_fingerprint

        target_payload = base_target.to_dict()
        target_payload.pop("execution_mode")
        target = build_runtime_target(
            **target_payload,
            live_continuity={
                "state": "ACTIVE_LKG",
                "baseline_kind": "legacy_authorized",
                "baseline_id": "soxl-schwab-lkg-20260830",
                "baseline_target_sha256": runtime_target_fingerprint(base_target.to_dict()),
                "captured_at": "2026-08-30",
            },
        )

        self.assertTrue(target.live_continuity.permits_standard_execution)
        self.assertEqual(target.to_dict()["live_continuity"]["state"], "ACTIVE_LKG")

    def test_runtime_target_rejects_continuity_fingerprint_drift(self) -> None:
        with self.assertRaisesRegex(ValueError, "does not match the runtime target"):
            build_runtime_target(
                platform_id="schwab",
                strategy_profile="soxl_soxx_trend_income",
                dry_run_only=False,
                live_continuity={
                    "state": "ACTIVE_LKG",
                    "baseline_kind": "legacy_authorized",
                    "baseline_id": "soxl-schwab-lkg-20260830",
                    "baseline_target_sha256": "a" * 64,
                    "captured_at": "2026-08-30",
                },
            )

    def test_live_continuity_fails_closed_for_non_standard_execution_states(self) -> None:
        from quant_platform_kit.common.live_continuity import (
            LiveContinuity,
            runtime_target_permits_standard_execution,
        )

        active = SimpleNamespace(
            live_continuity=LiveContinuity(
                state="ACTIVE_LKG",
                baseline_kind="legacy_authorized",
                baseline_id="soxl-schwab-lkg-20260830",
                baseline_target_sha256="a" * 64,
                captured_at="2026-08-30",
            )
        )
        paused = SimpleNamespace(
            live_continuity=LiveContinuity(
                state="PAUSED",
                baseline_kind="legacy_authorized",
                baseline_id="soxl-schwab-lkg-20260830",
                baseline_target_sha256="a" * 64,
                captured_at="2026-08-30",
            )
        )

        self.assertTrue(runtime_target_permits_standard_execution(SimpleNamespace()))
        self.assertTrue(runtime_target_permits_standard_execution(active))
        self.assertFalse(runtime_target_permits_standard_execution(paused))

    def test_resolve_runtime_target_from_env_prefers_structured_json(self) -> None:
        target = resolve_runtime_target_from_env(
            env={
                "RUNTIME_TARGET_JSON": (
                    '{"platform_id":"longbridge","strategy_profile":"global_etf_rotation",'
                    '"dry_run_only":true,"deployment_selector":"HK","account_selector":["HK"],'
                    '"account_scope":"HK","service_name":"longbridge-quant-hk-service",'
                    '"market":"HK","market_calendar":"XHKG",'
                    '"market_timezone":"Asia/Hong_Kong",'
                    '"scheduler":{"timezone":"Asia/Hong_Kong","main_time":"45 15 * * *"},'
                    '"execution_mode":"paper","execution_windows":{"precheck":{"enabled":true,'
                    '"offset_minutes":15,"mode":"notify_only"},"execution":{"enabled":true,'
                    '"offset_minutes":15,"mode":"paper"}}}'
                )
            },
        )

        self.assertEqual(target.platform_id, "longbridge")
        self.assertEqual(target.strategy_profile, "global_etf_rotation")
        self.assertTrue(target.dry_run_only)
        self.assertEqual(target.execution_mode, "paper")
        self.assertEqual(target.execution_environment, RuntimeExecutionEnvironment.DRY_RUN)
        self.assertEqual(target.deployment_selector, "HK")
        self.assertEqual(target.account_selector, ("HK",))
        self.assertEqual(target.account_scope, "HK")
        self.assertEqual(target.service_name, "longbridge-quant-hk-service")
        self.assertEqual(target.market, "HK")
        self.assertEqual(target.market_calendar, "XHKG")
        self.assertEqual(target.market_timezone, "Asia/Hong_Kong")
        self.assertEqual(target.scheduler["main_time"], "45 15 * * *")
        self.assertTrue(target.execution_windows["precheck"]["enabled"])
        self.assertEqual(target.execution_windows["execution"]["offset_minutes"], 15)

    def test_resolve_runtime_target_from_env_rejects_mismatched_execution_mode(self) -> None:
        with self.assertRaisesRegex(ValueError, "execution_mode does not match dry_run_only"):
            resolve_runtime_target_from_env(
                env={
                    "RUNTIME_TARGET_JSON": (
                        '{"platform_id":"schwab","strategy_profile":"tqqq_growth_income",'
                        '"dry_run_only":false,"execution_mode":"paper"}'
                )
            },
            expected_platform_id="schwab",
        )

    def test_runtime_target_supports_explicit_broker_paper_environment(self) -> None:
        target = resolve_runtime_target_from_env(
            env={
                "RUNTIME_TARGET_JSON": (
                    '{"platform_id":"ibkr","strategy_profile":"global_etf_rotation",'
                    '"dry_run_only":false,"execution_mode":"live",'
                    '"execution_environment":"paper"}'
                )
            },
            expected_platform_id="ibkr",
        )

        self.assertFalse(target.dry_run_only)
        self.assertEqual(target.execution_mode, "live")
        self.assertEqual(target.execution_environment, RuntimeExecutionEnvironment.PAPER)
        self.assertEqual(target.to_dict()["execution_environment"], "paper")

    def test_runtime_execution_environment_rejects_ambiguous_combinations(self) -> None:
        with self.assertRaisesRegex(ValueError, "requires execution_environment=dry_run"):
            resolve_runtime_execution_environment(
                dry_run_only=True,
                execution_environment="paper",
            )
        with self.assertRaisesRegex(ValueError, "requires dry_run_only=true"):
            resolve_runtime_execution_environment(
                dry_run_only=False,
                execution_environment="dry_run",
            )

    def test_resolve_runtime_target_from_env_rejects_partial_market_metadata(self) -> None:
        with self.assertRaisesRegex(ValueError, "market metadata must include"):
            resolve_runtime_target_from_env(
                env={
                    "RUNTIME_TARGET_JSON": (
                        '{"platform_id":"schwab","strategy_profile":"tqqq_growth_income",'
                        '"dry_run_only":false,"market":"US"}'
                    )
                },
                expected_platform_id="schwab",
            )

    def test_build_runtime_target_rejects_invalid_market_timezone(self) -> None:
        with self.assertRaisesRegex(ValueError, "invalid market_timezone"):
            build_runtime_target(
                platform_id="schwab",
                strategy_profile="tqqq_growth_income",
                dry_run_only=False,
                market="US",
                market_calendar="NYSE",
                market_timezone="../New_York",
            )

    def test_resolve_runtime_target_from_env_rejects_mismatched_platform(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "platform_id does not match the runtime platform",
        ):
            resolve_runtime_target_from_env(
                env={
                    "RUNTIME_TARGET_JSON": (
                        '{"platform_id":"ibkr","strategy_profile":"global_etf_rotation",'
                        '"dry_run_only":false}'
                )
            },
                expected_platform_id="longbridge",
            )

    def test_resolve_runtime_target_from_env_requires_structured_json(self) -> None:
        with self.assertRaisesRegex(EnvironmentError, "RUNTIME_TARGET_JSON"):
            resolve_runtime_target_from_env(env={})

    def test_build_runtime_context_fields_merges_runtime_target_without_overwriting_fields(self) -> None:
        target = build_runtime_target(
            platform_id="longbridge",
            strategy_profile="soxl_soxx_trend_income",
            dry_run_only=True,
            service_name="longbridge-platform",
            execution_windows={
                "precheck": {"enabled": True, "offset_minutes": 15, "mode": "notify_only"},
                "execution": {"enabled": True, "offset_minutes": 15, "mode": "paper"},
            },
        )

        fields = build_runtime_context_fields(
            {
                "service_name": "override-me",
                "account_scope": "HK",
            },
            runtime_target=target,
        )

        self.assertEqual(fields["service_name"], "override-me")
        self.assertEqual(fields["account_scope"], "HK")
        self.assertEqual(fields["runtime_target"]["platform_id"], "longbridge")
        self.assertEqual(fields["runtime_target"]["execution_mode"], "paper")
        self.assertEqual(fields["runtime_target"]["execution_windows"]["precheck"]["enabled"], True)
