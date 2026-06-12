"""Broker execution cost helpers."""

from __future__ import annotations

import math
from dataclasses import dataclass


__all__ = [
    "BrokerCostProfile",
    "minimum_economic_order_notional_usd",
]


@dataclass(frozen=True)
class BrokerCostProfile:
    """Small account broker cost inputs for economic order filtering."""

    fixed_order_fee_usd: float = 0.0
    minimum_order_fee_usd: float = 0.0
    max_fixed_fee_bps: float = 100.0
    explicit_min_order_notional_usd: float = 0.0


def _non_negative_finite(value: object, *, default: float = 0.0) -> float:
    try:
        numeric = float(value or 0.0)
    except (TypeError, ValueError):
        return float(default)
    if not math.isfinite(numeric):
        return float(default)
    return max(0.0, numeric)


def minimum_economic_order_notional_usd(profile: BrokerCostProfile | None) -> float:
    """Return the minimum order notional implied by fixed order costs.

    The helper intentionally models only fixed or minimum per-order fees. Per-share
    fees and sell-side regulatory fees do not produce a stable notional floor and
    should be handled by cost reporting/backtests rather than blocking risk exits.
    """

    if profile is None:
        return 0.0
    explicit_floor = _non_negative_finite(profile.explicit_min_order_notional_usd)
    fee_floor = max(
        _non_negative_finite(profile.fixed_order_fee_usd),
        _non_negative_finite(profile.minimum_order_fee_usd),
    )
    max_fee_bps = _non_negative_finite(profile.max_fixed_fee_bps)
    if fee_floor <= 0.0 or max_fee_bps <= 0.0:
        return explicit_floor
    implied_floor = fee_floor / (max_fee_bps / 10_000.0)
    return max(explicit_floor, implied_floor)
