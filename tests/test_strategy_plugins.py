import json
import tempfile
import unittest
from pathlib import Path

from quant_platform_kit.common.strategy_plugins import (
    PLUGIN_MODE_PAPER,
    PLUGIN_MODE_SHADOW,
    build_strategy_plugin_report_payload,
    load_configured_strategy_plugin_signals,
    load_strategy_plugin_signal,
    parse_strategy_plugin_mounts,
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
            "broker_order_allowed": mode == "live",
            "live_allocation_mutation_allowed": mode == "live",
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

    def test_load_strategy_plugin_signal_validates_identity_and_mode(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            signal_path = Path(tmp_dir) / "latest_signal.json"
            signal_path.write_text(json.dumps(_signal_payload(mode=PLUGIN_MODE_PAPER)), encoding="utf-8")

            signal = load_strategy_plugin_signal(
                str(signal_path),
                expected_strategy="tqqq_growth_income",
                expected_plugin="crisis_response_shadow",
                expected_mode=PLUGIN_MODE_PAPER,
            )

        self.assertEqual(signal.strategy, "tqqq_growth_income")
        self.assertEqual(signal.plugin, "crisis_response_shadow")
        self.assertEqual(signal.effective_mode, PLUGIN_MODE_PAPER)
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
                        "strategy": "soxl_growth_income",
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

    def test_validate_strategy_plugin_signal_payload_rejects_expected_mode_mismatch(self):
        with self.assertRaisesRegex(ValueError, "mode mismatch"):
            validate_strategy_plugin_signal_payload(
                _signal_payload(mode=PLUGIN_MODE_SHADOW),
                expected_mode=PLUGIN_MODE_PAPER,
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


if __name__ == "__main__":
    unittest.main()
