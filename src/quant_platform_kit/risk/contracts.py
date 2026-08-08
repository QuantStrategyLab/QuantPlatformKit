"""Risk management contracts — shared types for the unified risk framework.

Previously, risk signal types were defined ad-hoc in QuantStrategyPlugins
and market regime types were in strategy_lifecycle.market_regime. This module
consolidates them into a single, versioned contract.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Mapping


# ---------------------------------------------------------------------------
# Regime classification
# ---------------------------------------------------------------------------

REGIME_NORMAL = "normal"
REGIME_ELEVATED = "elevated"
REGIME_STRESS = "stress"
REGIME_UNKNOWN = "unknown"

_REGIME_RISK_ORDER = (REGIME_NORMAL, REGIME_ELEVATED, REGIME_STRESS)


def _is_lower_hex(value: object, length: int) -> bool:
    return (
        isinstance(value, str)
        and len(value) == length
        and all(character in "0123456789abcdef" for character in value)
    )


def normalise_regime(raw: str | None) -> str:
    """Normalise a free-form regime string to one of the canonical constants."""
    value = str(raw or "").strip().lower()
    if value in {"risk_on", "normal", "bull"}:
        return REGIME_NORMAL
    if value in {"elevated", "soft_defense", "risk_reduced"}:
        return REGIME_ELEVATED
    if value in {"stress", "hard_defense", "risk_off", "crisis"}:
        return REGIME_STRESS
    return REGIME_UNKNOWN


# ---------------------------------------------------------------------------
# Risk route constants (aligned with QuantStrategyPlugins conventions)
# ---------------------------------------------------------------------------

ROUTE_NO_ACTION = "no_action"
ROUTE_WATCH = "watch"
ROUTE_OPPORTUNITY_WATCH = "opportunity_watch"
ROUTE_RISK_REDUCED = "risk_reduced"
ROUTE_RISK_OFF = "risk_off"
ROUTE_BLOCKED = "blocked"

_RISK_ROUTE_SEVERITY: dict[str, int] = {
    ROUTE_NO_ACTION: 0,
    ROUTE_WATCH: 1,
    ROUTE_OPPORTUNITY_WATCH: 2,
    ROUTE_RISK_REDUCED: 3,
    ROUTE_RISK_OFF: 4,
    ROUTE_BLOCKED: 5,
}


@dataclass(frozen=True)
class RegimeRoute:
    """Structured classification produced by the regime detector."""

    route: str
    regime: str
    confidence: float
    reason_codes: tuple[str, ...] = ()
    suggested_action: str = ROUTE_NO_ACTION
    emergency: bool = False

    @property
    def severity(self) -> int:
        return _RISK_ROUTE_SEVERITY.get(self.route, 0)


# ---------------------------------------------------------------------------
# Risk signal contract
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RegimeContext:
    """Aggregated market context for a single evaluation point."""

    as_of: str  # ISO date
    volatility_percentile: float  # 0-1
    pairwise_correlation: float  # 0-1
    regime: str = REGIME_UNKNOWN
    vix_level: float | None = None
    credit_spread: float | None = None


@dataclass(frozen=True)
class RiskSignal:
    """A single risk signal produced by a plugin or regime detector."""

    plugin: str
    schema_version: str
    route: str
    confidence: float  # 0-1
    suggested_action: str
    reason_codes: tuple[str, ...] = ()
    execution_controls: Mapping[str, Any] = field(default_factory=dict)
    emergency: bool = False
    as_of: str = ""

    @property
    def severity(self) -> int:
        return _RISK_ROUTE_SEVERITY.get(self.route, 0)


@dataclass(frozen=True)
class RiskAssessment:
    """Aggregated result of risk evaluation across all signal sources."""

    as_of: str
    effective_route: str
    effective_regime: str
    confidence: float  # 0-1 — minimum across contributing signals
    signals: tuple[RiskSignal, ...]
    regime_context: RegimeContext | None = None
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def severity(self) -> int:
        return _RISK_ROUTE_SEVERITY.get(self.effective_route, 0)

    @property
    def actionable(self) -> bool:
        return self.effective_route not in {ROUTE_NO_ACTION, ROUTE_WATCH, ROUTE_OPPORTUNITY_WATCH}


@dataclass(frozen=True)
class RiskAction:
    """Concrete action to take in response to a risk assessment."""

    action: str
    reason: str
    budget_scalar: float = 1.0
    leverage_scalar: float = 1.0
    risk_asset_scalar: float = 1.0
    target_destination: str | None = None
    notify: bool = True


@dataclass(frozen=True)
class CandidateRiskIdentity:
    """Immutable identity of one mandate-bound promotion candidate."""

    strategy_profile: str
    account_mode: str
    strategy_revision: str
    runner_revision: str
    config_sha256: str
    input_manifest_sha256: str
    authority_receipt_sha256: str
    candidate_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        for name in ("strategy_profile", "account_mode"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value or value != value.strip():
                raise ValueError(f"{name} must be a non-empty canonical string")
        for name in ("strategy_revision", "runner_revision"):
            if not _is_lower_hex(getattr(self, name), 40):
                raise ValueError(f"{name} must be a lowercase 40-character Git revision")
        for name in (
            "config_sha256",
            "input_manifest_sha256",
            "authority_receipt_sha256",
        ):
            if not _is_lower_hex(getattr(self, name), 64):
                raise ValueError(f"{name} must be a lowercase SHA-256 digest")
        payload = {
            "strategy_profile": self.strategy_profile,
            "account_mode": self.account_mode,
            "strategy_revision": self.strategy_revision,
            "runner_revision": self.runner_revision,
            "config_sha256": self.config_sha256,
            "input_manifest_sha256": self.input_manifest_sha256,
            "authority_receipt_sha256": self.authority_receipt_sha256,
        }
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        object.__setattr__(self, "candidate_sha256", hashlib.sha256(encoded).hexdigest())


@dataclass(frozen=True)
class RiskGateAssessment:
    """Immutable redacted evidence from a scoped risk-gate evaluation."""

    contract_version: str
    scope: str
    evaluated_at: str
    policy_id: str
    policy_version: str
    qpk_source_revision: str | None
    mandate_id: str | None
    mandate_version: str | None
    mandate_authority_receipt_sha256: str | None
    mandate_scope: str | None
    candidate_identity_sha256: str | None
    decision_digest_sha256: str
    portfolio_snapshot_digest_sha256: str
    normalization_origin_digest_sha256: str | None
    effective_exposure_cap: float | None
    observed_effective_exposure: float | None
    proposed_effective_exposure: float | None
    outcome: str
    reason_codes: tuple[str, ...]
    execution_authorized: bool = False
    stop_loss_distance: float | None = None
    stop_intent_ready: bool | None = None
    strategy_breaker_triggered: bool | None = None
    account_breaker_triggered: bool | None = None
    account_drawdown_fraction: float | None = None
    drawdown_scalar: float | None = None
    risk_control_state_digest_sha256: str | None = None
    assessment_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        payload = {
            "contract_version": self.contract_version,
            "scope": self.scope,
            "evaluated_at": self.evaluated_at,
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "qpk_source_revision": self.qpk_source_revision,
            "mandate_id": self.mandate_id,
            "mandate_version": self.mandate_version,
            "mandate_authority_receipt_sha256": self.mandate_authority_receipt_sha256,
            "mandate_scope": self.mandate_scope,
            "candidate_identity_sha256": self.candidate_identity_sha256,
            "decision_digest_sha256": self.decision_digest_sha256,
            "portfolio_snapshot_digest_sha256": self.portfolio_snapshot_digest_sha256,
            "normalization_origin_digest_sha256": self.normalization_origin_digest_sha256,
            "effective_exposure_cap": self.effective_exposure_cap,
            "observed_effective_exposure": self.observed_effective_exposure,
            "proposed_effective_exposure": self.proposed_effective_exposure,
            "outcome": self.outcome,
            "reason_codes": self.reason_codes,
            "execution_authorized": self.execution_authorized,
            "stop_loss_distance": self.stop_loss_distance,
            "stop_intent_ready": self.stop_intent_ready,
            "strategy_breaker_triggered": self.strategy_breaker_triggered,
            "account_breaker_triggered": self.account_breaker_triggered,
            "account_drawdown_fraction": self.account_drawdown_fraction,
            "drawdown_scalar": self.drawdown_scalar,
            "risk_control_state_digest_sha256": self.risk_control_state_digest_sha256,
        }
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        object.__setattr__(self, "assessment_sha256", hashlib.sha256(encoded).hexdigest())


@dataclass(frozen=True)
class RiskGateResult:
    """Risk-gated decision paired with its immutable evidence receipt."""

    decision: Any
    assessment: RiskGateAssessment
