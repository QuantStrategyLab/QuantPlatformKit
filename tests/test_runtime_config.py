from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from quant_platform_kit.common.runtime_config import (
    first_non_empty,
    resolve_bool_value,
    resolve_cash_only_execution_env,
    resolve_dry_run_env,
    resolve_float_env,
    resolve_optional_bool_env,
    resolve_optional_float_env,
    resolve_quantity_step_env,
    resolve_strategy_config_path,
    resolve_strategy_runtime_path_settings,
)
from quant_platform_kit.common.strategies import (
    US_EQUITY_DOMAIN,
    StrategyDefinition,
    StrategyMetadata,
    build_strategy_catalog,
)


class RuntimeConfigTests(unittest.TestCase):
    def test_common_runtime_config_helpers_normalize_basic_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            bundled_config = tmp_path / "strategy.json"
            bundled_config.write_text("{}", encoding="utf-8")

            self.assertEqual(first_non_empty("", None, "  value  "), "value")
            self.assertIs(resolve_bool_value("yes"), True)
            self.assertIs(resolve_bool_value("0"), False)
            self.assertTrue(resolve_dry_run_env({}, "DRY_RUN_ONLY"))
            self.assertFalse(
                resolve_dry_run_env({"DRY_RUN_ONLY": "false"}, "DRY_RUN_ONLY")
            )
            env = {
                "DEFAULT_MIN_NOTIONAL": "25",
                "EMPTY_MIN_NOTIONAL": "",
                "FRACTIONAL_ENABLED": "true",
                "FORCED_STEP": "1",
            }
            self.assertEqual(resolve_optional_float_env(env, "DEFAULT_MIN_NOTIONAL"), 25.0)
            self.assertIsNone(resolve_optional_float_env(env, "EMPTY_MIN_NOTIONAL"))
            self.assertEqual(resolve_float_env(env, "MISSING", default=50.0), 50.0)
            self.assertEqual(
                resolve_quantity_step_env(
                    env,
                    step_env="MISSING_STEP",
                    fractional_env="FRACTIONAL_ENABLED",
                    fractional_default=False,
                ),
                0.0001,
            )
            self.assertEqual(
                resolve_quantity_step_env(
                    env,
                    step_env="MISSING_STEP",
                    fractional_env="FRACTIONAL_ENABLED",
                    fractional_default=False,
                    fractional_step=0.001,
                ),
                0.001,
            )
            self.assertEqual(
                resolve_quantity_step_env(
                    env,
                    step_env="FORCED_STEP",
                    fractional_env="FRACTIONAL_ENABLED",
                    fractional_default=True,
                ),
                1.0,
            )
            self.assertEqual(
                resolve_strategy_config_path(
                    explicit_path=" /tmp/live.json ",
                    bundled_path=str(bundled_config),
                ),
                ("/tmp/live.json", "env"),
            )
            self.assertEqual(
                resolve_strategy_config_path(
                    explicit_path=None,
                    bundled_path=str(bundled_config),
                ),
                (str(bundled_config), "bundled_canonical_default"),
            )

    def test_resolve_strategy_runtime_path_settings_derives_platform_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            bundled_config = tmp_path / "configs" / "strategy.json"
            bundled_config.parent.mkdir()
            bundled_config.write_text("{}", encoding="utf-8")
            catalog = build_strategy_catalog(
                strategy_definitions={
                    "feature_snapshot_strategy": StrategyDefinition(
                        profile="feature_snapshot_strategy",
                        domain=US_EQUITY_DOMAIN,
                        supported_platforms=frozenset({"ibkr"}),
                        required_inputs=frozenset({"feature_snapshot"}),
                        target_mode="weight",
                        bundled_config_relpath="configs/strategy.json",
                    )
                }
            )
            definition = catalog.definitions["feature_snapshot_strategy"]
            metadata = StrategyMetadata(
                canonical_profile="feature_snapshot_strategy",
                display_name="Feature Snapshot Strategy",
                description="test",
            )

            settings = resolve_strategy_runtime_path_settings(
                strategy_catalog=catalog,
                strategy_definition=definition,
                strategy_metadata=metadata,
                platform_env_prefix="IBKR",
                env={"IBKR_STRATEGY_ARTIFACT_ROOT": str(tmp_path / "artifacts")},
                repo_root=tmp_path,
                include_reconciliation_output=True,
            )

            self.assertEqual(settings.strategy_profile, "feature_snapshot_strategy")
            self.assertEqual(settings.strategy_display_name, "Feature Snapshot Strategy")
            self.assertEqual(settings.strategy_domain, US_EQUITY_DOMAIN)
            self.assertEqual(settings.strategy_target_mode, "weight")
            self.assertEqual(settings.strategy_artifact_root, str(tmp_path / "artifacts"))
            self.assertEqual(
                settings.strategy_artifact_dir,
                str(tmp_path / "artifacts" / "feature_snapshot_strategy"),
            )
            self.assertEqual(
                settings.feature_snapshot_path,
                str(
                    tmp_path
                    / "artifacts"
                    / "feature_snapshot_strategy"
                    / "feature_snapshot_strategy_feature_snapshot_latest.csv"
                ),
            )
            self.assertEqual(
                settings.feature_snapshot_manifest_path,
                str(
                    tmp_path
                    / "artifacts"
                    / "feature_snapshot_strategy"
                    / "feature_snapshot_strategy_feature_snapshot_latest.csv.manifest.json"
                ),
            )
            self.assertEqual(settings.strategy_config_path, str(bundled_config))
            self.assertEqual(settings.strategy_config_source, "bundled_canonical_default")
            self.assertEqual(
                settings.reconciliation_output_path,
                str(tmp_path / "artifacts" / "feature_snapshot_strategy" / "reconciliation"),
            )

    def test_resolve_strategy_runtime_path_settings_prefers_env_over_derived_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            catalog = build_strategy_catalog(
                strategy_definitions={
                    "feature_snapshot_strategy": StrategyDefinition(
                        profile="feature_snapshot_strategy",
                        domain=US_EQUITY_DOMAIN,
                        supported_platforms=frozenset({"schwab"}),
                        required_inputs=frozenset({"feature_snapshot"}),
                    )
                }
            )
            definition = catalog.definitions["feature_snapshot_strategy"]
            metadata = StrategyMetadata(
                canonical_profile="feature_snapshot_strategy",
                display_name="Feature Snapshot Strategy",
                description="test",
            )

            settings = resolve_strategy_runtime_path_settings(
                strategy_catalog=catalog,
                strategy_definition=definition,
                strategy_metadata=metadata,
                platform_env_prefix="SCHWAB",
                env={
                    "SCHWAB_STRATEGY_ARTIFACT_ROOT": str(tmp_path / "artifacts"),
                    "SCHWAB_FEATURE_SNAPSHOT_PATH": "gs://bucket/snapshot.csv",
                    "FEATURE_SNAPSHOT_MANIFEST_PATH": "gs://bucket/snapshot.csv.manifest.json",
                    "STRATEGY_CONFIG_PATH": "/workspace/config.json",
                },
                repo_root=tmp_path,
            )

            self.assertEqual(settings.feature_snapshot_path, "gs://bucket/snapshot.csv")
            self.assertEqual(
                settings.feature_snapshot_manifest_path,
                "gs://bucket/snapshot.csv.manifest.json",
            )
            self.assertEqual(settings.strategy_config_path, "/workspace/config.json")
            self.assertEqual(settings.strategy_config_source, "env")
            self.assertIsNone(settings.reconciliation_output_path)

    def test_resolve_cash_only_execution_env_prefers_platform_override(self) -> None:
        env = {
            "CASH_ONLY_EXECUTION": "false",
            "IBKR_CASH_ONLY_EXECUTION": "true",
            "SCHWAB_CASH_ONLY_EXECUTION": "false",
        }
        self.assertTrue(
            resolve_cash_only_execution_env(env, platform_env_prefix="IBKR")
        )
        self.assertFalse(
            resolve_cash_only_execution_env(env, platform_env_prefix="SCHWAB")
        )
        self.assertFalse(resolve_cash_only_execution_env(env))
        self.assertTrue(
            resolve_cash_only_execution_env({}, platform_env_prefix="IBKR")
        )

    def test_resolve_optional_bool_env_treats_blank_as_unset(self) -> None:
        self.assertIsNone(resolve_optional_bool_env({"FLAG": ""}, "FLAG"))
        self.assertIsNone(resolve_optional_bool_env({}, "FLAG"))
        self.assertFalse(resolve_optional_bool_env({"FLAG": "false"}, "FLAG"))


if __name__ == "__main__":
    unittest.main()
