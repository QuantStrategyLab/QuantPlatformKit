from __future__ import annotations

from decimal import Decimal
from typing import Any

from quant_platform_kit.common.models import ExecutionReport


def estimate_max_purchase_quantity(
    t_ctx: Any,
    symbol: str,
    *,
    order_kind: str,
    ref_price: float,
) -> float:
    from longport.openapi import OrderSide, OrderType

    order_type = OrderType.LO if order_kind == "limit" else OrderType.MO
    response = t_ctx.estimate_max_purchase_quantity(
        symbol=symbol,
        order_type=order_type,
        side=OrderSide.Buy,
        price=Decimal(str(ref_price)),
    )
    cash_max_qty = getattr(response, "cash_max_qty", 0)
    return max(0.0, float(Decimal(str(cash_max_qty or "0"))))


def submit_order(
    t_ctx: Any,
    symbol: str,
    *,
    order_kind: str,
    side: str,
    quantity: float,
    submitted_price: float | None = None,
) -> ExecutionReport:
    from longport.openapi import OrderSide, OrderType, TimeInForceType

    order_type = OrderType.LO if order_kind == "limit" else OrderType.MO
    order_side = OrderSide.Buy if side == "buy" else OrderSide.Sell
    submitted_quantity = Decimal(str(quantity))
    if submitted_quantity < Decimal("1"):
        return ExecutionReport(
            symbol=symbol.split(".")[0],
            side=side,
            quantity=float(quantity),
            status="rejected",
            raw_payload={
                "detail": (
                    "LongBridge submitted_quantity must be at least 1 share; "
                    f"got {submitted_quantity}."
                ),
                "order_kind": order_kind,
            },
        )

    kwargs: dict[str, Any] = {}
    if submitted_price is not None:
        kwargs["submitted_price"] = Decimal(str(submitted_price))

    response = t_ctx.submit_order(
        symbol,
        order_type,
        order_side,
        submitted_quantity,
        TimeInForceType.Day,
        **kwargs,
    )
    order_id = getattr(response, "order_id", "")
    return ExecutionReport(
        symbol=symbol.split(".")[0],
        side=side,
        quantity=float(quantity),
        status="submitted",
        broker_order_id=str(order_id) if order_id else None,
        raw_payload={"order_kind": order_kind},
    )


def fetch_order_status(t_ctx: Any, order_id: str) -> dict[str, str] | None:
    response = t_ctx.today_orders(order_id=order_id)
    orders = getattr(response, "orders", None) or []
    if not orders:
        return None

    order = orders[0]
    return {
        "status": str(getattr(order, "status", "UNKNOWN")),
        "executed_qty": str(getattr(order, "executed_quantity", "0")),
        "executed_price": str(getattr(order, "executed_price", "0")),
        "reason": getattr(order, "msg", "") or "—",
    }
