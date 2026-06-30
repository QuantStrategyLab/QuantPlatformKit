from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from .strategies import (
    StrategyCatalog,
    StrategyDefinition,
    StrategyMetadata,
    derive_strategy_artifact_paths,
)


@dataclass(frozen=True)
class StrategyRuntimePathSettings:
    strategy_profile: str
    strategy_display_name: str
    strategy_domain: str
    strategy_target_mode: str | None
    strategy_artifact_root: str | None
    strategy_artifact_dir: str | None
    feature_snapshot_path: str | None
    feature_snapshot_manifest_path: str | None
    strategy_config_path: str | None
    strategy_config_source: str | None
    reconciliation_output_path: str | None = None


def first_non_empty(*values: str | None) -> str | None:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return None


def resolve_bool_value(raw_value: str | None) -> bool:
    return str(raw_value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _resolve_optional_bool_env(
    env: Mapping[str, str | None],
    name: str,
) -> bool | None:
    """Internal helper: resolve bool from a Mapping (not os.environ)."""
    raw_value = env.get(name)
    if raw_value is None or str(raw_value).strip() == "":
        return None
    return resolve_bool_value(raw_value)


def resolve_cash_only_execution_env(
    env: Mapping[str, str | None],
    *,
    platform_env_prefix: str | None = None,
    legacy_name: str = "CASH_ONLY_EXECUTION",
    default: bool = True,
) -> bool:
    """Resolve cash-only execution with platform-specific override precedence."""
    candidates: list[str] = []
    prefix = str(platform_env_prefix or "").strip().upper()
    if prefix:
        candidates.append(f"{prefix}_CASH_ONLY_EXECUTION")
    legacy = str(legacy_name or "").strip()
    if legacy:
        candidates.append(legacy)
    for name in candidates:
        value = _resolve_optional_bool_env(env, name)
        if value is not None:
            return value
    return default


def resolve_dry_run_env(
    env: Mapping[str, str | None],
    name: str,
    *,
    default: bool = True,
) -> bool:
    """Resolve a dry-run env flag; unset values default to dry-run (safe)."""
    raw_value = env.get(name)
    if raw_value is None or str(raw_value).strip() == "":
        return default
    return resolve_bool_value(raw_value)


def resolve_optional_float_env(
    env: Mapping[str, str | None],
    name: str,
) -> float | None:
    raw_value = env.get(name)
    if raw_value is None or str(raw_value).strip() == "":
        return None
    return float(raw_value)


def resolve_float_env(
    env: Mapping[str, str | None],
    name: str,
    *,
    default: float,
) -> float:
    value = resolve_optional_float_env(env, name)
    return float(default) if value is None else value


def resolve_quantity_step_env(
    env: Mapping[str, str | None],
    *,
    step_env: str,
    fractional_env: str,
    fractional_default: bool,
    fractional_step: float = 0.0001,
) -> float:
    explicit_step = resolve_optional_float_env(env, step_env)
    if explicit_step is not None:
        return explicit_step
    raw_enabled = env.get(fractional_env)
    fractional_enabled = (
        fractional_default
        if raw_enabled is None
        else resolve_bool_value(raw_enabled)
    )
    return float(fractional_step) if fractional_enabled else 1.0


def resolve_optional_bool_env(name: str, default: bool = False) -> bool:
    """Read env var *name* and parse as bool. Returns *default* when unset/empty."""
    raw_value = os.getenv(name)
    if raw_value is None or str(raw_value).strip() == "":
        return default
    value = str(raw_value).strip().lower()
    if value in {"1", "true", "yes", "y", "on"}:
        return True
    if value in {"0", "false", "no", "n", "off"}:
        return False
    raise ValueError(f"{name} must be boolean, got {raw_value!r}")


def resolve_optional_ratio_env(name: str, default: float | None = None) -> float | None:
    """Read env var *name* and parse as a float ratio in [0, 1]. Returns *default* when unset/empty."""
    raw_value = os.getenv(name)
    if raw_value is None or str(raw_value).strip() == "":
        return default
    value = float(raw_value)
    if not (0.0 <= value <= 1.0):
        raise ValueError(f"{name} must be in [0,1], got {value}")
    return value


def resolve_optional_positive_float_env(name: str, default: float | None = None) -> float | None:
    """Read env var *name* and parse as a positive float. Returns *default* when unset/empty."""
    raw_value = os.getenv(name)
    if raw_value is None or str(raw_value).strip() == "":
        return default
    value = float(raw_value)
    if value <= 0.0:
        raise ValueError(f"{name} must be positive, got {value}")
    return value


def resolve_optional_dca_mode_env(name: str, default: str | None = None) -> str | None:
    """Read env var *name* and resolve to 'fixed', 'smart', or *default* when unset."""
    raw_value = os.getenv(name)
    if raw_value is None or str(raw_value).strip() == "":
        return default
    value = str(raw_value).strip().lower()
    aliases = {
        "ordinary": "fixed",
        "ordinary_dca": "fixed",
        "fixed_dca": "fixed",
        "smart_dca": "smart",
    }
    mode = aliases.get(value, value)
    if mode not in {"fixed", "smart"}:
        raise ValueError(f"{name} must be fixed or smart, got {raw_value!r}")
    return mode


def resolve_optional_ibit_zscore_exit_mode_env(name: str, default: str | None = None) -> str | None:
    """Read env var *name* and resolve to 'disabled', 'paper', 'live', or *default* when unset."""
    raw_value = os.getenv(name)
    if raw_value is None or str(raw_value).strip() == "":
        return default
    value = str(raw_value).strip().lower()
    aliases = {
        "off": "disabled",
        "none": "disabled",
        "false": "disabled",
        "disable": "disabled",
        "enabled": "live",
        "shadow": "paper",
        "dry_run": "paper",
        "dry-run": "paper",
    }
    mode = aliases.get(value, value)
    if mode not in {"disabled", "paper", "live"}:
        raise ValueError(f"{name} must be disabled, paper, or live, got {raw_value!r}")
    return mode


def resolve_optional_symbol_env(name: str, default: str | None = None) -> str | None:
    """Read env var *name* and validate as a ticker symbol. Returns *default* when unset/empty."""
    raw_value = os.getenv(name)
    if raw_value is None or str(raw_value).strip() == "":
        return default
    value = str(raw_value).strip().upper()
    if len(value) > 16 or not value.replace(".", "").replace("-", "").isalnum():
        raise ValueError(f"{name} must be a symbol, got {raw_value!r}")
    return value


def resolve_optional_int(name: str, default: int | None = None) -> int | None:
    """Read env var *name* and parse as int. Returns *default* when unset/empty."""
    raw_value = os.getenv(name)
    if raw_value is None or str(raw_value).strip() == "":
        return default
    return int(raw_value)


def resolve_split_env_list(name: str, separator: str = ",") -> tuple[str, ...]:
    """Read env var *name*, split by *separator*, return deduplicated tuple."""
    raw_value = os.getenv(name)
    if raw_value is None:
        return ()
    items = []
    seen = set()
    for value in str(raw_value).replace(";", ",").replace("\n", ",").split(separator):
        item = value.strip()
        if not item or item in seen:
            continue
        items.append(item)
        seen.add(item)
    return tuple(items)


def resolve_strategy_config_path(
    *,
    explicit_path: str | None,
    bundled_path: str | None,
) -> tuple[str | None, str | None]:
    path = first_non_empty(explicit_path)
    if path is not None:
        return path, "env"

    bundled = first_non_empty(bundled_path)
    if bundled is not None and Path(bundled).exists():
        return bundled, "bundled_canonical_default"
    return None, None


def resolve_strategy_runtime_path_settings(
    *,
    strategy_catalog: StrategyCatalog,
    strategy_definition: StrategyDefinition,
    strategy_metadata: StrategyMetadata,
    platform_env_prefix: str,
    env: Mapping[str, str | None],
    repo_root: str | Path | None,
    include_reconciliation_output: bool = False,
) -> StrategyRuntimePathSettings:
    prefix = str(platform_env_prefix).strip().upper()
    if not prefix:
        raise ValueError("platform_env_prefix must be non-empty")

    artifact_paths = derive_strategy_artifact_paths(
        strategy_catalog,
        strategy_definition.profile,
        artifact_root=first_non_empty(
            env.get(f"{prefix}_STRATEGY_ARTIFACT_ROOT"),
            env.get("STRATEGY_ARTIFACT_ROOT"),
        ),
        repo_root=repo_root,
    )
    strategy_config_path, strategy_config_source = resolve_strategy_config_path(
        explicit_path=first_non_empty(
            env.get(f"{prefix}_STRATEGY_CONFIG_PATH"),
            env.get("STRATEGY_CONFIG_PATH"),
        ),
        bundled_path=(
            str(artifact_paths.bundled_config_path)
            if artifact_paths.bundled_config_path is not None
            else None
        ),
    )

    reconciliation_output_path = None
    if include_reconciliation_output:
        reconciliation_output_path = first_non_empty(
            env.get(f"{prefix}_RECONCILIATION_OUTPUT_PATH"),
            env.get("RECONCILIATION_OUTPUT_PATH"),
            str(artifact_paths.reconciliation_output_dir)
            if artifact_paths.reconciliation_output_dir is not None
            else None,
        )

    return StrategyRuntimePathSettings(
        strategy_profile=strategy_definition.profile,
        strategy_display_name=strategy_metadata.display_name,
        strategy_domain=strategy_definition.domain,
        strategy_target_mode=strategy_definition.target_mode,
        strategy_artifact_root=str(artifact_paths.artifact_root)
        if artifact_paths.artifact_root is not None
        else None,
        strategy_artifact_dir=str(artifact_paths.artifact_dir)
        if artifact_paths.artifact_dir is not None
        else None,
        feature_snapshot_path=first_non_empty(
            env.get(f"{prefix}_FEATURE_SNAPSHOT_PATH"),
            env.get("FEATURE_SNAPSHOT_PATH"),
            str(artifact_paths.feature_snapshot_path)
            if artifact_paths.feature_snapshot_path is not None
            else None,
        ),
        feature_snapshot_manifest_path=first_non_empty(
            env.get(f"{prefix}_FEATURE_SNAPSHOT_MANIFEST_PATH"),
            env.get("FEATURE_SNAPSHOT_MANIFEST_PATH"),
            str(artifact_paths.feature_snapshot_manifest_path)
            if artifact_paths.feature_snapshot_manifest_path is not None
            else None,
        ),
        strategy_config_path=strategy_config_path,
        strategy_config_source=strategy_config_source,
        reconciliation_output_path=reconciliation_output_path,
    )
