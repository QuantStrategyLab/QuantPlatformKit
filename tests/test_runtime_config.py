from __future__ import annotations

from pathlib import Path

from quant_platform_kit.common.runtime_config import (
    first_non_empty,
    resolve_bool_value,
    resolve_strategy_config_path,
    resolve_strategy_runtime_path_settings,
)
from quant_platform_kit.common.strategies import (
    US_EQUITY_DOMAIN,
    StrategyDefinition,
    StrategyMetadata,
    build_strategy_catalog,
)


def test_common_runtime_config_helpers_normalize_basic_values(tmp_path: Path) -> None:
    bundled_config = tmp_path / "strategy.json"
    bundled_config.write_text("{}", encoding="utf-8")

    assert first_non_empty("", None, "  value  ") == "value"
    assert resolve_bool_value("yes") is True
    assert resolve_bool_value("0") is False
    assert resolve_strategy_config_path(
        explicit_path=" /tmp/live.json ",
        bundled_path=str(bundled_config),
    ) == ("/tmp/live.json", "env")
    assert resolve_strategy_config_path(
        explicit_path=None,
        bundled_path=str(bundled_config),
    ) == (str(bundled_config), "bundled_canonical_default")


def test_resolve_strategy_runtime_path_settings_derives_platform_paths(tmp_path: Path) -> None:
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

    assert settings.strategy_profile == "feature_snapshot_strategy"
    assert settings.strategy_display_name == "Feature Snapshot Strategy"
    assert settings.strategy_domain == US_EQUITY_DOMAIN
    assert settings.strategy_target_mode == "weight"
    assert settings.strategy_artifact_root == str(tmp_path / "artifacts")
    assert settings.strategy_artifact_dir == str(
        tmp_path / "artifacts" / "feature_snapshot_strategy"
    )
    assert settings.feature_snapshot_path == str(
        tmp_path
        / "artifacts"
        / "feature_snapshot_strategy"
        / "feature_snapshot_strategy_feature_snapshot_latest.csv"
    )
    assert settings.feature_snapshot_manifest_path == str(
        tmp_path
        / "artifacts"
        / "feature_snapshot_strategy"
        / "feature_snapshot_strategy_feature_snapshot_latest.csv.manifest.json"
    )
    assert settings.strategy_config_path == str(bundled_config)
    assert settings.strategy_config_source == "bundled_canonical_default"
    assert settings.reconciliation_output_path == str(
        tmp_path / "artifacts" / "feature_snapshot_strategy" / "reconciliation"
    )


def test_resolve_strategy_runtime_path_settings_prefers_env_over_derived_paths(
    tmp_path: Path,
) -> None:
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

    assert settings.feature_snapshot_path == "gs://bucket/snapshot.csv"
    assert settings.feature_snapshot_manifest_path == "gs://bucket/snapshot.csv.manifest.json"
    assert settings.strategy_config_path == "/workspace/config.json"
    assert settings.strategy_config_source == "env"
    assert settings.reconciliation_output_path is None
