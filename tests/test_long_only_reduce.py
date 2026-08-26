from __future__ import annotations

import pytest

from quant_platform_kit.common.long_only_reduce import (
    LongOnlyReduceOnlyFinding,
    validate_long_only_reduce_only_order,
)
from quant_platform_kit.common.models import OrderIntent


def _validate(order: OrderIntent, **overrides):
    payload = {
        "long_quantities": {"SOXL": 10.0},
        "short_quantities": {"SOXL": 0.0},
        "sellable_quantities": {"SOXL": 8.0},
        "allowed_symbols": ("SOXL",),
        **overrides,
    }
    return validate_long_only_reduce_only_order(order, **payload)


def test_reconciled_long_only_sell_is_approved() -> None:
    result = _validate(OrderIntent(symbol="soxl", side="sell", quantity=8.0))

    assert result.approved is True
    assert result.findings == ()
    assert result.to_safe_dict() == {"approved": True, "findings": ()}


@pytest.mark.parametrize(
    ("order", "overrides", "expected"),
    (
        (
            OrderIntent(symbol="SOXL", side="buy", quantity=1.0),
            {},
            LongOnlyReduceOnlyFinding.NOT_SELL.value,
        ),
        (
            OrderIntent(symbol="SOXL", side="sell", quantity=9.0),
            {},
            LongOnlyReduceOnlyFinding.QUANTITY_EXCEEDS_SELLABLE.value,
        ),
        (
            OrderIntent(symbol="TQQQ", side="sell", quantity=1.0),
            {"long_quantities": {"TQQQ": 1.0}, "short_quantities": {"TQQQ": 0.0}, "sellable_quantities": {"TQQQ": 1.0}},
            LongOnlyReduceOnlyFinding.SYMBOL_NOT_ALLOWED.value,
        ),
        (
            OrderIntent(symbol="SOXL", side="sell", quantity=1.0),
            {"short_quantities": {"SOXL": 1.0}},
            LongOnlyReduceOnlyFinding.SHORT_QUANTITY_PRESENT.value,
        ),
        (
            OrderIntent(symbol="SOXL", side="sell", quantity=1.0),
            {"sellable_quantities": {}},
            LongOnlyReduceOnlyFinding.SELLABLE_QUANTITY_UNAVAILABLE.value,
        ),
    ),
)
def test_invalid_or_nonreducing_orders_fail_closed(order, overrides, expected) -> None:
    result = _validate(order, **overrides)

    assert result.approved is False
    assert expected in result.findings


def test_invalid_order_object_fails_closed() -> None:
    result = validate_long_only_reduce_only_order(
        object(),
        long_quantities={},
        short_quantities={},
        sellable_quantities={},
        allowed_symbols=("SOXL",),
    )

    assert result.approved is False
    assert result.findings == (LongOnlyReduceOnlyFinding.INVALID_ORDER.value,)
