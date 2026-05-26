import json
import tempfile
import unittest
from pathlib import Path

from quant_platform_kit.common.strategy_plugins import (
    CRISIS_RESPONSE_SHADOW_SUPPORTED_STRATEGIES,
    DEFAULT_STRATEGY_PLUGIN_DEFINITIONS,
    PLUGIN_CRISIS_RESPONSE_SHADOW,
    PLUGIN_TACO_REBOUND_SHADOW,
    PLUGIN_MODE_SHADOW,
    STRATEGY_PLUGIN_ALERT_CHANNEL_EMAIL,
    STRATEGY_PLUGIN_ALERT_CHANNEL_PUSH,
    STRATEGY_PLUGIN_ALERT_CHANNEL_SMS,
    STRATEGY_PLUGIN_ALERT_CHANNEL_TELEGRAM,
    TACO_REBOUND_SHADOW_SUPPORTED_STRATEGIES,
    StrategyPluginDefinition,
    build_strategy_plugin_alert_messages,
    build_strategy_plugin_notification_lines,
    build_strategy_plugin_report_payload,
    load_configured_strategy_plugin_signals,
    load_strategy_plugin_signal,
    parse_strategy_plugin_mounts,
    should_alert_strategy_plugin_signal,
    validate_strategy_plugin_compatibility,
    validate_strategy_plugin_signal_payload,
)


def _signal_payload(*, strategy="tqqq_growth_income", plugin="crisis_response_shadow", mode=PLUGIN_MODE_SHADOW):
    return {
        "as_of": "2026-04-17",
        "strategy": strategy,
        "plugin": plugin,
        "mode": mode,
        "configured_mode": mode,
        "effective_mode": mode,
        "schema_version": "crisis_response_shadow.v1",
        "canonical_route": "no_action",
        "suggested_action": "watch_only",
        "would_trade_if_enabled": False,
        "execution_controls": {
            "broker_order_allowed": False,
            "live_allocation_mutation_allowed": False,
            "repository_broker_write_allowed": False,
            "repository_allocation_mutation_allowed": False,
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

    def test_default_plugin_definition_limits_crisis_response_to_supported_strategies(self):
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
            )

        self.assertEqual(signal.strategy, "tqqq_growth_income")
        self.assertEqual(signal.plugin, "crisis_response_shadow")
        self.assertEqual(signal.effective_mode, PLUGIN_MODE_SHADOW)
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
                        "strategy": "soxl_soxx_trend_income",
                        "plugin": "crisis_response_shadow",
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

    def test_strategy_plugin_no_action_signal_does_not_escalate_alert(self):
        signal = validate_strategy_plugin_signal_payload(_signal_payload())

        self.assertFalse(should_alert_strategy_plugin_signal(signal))
        self.assertEqual(build_strategy_plugin_alert_messages([signal]), ())

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
            "strategy_plugin_name_crisis_response_shadow": "Crisis",
            "strategy_plugin_mode_shadow": "shadow",
            "strategy_plugin_route_true_crisis": "true crisis",
            "strategy_plugin_action_defend": "defend",
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
        self.assertNotIn("would_trade=", alerts[0].body)
        self.assertNotIn("source=", alerts[0].body)
        self.assertTrue(alerts[0].metadata["would_trade_if_enabled"])

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
        self.assertFalse(alerts[0].metadata["would_trade_if_enabled"])


if __name__ == "__main__":
    unittest.main()
