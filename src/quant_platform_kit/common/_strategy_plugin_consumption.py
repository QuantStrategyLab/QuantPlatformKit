"""Runtime consumption policy & summary helpers for strategy plugins."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Callable

from quant_platform_kit.common._strategy_plugin_helpers import (
    _as_bool,
    _normalize_strategy_plugin_field,
    _optional_string,
    _translate,
)
from quant_platform_kit.common._strategy_plugin_models import (
    STRATEGY_PLUGIN_AUTOMATED_POSITION_ACTIONS,
    STRATEGY_PLUGIN_DIRECT_POSITION_CONTROL_ALLOWED,
    StrategyPluginSignal,
    _strategy_plugin_consumption_policy,
)

def _strategy_plugin_enabled_label(
    signal: StrategyPluginSignal,
    *,
    translator: Callable[..., str] | None = None,
) -> str:
    return _translate(
        translator,
        f"strategy_plugin_enabled_{str(signal.enabled).lower()}",
        fallback="yes" if signal.enabled else "no",
    )


def _strategy_plugin_value_is_present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        normalized = value.strip().lower()
        return bool(normalized) and normalized not in {"none", "null", "unbounded", "unlimited", "infinite", "inf"}
    if isinstance(value, Mapping):
        return any(_strategy_plugin_value_is_present(item) for item in value.values())
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return any(_strategy_plugin_value_is_present(item) for item in value)
    return bool(value)


def _strategy_plugin_find_field_value(value: Any, field_names: frozenset[str]) -> Any | None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if key in field_names and _strategy_plugin_value_is_present(item):
                return item
            found = _strategy_plugin_find_field_value(item, field_names)
            if found is not None:
                return found
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for item in value:
            found = _strategy_plugin_find_field_value(item, field_names)
            if found is not None:
                return found
    return None


def _strategy_plugin_has_auditable_position_control(signal: StrategyPluginSignal) -> bool:
    if not STRATEGY_PLUGIN_DIRECT_POSITION_CONTROL_ALLOWED:
        return False
    controls = signal.execution_controls
    policy = _strategy_plugin_consumption_policy(signal)
    if not (
        _as_bool(controls.get("position_control_allowed"), default=False)
        or _as_bool(policy.get("position_control_allowed"), default=False)
    ):
        return False
    if _strategy_plugin_consumption_status(signal) != "automation_approved":
        return False
    evidence_sources: tuple[Any, ...] = (controls, signal.payload)
    return all(
        _strategy_plugin_find_field_value(evidence_sources, field_names) is not None
        for field_names in (
            frozenset({"evidence_package_id", "evidence_package", "package_id"}),
            frozenset(
                {
                    "evidence_valid_until",
                    "evidence_valid_until_at",
                    "evidence_expires_at",
                    "valid_until",
                    "valid_until_at",
                    "expires_at",
                }
            ),
            frozenset({"bounded_budget", "budget", "budget_limit"}),
        )
    )


def _strategy_plugin_consumption_status(signal: StrategyPluginSignal) -> str:
    status = _optional_string(signal.execution_controls.get("consumption_evidence_status"))
    if status is None:
        status = _optional_string(_strategy_plugin_consumption_policy(signal).get("evidence_status"))
    return _normalize_strategy_plugin_field(status)


def _strategy_plugin_policy_allows_position_control(signal: StrategyPluginSignal) -> bool:
    if not STRATEGY_PLUGIN_DIRECT_POSITION_CONTROL_ALLOWED:
        return False
    controls = signal.execution_controls
    if "position_control_allowed" in controls:
        return _as_bool(controls.get("position_control_allowed"), default=False)
    return _as_bool(
        _strategy_plugin_consumption_policy(signal).get("position_control_allowed"),
        default=False,
    )


def _strategy_plugin_is_notification_only(signal: StrategyPluginSignal) -> bool:
    controls = signal.execution_controls
    policy = _strategy_plugin_consumption_policy(signal)
    if _strategy_plugin_consumption_status(signal) == "notification_only":
        return True
    if str(controls.get("capital_impact") or policy.get("capital_impact") or "").strip().lower() == "notification_only":
        return True
    if str(controls.get("notification_profile") or policy.get("notification_profile") or "").strip().lower() == "shadow_only":
        return True
    return False


def _strategy_plugin_auto_consumption_allowed(signal: StrategyPluginSignal, *, action: str) -> bool:
    if _is_strategy_position_control_notice(signal, action=action):
        return True
    if signal.execution_controls:
        return False
    return bool(
        action in STRATEGY_PLUGIN_AUTOMATED_POSITION_ACTIONS
        and _strategy_plugin_policy_allows_position_control(signal)
        and _strategy_plugin_consumption_status(signal) == "automation_approved"
        and _strategy_plugin_has_auditable_position_control(signal)
    )


def _is_strategy_position_control_notice(signal: StrategyPluginSignal, *, action: str | None = None) -> bool:
    """Return true when strategy runtime should carry the alert instead of the plugin bot."""

    if signal.normalized_target_type != "strategy":
        return False
    normalized_action = action if action is not None else signal.normalized_action
    if normalized_action not in STRATEGY_PLUGIN_AUTOMATED_POSITION_ACTIONS:
        return False
    if not _as_bool(signal.execution_controls.get("strategy_runtime_metadata_allowed"), default=False):
        return False
    return _strategy_plugin_has_auditable_position_control(signal)


