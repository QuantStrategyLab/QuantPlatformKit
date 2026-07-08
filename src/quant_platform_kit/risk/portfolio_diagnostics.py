"""Portfolio-level risk diagnostics for runtime enrichment."""

from __future__ import annotations

from typing import Any

from quant_platform_kit.common.models import Position


def _position_unrealized_pnl(position: Position | Any) -> float | None:
    quantity = float(getattr(position, "quantity", 0.0) or 0.0)
    if quantity == 0.0:
        return 0.0
    market_value = float(getattr(position, "market_value", 0.0) or 0.0)
    average_cost = getattr(position, "average_cost", None)
    if average_cost is None:
        return None
    cost_basis = abs(quantity) * float(average_cost)
    return market_value - cost_basis


def compute_unrealized_pnl_pct(snapshot: Any) -> float | None:
    """Return portfolio unrealized PnL as a fraction of total_equity."""
    total_equity = float(getattr(snapshot, "total_equity", 0.0) or 0.0)
    if total_equity <= 0.0:
        return None

    metadata = dict(getattr(snapshot, "metadata", None) or {})
    if metadata.get("unrealized_pnl_pct") is not None:
        return float(metadata["unrealized_pnl_pct"])

    positions = getattr(snapshot, "positions", ()) or ()
    if not positions:
        return 0.0

    unrealized = 0.0
    has_cost_basis = False
    for position in positions:
        position_pnl = _position_unrealized_pnl(position)
        if position_pnl is None:
            continue
        has_cost_basis = True
        unrealized += position_pnl

    if not has_cost_basis:
        return None
    return unrealized / total_equity


def extract_portfolio_risk_diagnostics(snapshot: Any) -> dict[str, float | int]:
    """Extract risk diagnostics from a portfolio snapshot for runtime metadata."""
    diagnostics: dict[str, float | int] = {}
    pnl_pct = compute_unrealized_pnl_pct(snapshot)
    if pnl_pct is not None:
        diagnostics["unrealized_pnl_pct"] = float(pnl_pct)

    metadata = dict(getattr(snapshot, "metadata", None) or {})
    if metadata.get("consecutive_losses") is not None:
        diagnostics["consecutive_losses"] = int(metadata["consecutive_losses"])

    return diagnostics
