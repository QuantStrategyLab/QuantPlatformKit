from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from .models import ExecutionReport

_CONFIRMED_FILL_STATUSES = frozenset(
    {
        "filled",
        "partial",
        "partiallyfilled",
        "partially_filled",
        "partiallyexecuted",
        "executed",
    }
)
_NORMALIZED_CONFIRMED_FILL_STATUSES = frozenset(
    "".join(ch for ch in str(value or "").lower() if ch.isalnum())
    for value in _CONFIRMED_FILL_STATUSES
)


def _float_or_none(value: Any) -> float | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    if not text:
        return None
    negative_parentheses = text.startswith("(") and text.endswith(")")
    if negative_parentheses:
        text = text[1:-1].strip()
    if text.startswith("$"):
        text = text[1:].strip()
    try:
        number = float(text.replace(",", ""))
    except (TypeError, ValueError):
        return None
    return -number if negative_parentheses else number


def _sanitize_key(value: Any) -> str:
    return "".join(ch for ch in str(value or "").lower() if ch.isalnum())


def _normalize_status(value: Any) -> str:
    return _sanitize_key(value)


def _flatten_values(payload: Any, prefix: str = "") -> dict[str, Any]:
    values: dict[str, Any] = {}
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            child_key = f"{prefix}.{key}" if prefix else str(key)
            values.update(_flatten_values(value, child_key))
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            values.update(_flatten_values(value, f"{prefix}.{index}"))
    else:
        values[prefix] = payload
    return values


def _extract_first_value(payload: Any, *candidate_keys: str) -> Any:
    flattened = _flatten_values(payload)
    candidates = {_sanitize_key(key) for key in candidate_keys}
    for key, value in flattened.items():
        normalized_key = _sanitize_key(key.rsplit(".", 1)[-1])
        if normalized_key in candidates:
            return value
    return None


def _iter_execution_legs(payload: Any):
    if not isinstance(payload, Mapping):
        return
    activities = payload.get("orderActivityCollection") or payload.get("order_activity_collection")
    if not isinstance(activities, list):
        return
    for activity in activities:
        if not isinstance(activity, Mapping):
            continue
        legs = activity.get("executionLegs") or activity.get("execution_legs")
        if not isinstance(legs, list):
            continue
        for leg in legs:
            if isinstance(leg, Mapping):
                yield leg


def _extract_executed_qty_from_activities(payload: Any) -> float | None:
    total_qty = 0.0
    for leg in _iter_execution_legs(payload):
        quantity = _float_or_none(
            leg.get("quantity")
            or leg.get("executedQuantity")
            or leg.get("executed_quantity")
        )
        if quantity is None or quantity <= 0.0:
            continue
        total_qty += quantity
    if total_qty <= 0.0:
        return None
    return total_qty


def _extract_executed_price_from_activities(payload: Any) -> float | None:
    total_qty = 0.0
    total_notional = 0.0
    for leg in _iter_execution_legs(payload):
        quantity = _float_or_none(
            leg.get("quantity")
            or leg.get("executedQuantity")
            or leg.get("executed_quantity")
        )
        price = _float_or_none(
            leg.get("price")
            or leg.get("executionPrice")
            or leg.get("execution_price")
        )
        if quantity is None or quantity <= 0.0 or price is None or price <= 0.0:
            continue
        total_qty += quantity
        total_notional += quantity * price
    if total_qty <= 0.0:
        return None
    return total_notional / total_qty


def normalize_order_status_payload(payload: Any) -> dict[str, Any] | None:
    if isinstance(payload, ExecutionReport):
        return {
            "status": str(payload.status or ""),
            "executed_qty": max(0.0, float(payload.filled_quantity or 0.0)),
            "executed_price": max(0.0, float(payload.average_fill_price or 0.0)),
            "broker_order_id": str(payload.broker_order_id or "").strip() or None,
            "raw_payload": dict(payload.raw_payload or {}),
        }
    if not isinstance(payload, Mapping):
        return None
    status = str(
        _extract_first_value(
            payload,
            "status",
            "order_status",
            "orderStatus",
            "state",
            "order_state",
            "orderState",
            "status_description",
            "statusDescription",
            "orderStatusDescription",
        )
        or ""
    ).strip()
    executed_qty = _extract_executed_qty_from_activities(payload)
    if executed_qty is None:
        executed_qty = _float_or_none(
            _extract_first_value(
                payload,
                "executed_qty",
                "executed_quantity",
                "filled_quantity",
                "filled_qty",
                "filled",
                "filledQuantity",
                "filledShares",
                "executedShares",
                "quantityFilled",
            )
        )
    executed_price = _extract_executed_price_from_activities(payload)
    if executed_price is None:
        executed_price = _float_or_none(
            _extract_first_value(
                payload,
                "executed_price",
                "average_fill_price",
                "avg_fill_price",
                "avgFillPrice",
                "avg_price",
                "average_price",
                "fill_price",
                "filled_price",
            )
        )
    broker_order_id = _extract_first_value(
        payload,
        "broker_order_id",
        "brokerOrderId",
        "order_id",
        "orderId",
        "order_number",
        "orderNumber",
        "orderno",
        "orderNo",
    )
    return {
        "status": status,
        "executed_qty": max(0.0, float(executed_qty or 0.0)),
        "executed_price": max(0.0, float(executed_price or 0.0)),
        "broker_order_id": str(broker_order_id or "").strip() or None,
        "raw_payload": dict(payload),
    }


def _resolve_broker_order_id(order: Any) -> str:
    if isinstance(order, ExecutionReport):
        return str(order.broker_order_id or "").strip()
    if isinstance(order, Mapping):
        direct = str(order.get("broker_order_id") or "").strip()
        if direct:
            return direct
        raw_payload = normalize_order_status_payload(order.get("raw_payload"))
        return str((raw_payload or {}).get("broker_order_id") or "").strip()
    return ""


def _call_fetch_order_status(
    fetch_order_status: Callable[..., Any] | None,
    *,
    order_status_context: Any = None,
    broker_order_id: str,
) -> Any:
    if fetch_order_status is None or not broker_order_id:
        return None
    if order_status_context is not None:
        try:
            return fetch_order_status(order_status_context, broker_order_id)
        except TypeError:
            pass
    return fetch_order_status(broker_order_id)


def _resolve_order_status(
    order: Any,
    *,
    fetch_order_status: Callable[..., Any] | None = None,
    order_status_context: Any = None,
) -> dict[str, Any] | None:
    broker_order_id = _resolve_broker_order_id(order)
    if broker_order_id:
        fetched = _call_fetch_order_status(
            fetch_order_status,
            order_status_context=order_status_context,
            broker_order_id=broker_order_id,
        )
        normalized = normalize_order_status_payload(fetched)
        if normalized is not None:
            if not normalized.get("broker_order_id"):
                normalized["broker_order_id"] = broker_order_id
            return normalized
    if isinstance(order, Mapping):
        raw_payload = normalize_order_status_payload(order.get("raw_payload"))
        direct_payload = normalize_order_status_payload(order)
        if raw_payload and (
            raw_payload.get("executed_qty")
            or raw_payload.get("executed_price")
            or raw_payload.get("status")
        ):
            if not raw_payload.get("broker_order_id"):
                raw_payload["broker_order_id"] = broker_order_id or direct_payload and direct_payload.get("broker_order_id")
            return raw_payload
        if direct_payload is not None:
            if not direct_payload.get("broker_order_id"):
                direct_payload["broker_order_id"] = broker_order_id or None
            return direct_payload
    return normalize_order_status_payload(order)


def is_confirmed_fill_status(status: Any) -> bool:
    return _normalize_status(status) in _NORMALIZED_CONFIRMED_FILL_STATUSES


def compute_confirmed_sell_release_value(
    *,
    submitted_sell_orders,
    fetch_order_status: Callable[..., Any] | None = None,
    order_status_context: Any = None,
) -> float:
    released_value = 0.0
    for order in tuple(submitted_sell_orders or ()):
        resolved = _resolve_order_status(
            order,
            fetch_order_status=fetch_order_status,
            order_status_context=order_status_context,
        )
        if not isinstance(resolved, Mapping):
            continue
        executed_qty = max(0.0, float(resolved.get("executed_qty") or 0.0))
        executed_price = max(0.0, float(resolved.get("executed_price") or 0.0))
        status = resolved.get("status")
        if not is_confirmed_fill_status(status) and executed_qty <= 0.0:
            continue
        if executed_qty <= 0.0 or executed_price <= 0.0:
            continue
        released_value += executed_qty * executed_price
    return released_value
