"""Pure-offline Time-Weighted Return (TWR) & net-inflow capital ladder (Roadmap P1 #2).

Uses the start-of-period external cash-flow convention consistent with
``quant_platform_kit.risk.flow_adjusted_hwm`` for multi-session NAV series:
each session after the anchor computes
``r_t = (V_t - (V_{t-1} + CF_t)) / (V_{t-1} + CF_t)`` (where ``CF_t`` is the
external deposit/withdrawal entering before session ``t``'s return).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
import math


def _is_finite(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


@dataclass(frozen=True)
class NavCashFlowObservation:
    """One session NAV snapshot with associated external cash flow."""

    session_date: date
    nav_usd: float
    external_cash_flow_usd: float = 0.0


@dataclass(frozen=True)
class CapitalLadderTier:
    """Named net-capital tier threshold in USD."""

    name: str
    min_nav_usd: float


DEFAULT_CAPITAL_LADDER_TIERS: tuple[CapitalLadderTier, ...] = (
    CapitalLadderTier(name="STARTER", min_nav_usd=0.0),
    CapitalLadderTier(name="PILOT", min_nav_usd=1_000.0),
    CapitalLadderTier(name="GROWTH", min_nav_usd=5_000.0),
    CapitalLadderTier(name="SCALE", min_nav_usd=25_000.0),
)


@dataclass(frozen=True)
class TwrCapitalLadderReport:
    """Flow-invariant TWR summary paired with current capital-ladder tier."""

    session_count: int
    twr_index: float
    cumulative_twr_return: float
    annualized_twr_return: float | None
    ending_nav_usd: float
    cumulative_net_inflow_usd: float
    current_tier: CapitalLadderTier
    next_tier: CapitalLadderTier | None
    distance_to_next_tier_usd: float


def _validate_tiers(tiers: Iterable[CapitalLadderTier]) -> tuple[CapitalLadderTier, ...]:
    tier_list = list(tiers)
    if not tier_list:
        raise ValueError("EMPTY_CAPITAL_LADDER_TIERS")
    prev_min = -math.inf
    for tier in tier_list:
        if not isinstance(tier.name, str) or not tier.name.strip():
            raise ValueError("INVALID_TIER_NAME")
        if not _is_finite(tier.min_nav_usd) or float(tier.min_nav_usd) < 0.0:
            raise ValueError("INVALID_TIER_MIN_NAV")
        val = float(tier.min_nav_usd)
        if val <= prev_min and prev_min != -math.inf:
            raise ValueError("UNSORTED_OR_DUPLICATE_CAPITAL_LADDER_TIERS")
        prev_min = val
    if float(tier_list[0].min_nav_usd) != 0.0:
        raise ValueError("CAPITAL_LADDER_MUST_START_AT_ZERO")
    return tuple(tier_list)


def resolve_capital_ladder_tier(
    nav_usd: float,
    tiers: Iterable[CapitalLadderTier] = DEFAULT_CAPITAL_LADDER_TIERS,
) -> tuple[CapitalLadderTier, CapitalLadderTier | None, float]:
    """Return ``(current_tier, next_tier, distance_to_next_tier_usd)``."""
    if not _is_finite(nav_usd) or float(nav_usd) < 0.0:
        raise ValueError("INVALID_NAV_USD")
    validated = _validate_tiers(tiers)
    nav = float(nav_usd)

    current_idx = 0
    for idx, tier in enumerate(validated):
        if nav >= float(tier.min_nav_usd):
            current_idx = idx
    current = validated[current_idx]
    if current_idx + 1 < len(validated):
        nxt = validated[current_idx + 1]
        distance = max(0.0, float(nxt.min_nav_usd) - nav)
    else:
        nxt = None
        distance = 0.0
    return current, nxt, distance


def evaluate_twr_and_capital_ladder(
    observations: Iterable[NavCashFlowObservation],
    *,
    tiers: Iterable[CapitalLadderTier] = DEFAULT_CAPITAL_LADDER_TIERS,
    periods_per_year: int = 252,
) -> TwrCapitalLadderReport:
    """Compute exact chain-linked TWR and capital-ladder progress."""
    if isinstance(periods_per_year, bool) or not isinstance(periods_per_year, int) or periods_per_year < 1:
        raise ValueError("INVALID_PERIODS_PER_YEAR")
    validated_tiers = _validate_tiers(tiers)
    obs_list = list(observations)
    if not obs_list:
        raise ValueError("EMPTY_OBSERVATIONS")

    for idx, obs in enumerate(obs_list):
        if not isinstance(obs.session_date, date):
            raise ValueError("INVALID_SESSION_DATE")
        if not _is_finite(obs.nav_usd) or float(obs.nav_usd) <= 0.0:
            raise ValueError("INVALID_NAV_USD")
        if not _is_finite(obs.external_cash_flow_usd):
            raise ValueError("INVALID_EXTERNAL_CASH_FLOW")
        if idx > 0 and obs.session_date <= obs_list[idx - 1].session_date:
            raise ValueError("UNSORTED_OR_DUPLICATE_SESSION_DATE")

    twr_index = 1.0
    net_inflow = float(obs_list[0].external_cash_flow_usd)
    for idx in range(1, len(obs_list)):
        prev_nav = float(obs_list[idx - 1].nav_usd)
        curr_nav = float(obs_list[idx].nav_usd)
        flow = float(obs_list[idx].external_cash_flow_usd)
        net_inflow += flow
        denom = prev_nav + flow
        if denom <= 0.0:
            raise ValueError("NON_POSITIVE_RETURN_BASE")
        period_factor = curr_nav / denom
        twr_index *= period_factor

    n_return_periods = len(obs_list) - 1
    annualized = (twr_index ** (periods_per_year / n_return_periods) - 1.0) if n_return_periods >= 1 else None
    ending_nav = float(obs_list[-1].nav_usd)
    current_tier, next_tier, distance = resolve_capital_ladder_tier(ending_nav, tiers=validated_tiers)

    return TwrCapitalLadderReport(
        session_count=len(obs_list),
        twr_index=twr_index,
        cumulative_twr_return=twr_index - 1.0,
        annualized_twr_return=annualized,
        ending_nav_usd=ending_nav,
        cumulative_net_inflow_usd=net_inflow,
        current_tier=current_tier,
        next_tier=next_tier,
        distance_to_next_tier_usd=distance,
    )


__all__ = [
    "CapitalLadderTier",
    "DEFAULT_CAPITAL_LADDER_TIERS",
    "NavCashFlowObservation",
    "TwrCapitalLadderReport",
    "evaluate_twr_and_capital_ladder",
    "resolve_capital_ladder_tier",
]
