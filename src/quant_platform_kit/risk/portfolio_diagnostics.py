"""Portfolio-level risk diagnostics for runtime enrichment."""

from __future__ import annotations

import math
from typing import Any

from quant_platform_kit.common.models import Position


def _finite_number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        number = float(value)
    except (OverflowError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def _position_unrealized_pnl(position: Position | Any) -> float | None:
    quantity = _finite_number(getattr(position, "quantity", None))
    market_value = _finite_number(getattr(position, "market_value", None))
    if quantity is None or market_value is None:
        return None
    if quantity == 0.0:
        return 0.0
    average_cost = getattr(position, "average_cost", None)
    cost = _finite_number(average_cost)
    if cost is None:
        return None
    # Keep the signed quantity so shorts use market_value - quantity * cost.
    pnl = market_value - quantity * cost
    return pnl if math.isfinite(pnl) else None


def _position_coverage(positions: Any) -> tuple[float, float | None]:
    normalized = tuple(positions or ())
    if not normalized:
        return 1.0, 0.0

    known = 0
    unrealized = 0.0
    for position in normalized:
        position_pnl = _position_unrealized_pnl(position)
        if position_pnl is None:
            continue
        known += 1
        unrealized += position_pnl
    coverage = known / len(normalized)
    if coverage < 1.0 or not math.isfinite(unrealized):
        return coverage, None
    return coverage, unrealized


def compute_unrealized_pnl_pct(snapshot: Any) -> float | None:
    """Return portfolio unrealized PnL as a fraction of total_equity.

    Partial cost coverage or non-finite mark/cost values return unknown
    (``None``).  Only complete coverage is treated as a full PnL figure.
    """
    total_equity = _finite_number(getattr(snapshot, "total_equity", 0.0) or 0.0)
    if total_equity is None or total_equity <= 0.0:
        return None

    metadata = dict(getattr(snapshot, "metadata", None) or {})
    if metadata.get("unrealized_pnl_pct") is not None:
        override = _finite_number(metadata["unrealized_pnl_pct"])
        return override

    coverage, unrealized = _position_coverage(getattr(snapshot, "positions", ()) or ())
    if coverage < 1.0 or unrealized is None:
        return None
    pnl_pct = unrealized / total_equity
    return pnl_pct if math.isfinite(pnl_pct) else None


def extract_portfolio_risk_diagnostics(snapshot: Any) -> dict[str, float | int | str]:
    """Extract risk diagnostics from a portfolio snapshot for runtime metadata."""
    diagnostics: dict[str, float | int | str] = {}
    metadata = dict(getattr(snapshot, "metadata", None) or {})
    pnl_pct = compute_unrealized_pnl_pct(snapshot)

    if metadata.get("unrealized_pnl_pct") is not None:
        if pnl_pct is not None:
            diagnostics["unrealized_pnl_pct"] = float(pnl_pct)
            diagnostics["unrealized_pnl_coverage"] = 1.0
            diagnostics["unrealized_pnl_source"] = "metadata"
    else:
        coverage, unrealized = _position_coverage(
            getattr(snapshot, "positions", ()) or ()
        )
        diagnostics["unrealized_pnl_coverage"] = float(coverage)
        diagnostics["unrealized_pnl_source"] = "positions"
        if coverage >= 1.0 and unrealized is not None and pnl_pct is not None:
            diagnostics["unrealized_pnl_pct"] = float(pnl_pct)

    if metadata.get("consecutive_losses") is not None:
        diagnostics["consecutive_losses"] = int(metadata["consecutive_losses"])

    return diagnostics
