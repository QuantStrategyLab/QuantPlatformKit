"""Strict JSON input/output boundary for Shadow-only adaptive selection."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import date, datetime
from pathlib import Path
from typing import Any

from quant_platform_kit.adaptive_allocation.contracts import (
    PLATFORM_HEALTH_SCHEMA,
    MARKET_CONTEXT_SCHEMA,
    AdaptiveSelectionPolicy,
    MarketContextSnapshot,
    PlatformHealthSnapshot,
    PluginRiskAdjustment,
    SelectionDecision,
    StrategyCandidate,
)
from quant_platform_kit.adaptive_allocation.selector import select_shadow


SELECTION_INPUT_SCHEMA = "qsl.selection_input.v1"


def _mapping(value: object, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be an object")
    return value


def _sequence(value: object, field_name: str) -> Sequence[object]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        raise ValueError(f"{field_name} must be an array")
    return value


def _required(mapping: Mapping[str, Any], field_name: str) -> Any:
    if field_name not in mapping:
        raise ValueError(f"{field_name} is required")
    return mapping[field_name]


def _bool(value: object, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} must be boolean")
    return value


def _number(value: object, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field_name} must be numeric")
    return float(value)


def _integer(value: object, field_name: str) -> int:
    normalized = _number(value, field_name)
    if not normalized.is_integer():
        raise ValueError(f"{field_name} must be an integer")
    return int(normalized)


def _string(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    return value


def _date(value: object, field_name: str) -> date:
    try:
        return date.fromisoformat(_string(value, field_name))
    except ValueError as exc:
        raise ValueError(f"{field_name} must be an ISO date") from exc


def _datetime(value: object, field_name: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(_string(value, field_name).replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field_name} must be an ISO datetime") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field_name} must include a timezone")
    return parsed


def _numeric_mapping(value: object, field_name: str) -> dict[str, float]:
    return {
        _string(key, f"{field_name} key"): _number(item, f"{field_name}.{key}")
        for key, item in _mapping(value, field_name).items()
    }


def _strings(value: object, field_name: str) -> tuple[str, ...]:
    return tuple(_string(item, f"{field_name} item") for item in _sequence(value, field_name))


def _parse_market_context(payload: object) -> MarketContextSnapshot:
    item = _mapping(payload, "market_context")
    if item.get("schema") != MARKET_CONTEXT_SCHEMA:
        raise ValueError("market_context schema is unsupported")
    return MarketContextSnapshot(
        as_of=_date(_required(item, "as_of"), "market_context.as_of"),
        domain=_string(_required(item, "domain"), "market_context.domain"),
        data_version=_string(_required(item, "data_version"), "market_context.data_version"),
        data_freshness_days=_integer(_required(item, "data_freshness_days"), "market_context.data_freshness_days"),
        regime=_string(_required(item, "regime"), "market_context.regime"),
        regime_confidence=_number(_required(item, "regime_confidence"), "market_context.regime_confidence"),
        factors=_numeric_mapping(item.get("factors", {}), "market_context.factors"),
    )


def _parse_candidate(payload: object) -> StrategyCandidate:
    item = _mapping(payload, "candidate")
    return StrategyCandidate(
        strategy_profile=_string(_required(item, "strategy_profile"), "candidate.strategy_profile"),
        release_digest=_string(_required(item, "release_digest"), "candidate.release_digest"),
        lifecycle_stage=_string(_required(item, "lifecycle_stage"), "candidate.lifecycle_stage"),
        approved_for_shadow=_bool(_required(item, "approved_for_shadow"), "candidate.approved_for_shadow"),
        base_score=_number(_required(item, "base_score"), "candidate.base_score"),
        estimated_volatility=_number(_required(item, "estimated_volatility"), "candidate.estimated_volatility"),
        factor_exposures=_numeric_mapping(item.get("factor_exposures", {}), "candidate.factor_exposures"),
        required_plugins=_strings(item.get("required_plugins", []), "candidate.required_plugins"),
        allowed_platform_ids=_strings(item.get("allowed_platform_ids", []), "candidate.allowed_platform_ids"),
    )


def _parse_platform_health(payload: object) -> PlatformHealthSnapshot:
    item = _mapping(payload, "platform_health item")
    if item.get("schema") != PLATFORM_HEALTH_SCHEMA:
        raise ValueError("platform_health schema is unsupported")
    return PlatformHealthSnapshot(
        platform_id=_string(_required(item, "platform_id"), "platform_health.platform_id"),
        observed_at=_datetime(_required(item, "observed_at"), "platform_health.observed_at"),
        healthy=_bool(_required(item, "healthy"), "platform_health.healthy"),
        shadow_capable=_bool(_required(item, "shadow_capable"), "platform_health.shadow_capable"),
        reconciliation_ok=_bool(_required(item, "reconciliation_ok"), "platform_health.reconciliation_ok"),
        capacity_score=_number(_required(item, "capacity_score"), "platform_health.capacity_score"),
        expected_cost_bps=_number(_required(item, "expected_cost_bps"), "platform_health.expected_cost_bps"),
    )


def _parse_plugin_adjustment(payload: object) -> PluginRiskAdjustment:
    item = _mapping(payload, "plugin_adjustment")
    return PluginRiskAdjustment(
        plugin_id=_string(_required(item, "plugin_id"), "plugin_adjustment.plugin_id"),
        risk_multiplier=_number(_required(item, "risk_multiplier"), "plugin_adjustment.risk_multiplier"),
        approved=_bool(item.get("approved", True), "plugin_adjustment.approved"),
    )


def _parse_policy(payload: object) -> AdaptiveSelectionPolicy:
    item = _mapping(payload, "policy")
    return AdaptiveSelectionPolicy(
        policy_id=_string(_required(item, "policy_id"), "policy.policy_id"),
        max_data_freshness_days=_integer(_required(item, "max_data_freshness_days"), "policy.max_data_freshness_days"),
        minimum_regime_confidence=_number(_required(item, "minimum_regime_confidence"), "policy.minimum_regime_confidence"),
        minimum_score=_number(_required(item, "minimum_score"), "policy.minimum_score"),
        volatility_penalty=_number(_required(item, "volatility_penalty"), "policy.volatility_penalty"),
        cost_penalty=_number(_required(item, "cost_penalty"), "policy.cost_penalty"),
        max_recommendations=_integer(item.get("max_recommendations", 1), "policy.max_recommendations"),
        fail_closed_on_unknown_regime=_bool(item.get("fail_closed_on_unknown_regime", True), "policy.fail_closed_on_unknown_regime"),
    )


def build_shadow_selection(payload: Mapping[str, object]) -> SelectionDecision:
    """Validate one versioned input bundle and produce a no-order decision record."""
    if payload.get("schema") != SELECTION_INPUT_SCHEMA:
        raise ValueError(f"schema must equal {SELECTION_INPUT_SCHEMA}")
    return select_shadow(
        decision_id=_string(_required(payload, "decision_id"), "decision_id"),
        created_at=_datetime(_required(payload, "created_at"), "created_at"),
        market_context=_parse_market_context(_required(payload, "market_context")),
        candidates=[_parse_candidate(item) for item in _sequence(_required(payload, "candidates"), "candidates")],
        platform_health=[
            _parse_platform_health(item)
            for item in _sequence(_required(payload, "platform_health"), "platform_health")
        ],
        plugin_adjustments=[
            _parse_plugin_adjustment(item)
            for item in _sequence(payload.get("plugin_adjustments", []), "plugin_adjustments")
        ],
        policy=_parse_policy(_required(payload, "policy")),
    )


def load_shadow_selection_input(path: str | Path) -> Mapping[str, object]:
    """Read a JSON input bundle without accepting executable configuration."""
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read selection input: {path}") from exc
    return _mapping(payload, "selection input")


__all__ = ["SELECTION_INPUT_SCHEMA", "build_shadow_selection", "load_shadow_selection_input"]
