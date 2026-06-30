"""Risk management contracts — shared types for the unified risk framework.

Previously, risk signal types were defined ad-hoc in QuantStrategyPlugins
and market regime types were in strategy_lifecycle.market_regime. This module
consolidates them into a single, versioned contract.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping


# ---------------------------------------------------------------------------
# Regime classification
# ---------------------------------------------------------------------------

REGIME_NORMAL = "normal"
REGIME_ELEVATED = "elevated"
REGIME_STRESS = "stress"
REGIME_UNKNOWN = "unknown"

_REGIME_RISK_ORDER = (REGIME_NORMAL, REGIME_ELEVATED, REGIME_STRESS)


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
