from __future__ import annotations

import unittest

from quant_platform_kit.common.runtime_target import (
    RuntimeTarget,
    build_runtime_context_fields,
    build_runtime_target,
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

    def test_runtime_target_rejects_incomplete_strategy_release_identity(self) -> None:
        with self.assertRaisesRegex(ValueError, "strategy_release is missing required fields"):
            build_runtime_target(
                platform_id="longbridge",
                strategy_profile="soxl_soxx_trend_income",
                dry_run_only=True,
                strategy_release={"release_id": "soxl-p2-v3"},
            )

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
