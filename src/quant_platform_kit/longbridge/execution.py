from __future__ import annotations

from decimal import Decimal
from typing import Any

from quant_platform_kit.common.models import ExecutionReport

LONGBRIDGE_FRACTIONAL_QUANTITY_STEP = Decimal("0.0001")
LONGBRIDGE_MIN_FRACTIONAL_BUY_QUANTITY = Decimal("0.0001")


def estimate_max_purchase_quantity(
    t_ctx: Any,
    symbol: str,
    *,
    order_kind: str,
    ref_price: float,
    fractional_shares: bool = False,
) -> float:
    from longport.openapi import OrderSide, OrderType

    order_type = OrderType.LO if order_kind == "limit" else OrderType.MO
    estimate_kwargs: dict[str, Any] = {
        "symbol": symbol,
        "order_type": order_type,
        "side": OrderSide.Buy,
        "price": Decimal(str(ref_price)),
    }
    if fractional_shares:
        estimate_kwargs["fractional_shares"] = True
    response = t_ctx.estimate_max_purchase_quantity(**estimate_kwargs)
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
    allow_fractional_shares: bool = False,
    quantity_step: float = 1.0,
) -> ExecutionReport:
    from longport.openapi import OrderSide, OrderType, TimeInForceType

    order_type = OrderType.LO if order_kind == "limit" else OrderType.MO
    order_side = OrderSide.Buy if side == "buy" else OrderSide.Sell
    submitted_quantity = Decimal(str(quantity))
    if side == "buy" and allow_fractional_shares:
        min_buy_quantity = max(
            LONGBRIDGE_MIN_FRACTIONAL_BUY_QUANTITY,
            Decimal(str(quantity_step)),
        )
        if submitted_quantity < min_buy_quantity:
            return ExecutionReport(
                symbol=symbol.split(".")[0],
                side=side,
                quantity=float(quantity),
                status="rejected",
                raw_payload={
                    "detail": (
                        "LongBridge fractional buy submitted_quantity must be at least "
                        f"{min_buy_quantity}; got {submitted_quantity}."
                    ),
                    "order_kind": order_kind,
                },
            )
    elif submitted_quantity < Decimal("1"):
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
    if (
        not allow_fractional_shares
        and order_kind == "limit"
        and side == "buy"
        and submitted_quantity != submitted_quantity.to_integral_value()
    ):
        return ExecutionReport(
            symbol=symbol.split(".")[0],
            side=side,
            quantity=float(quantity),
            status="rejected",
            raw_payload={
                "detail": (
                    "LongBridge limit buy submitted_quantity must be a whole-share quantity "
                    "of at least 1 share; "
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
