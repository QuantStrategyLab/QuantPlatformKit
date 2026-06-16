import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from quant_platform_kit.common.notification_localization import STRATEGY_PLUGIN_I18N
from quant_platform_kit.common.models import PortfolioSnapshot
from quant_platform_kit.common.strategy_plugins import (
    CRISIS_RESPONSE_SHADOW_SUPPORTED_STRATEGIES,
    DEFAULT_STRATEGY_PLUGIN_DEFINITIONS,
    GENERAL_MARKET_REGIME_NOTIFICATION_TARGET,
    MACRO_RISK_GOVERNOR_SUPPORTED_STRATEGIES,
    PLUGIN_CRISIS_RESPONSE_SHADOW,
    PLUGIN_MARKET_REGIME_CONTROL,
    PLUGIN_MACRO_RISK_GOVERNOR,
    PLUGIN_TACO_REBOUND_SHADOW,
    PLUGIN_MODE_SHADOW,
    STRATEGY_PLUGIN_ALERT_CHANNEL_EMAIL,
    STRATEGY_PLUGIN_ALERT_CHANNEL_PUSH,
    STRATEGY_PLUGIN_ALERT_CHANNEL_SMS,
    STRATEGY_PLUGIN_ALERT_CHANNEL_TELEGRAM,
    STRATEGY_PLUGIN_NOTIFICATION_TARGETS,
    STRATEGY_PLUGIN_SCHEMA_VERSIONS,
    MARKET_REGIME_CONTROL_SUPPORTED_STRATEGIES,
    TACO_REBOUND_SHADOW_SUPPORTED_STRATEGIES,
    StrategyPluginDefinition,
    attach_strategy_plugin_metadata,
    build_strategy_plugin_alert_messages,
    build_strategy_plugin_notification_lines,
    build_strategy_plugin_report_payload,
    extract_strategy_plugin_localized_message,
    load_configured_strategy_plugin_notification_target_signals,
    load_configured_strategy_plugin_signals,
    load_strategy_plugin_signal,
    parse_strategy_plugin_notification_targets,
    parse_strategy_plugin_mounts,
    should_alert_strategy_plugin_signal,
    validate_strategy_plugin_compatibility,
    validate_strategy_plugin_notification_target,
    validate_strategy_plugin_schema_version,
    validate_strategy_plugin_signal_payload,
)


def _signal_payload(*, strategy="tqqq_growth_income", plugin="crisis_response_shadow", mode=PLUGIN_MODE_SHADOW):
    schema_versions = {
        PLUGIN_CRISIS_RESPONSE_SHADOW: "crisis_response_shadow.v1",
        PLUGIN_MARKET_REGIME_CONTROL: "market_regime_control.v1",
        PLUGIN_MACRO_RISK_GOVERNOR: "macro_risk_governor.v1",
        PLUGIN_TACO_REBOUND_SHADOW: "taco_rebound_shadow.v2",
    }
    return {
        "as_of": "2026-04-17",
        "strategy": strategy,
        "plugin": plugin,
        "mode": mode,
        "configured_mode": mode,
        "effective_mode": mode,
        "schema_version": schema_versions.get(plugin, "crisis_response_shadow.v1"),
        "canonical_route": "no_action",
        "suggested_action": "watch_only",
        "would_trade_if_enabled": False,
        "execution_controls": {
            "broker_order_allowed": False,
            "live_allocation_mutation_allowed": False,
            "repository_broker_write_allowed": False,
            "repository_allocation_mutation_allowed": False,
            "strategy_runtime_metadata_allowed": False,
        },
    }


class StrategyPluginsTests(unittest.TestCase):
    def test_parse_strategy_plugin_mounts_uses_artifact_mode_not_platform_mode(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            signal_path = Path(tmp_dir) / "latest_signal.json"
            raw = json.dumps(
                {
                    "strategy_plugins": [
                        {
                            "strategy": "tqqq_growth_income",
                            "plugin": "crisis_response_shadow",
                            "signal_path": str(signal_path),
                            "enabled": True,
                        }
                    ]
                }
            )

            mounts = parse_strategy_plugin_mounts(raw)

        self.assertEqual(len(mounts), 1)
        self.assertEqual(mounts[0].strategy, "tqqq_growth_income")
        self.assertEqual(mounts[0].plugin, "crisis_response_shadow")
        self.assertEqual(mounts[0].signal_path, str(signal_path))
        self.assertIsNone(mounts[0].expected_mode)

    def test_parse_strategy_plugin_mounts_rejects_platform_mode_selection(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            raw = json.dumps(
                [
                    {
                        "strategy": "tqqq_growth_income",
                        "plugin": "crisis_response_shadow",
                        "signal_path": str(Path(tmp_dir) / "latest_signal.json"),
                        "mode": "shadow",
                    }
                ]
            )

            with self.assertRaisesRegex(ValueError, "must not set mode"):
                parse_strategy_plugin_mounts(raw)

    def test_default_plugin_definition_limits_crisis_response_to_tqqq(self):
        definition = DEFAULT_STRATEGY_PLUGIN_DEFINITIONS[PLUGIN_CRISIS_RESPONSE_SHADOW]

        self.assertEqual(definition.supported_strategies, CRISIS_RESPONSE_SHADOW_SUPPORTED_STRATEGIES)
        self.assertEqual(
            definition.alert_channels,
            (
                STRATEGY_PLUGIN_ALERT_CHANNEL_EMAIL,
                STRATEGY_PLUGIN_ALERT_CHANNEL_SMS,
                STRATEGY_PLUGIN_ALERT_CHANNEL_PUSH,
                STRATEGY_PLUGIN_ALERT_CHANNEL_TELEGRAM,
            ),
        )
        validate_strategy_plugin_compatibility(
            strategy="tqqq_growth_income",
            plugin=PLUGIN_CRISIS_RESPONSE_SHADOW,
            mode=PLUGIN_MODE_SHADOW,
        )
        with self.assertRaisesRegex(
            ValueError,
            "crisis_response_shadow does not support strategy soxl_soxx_trend_income",
        ):
            validate_strategy_plugin_compatibility(
                strategy="soxl_soxx_trend_income",
                plugin=PLUGIN_CRISIS_RESPONSE_SHADOW,
                mode=PLUGIN_MODE_SHADOW,
            )

    def test_default_plugin_definition_limits_taco_rebound_to_tqqq_notifications(self):
        definition = DEFAULT_STRATEGY_PLUGIN_DEFINITIONS[PLUGIN_TACO_REBOUND_SHADOW]

        self.assertEqual(definition.supported_strategies, TACO_REBOUND_SHADOW_SUPPORTED_STRATEGIES)
        self.assertEqual(
            definition.alert_channels,
            (
                STRATEGY_PLUGIN_ALERT_CHANNEL_EMAIL,
                STRATEGY_PLUGIN_ALERT_CHANNEL_SMS,
                STRATEGY_PLUGIN_ALERT_CHANNEL_PUSH,
                STRATEGY_PLUGIN_ALERT_CHANNEL_TELEGRAM,
            ),
        )
        validate_strategy_plugin_compatibility(
            strategy="tqqq_growth_income",
            plugin=PLUGIN_TACO_REBOUND_SHADOW,
            mode=PLUGIN_MODE_SHADOW,
        )
        with self.assertRaisesRegex(
            ValueError,
            "taco_rebound_shadow does not support strategy soxl_soxx_trend_income",
        ):
            validate_strategy_plugin_compatibility(
                strategy="soxl_soxx_trend_income",
                plugin=PLUGIN_TACO_REBOUND_SHADOW,
                mode=PLUGIN_MODE_SHADOW,
            )

    def test_default_plugin_definition_limits_macro_risk_governor_to_tqqq(self):
        definition = DEFAULT_STRATEGY_PLUGIN_DEFINITIONS[PLUGIN_MACRO_RISK_GOVERNOR]

        self.assertEqual(definition.supported_strategies, MACRO_RISK_GOVERNOR_SUPPORTED_STRATEGIES)
        self.assertEqual(
            definition.alert_channels,
            (
                STRATEGY_PLUGIN_ALERT_CHANNEL_EMAIL,
                STRATEGY_PLUGIN_ALERT_CHANNEL_SMS,
                STRATEGY_PLUGIN_ALERT_CHANNEL_PUSH,
                STRATEGY_PLUGIN_ALERT_CHANNEL_TELEGRAM,
            ),
        )
        validate_strategy_plugin_compatibility(
            strategy="tqqq_growth_income",
            plugin=PLUGIN_MACRO_RISK_GOVERNOR,
            mode=PLUGIN_MODE_SHADOW,
        )
        with self.assertRaisesRegex(
            ValueError,
            "macro_risk_governor does not support strategy soxl_soxx_trend_income",
        ):
            validate_strategy_plugin_compatibility(
                strategy="soxl_soxx_trend_income",
                plugin=PLUGIN_MACRO_RISK_GOVERNOR,
                mode=PLUGIN_MODE_SHADOW,
            )

    def test_default_plugin_definition_supports_market_regime_control_for_approved_strategies(self):
        definition = DEFAULT_STRATEGY_PLUGIN_DEFINITIONS[PLUGIN_MARKET_REGIME_CONTROL]

        self.assertEqual(definition.supported_strategies, MARKET_REGIME_CONTROL_SUPPORTED_STRATEGIES)
        self.assertEqual(
            STRATEGY_PLUGIN_NOTIFICATION_TARGETS[PLUGIN_MARKET_REGIME_CONTROL],
            frozenset({GENERAL_MARKET_REGIME_NOTIFICATION_TARGET}),
        )
        self.assertEqual(definition.supported_schema_versions, STRATEGY_PLUGIN_SCHEMA_VERSIONS[PLUGIN_MARKET_REGIME_CONTROL])
        self.assertEqual(definition.default_schema_version, "market_regime_control.v1")
        self.assertFalse(definition.deprecated)
        self.assertEqual(
            definition.alert_channels,
            (
                STRATEGY_PLUGIN_ALERT_CHANNEL_EMAIL,
                STRATEGY_PLUGIN_ALERT_CHANNEL_SMS,
                STRATEGY_PLUGIN_ALERT_CHANNEL_PUSH,
                STRATEGY_PLUGIN_ALERT_CHANNEL_TELEGRAM,
            ),
        )
        for strategy in (
            "tqqq_growth_income",
            "soxl_soxx_trend_income",
            "global_etf_rotation",
            "russell_1000_multi_factor_defensive",
            "mega_cap_leader_rotation_top50_balanced",
        ):
            validate_strategy_plugin_compatibility(
                strategy=strategy,
                plugin=PLUGIN_MARKET_REGIME_CONTROL,
                mode=PLUGIN_MODE_SHADOW,
            )
        with self.assertRaisesRegex(
            ValueError,
            "market_regime_control does not support strategy tech_communication_pullback_enhancement",
        ):
            validate_strategy_plugin_compatibility(
                strategy="tech_communication_pullback_enhancement",
                plugin=PLUGIN_MARKET_REGIME_CONTROL,
                mode=PLUGIN_MODE_SHADOW,
            )
        validate_strategy_plugin_notification_target(
            notification_target=GENERAL_MARKET_REGIME_NOTIFICATION_TARGET,
            plugin=PLUGIN_MARKET_REGIME_CONTROL,
        )

    def test_parse_strategy_plugin_notification_targets_accepts_general_market_regime(self):
        targets = parse_strategy_plugin_notification_targets(
            {
                "notification_targets": [
                    {
                        "notification_target": GENERAL_MARKET_REGIME_NOTIFICATION_TARGET,
                        "plugin": PLUGIN_MARKET_REGIME_CONTROL,
                        "signal_path": "gs://bucket/market_regime_notification/latest_signal.json",
                        "expected_schema_version": "market_regime_control.v1",
                    }
                ]
            }
        )

        self.assertEqual(targets[0].notification_target, GENERAL_MARKET_REGIME_NOTIFICATION_TARGET)
        self.assertEqual(targets[0].plugin, PLUGIN_MARKET_REGIME_CONTROL)
        self.assertEqual(targets[0].expected_schema_version, "market_regime_control.v1")

    def test_parse_strategy_plugin_notification_targets_rejects_strategy_only_target(self):
        with self.assertRaisesRegex(ValueError, "does not support notification target"):
            parse_strategy_plugin_notification_targets(
                [
                    {
                        "notification_target": "soxl_soxx_trend_income",
                        "plugin": PLUGIN_MARKET_REGIME_CONTROL,
                        "signal_path": "gs://bucket/market_regime/latest_signal.json",
                    }
                ]
            )

    def test_parse_strategy_plugin_mounts_rejects_unsupported_crisis_response_strategy(self):
        raw = [
            {
                "strategy": "global_etf_rotation",
                "plugin": PLUGIN_CRISIS_RESPONSE_SHADOW,
                "signal_path": "gs://bucket/latest_signal.json",
            }
        ]

        with self.assertRaisesRegex(
            ValueError,
            "crisis_response_shadow does not support strategy global_etf_rotation",
        ):
            parse_strategy_plugin_mounts(raw)

    def test_parse_strategy_plugin_mounts_accepts_taco_rebound_tqqq_notification(self):
        mounts = parse_strategy_plugin_mounts(
            [
                {
                    "strategy": "tqqq_growth_income",
                    "plugin": PLUGIN_TACO_REBOUND_SHADOW,
                    "signal_path": "gs://bucket/taco/latest_signal.json",
                }
            ]
        )

        self.assertEqual(mounts[0].strategy, "tqqq_growth_income")
        self.assertEqual(mounts[0].plugin, PLUGIN_TACO_REBOUND_SHADOW)

    def test_parse_strategy_plugin_mounts_accepts_macro_risk_governor_tqqq(self):
        mounts = parse_strategy_plugin_mounts(
            [
                {
                    "strategy": "tqqq_growth_income",
                    "plugin": PLUGIN_MACRO_RISK_GOVERNOR,
                    "signal_path": "gs://bucket/macro/latest_signal.json",
                }
            ]
        )

        self.assertEqual(mounts[0].strategy, "tqqq_growth_income")
        self.assertEqual(mounts[0].plugin, PLUGIN_MACRO_RISK_GOVERNOR)

    def test_parse_strategy_plugin_mounts_accepts_market_regime_control_tqqq(self):
        mounts = parse_strategy_plugin_mounts(
            [
                {
                    "strategy": "tqqq_growth_income",
                    "plugin": PLUGIN_MARKET_REGIME_CONTROL,
                    "signal_path": "gs://bucket/market_regime/latest_signal.json",
                    "expected_schema_version": "market_regime_control.v1",
                }
            ]
        )

        self.assertEqual(mounts[0].strategy, "tqqq_growth_income")
        self.assertEqual(mounts[0].plugin, PLUGIN_MARKET_REGIME_CONTROL)
        self.assertEqual(mounts[0].expected_schema_version, "market_regime_control.v1")

    def test_parse_strategy_plugin_mounts_accepts_market_regime_control_soxl(self):
        mounts = parse_strategy_plugin_mounts(
            [
                {
                    "strategy": "soxl_soxx_trend_income",
                    "plugin": PLUGIN_MARKET_REGIME_CONTROL,
                    "signal_path": "gs://bucket/market_regime/latest_signal.json",
                    "expected_schema_version": "market_regime_control.v1",
                }
            ]
        )

        self.assertEqual(mounts[0].strategy, "soxl_soxx_trend_income")
        self.assertEqual(mounts[0].plugin, PLUGIN_MARKET_REGIME_CONTROL)
        self.assertEqual(mounts[0].expected_schema_version, "market_regime_control.v1")

    def test_parse_strategy_plugin_mounts_accepts_market_regime_control_weight_profile(self):
        mounts = parse_strategy_plugin_mounts(
            [
                {
                    "strategy": "global_etf_rotation",
                    "plugin": PLUGIN_MARKET_REGIME_CONTROL,
                    "signal_path": "gs://bucket/market_regime/latest_signal.json",
                }
            ]
        )

        self.assertEqual(mounts[0].strategy, "global_etf_rotation")
        self.assertEqual(mounts[0].plugin, PLUGIN_MARKET_REGIME_CONTROL)

    def test_plugin_definition_marks_legacy_plugins_deprecated(self):
        for plugin in (
            PLUGIN_CRISIS_RESPONSE_SHADOW,
            PLUGIN_MACRO_RISK_GOVERNOR,
            PLUGIN_TACO_REBOUND_SHADOW,
        ):
            definition = DEFAULT_STRATEGY_PLUGIN_DEFINITIONS[plugin]
            self.assertTrue(definition.deprecated)
            self.assertEqual(definition.successor_plugin, PLUGIN_MARKET_REGIME_CONTROL)

    def test_parse_strategy_plugin_mounts_rejects_unknown_schema_version(self):
        with self.assertRaisesRegex(ValueError, "does not support schema_version"):
            parse_strategy_plugin_mounts(
                [
                    {
                        "strategy": "tqqq_growth_income",
                        "plugin": PLUGIN_MARKET_REGIME_CONTROL,
                        "signal_path": "gs://bucket/market_regime/latest_signal.json",
                        "expected_schema_version": "market_regime_control.v99",
                    }
                ]
            )

    def test_plugin_definition_can_extend_future_strategy_support(self):
        raw = [
            {
                "strategy": "global_etf_rotation",
                "plugin": PLUGIN_CRISIS_RESPONSE_SHADOW,
                "signal_path": "gs://bucket/latest_signal.json",
            }
        ]
        definitions = {
            PLUGIN_CRISIS_RESPONSE_SHADOW: StrategyPluginDefinition(
                plugin=PLUGIN_CRISIS_RESPONSE_SHADOW,
                supported_strategies=frozenset({"global_etf_rotation"}),
                supported_modes=frozenset({PLUGIN_MODE_SHADOW}),
                alert_channels=(STRATEGY_PLUGIN_ALERT_CHANNEL_EMAIL,),
            )
        }

        mounts = parse_strategy_plugin_mounts(raw, plugin_definitions=definitions)

        self.assertEqual(mounts[0].strategy, "global_etf_rotation")

    def test_load_strategy_plugin_signal_validates_identity_and_mode(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            signal_path = Path(tmp_dir) / "latest_signal.json"
            signal_path.write_text(json.dumps(_signal_payload(mode=PLUGIN_MODE_SHADOW)), encoding="utf-8")

            signal = load_strategy_plugin_signal(
                str(signal_path),
                expected_strategy="tqqq_growth_income",
                expected_plugin="crisis_response_shadow",
                expected_mode=PLUGIN_MODE_SHADOW,
                expected_schema_version="crisis_response_shadow.v1",
            )

        self.assertEqual(signal.strategy, "tqqq_growth_income")
        self.assertEqual(signal.plugin, "crisis_response_shadow")
        self.assertEqual(signal.effective_mode, PLUGIN_MODE_SHADOW)
        self.assertEqual(signal.schema_version, "crisis_response_shadow.v1")
        self.assertTrue(signal.deprecated_plugin)
        self.assertEqual(signal.successor_plugin, PLUGIN_MARKET_REGIME_CONTROL)
        self.assertFalse(signal.execution_controls["repository_broker_write_allowed"])
        self.assertEqual(signal.local_path, str(signal_path))

    def test_load_strategy_plugin_signal_rejects_mismatched_mount(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            signal_path = Path(tmp_dir) / "latest_signal.json"
            signal_path.write_text(
                json.dumps(_signal_payload(plugin="crisis_response_shadow")),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "plugin mismatch"):
                load_strategy_plugin_signal(
                    str(signal_path),
                    expected_strategy="tqqq_growth_income",
                    expected_plugin="other_plugin",
                )

    def test_load_configured_strategy_plugin_signals_filters_strategy_and_disabled_mounts(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            signal_path = root / "latest_signal.json"
            signal_path.write_text(json.dumps(_signal_payload()), encoding="utf-8")
            mounts = parse_strategy_plugin_mounts(
                [
                    {
                        "strategy": "tqqq_growth_income",
                        "plugin": "crisis_response_shadow",
                        "signal_path": str(signal_path),
                    },
                    {
                        "strategy": "global_etf_rotation",
                        "plugin": PLUGIN_MARKET_REGIME_CONTROL,
                        "signal_path": str(root / "missing.json"),
                    },
                    {
                        "strategy": "tqqq_growth_income",
                        "plugin": "disabled_plugin",
                        "signal_path": str(root / "disabled.json"),
                        "enabled": False,
                    },
                ]
            )

            signals = load_configured_strategy_plugin_signals(mounts, strategy_profile="tqqq_growth_income")

        self.assertEqual([signal.plugin for signal in signals], ["crisis_response_shadow"])

    def test_validate_strategy_plugin_signal_payload_rejects_non_shadow_artifact_mode(self):
        with self.assertRaisesRegex(ValueError, "mode must be one of shadow"):
            validate_strategy_plugin_signal_payload(
                _signal_payload(mode="paper"),
                expected_mode=PLUGIN_MODE_SHADOW,
            )

    def test_validate_strategy_plugin_signal_payload_rejects_non_shadow_expected_mode(self):
        with self.assertRaisesRegex(ValueError, "expected_mode must be one of shadow"):
            validate_strategy_plugin_signal_payload(
                _signal_payload(mode=PLUGIN_MODE_SHADOW),
                expected_mode="live",
            )

    def test_validate_strategy_plugin_signal_payload_rejects_unknown_schema_version(self):
        with self.assertRaisesRegex(ValueError, "does not support schema_version"):
            validate_strategy_plugin_signal_payload(
                {
                    **_signal_payload(plugin=PLUGIN_MARKET_REGIME_CONTROL),
                    "schema_version": "market_regime_control.v99",
                }
            )

    def test_validate_strategy_plugin_schema_version_accepts_known_schema(self):
        validate_strategy_plugin_schema_version(
            plugin=PLUGIN_MARKET_REGIME_CONTROL,
            schema_version="market_regime_control.v1",
        )

    def test_validate_strategy_plugin_signal_payload_rejects_unsupported_crisis_response_strategy(self):
        with self.assertRaisesRegex(
            ValueError,
            "crisis_response_shadow does not support strategy global_etf_rotation",
        ):
            validate_strategy_plugin_signal_payload(
                _signal_payload(strategy="global_etf_rotation"),
            )

    def test_build_strategy_plugin_report_payload_uses_compact_summary(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            signal_path = Path(tmp_dir) / "latest_signal.json"
            signal_path.write_text(json.dumps(_signal_payload()), encoding="utf-8")
            signal = load_strategy_plugin_signal(str(signal_path))

            report_payload = build_strategy_plugin_report_payload([signal])

        self.assertEqual(report_payload["strategy_plugins"][0]["strategy"], "tqqq_growth_income")
        self.assertEqual(report_payload["strategy_plugins"][0]["plugin"], "crisis_response_shadow")
        self.assertNotIn("payload", report_payload["strategy_plugins"][0])

    def test_attach_strategy_plugin_metadata_adds_payloads_to_snapshot(self):
        signal = validate_strategy_plugin_signal_payload(
            {
                **_signal_payload(plugin=PLUGIN_TACO_REBOUND_SHADOW),
                "canonical_route": "taco_rebound",
                "rebound_context_active": True,
                "execution_controls": {
                    **_signal_payload()["execution_controls"],
                    "strategy_runtime_metadata_allowed": True,
                },
            }
        )
        snapshot = PortfolioSnapshot(
            as_of=datetime(2026, 4, 17, tzinfo=timezone.utc),
            total_equity=100000.0,
            metadata={"account_hash": "demo"},
        )

        enriched = attach_strategy_plugin_metadata(snapshot, (signal,))

        self.assertIsNot(enriched, snapshot)
        self.assertEqual(enriched.metadata["account_hash"], "demo")
        self.assertEqual(enriched.metadata[PLUGIN_TACO_REBOUND_SHADOW]["canonical_route"], "taco_rebound")
        self.assertEqual(
            enriched.metadata["strategy_plugins"][PLUGIN_TACO_REBOUND_SHADOW]["canonical_route"],
            "taco_rebound",
        )

    def test_attach_strategy_plugin_metadata_ignores_shadow_artifact_without_runtime_guard(self):
        signal = validate_strategy_plugin_signal_payload(
            {
                **_signal_payload(plugin=PLUGIN_TACO_REBOUND_SHADOW),
                "canonical_route": "taco_rebound",
                "rebound_context_active": True,
            }
        )
        snapshot = PortfolioSnapshot(
            as_of=datetime(2026, 4, 17, tzinfo=timezone.utc),
            total_equity=100000.0,
            metadata={"account_hash": "demo"},
        )

        enriched = attach_strategy_plugin_metadata(snapshot, (signal,))

        self.assertIs(enriched, snapshot)
        self.assertEqual(enriched.metadata, {"account_hash": "demo"})

    def test_strategy_plugin_notification_lines_use_translator_when_available(self):
        signal = validate_strategy_plugin_signal_payload(_signal_payload())
        translations = {
            "strategy_plugin_line": "plugin={plugin}|mode={mode}|route={route}|action={action}",
            "strategy_plugin_name_crisis_response_shadow": "Crisis",
            "strategy_plugin_mode_shadow": "shadow",
            "strategy_plugin_route_no_action": "no action",
            "strategy_plugin_action_watch_only": "watch only",
        }

        lines = build_strategy_plugin_notification_lines(
            [signal],
            translator=lambda key, **kwargs: translations.get(key, key).format(**kwargs)
            if kwargs
            else translations.get(key, key),
        )

        self.assertEqual(lines, ("plugin=Crisis|mode=shadow|route=no action|action=watch only",))

    def test_strategy_plugin_notification_lines_can_use_artifact_localized_message(self):
        signal = validate_strategy_plugin_signal_payload(
            {
                **_signal_payload(plugin=PLUGIN_MARKET_REGIME_CONTROL),
                "canonical_route": "risk_reduced",
                "suggested_action": "delever",
                "localized_messages": {
                    "schema_version": "strategy_plugin_messages.v1",
                    "default_locale": "en-US",
                    "notification": {
                        "en-US": "Notification required: risk reduced.",
                        "zh-CN": "需要通知：市场状态风险降低。",
                    },
                },
            }
        )

        self.assertEqual(
            extract_strategy_plugin_localized_message(signal, section="notification", locale="zh-CN"),
            "需要通知：市场状态风险降低。",
        )
        self.assertEqual(
            build_strategy_plugin_notification_lines([signal], locale="zh-CN"),
            ("需要通知：市场状态风险降低。",),
        )

    def test_notification_target_signal_loads_without_strategy(self):
        payload = {
            **_signal_payload(plugin=PLUGIN_MARKET_REGIME_CONTROL),
            "target_type": "notification_target",
            "notification_target": GENERAL_MARKET_REGIME_NOTIFICATION_TARGET,
        }
        payload.pop("strategy", None)

        signal = validate_strategy_plugin_signal_payload(
            payload,
            expected_notification_target=GENERAL_MARKET_REGIME_NOTIFICATION_TARGET,
            expected_plugin=PLUGIN_MARKET_REGIME_CONTROL,
        )

        self.assertEqual(signal.strategy, "")
        self.assertEqual(signal.target_type, "notification_target")
        self.assertEqual(signal.notification_target, GENERAL_MARKET_REGIME_NOTIFICATION_TARGET)
        self.assertEqual(signal.report_summary()["notification_target"], GENERAL_MARKET_REGIME_NOTIFICATION_TARGET)

    def test_load_configured_strategy_plugin_notification_target_signals(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            signal_path = Path(tmp_dir) / "latest_signal.json"
            payload = {
                **_signal_payload(plugin=PLUGIN_MARKET_REGIME_CONTROL),
                "target_type": "notification_target",
                "notification_target": GENERAL_MARKET_REGIME_NOTIFICATION_TARGET,
            }
            payload.pop("strategy", None)
            signal_path.write_text(json.dumps(payload), encoding="utf-8")
            targets = parse_strategy_plugin_notification_targets(
                [
                    {
                        "notification_target": GENERAL_MARKET_REGIME_NOTIFICATION_TARGET,
                        "plugin": PLUGIN_MARKET_REGIME_CONTROL,
                        "signal_path": str(signal_path),
                    }
                ]
            )

            signals = load_configured_strategy_plugin_notification_target_signals(targets)

        self.assertEqual(len(signals), 1)
        self.assertEqual(signals[0].notification_target, GENERAL_MARKET_REGIME_NOTIFICATION_TARGET)

    def test_strategy_plugin_no_action_signal_does_not_escalate_alert(self):
        signal = validate_strategy_plugin_signal_payload(_signal_payload())

        self.assertFalse(should_alert_strategy_plugin_signal(signal))
        self.assertEqual(build_strategy_plugin_alert_messages([signal]), ())

    def test_strategy_plugin_auto_position_control_signal_stays_with_strategy_notification(self):
        signal = validate_strategy_plugin_signal_payload(
            {
                **_signal_payload(plugin=PLUGIN_MARKET_REGIME_CONTROL),
                "canonical_route": "risk_off",
                "suggested_action": "defend",
                "would_trade_if_enabled": True,
                "execution_controls": {
                    **_signal_payload()["execution_controls"],
                    "strategy_runtime_metadata_allowed": True,
                    "position_control_allowed": True,
                    "consumption_evidence_status": "automation_approved",
                },
            }
        )

        self.assertFalse(should_alert_strategy_plugin_signal(signal))
        self.assertEqual(build_strategy_plugin_alert_messages([signal]), ())

    def test_strategy_plugin_notification_target_still_alerts_plugin_bot(self):
        signal = validate_strategy_plugin_signal_payload(
            {
                **_signal_payload(plugin=PLUGIN_MARKET_REGIME_CONTROL),
                "target_type": "notification_target",
                "strategy": "",
                "notification_target": GENERAL_MARKET_REGIME_NOTIFICATION_TARGET,
                "canonical_route": "risk_off",
                "suggested_action": "defend",
                "would_trade_if_enabled": True,
                "execution_controls": {
                    **_signal_payload()["execution_controls"],
                    "strategy_runtime_metadata_allowed": False,
                    "position_control_allowed": False,
                    "consumption_evidence_status": "notification_only",
                    "capital_impact": "notification_only",
                },
            }
        )

        self.assertTrue(should_alert_strategy_plugin_signal(signal))
        alerts = build_strategy_plugin_alert_messages([signal])
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].metadata["target_type"], "notification_target")

    def test_strategy_plugin_manual_review_strategy_signal_still_alerts_plugin_bot(self):
        signal = validate_strategy_plugin_signal_payload(
            {
                **_signal_payload(plugin=PLUGIN_MARKET_REGIME_CONTROL),
                "canonical_route": "opportunity_watch",
                "suggested_action": "notify_manual_review",
                "would_trade_if_enabled": False,
                "execution_controls": {
                    **_signal_payload()["execution_controls"],
                    "strategy_runtime_metadata_allowed": True,
                    "position_control_allowed": True,
                    "consumption_evidence_status": "automation_approved",
                },
            }
        )

        self.assertTrue(should_alert_strategy_plugin_signal(signal))
        alerts = build_strategy_plugin_alert_messages([signal])
        self.assertEqual(len(alerts), 1)
        self.assertIn("Manual review only", alerts[0].body)

    def test_delegated_manual_review_strategy_signal_stays_with_notification_target(self):
        signal = validate_strategy_plugin_signal_payload(
            {
                **_signal_payload(plugin=PLUGIN_MARKET_REGIME_CONTROL),
                "canonical_route": "opportunity_watch",
                "suggested_action": "notify_manual_review",
                "would_trade_if_enabled": False,
                "execution_controls": {
                    **_signal_payload()["execution_controls"],
                    "strategy_runtime_metadata_allowed": True,
                    "position_control_allowed": True,
                    "consumption_evidence_status": "automation_approved",
                    "manual_review_notification_delegated": True,
                    "manual_review_notification_target": GENERAL_MARKET_REGIME_NOTIFICATION_TARGET,
                    "manual_review_notification_delegate": (
                        f"notification_target:{GENERAL_MARKET_REGIME_NOTIFICATION_TARGET}"
                    ),
                },
            }
        )

        self.assertFalse(should_alert_strategy_plugin_signal(signal))
        self.assertEqual(build_strategy_plugin_alert_messages([signal]), ())

    def test_notification_target_alert_uses_localized_target_name(self):
        signal = validate_strategy_plugin_signal_payload(
            {
                **_signal_payload(plugin=PLUGIN_MARKET_REGIME_CONTROL),
                "target_type": "notification_target",
                "strategy": "",
                "notification_target": GENERAL_MARKET_REGIME_NOTIFICATION_TARGET,
                "canonical_route": "watch",
                "suggested_action": "notify_manual_review",
                "would_trade_if_enabled": False,
                "execution_controls": {
                    **_signal_payload()["execution_controls"],
                    "strategy_runtime_metadata_allowed": False,
                    "position_control_allowed": False,
                    "consumption_evidence_status": "notification_only",
                    "capital_impact": "notification_only",
                },
            }
        )
        translations = {
            "strategy_plugin_alert_subject": "告警:{plugin}:{route}",
            "strategy_plugin_alert_title": "插件告警",
            "strategy_plugin_alert_target": "{target_name}={target}",
            "strategy_plugin_alert_target_name_notification_target": "通知目标",
            "strategy_plugin_alert_plugin": "插件={plugin}",
            "strategy_plugin_alert_status": "状态={route}",
            "strategy_plugin_alert_action": "建议={action}",
            "strategy_plugin_alert_mode": "模式={mode}",
            "strategy_plugin_alert_as_of": "时间={as_of}",
            "strategy_plugin_alert_scope_note": "范围={scope_note}",
            "strategy_plugin_alert_scope": "只通知人工复核",
            "strategy_plugin_name_market_regime_control": "市场状态控制通知",
            "strategy_plugin_mode_shadow": "影子观察",
            "strategy_plugin_route_watch": "观察",
            "strategy_plugin_action_notify_manual_review": "通知人工复核",
        }

        alerts = build_strategy_plugin_alert_messages(
            [signal],
            translator=lambda key, **kwargs: translations.get(key, key).format(**kwargs)
            if kwargs
            else translations.get(key, key),
        )

        self.assertEqual(len(alerts), 1)
        self.assertIn("通知目标=market_regime_notification", alerts[0].body)
        self.assertNotIn("Notification target", alerts[0].body)

    def test_market_regime_notification_alert_explains_situation_and_next_step_in_zh(self):
        signal = validate_strategy_plugin_signal_payload(
            {
                **_signal_payload(plugin=PLUGIN_MARKET_REGIME_CONTROL),
                "target_type": "notification_target",
                "strategy": "",
                "notification_target": GENERAL_MARKET_REGIME_NOTIFICATION_TARGET,
                "canonical_route": "watch",
                "suggested_action": "watch_only",
                "would_trade_if_enabled": False,
                "execution_controls": {
                    **_signal_payload()["execution_controls"],
                    "strategy_runtime_metadata_allowed": False,
                    "position_control_allowed": False,
                    "consumption_evidence_status": "notification_only",
                    "capital_impact": "notification_only",
                },
                "localized_messages": {
                    "default_locale": "en-US",
                    "labels": {
                        "reason_codes": {
                            "en-US": ["Macro: high realized volatility"],
                            "zh-CN": ["宏观：实现波动偏高"],
                        }
                    },
                },
                "log_record": {
                    "reason_codes": ["macro:benchmark_realized_volatility_high"],
                },
            }
        )
        translations = STRATEGY_PLUGIN_I18N["zh"]

        alerts = build_strategy_plugin_alert_messages(
            [signal],
            translator=lambda key, **kwargs: translations.get(key, key).format(**kwargs)
            if kwargs
            else translations.get(key, key),
            context_label="strategy-plugin-publish / market_regime_notification",
        )

        self.assertEqual(len(alerts), 1)
        self.assertIn("[插件发布 / 统一市场状态通知]", alerts[0].subject)
        self.assertNotIn("strategy-plugin-publish", alerts[0].subject)
        self.assertIn("通知对象：统一市场状态通知", alerts[0].body)
        self.assertIn("当前情况：当前不是危机，也不是自动抄底信号", alerts[0].body)
        self.assertIn("宏观：实现波动偏高", alerts[0].body)
        self.assertIn("建议处理：先人工核对市场环境和现有仓位", alerts[0].body)
        self.assertIn("动作边界：仅观察，不自动交易", alerts[0].body)
        self.assertIn("自动化边界：这条通知只用于人工复核", alerts[0].body)
        self.assertEqual(alerts[0].metadata["display_target"], "统一市场状态通知")
        self.assertEqual(alerts[0].metadata["reason_summary"], "宏观：实现波动偏高")

    def test_strategy_plugin_true_crisis_builds_generic_alert_message(self):
        signal = validate_strategy_plugin_signal_payload(
            {
                **_signal_payload(),
                "canonical_route": "true_crisis",
                "suggested_action": "defend",
                "would_trade_if_enabled": True,
            },
            source_uri="gs://bucket/latest_signal.json",
        )
        translations = {
            "strategy_plugin_alert_subject": "alert:{strategy}:{plugin}:{route}",
            "strategy_plugin_alert_title": "alert title",
            "strategy_plugin_line": "plugin={plugin}|mode={mode}|route={route}|action={action}",
            "strategy_plugin_alert_strategy": "strategy={strategy}",
            "strategy_plugin_alert_plugin": "plugin={plugin}",
            "strategy_plugin_alert_status": "status={route}",
            "strategy_plugin_alert_action": "action={action}",
            "strategy_plugin_alert_mode": "mode={mode}",
            "strategy_plugin_alert_as_of": "as_of={as_of}",
            "strategy_plugin_alert_guidance": "guidance={guidance}",
            "strategy_plugin_alert_scope_note": "scope={scope_note}",
            "strategy_plugin_name_crisis_response_shadow": "Crisis",
            "strategy_plugin_mode_shadow": "shadow",
            "strategy_plugin_route_true_crisis": "true crisis",
            "strategy_plugin_action_defend": "defend",
            "strategy_plugin_guidance_crisis_response_shadow_true_crisis_defend": "reduce leverage or move to cash",
            "strategy_plugin_alert_scope": "manual review only",
        }

        alerts = build_strategy_plugin_alert_messages(
            [signal],
            translator=lambda key, **kwargs: translations.get(key, key).format(**kwargs)
            if kwargs
            else translations.get(key, key),
            strategy_label="TQQQ Growth Income",
        )

        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].subject, "alert:TQQQ Growth Income:Crisis:true crisis")
        self.assertIn("strategy_plugin_alert", alerts[0].alert_key)
        self.assertIn("plugin=Crisis", alerts[0].body)
        self.assertIn("status=true crisis", alerts[0].body)
        self.assertIn("action=defend", alerts[0].body)
        self.assertIn("mode=shadow", alerts[0].body)
        self.assertIn("guidance=reduce leverage or move to cash", alerts[0].body)
        self.assertIn("scope=manual review only", alerts[0].body)
        self.assertNotIn("would_trade=", alerts[0].body)
        self.assertNotIn("source=", alerts[0].body)
        self.assertTrue(alerts[0].metadata["would_trade_if_enabled"])
        self.assertEqual(alerts[0].metadata["guidance"], "reduce leverage or move to cash")

    def test_strategy_plugin_alert_message_includes_ai_audit_note_when_present(self):
        signal = validate_strategy_plugin_signal_payload(
            {
                **_signal_payload(),
                "canonical_route": "true_crisis",
                "suggested_action": "defend",
                "would_trade_if_enabled": True,
                "ai_audit": {
                    "enabled": True,
                    "status": "ok",
                    "verdict": "agree",
                    "route_assessment": "confirm_true_crisis",
                    "summary": "Evidence is coherent; keep deterministic route unchanged.",
                    "final_route_unchanged": True,
                },
            },
            source_uri="gs://bucket/latest_signal.json",
        )

        alerts = build_strategy_plugin_alert_messages([signal], strategy_label="TQQQ Growth Income")

        self.assertEqual(len(alerts), 1)
        self.assertIn("AI audit: ok", alerts[0].body)
        self.assertIn("verdict=agree", alerts[0].body)
        self.assertIn("Evidence is coherent", alerts[0].body)
        self.assertEqual(alerts[0].metadata["ai_audit"]["final_route_unchanged"], True)

    def test_taco_rebound_notification_alerts_without_trade_flag(self):
        signal = validate_strategy_plugin_signal_payload(
            {
                **_signal_payload(plugin=PLUGIN_TACO_REBOUND_SHADOW),
                "schema_version": "taco_rebound_shadow.v2",
                "canonical_route": "taco_rebound",
                "suggested_action": "notify_manual_review",
                "would_trade_if_enabled": False,
                "manual_review_required": True,
            },
            source_uri="gs://bucket/taco/latest_signal.json",
        )

        self.assertTrue(should_alert_strategy_plugin_signal(signal))
        alerts = build_strategy_plugin_alert_messages([signal], strategy_label="TQQQ Growth Income")

        self.assertEqual(len(alerts), 1)
        self.assertIn("taco_rebound_shadow", alerts[0].subject)
        self.assertIn("small, pre-sized probe", alerts[0].body)
        self.assertIn("does not place orders", alerts[0].body)
        self.assertFalse(alerts[0].metadata["would_trade_if_enabled"])


if __name__ == "__main__":
    unittest.main()
