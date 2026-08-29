"""Versioned, non-authoritative adaptive-allocation records."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Mapping


MARKET_CONTEXT_SCHEMA = "qsl.market_context_snapshot.v1"
PLATFORM_HEALTH_SCHEMA = "qsl.platform_health_snapshot.v1"
SELECTION_DECISION_SCHEMA = "qsl.selection_decision.v1"
SHADOW_ONLY_AUTHORITY = "shadow_only"
_SHADOW_ELIGIBLE_STAGES = frozenset(
    {"shadow_candidate", "shadow_active", "paper_active", "live_candidate", "live_enabled"}
)


def _nonblank(value: str, field_name: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise ValueError(f"{field_name} is required")
    return normalized


def _finite(value: float, field_name: str) -> float:
    normalized = float(value)
    if not math.isfinite(normalized):
        raise ValueError(f"{field_name} must be finite")
    return normalized


def _bounded(value: float, field_name: str, *, minimum: float = 0.0, maximum: float = 1.0) -> float:
    normalized = _finite(value, field_name)
    if not minimum <= normalized <= maximum:
        raise ValueError(f"{field_name} must be between {minimum} and {maximum}")
    return normalized


def _numeric_mapping(values: Mapping[str, float], field_name: str) -> dict[str, float]:
    normalized: dict[str, float] = {}
    for key, value in values.items():
        normalized[_nonblank(key, f"{field_name} key")] = _finite(value, f"{field_name}.{key}")
    return dict(sorted(normalized.items()))


@dataclass(frozen=True)
class MarketContextSnapshot:
    """Auditable, point-in-time market data used by a Shadow decision."""

    as_of: date
    domain: str
    data_version: str
    data_freshness_days: int
    regime: str
    regime_confidence: float
    factors: Mapping[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _nonblank(self.domain, "domain")
        _nonblank(self.data_version, "data_version")
        _nonblank(self.regime, "regime")
        if int(self.data_freshness_days) < 0:
            raise ValueError("data_freshness_days must be non-negative")
        _bounded(self.regime_confidence, "regime_confidence")
        object.__setattr__(self, "factors", _numeric_mapping(self.factors, "factors"))

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": MARKET_CONTEXT_SCHEMA,
            "as_of": self.as_of.isoformat(),
            "domain": self.domain,
            "data_version": self.data_version,
            "data_freshness_days": self.data_freshness_days,
            "regime": self.regime,
            "regime_confidence": self.regime_confidence,
            "factors": dict(self.factors),
        }


@dataclass(frozen=True)
class PlatformHealthSnapshot:
    """Non-secret platform-health input for a potential Shadow route."""

    platform_id: str
    observed_at: datetime
    healthy: bool
    shadow_capable: bool
    reconciliation_ok: bool
    capacity_score: float
    expected_cost_bps: float

    def __post_init__(self) -> None:
        _nonblank(self.platform_id, "platform_id")
        _bounded(self.capacity_score, "capacity_score")
        if _finite(self.expected_cost_bps, "expected_cost_bps") < 0:
            raise ValueError("expected_cost_bps must be non-negative")

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": PLATFORM_HEALTH_SCHEMA,
            "platform_id": self.platform_id,
            "observed_at": self.observed_at.astimezone(timezone.utc).isoformat(),
            "healthy": self.healthy,
            "shadow_capable": self.shadow_capable,
            "reconciliation_ok": self.reconciliation_ok,
            "capacity_score": self.capacity_score,
            "expected_cost_bps": self.expected_cost_bps,
        }


@dataclass(frozen=True)
class PluginRiskAdjustment:
    """A plugin may scale risk down, never add risk or execution authority."""

    plugin_id: str
    risk_multiplier: float
    approved: bool = True

    def __post_init__(self) -> None:
        _nonblank(self.plugin_id, "plugin_id")
        _bounded(self.risk_multiplier, "risk_multiplier")


@dataclass(frozen=True)
class StrategyCandidate:
    """One immutable-release candidate supplied by an admitted strategy catalog."""

    strategy_profile: str
    release_digest: str
    lifecycle_stage: str
    approved_for_shadow: bool
    base_score: float
    estimated_volatility: float
    factor_exposures: Mapping[str, float] = field(default_factory=dict)
    required_plugins: tuple[str, ...] = ()
    allowed_platform_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _nonblank(self.strategy_profile, "strategy_profile")
        _nonblank(self.release_digest, "release_digest")
        _nonblank(self.lifecycle_stage, "lifecycle_stage")
        _finite(self.base_score, "base_score")
        if _finite(self.estimated_volatility, "estimated_volatility") < 0:
            raise ValueError("estimated_volatility must be non-negative")
        object.__setattr__(self, "factor_exposures", _numeric_mapping(self.factor_exposures, "factor_exposures"))
        object.__setattr__(self, "required_plugins", tuple(sorted({_nonblank(item, "required_plugins item") for item in self.required_plugins})))
        object.__setattr__(self, "allowed_platform_ids", tuple(sorted({_nonblank(item, "allowed_platform_ids item") for item in self.allowed_platform_ids})))


@dataclass(frozen=True)
class AdaptiveSelectionPolicy:
    """Frozen scoring limits; callers must version and audit this input."""

    policy_id: str
    max_data_freshness_days: int
    minimum_regime_confidence: float
    minimum_score: float
    volatility_penalty: float
    cost_penalty: float
    max_recommendations: int = 1
    fail_closed_on_unknown_regime: bool = True

    def __post_init__(self) -> None:
        _nonblank(self.policy_id, "policy_id")
        if int(self.max_data_freshness_days) < 0:
            raise ValueError("max_data_freshness_days must be non-negative")
        _bounded(self.minimum_regime_confidence, "minimum_regime_confidence")
        if _finite(self.volatility_penalty, "volatility_penalty") < 0:
            raise ValueError("volatility_penalty must be non-negative")
        if _finite(self.cost_penalty, "cost_penalty") < 0:
            raise ValueError("cost_penalty must be non-negative")
        if int(self.max_recommendations) < 1:
            raise ValueError("max_recommendations must be at least one")


@dataclass(frozen=True)
class CandidateDecision:
    strategy_profile: str
    release_digest: str
    selected_platform_id: str | None
    score: float | None
    risk_multiplier: float
    accepted: bool
    reasons: tuple[str, ...]
    proposed_weight: float = 0.0

    def __post_init__(self) -> None:
        _nonblank(self.strategy_profile, "strategy_profile")
        _nonblank(self.release_digest, "release_digest")
        _bounded(self.risk_multiplier, "risk_multiplier")
        if self.score is not None:
            _finite(self.score, "score")
        if float(self.proposed_weight) != 0.0:
            raise ValueError("shadow-only decisions must not propose a non-zero weight")

    def to_dict(self) -> dict[str, object]:
        return {
            "strategy_profile": self.strategy_profile,
            "release_digest": self.release_digest,
            "selected_platform_id": self.selected_platform_id,
            "score": self.score,
            "risk_multiplier": self.risk_multiplier,
            "accepted": self.accepted,
            "reasons": list(self.reasons),
            "proposed_weight": self.proposed_weight,
        }


@dataclass(frozen=True)
class SelectionDecision:
    """A complete, immutable audit record with intentionally zero authority."""

    decision_id: str
    created_at: datetime
    market_context: MarketContextSnapshot
    policy_id: str
    candidate_decisions: tuple[CandidateDecision, ...]
    recommended_strategy_profile: str | None
    recommended_platform_id: str | None
    authority: str = SHADOW_ONLY_AUTHORITY
    no_order: bool = True

    def __post_init__(self) -> None:
        _nonblank(self.decision_id, "decision_id")
        _nonblank(self.policy_id, "policy_id")
        if self.authority != SHADOW_ONLY_AUTHORITY or not self.no_order:
            raise ValueError("adaptive selection is shadow-only and cannot authorize orders")
        if any(item.proposed_weight != 0.0 for item in self.candidate_decisions):
            raise ValueError("shadow-only decisions must retain zero proposed weights")

    def to_dict(self) -> dict[str, object]:
        payload = {
            "schema": SELECTION_DECISION_SCHEMA,
            "decision_id": self.decision_id,
            "created_at": self.created_at.astimezone(timezone.utc).isoformat(),
            "authority": self.authority,
            "no_order": self.no_order,
            "market_context": self.market_context.to_dict(),
            "policy_id": self.policy_id,
            "recommended_strategy_profile": self.recommended_strategy_profile,
            "recommended_platform_id": self.recommended_platform_id,
            "candidates": [item.to_dict() for item in self.candidate_decisions],
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        payload["input_digest"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return payload
