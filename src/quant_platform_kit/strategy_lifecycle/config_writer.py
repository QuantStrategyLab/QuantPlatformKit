"""Config writer — safely write optimized parameters to platform-config.json."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from quant_platform_kit.strategy_lifecycle.contracts import OptimizationProposal


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_params_to_config(
    proposal: OptimizationProposal,
    *,
    config_path: str | Path | None = None,
    config_data: Mapping[str, Any] | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Write proposed parameters into platform-config.json format.

    This does NOT write to the actual live config file by default.
    Instead, it produces a config patch that can be applied via a PR.

    Args:
        proposal: The approved optimization proposal.
        config_path: Path to platform-config.json.
        config_data: Pre-loaded config dict (takes precedence over config_path).
        dry_run: If True, return the patch without writing.

    Returns:
        Dict with the config patch that should be merged into platform-config.json.
    """
    # Build the params_overrides section
    version = (proposal.proposed_metrics.param_version if proposal.proposed_metrics else 0) + 1

    params_overrides = {
        "version": version,
        "updated_at": _now_iso(),
        "updated_by": "auto_optimizer",
        "improvement_score": proposal.improvement_score,
        "recommendation": proposal.recommendation,
        "parameters": dict(proposal.proposed_params),
    }

    # Build params_history entry
    history_entry = {
        "version": version - 1,
        "parameters": dict(proposal.current_params),
        "updated_at": _now_iso(),
        "sharpe": proposal.current_metrics.sharpe_ratio if proposal.current_metrics else None,
    }

    patch = {
        "strategy": proposal.strategy_profile,
        "params_overrides": params_overrides,
        "params_history_append": history_entry,
    }

    if not dry_run and config_path:
        _apply_patch(Path(config_path), proposal.strategy_profile, params_overrides, history_entry)

    if not dry_run and config_data is not None:
        _apply_to_dict(config_data, proposal.strategy_profile, params_overrides, history_entry)

    return patch


def _apply_patch(
    config_path: Path,
    strategy_profile: str,
    params_overrides: dict[str, Any],
    history_entry: dict[str, Any],
) -> None:
    """Apply params_overrides to an on-disk platform-config.json."""
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    raw = json.loads(config_path.read_text(encoding="utf-8"))
    _apply_to_dict(raw, strategy_profile, params_overrides, history_entry)

    # Write back
    config_path.write_text(json.dumps(raw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _apply_to_dict(
    config: dict[str, Any],
    strategy_profile: str,
    params_overrides: dict[str, Any],
    history_entry: dict[str, Any],
) -> None:
    """Merge params_overrides and history into a config dict in-place."""
    strategies = config.setdefault("strategies", {})
    strategy_config = strategies.get(strategy_profile, {})
    if not isinstance(strategy_config, dict):
        strategy_config = {}

    strategy_config["params_overrides"] = params_overrides

    history = strategy_config.get("params_history", [])
    if not isinstance(history, list):
        history = []
    history.append(history_entry)
    strategy_config["params_history"] = history

    strategies[strategy_profile] = strategy_config
