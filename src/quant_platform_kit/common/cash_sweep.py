"""Shared helpers for cash sweep execution flows."""

from __future__ import annotations

import math
from collections.abc import Iterable


def estimate_cash_sweep_sale_quantity_to_fund_buy(
    max_quantity: int,
    cash_sweep_price: float,
    base_buying_power: float,
    funding_needs: Iterable[tuple[float, float]],
) -> int:
    """Estimate how much cash sweep symbol to sell to fund the first buy candidate.

    The helper keeps platform-specific data fetching outside of shared logic.
    Each funding need is provided as ``(underweight_value, ask_price)``.
    """
    if max_quantity <= 0:
        return 0
    sweep_price = float(cash_sweep_price or 0.0)
    if sweep_price <= 0.0:
        return 0
    current_buying_power = max(0.0, float(base_buying_power or 0.0))

    for underweight_value, ask_price in funding_needs:
        needed_value = float(underweight_value or 0.0)
        quote_price = float(ask_price or 0.0)
        if needed_value <= 0.0 or quote_price <= 0.0:
            continue
        max_buy_quantity = int(needed_value // quote_price)
        if max_buy_quantity <= 0:
            continue
        required_buying_power = max_buy_quantity * quote_price
        if current_buying_power >= required_buying_power:
            return 0
        return min(
            int(max_quantity),
            max(1, math.ceil((required_buying_power - current_buying_power) / sweep_price)),
        )
    return 0

