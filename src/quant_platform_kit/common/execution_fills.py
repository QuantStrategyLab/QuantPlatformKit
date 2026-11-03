"""Pure accumulation of cumulative execution-leg quantities across snapshots."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from hashlib import sha256
import json
from math import isfinite
from numbers import Number
from typing import Any


EXECUTION_FILL_SCHEMA_VERSION = "qsl.execution_fills.v1"
_MISSING = object()


@dataclass(frozen=True)
class ExecutionFillAccumulation:
    state: dict[str, float]
    delta: float
    findings: tuple[str, ...]
    degraded_legs: tuple[str, ...]
    schema_version: str = EXECUTION_FILL_SCHEMA_VERSION


def _field(leg: Any, *names: str, default: Any = None) -> Any:
    for name in names:
        if isinstance(leg, Mapping):
            if name in leg:
                return leg[name]
        else:
            value = getattr(leg, name, _MISSING)
            if value is not _MISSING:
                return value
    return default


def _key_part(value: Any) -> str:
    return "".join(ch for ch in str("" if value is None else value).lower() if ch.isalnum())


def _quantity(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, Number):
        raise ValueError("EXECUTION_FILL_INVALID")
    try:
        quantity = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("EXECUTION_FILL_INVALID") from exc
    if not isfinite(quantity) or quantity < 0:
        raise ValueError("EXECUTION_FILL_INVALID")
    return quantity


def _digest_value(value: Any) -> Any:
    """Canonicalize numeric forms so 2 and 2.0 cannot become distinct legs."""
    if isinstance(value, bool):
        return value
    if isinstance(value, Number):
        try:
            return float(value)
        except (TypeError, ValueError, OverflowError):
            return str(value)
    if isinstance(value, str):
        try:
            number = float(value.strip())
        except (TypeError, ValueError):
            return value
        return number if isfinite(number) else value
    return value


def accumulate_execution_fills(
    previous: Mapping[str, float] | None,
    incoming: Iterable[Any],
) -> ExecutionFillAccumulation:
    """Copy state and count only increases to each execution's high-water mark.

    Missing execution IDs use a digest of the normalized order ID and identifying
    payload fields. The cumulative quantity is tracked by the high-water mark and
    deliberately excluded from the digest, so a growing leg keeps one identity.
    """
    if previous is not None and not isinstance(previous, Mapping):
        raise ValueError("EXECUTION_FILL_INVALID")
    state = {} if previous is None else {key: _quantity(value) for key, value in previous.items()}
    delta = 0.0
    findings: list[str] = []
    degraded_legs: list[str] = []

    for leg in incoming:
        raw_quantity = _field(leg, "quantity", "executed_qty", "cumulative_quantity")
        quantity = _quantity(raw_quantity)
        order_id = _key_part(_field(leg, "broker_order_id", "order_id"))
        execution_id = _key_part(_field(leg, "execution_id", "exec_id", "trade_id"))
        if not order_id:
            raise ValueError("EXECUTION_FILL_INVALID")
        if execution_id:
            key = f"{order_id}|{execution_id}"
        else:
            identifying_fields = {}
            for name in ("price", "executed_price", "executed_at", "timestamp"):
                value = _field(leg, name, default=_MISSING)
                if value is not _MISSING and value is not None:
                    identifying_fields[name] = _digest_value(value)
            canonical = json.dumps(
                [order_id, identifying_fields], sort_keys=True, separators=(",", ":"), default=str,
            )
            key = f"{order_id}|digest:{sha256(canonical.encode('utf-8')).hexdigest()}"
            degraded_legs.append(key)

        recorded = state.get(key, 0.0)
        if quantity < recorded:
            findings.append("EXECUTION_CUMULATIVE_DECREASE")
        else:
            delta += quantity - recorded
            state[key] = quantity

    return ExecutionFillAccumulation(
        state=state,
        delta=delta,
        findings=tuple(dict.fromkeys(findings)),
        degraded_legs=tuple(dict.fromkeys(degraded_legs)),
    )
