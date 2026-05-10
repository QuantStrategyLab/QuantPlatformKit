from __future__ import annotations

from typing import Any, Callable

from quant_platform_kit.common.models import ExecutionReport, OrderIntent


def _normalize_account_id(value: str | None) -> str | None:
    text = str(value or "").strip()
    return text or None


def _build_stock_contract(
    symbol: str,
    *,
    stock_factory: Callable[..., Any] | None = None,
    exchange: str = "SMART",
    currency: str = "USD",
) -> Any:
    if stock_factory is None:
        from ib_insync import Stock

        stock_factory = Stock
    return stock_factory(symbol, exchange, currency)


def submit_order_intent(
    ib: Any,
    order_intent: OrderIntent,
    *,
    account_id: str | None = None,
    wait_seconds: float = 1.0,
    stock_factory: Callable[..., Any] | None = None,
    market_order_factory: Callable[..., Any] | None = None,
    limit_order_factory: Callable[..., Any] | None = None,
) -> ExecutionReport:
    contract = _build_stock_contract(
        order_intent.symbol,
        stock_factory=stock_factory,
    )
    ib.qualifyContracts(contract)

    side = order_intent.side.upper()
    order_type = order_intent.order_type.lower()
    if order_type == "market":
        if market_order_factory is None:
            from ib_insync import MarketOrder

            market_order_factory = MarketOrder
        order = market_order_factory(side, order_intent.quantity)
    elif order_type == "limit":
        if order_intent.limit_price is None:
            raise ValueError("Limit orders require OrderIntent.limit_price.")
        if limit_order_factory is None:
            from ib_insync import LimitOrder

            limit_order_factory = LimitOrder
        order = limit_order_factory(side, order_intent.quantity, order_intent.limit_price)
        if order_intent.time_in_force:
            order.tif = order_intent.time_in_force
    else:
        raise ValueError(f"Unsupported IBKR order type: {order_intent.order_type!r}")

    intent_account_id = _normalize_account_id(order_intent.account_id)
    explicit_account_id = _normalize_account_id(account_id)
    if intent_account_id and explicit_account_id and intent_account_id != explicit_account_id:
        raise ValueError(
            "OrderIntent.account_id conflicts with submit_order_intent(account_id=...)."
        )
    resolved_account_id = intent_account_id or explicit_account_id
    if resolved_account_id:
        order.account = resolved_account_id

    trade = ib.placeOrder(contract, order)
    if wait_seconds:
        import time as time_module

        time_module.sleep(wait_seconds)

    order_status = trade.orderStatus
    return ExecutionReport(
        symbol=order_intent.symbol,
        side=order_intent.side.lower(),
        quantity=float(order_intent.quantity),
        status=order_status.status,
        filled_quantity=float(getattr(order_status, "filled", 0) or 0),
        average_fill_price=float(getattr(order_status, "avgFillPrice", 0) or 0),
        broker_order_id=str(trade.order.orderId),
        raw_payload={
            "order_type": order_type,
            "time_in_force": getattr(order, "tif", None),
            "account_id": resolved_account_id,
        },
    )
