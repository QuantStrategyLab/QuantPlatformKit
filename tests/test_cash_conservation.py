from __future__ import annotations

from decimal import Decimal
from fractions import Fraction
from types import SimpleNamespace

import pytest

from quant_platform_kit.common.broker_reconciliation import BrokerReconciliationFinding
from quant_platform_kit.common.cash_conservation import (
    CASH_CONSERVATION_SCHEMA_VERSION,
    evaluate_cash_conservation,
    expected_cash_delta,
)


INVALID_NUMBERS = [True, False, float("nan"), float("inf"), -float("inf"), "1", None, 1j]


@pytest.mark.parametrize(("side", "expected"), [("buy", -1001.0), ("sell", 999.0)])
def test_fill_notional_and_fee(side, expected) -> None:
    result = expected_cash_delta([{"side": side, "quantity": 100, "price": 10}], [1], None, None)

    assert result == expected
    assert isinstance(result, float)


def test_dividends_and_signed_transfers_with_multiple_fills() -> None:
    fills = [
        {"side": "buy", "quantity": 100, "price": 10},
        {"side": "sell", "quantity": 20, "price": 12},
    ]

    assert expected_cash_delta(fills, [1, 2], [500, -100], [5, 10]) == -348.0


def test_none_arguments_are_empty() -> None:
    assert expected_cash_delta(None, None, None, None) == 0.0
    assert expected_cash_delta([], [], [], []) == 0.0


@pytest.mark.parametrize("quantity_field", ["quantity", "qty", "filled_quantity", "executed_qty"])
@pytest.mark.parametrize("price_field", ["price", "executed_price", "average_fill_price"])
@pytest.mark.parametrize("attribute_style", [False, True])
def test_fill_field_aliases(quantity_field, price_field, attribute_style) -> None:
    fill = {"side": "sell", quantity_field: 100, price_field: 10}
    if attribute_style:
        fill = SimpleNamespace(**fill)

    assert expected_cash_delta([fill], None, None, None) == 1000.0


def test_generators_and_non_float_numbers() -> None:
    fills = ({"side": "buy", "quantity": Decimal("2.5"), "price": Fraction(3, 2)} for _ in range(2))

    assert expected_cash_delta(
        fills, (fee for fee in [Decimal("0.5")]),
        (transfer for transfer in [-1]), (dividend for dividend in [Fraction(1, 2)]),
    ) == -8.5


def test_zero_amounts_are_valid() -> None:
    assert expected_cash_delta(
        [{"side": "buy", "quantity": 0, "price": 0}], [0], [0], [0],
    ) == 0.0


@pytest.mark.parametrize("side", ["hold", "BUY", "", None, True, 1])
def test_invalid_side(side) -> None:
    with pytest.raises(ValueError, match="^CASH_CONSERVATION_INVALID$"):
        expected_cash_delta([{"side": side, "quantity": 100, "price": 10}], None, None, None)


@pytest.mark.parametrize("missing_field", ["side", "quantity", "price"])
def test_missing_fill_fields(missing_field) -> None:
    fill = {"side": "buy", "quantity": 100, "price": 10}
    del fill[missing_field]

    with pytest.raises(ValueError, match="^CASH_CONSERVATION_INVALID$"):
        expected_cash_delta([fill], None, None, None)


@pytest.mark.parametrize("field", ["quantity", "price", "fee", "dividend"])
def test_negative_unsigned_amounts(field) -> None:
    fill = {"side": "buy", "quantity": 100, "price": 10}
    fees, dividends = [], []
    if field in fill:
        fill[field] = -1
    elif field == "fee":
        fees = [-1]
    else:
        dividends = [-1]

    with pytest.raises(ValueError, match="^CASH_CONSERVATION_INVALID$"):
        expected_cash_delta([fill], fees, None, dividends)


@pytest.mark.parametrize("value", INVALID_NUMBERS)
@pytest.mark.parametrize("field", ["quantity", "price", "fee", "transfer", "dividend"])
def test_invalid_cash_inputs(field, value) -> None:
    fill = {"side": "buy", "quantity": 100, "price": 10}
    amounts = {"fee": [], "transfer": [], "dividend": []}
    if field in fill:
        fill[field] = value
    else:
        amounts[field] = [value]

    with pytest.raises(ValueError, match="^CASH_CONSERVATION_INVALID$"):
        expected_cash_delta([fill], amounts["fee"], amounts["transfer"], amounts["dividend"])


@pytest.mark.parametrize("observed", [-1002.0, -1000.0])
def test_one_dollar_mismatch_uses_the_broker_enum(observed) -> None:
    findings = evaluate_cash_conservation(-1001.0, observed)

    assert len(findings) == 1
    assert findings[0] is BrokerReconciliationFinding.CASH_CONSERVATION_MISMATCH
    assert findings[0].value == "cash_conservation_mismatch"


@pytest.mark.parametrize(
    ("observed", "tolerance"), [(-1001.0, 0.0), (-1000.5, 1.0), (-1000.0, 1.0), (-1002.0, 1.0)],
)
def test_equal_or_within_tolerance_has_no_finding(observed, tolerance) -> None:
    assert evaluate_cash_conservation(-1001.0, observed, tolerance=tolerance) == ()


@pytest.mark.parametrize("value", INVALID_NUMBERS)
@pytest.mark.parametrize("field", ["expected_delta", "observed_delta", "tolerance"])
def test_invalid_evaluation_inputs(field, value) -> None:
    arguments = {"expected_delta": 0, "observed_delta": 0, "tolerance": 0}
    arguments[field] = value

    with pytest.raises(ValueError, match="^CASH_CONSERVATION_INVALID$"):
        evaluate_cash_conservation(**arguments)


def test_negative_tolerance_is_invalid() -> None:
    with pytest.raises(ValueError, match="^CASH_CONSERVATION_INVALID$"):
        evaluate_cash_conservation(0, 0, tolerance=-1)


@pytest.mark.parametrize(
    ("fills", "fees"),
    [
        ([{"side": "buy", "quantity": 1e308, "price": 10}], None),
        ([{"side": "sell", "quantity": 1e308, "price": 1}] * 2, None),
        ([{"side": "sell", "quantity": 1e308, "price": 10},
          {"side": "buy", "quantity": 1e308, "price": 10}], None),
        (None, [1e308, 1e308]),
    ],
)
def test_overflowing_cash_delta_is_invalid(fills, fees) -> None:
    with pytest.raises(ValueError, match="^CASH_CONSERVATION_INVALID$"):
        expected_cash_delta(fills, fees, None, None)


def test_attribute_property_failure_is_normalized() -> None:
    class BrokenFill:
        @property
        def side(self):
            raise RuntimeError("db offline")

    with pytest.raises(ValueError, match="^CASH_CONSERVATION_INVALID$") as error:
        expected_cash_delta([BrokenFill()], None, None, None)
    assert isinstance(error.value.__cause__, RuntimeError)


def test_schema_version() -> None:
    assert CASH_CONSERVATION_SCHEMA_VERSION == "qsl.cash_conservation.v1"
