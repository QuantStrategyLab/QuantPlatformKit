"""Pure cash identity: signed fill notional minus fees plus transfers and dividends."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from math import isfinite
from numbers import Number

from .broker_reconciliation import BrokerReconciliationFinding


CASH_CONSERVATION_SCHEMA_VERSION = "qsl.cash_conservation.v1"


def _number(value: object, *, non_negative: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, Number):
        raise ValueError("CASH_CONSERVATION_INVALID")
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("CASH_CONSERVATION_INVALID") from exc
    if not isfinite(number) or (non_negative and number < 0):
        raise ValueError("CASH_CONSERVATION_INVALID")
    return number


def _field(fill: object, *names: str) -> object:
    for name in names:
        if isinstance(fill, Mapping):
            if name in fill:
                return fill[name]
        else:
            try:
                return getattr(fill, name)
            except AttributeError:
                continue
            except Exception as exc:
                raise ValueError("CASH_CONSERVATION_INVALID") from exc
    return None


def expected_cash_delta(
    fills: Iterable[object] | None,
    fees: Iterable[object] | None,
    transfers: Iterable[object] | None,
    dividends: Iterable[object] | None,
) -> float:
    """Calculate cash change; buys consume cash and sells release cash.

    Fees and dividends are non-negative amounts. Transfers retain their sign.
    Missing iterables are empty; missing or invalid fill fields are rejected.
    """
    delta = 0.0
    for fill in (() if fills is None else fills):
        side = _field(fill, "side")
        if side not in ("buy", "sell"):
            raise ValueError("CASH_CONSERVATION_INVALID")
        quantity = _number(
            _field(fill, "quantity", "qty", "filled_quantity", "executed_qty"),
            non_negative=True,
        )
        price = _number(_field(fill, "price", "executed_price", "average_fill_price"), non_negative=True)
        notional = quantity * price
        if not isfinite(notional):
            raise ValueError("CASH_CONSERVATION_INVALID")
        delta += -notional if side == "buy" else notional
        if not isfinite(delta):
            raise ValueError("CASH_CONSERVATION_INVALID")
    for fee in (() if fees is None else fees):
        delta -= _number(fee, non_negative=True)
        if not isfinite(delta):
            raise ValueError("CASH_CONSERVATION_INVALID")
    for transfer in (() if transfers is None else transfers):
        delta += _number(transfer)
        if not isfinite(delta):
            raise ValueError("CASH_CONSERVATION_INVALID")
    for dividend in (() if dividends is None else dividends):
        delta += _number(dividend, non_negative=True)
        if not isfinite(delta):
            raise ValueError("CASH_CONSERVATION_INVALID")
    return delta


def evaluate_cash_conservation(
    expected_delta: object,
    observed_delta: object,
    *,
    tolerance: object = 0.0,
) -> tuple[BrokerReconciliationFinding, ...]:
    """Report a cash mismatch only when the absolute difference exceeds tolerance."""
    expected = _number(expected_delta)
    observed = _number(observed_delta)
    allowed_difference = _number(tolerance, non_negative=True)
    if abs(observed - expected) > allowed_difference:
        return (BrokerReconciliationFinding.CASH_CONSERVATION_MISMATCH,)
    return ()
