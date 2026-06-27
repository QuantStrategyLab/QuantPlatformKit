from __future__ import annotations

from typing import Any

from quant_platform_kit.common.models import ExecutionReport, OrderIntent

MIN_DOLLAR_BUY_NOTIONAL_USD = 1.0


def build_equity_dollar_buy_market_order(symbol: str, notional_usd: float) -> dict[str, Any]:
    notional = round(float(notional_usd), 2)
    if notional < MIN_DOLLAR_BUY_NOTIONAL_USD:
        raise ValueError(
            f"Schwab dollar buy notional_usd must be at least {MIN_DOLLAR_BUY_NOTIONAL_USD:.2f}; got {notional:.2f}."
        )
    normalized_symbol = str(symbol or "").strip().upper()
    if not normalized_symbol:
        raise ValueError("Schwab dollar buy requires a non-empty symbol.")
    return {
        "orderType": "MARKET",
        "session": "NORMAL",
        "duration": "DAY",
        "orderStrategyType": "SINGLE",
        "orderLegCollection": [
            {
                "instruction": "BUY",
                "quantity": notional,
                "quantityType": "DOLLARS",
                "instrument": {
                    "symbol": normalized_symbol,
                    "assetType": "EQUITY",
                },
            }
        ],
    }


def submit_equity_order(api_client: Any, account_hash: str, order_intent: OrderIntent) -> ExecutionReport:
    side = order_intent.side.lower()
    order_type = order_intent.order_type.lower()
    metadata = dict(getattr(order_intent, "metadata", {}) or {})
    notional_usd = metadata.get("notional_usd")

    if side == "buy" and notional_usd is not None:
        order = build_equity_dollar_buy_market_order(order_intent.symbol, float(notional_usd))
        reported_quantity = float(notional_usd)
    else:
        from schwab.orders.equities import equity_buy_limit, equity_buy_market, equity_sell_market

        if side == "sell" and order_type == "market":
            order = equity_sell_market(order_intent.symbol, order_intent.quantity)
            reported_quantity = float(order_intent.quantity)
        elif side == "buy" and order_type == "market":
            order = equity_buy_market(order_intent.symbol, order_intent.quantity)
            reported_quantity = float(order_intent.quantity)
        elif side == "buy" and order_type == "limit":
            if order_intent.limit_price is None:
                raise ValueError("Limit buy orders require OrderIntent.limit_price.")
            order = equity_buy_limit(order_intent.symbol, order_intent.quantity, f"{order_intent.limit_price:.2f}")
            reported_quantity = float(order_intent.quantity)
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
            quantity=reported_quantity,
            status="accepted",
            broker_order_id=order_id,
            raw_payload={"status_code": response.status_code},
        )

    return ExecutionReport(
        symbol=order_intent.symbol,
        side=side,
        quantity=reported_quantity,
        status="rejected",
        raw_payload={
            "status_code": response.status_code,
            "detail": f"{response.status_code} {response.text}",
        },
    )
