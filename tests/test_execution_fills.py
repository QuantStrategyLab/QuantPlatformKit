from __future__ import annotations

from dataclasses import FrozenInstanceError
from decimal import Decimal
from types import MappingProxyType, SimpleNamespace

import pytest

from quant_platform_kit.common.execution_fills import (
    EXECUTION_FILL_SCHEMA_VERSION,
    ExecutionFillAccumulation,
    accumulate_execution_fills,
)


def test_execution_replay_across_calls_adds_nothing() -> None:
    leg = {"broker_order_id": " OID-1 ", "execution_id": " EX-1 ", "quantity": 2}
    first = accumulate_execution_fills(None, [leg])
    replay = accumulate_execution_fills(first.state, [leg])

    assert first.state == {"oid1|ex1": 2.0}
    assert first.delta == 2.0
    assert replay.state == first.state
    assert replay.state is not first.state
    assert replay.delta == 0.0
    assert replay.findings == replay.degraded_legs == ()


def test_different_executions_on_same_order_add_quantities() -> None:
    result = accumulate_execution_fills(None, [
        {"order_id": "order", "exec_id": "a", "quantity": 2},
        {"order_id": "order", "exec_id": "b", "quantity": 3},
    ])

    assert result.state == {"order|a": 2.0, "order|b": 3.0}
    assert result.delta == 5.0


def test_late_execution_is_counted_once() -> None:
    recent = {
        "order_id": "order", "execution_id": "recent", "quantity": 2,
        "executed_at": "2026-10-22T12:00:00Z",
    }
    late = {
        "order_id": "order", "execution_id": "late", "quantity": 3,
        "executed_at": "2026-10-22T11:00:00Z",
    }
    first = accumulate_execution_fills(None, [recent])
    second = accumulate_execution_fills(first.state, [recent, late])
    replay = accumulate_execution_fills(second.state, [late, recent])

    assert second.delta == 3.0
    assert second.state == {"order|recent": 2.0, "order|late": 3.0}
    assert replay.delta == 0.0
    assert replay.state == second.state


def test_cumulative_decrease_preserves_highest_quantity() -> None:
    result = accumulate_execution_fills({"order|a": 5.0}, [
        {"order_id": "order", "exec_id": "a", "quantity": 3},
        {"order_id": "order", "exec_id": "a", "quantity": 4},
    ])

    assert result.state == {"order|a": 5.0}
    assert result.delta == 0.0
    assert result.findings == ("EXECUTION_CUMULATIVE_DECREASE",)


def test_duplicates_and_increases_within_one_iterable() -> None:
    legs = (
        {"order_id": "order", "exec_id": "a", "quantity": quantity}
        for quantity in (2, 2, 5, 3, 6)
    )
    result = accumulate_execution_fills({"order|a": 1.0}, legs)

    assert result.delta == 5.0
    assert result.state == {"order|a": 6.0}
    assert result.findings == ("EXECUTION_CUMULATIVE_DECREASE",)


@pytest.mark.parametrize("execution_id", [None, "", "  "])
def test_degraded_execution_replay_and_distinct_payload(execution_id) -> None:
    leg = {
        "broker_order_id": " OID-1 ", "execution_id": execution_id,
        "quantity": 2, "price": 100, "executed_at": "2026-10-22T11:00:00Z",
    }
    first = accumulate_execution_fills(None, [leg, dict(leg)])
    key, = first.degraded_legs
    assert key.startswith("oid1|digest:")
    assert len(key.split("digest:")[1]) == 64
    assert first.state == {key: 2.0}
    assert first.delta == 2.0

    replay = accumulate_execution_fills(first.state, [dict(reversed(list(leg.items())))])
    assert replay.delta == 0.0
    assert replay.state == first.state
    assert replay.degraded_legs == (key,)

    changed = accumulate_execution_fills(first.state, [{**leg, "price": 101}])
    changed_key, = changed.degraded_legs
    assert changed_key != key
    assert changed.delta == 2.0
    assert changed.state == {key: 2.0, changed_key: 2.0}


def test_degraded_key_is_stable_across_numeric_forms() -> None:
    first = accumulate_execution_fills(None, [
        {"order_id": "OID-1", "quantity": 2, "price": 100},
    ])
    replay = accumulate_execution_fills(first.state, [
        {"order_id": "OID-1", "quantity": 2.0, "price": 100.0},
    ])

    assert replay.delta == 0.0
    assert replay.state == first.state
    assert replay.degraded_legs == first.degraded_legs


@pytest.mark.parametrize("field", [
    "quantity", "price", "executed_price", "executed_at", "timestamp",
])
def test_degraded_identity_includes_each_present_identifying_field(field) -> None:
    leg = {
        "order_id": "order", "quantity": 2, "price": 100, "executed_price": 100,
        "executed_at": "older", "timestamp": "older",
    }
    first = accumulate_execution_fills(None, [leg])
    changed = {**leg, field: 3 if field == "quantity" else "different"}
    second = accumulate_execution_fills(first.state, [changed])

    assert second.degraded_legs != first.degraded_legs
    assert second.delta == changed["quantity"]
    assert len(second.state) == 2


def test_degraded_keys_are_deduplicated_in_first_seen_order() -> None:
    legs = [{"order_id": "order", "quantity": quantity} for quantity in (2, 3)]
    first = accumulate_execution_fills(None, legs)
    replay = accumulate_execution_fills(first.state, [legs[1], legs[0], legs[1]])

    assert replay.degraded_legs == tuple(reversed(first.degraded_legs))
    assert replay.delta == 0.0


@pytest.mark.parametrize("leg", [
    {"quantity": 1},
    {"order_id": None, "execution_id": None, "quantity": 1},
    {"order_id": "  ", "execution_id": "  ", "quantity": 1},
])
def test_missing_both_ids_is_invalid(leg) -> None:
    with pytest.raises(ValueError, match="^EXECUTION_FILL_INVALID$"):
        accumulate_execution_fills(None, [leg])


INVALID_QUANTITIES = (
    -1, float("nan"), float("inf"), float("-inf"), True, False, "2", None,
    1 + 2j, 10 ** 400,
)


@pytest.mark.parametrize("quantity", INVALID_QUANTITIES)
def test_invalid_incoming_quantity(quantity) -> None:
    with pytest.raises(ValueError, match="^EXECUTION_FILL_INVALID$"):
        accumulate_execution_fills(None, [
            {"order_id": "order", "exec_id": "a", "quantity": quantity},
        ])


@pytest.mark.parametrize("quantity", INVALID_QUANTITIES)
def test_invalid_previous_quantity(quantity) -> None:
    with pytest.raises(ValueError, match="^EXECUTION_FILL_INVALID$"):
        accumulate_execution_fills({"order|a": quantity}, [])


def test_previous_mapping_and_incoming_payload_are_not_mutated() -> None:
    previous = {"order|a": 2.0}
    leg = {"order_id": "order", "exec_id": "a", "quantity": 3}
    result = accumulate_execution_fills(MappingProxyType(previous), [MappingProxyType(leg)])

    assert result.state == {"order|a": 3.0}
    assert previous == {"order|a": 2.0}
    assert leg == {"order_id": "order", "exec_id": "a", "quantity": 3}


@pytest.mark.parametrize("factory", [dict, SimpleNamespace])
@pytest.mark.parametrize("id_field,quantity_field", [
    ("execution_id", "quantity"),
    ("exec_id", "executed_qty"),
    ("trade_id", "cumulative_quantity"),
])
def test_mapping_and_attribute_aliases(factory, id_field, quantity_field) -> None:
    leg = factory(**{"order_id": "order", id_field: "a", quantity_field: Decimal("1.5")})
    result = accumulate_execution_fills(None, iter([leg]))

    assert result.state == {"order|a": 1.5}
    assert result.delta == 1.5


def test_degraded_attribute_aliases_work() -> None:
    leg = SimpleNamespace(
        order_id="order", executed_qty=2, executed_price=100, timestamp="older",
    )
    first = accumulate_execution_fills(None, [leg])
    replay = accumulate_execution_fills(first.state, [vars(leg)])

    assert first.delta == 2.0
    assert replay.delta == 0.0
    assert replay.degraded_legs == first.degraded_legs


@pytest.mark.parametrize("factory", [dict, SimpleNamespace])
def test_fields_are_first_present_including_zero_and_blank(factory) -> None:
    leg = factory(
        broker_order_id="primary", order_id="secondary", execution_id="a", exec_id="b",
        trade_id="c", quantity=0, executed_qty=2, cumulative_quantity=3,
    )
    result = accumulate_execution_fills(None, [leg])
    assert result.state == {"primary|a": 0.0}
    assert result.delta == 0.0

    blank = factory(order_id="order", execution_id=" ", exec_id="fallback", quantity=1)
    degraded = accumulate_execution_fills(None, [blank])
    assert len(degraded.degraded_legs) == 1

    invalid = factory(order_id="order", exec_id="a", quantity=None, executed_qty=2)
    with pytest.raises(ValueError, match="^EXECUTION_FILL_INVALID$"):
        accumulate_execution_fills(None, [invalid])


def test_empty_input_and_frozen_schema_result() -> None:
    result = accumulate_execution_fills(None, [])

    assert isinstance(result, ExecutionFillAccumulation)
    assert result.state == {}
    assert result.delta == 0.0
    assert result.findings == result.degraded_legs == ()
    assert result.schema_version == EXECUTION_FILL_SCHEMA_VERSION == "qsl.execution_fills.v1"
    with pytest.raises(FrozenInstanceError):
        result.delta = 1.0
