"""Helpers for whole-share execution on small accounts."""

from __future__ import annotations

from collections.abc import Iterable, Mapping


__all__ = ["project_unbuyable_value_targets_to_cash"]


def _normalize_symbol(value: object) -> str:
    return str(value or "").strip().upper()


def project_unbuyable_value_targets_to_cash(
    target_values: Mapping[str, object],
    prices: Mapping[str, object],
    *,
    symbols: Iterable[str] | None = None,
    quantity_step: float = 1.0,
) -> tuple[dict[str, float], tuple[str, ...]]:
    """Zero value targets that cannot buy one execution quantity step.

    This keeps strategy output intact while letting whole-share execution layers
    avoid preserving a single oversized share for a sleeve whose target is less
    than one tradable unit.
    """

    adjusted = {
        _normalize_symbol(symbol): float(value or 0.0)
        for symbol, value in dict(target_values or {}).items()
    }
    step = max(0.0, float(quantity_step or 0.0))
    if step <= 0.0:
        return adjusted, ()

    if symbols is None:
        candidate_symbols = tuple(adjusted)
    else:
        candidate_symbols = tuple(dict.fromkeys(_normalize_symbol(symbol) for symbol in symbols))

    substituted: list[str] = []
    normalized_prices = {
        _normalize_symbol(symbol): float(price or 0.0)
        for symbol, price in dict(prices or {}).items()
    }
    for symbol in candidate_symbols:
        if not symbol:
            continue
        target_value = max(0.0, float(adjusted.get(symbol, 0.0) or 0.0))
        price = max(0.0, float(normalized_prices.get(symbol, 0.0) or 0.0))
        if price <= 0.0:
            continue
        if 0.0 < target_value < (price * step):
            adjusted[symbol] = 0.0
            substituted.append(symbol)

    return adjusted, tuple(dict.fromkeys(substituted))
