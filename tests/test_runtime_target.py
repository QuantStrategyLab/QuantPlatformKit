from __future__ import annotations

import unittest

from quant_platform_kit.common.runtime_target import (
    build_runtime_context_fields,
    build_runtime_target,
    resolve_runtime_target_from_env,
)


class RuntimeTargetTests(unittest.TestCase):
    def test_build_runtime_target_normalizes_selectors_and_mode(self) -> None:
        target = build_runtime_target(
            platform_id=" longbridge ",
            strategy_profile=" soxl_soxx_trend_income ",
            dry_run_only=True,
            deployment_selector=" HK ",
            account_selector=(" U123 ", "", None),
            account_scope=" hk ",
            service_name=" longbridge-quant-hk-service ",
        )

        self.assertEqual(target.platform_id, "longbridge")
        self.assertEqual(target.strategy_profile, "soxl_soxx_trend_income")
        self.assertEqual(target.execution_mode, "paper")
        self.assertEqual(target.deployment_selector, "HK")
        self.assertEqual(target.account_selector, ("U123",))
        self.assertEqual(target.account_scope, "hk")
        self.assertEqual(target.service_name, "longbridge-quant-hk-service")

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

    def test_resolve_runtime_target_from_env_prefers_structured_json(self) -> None:
        target = resolve_runtime_target_from_env(
            env={
                "RUNTIME_TARGET_JSON": (
                    '{"platform_id":"longbridge","strategy_profile":"global_etf_rotation",'
                    '"dry_run_only":true,"deployment_selector":"HK","account_selector":["HK"],'
                    '"account_scope":"HK","service_name":"longbridge-quant-hk-service",'
                    '"execution_mode":"paper"}'
                )
            },
            platform_id="longbridge",
            strategy_profile="fallback_profile",
            dry_run_only=False,
            deployment_selector="SG",
            account_selector=("SG",),
            account_scope="SG",
            service_name="fallback-service",
        )

        self.assertEqual(target.platform_id, "longbridge")
        self.assertEqual(target.strategy_profile, "global_etf_rotation")
        self.assertTrue(target.dry_run_only)
        self.assertEqual(target.execution_mode, "paper")
        self.assertEqual(target.deployment_selector, "HK")
        self.assertEqual(target.account_selector, ("HK",))
        self.assertEqual(target.account_scope, "HK")
        self.assertEqual(target.service_name, "longbridge-quant-hk-service")

    def test_resolve_runtime_target_from_env_rejects_mismatched_execution_mode(self) -> None:
        with self.assertRaisesRegex(ValueError, "execution_mode does not match dry_run_only"):
            resolve_runtime_target_from_env(
                env={
                    "RUNTIME_TARGET_JSON": (
                        '{"platform_id":"schwab","strategy_profile":"tqqq_growth_income",'
                        '"dry_run_only":false,"execution_mode":"paper"}'
                    )
                },
                platform_id="schwab",
                strategy_profile="tqqq_growth_income",
                dry_run_only=False,
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
                platform_id="longbridge",
                strategy_profile="global_etf_rotation",
                dry_run_only=False,
            )

    def test_build_runtime_context_fields_merges_runtime_target_without_overwriting_fields(self) -> None:
        target = build_runtime_target(
            platform_id="longbridge",
            strategy_profile="soxl_soxx_trend_income",
            dry_run_only=True,
            service_name="longbridge-platform",
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
