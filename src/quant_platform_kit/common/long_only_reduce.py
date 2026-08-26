"""Broker-neutral validation for a reconciled long-only reduce-only order.

This contract deliberately does not create an order or infer a position from
an order side.  A platform has to provide a fresh broker reconciliation of
the long, short, and sellable quantities immediately before submission.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any

from .models import OrderIntent


class LongOnlyReduceOnlyFinding(str, Enum):
    """Stable, non-sensitive reasons for refusing a reduce-only request."""

    INVALID_ORDER = "invalid_order"
    NOT_SELL = "not_sell"
    SYMBOL_NOT_ALLOWED = "symbol_not_allowed"
    LONG_QUANTITY_UNAVAILABLE = "long_quantity_unavailable"
    SHORT_QUANTITY_PRESENT = "short_quantity_present"
    SELLABLE_QUANTITY_UNAVAILABLE = "sellable_quantity_unavailable"
    SELLABLE_EXCEEDS_LONG = "sellable_exceeds_long"
    QUANTITY_EXCEEDS_SELLABLE = "quantity_exceeds_sellable"


def _symbol(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().upper()
    return normalized or None


def _nonnegative_quantity(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    quantity = float(value)
    return quantity if math.isfinite(quantity) and quantity >= 0.0 else None


def _positive_quantity(value: object) -> float | None:
    quantity = _nonnegative_quantity(value)
    return quantity if quantity is not None and quantity > 0.0 else None


def _normalized_symbols(values: Iterable[object]) -> frozenset[str] | None:
    symbols: set[str] = set()
    for value in values:
        symbol = _symbol(value)
        if symbol is None:
            return None
        symbols.add(symbol)
    return frozenset(symbols) if symbols else None


@dataclass(frozen=True)
class LongOnlyReduceOnlyValidation:
    """The result of checking one order against refreshed broker facts."""

    approved: bool
    findings: tuple[str, ...]

    def to_safe_dict(self) -> dict[str, object]:
        """Expose policy status without account, quantity, or order data."""

        return asdict(self)


def validate_long_only_reduce_only_order(
    order: OrderIntent | object,
    *,
    long_quantities: Mapping[object, object],
    short_quantities: Mapping[object, object],
    sellable_quantities: Mapping[object, object],
    allowed_symbols: Iterable[object],
) -> LongOnlyReduceOnlyValidation:
    """Accept only a sell that reduces a reconciled, long-only cash position.

    The caller must obtain all three quantity maps from the same fresh broker
    reconciliation.  Missing facts fail closed; a value target, account
    balance, or a bare ``sell`` side is not sufficient evidence of reduction.
    """

    findings: list[str] = []

    if not isinstance(order, OrderIntent):
        return LongOnlyReduceOnlyValidation(
            approved=False,
            findings=(LongOnlyReduceOnlyFinding.INVALID_ORDER.value,),
        )

    symbol = _symbol(order.symbol)
    if symbol is None or str(order.side or "").strip().lower() != "sell":
        if symbol is None:
            findings.append(LongOnlyReduceOnlyFinding.INVALID_ORDER.value)
        if str(order.side or "").strip().lower() != "sell":
            findings.append(LongOnlyReduceOnlyFinding.NOT_SELL.value)
        return LongOnlyReduceOnlyValidation(approved=False, findings=tuple(findings))

    normalized_allowed = _normalized_symbols(allowed_symbols)
    if normalized_allowed is None or symbol not in normalized_allowed:
        findings.append(LongOnlyReduceOnlyFinding.SYMBOL_NOT_ALLOWED.value)

    requested_quantity = _positive_quantity(order.quantity)
    if requested_quantity is None:
        findings.append(LongOnlyReduceOnlyFinding.INVALID_ORDER.value)

    long_quantity = _nonnegative_quantity(long_quantities.get(symbol))
    if long_quantity is None or long_quantity <= 0.0:
        findings.append(LongOnlyReduceOnlyFinding.LONG_QUANTITY_UNAVAILABLE.value)

    short_quantity = _nonnegative_quantity(short_quantities.get(symbol))
    if short_quantity is None:
        findings.append(LongOnlyReduceOnlyFinding.SHORT_QUANTITY_PRESENT.value)
    elif short_quantity > 0.0:
        findings.append(LongOnlyReduceOnlyFinding.SHORT_QUANTITY_PRESENT.value)

    sellable_quantity = _nonnegative_quantity(sellable_quantities.get(symbol))
    if sellable_quantity is None:
        findings.append(LongOnlyReduceOnlyFinding.SELLABLE_QUANTITY_UNAVAILABLE.value)
    elif long_quantity is not None and sellable_quantity > long_quantity + 1e-9:
        findings.append(LongOnlyReduceOnlyFinding.SELLABLE_EXCEEDS_LONG.value)

    if (
        requested_quantity is not None
        and sellable_quantity is not None
        and requested_quantity > sellable_quantity + 1e-9
    ):
        findings.append(LongOnlyReduceOnlyFinding.QUANTITY_EXCEEDS_SELLABLE.value)

    return LongOnlyReduceOnlyValidation(
        approved=not findings,
        findings=tuple(findings),
    )


__all__ = [
    "LongOnlyReduceOnlyFinding",
    "LongOnlyReduceOnlyValidation",
    "validate_long_only_reduce_only_order",
]
