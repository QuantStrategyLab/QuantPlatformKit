from __future__ import annotations

from typing import Any

from quant_platform_kit.common.models import ExecutionReport, OrderIntent


def submit_equity_order(api_client: Any, account_hash: str, order_intent: OrderIntent) -> ExecutionReport:
    from schwab.orders.equities import equity_buy_limit, equity_buy_market, equity_sell_market

    side = order_intent.side.lower()
    order_type = order_intent.order_type.lower()

    if side == "sell" and order_type == "market":
        order = equity_sell_market(order_intent.symbol, order_intent.quantity)
    elif side == "buy" and order_type == "market":
        order = equity_buy_market(order_intent.symbol, order_intent.quantity)
    elif side == "buy" and order_type == "limit":
        if order_intent.limit_price is None:
            raise ValueError("Limit buy orders require OrderIntent.limit_price.")
        order = equity_buy_limit(order_intent.symbol, order_intent.quantity, f"{order_intent.limit_price:.2f}")
    else:
        raise ValueError(
            f"Unsupported Schwab order intent: side={order_intent.side!r}, order_type={order_intent.order_type!r}"
        )

    response = api_client.place_order(account_hash, order)
    if response.status_code in (200, 201):
        location = response.headers.get("Location", "")
        order_id = location.split("/")[-1] if location else None
        return ExecutionReport(
            symbol=order_intent.symbol,
            side=side,
            quantity=float(order_intent.quantity),
            status="accepted",
            broker_order_id=order_id,
            raw_payload={"status_code": response.status_code},
        )

    return ExecutionReport(
        symbol=order_intent.symbol,
        side=side,
        quantity=float(order_intent.quantity),
        status="rejected",
        raw_payload={
            "status_code": response.status_code,
            "detail": f"{response.status_code} {response.text}",
        },
    )
