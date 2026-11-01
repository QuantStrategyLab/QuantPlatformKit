from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlsplit

from quant_platform_kit.common.order_status import normalize_order_status_payload
from quant_platform_kit.common.models import ExecutionReport, OrderIntent

MIN_DOLLAR_BUY_NOTIONAL_USD = 1.0


def _order_id_from_location(location: Any) -> str | None:
    if not isinstance(location, str):
        return None
    try:
        parsed = urlsplit(location)
    except ValueError:
        return None
    valid_uri = (not parsed.scheme and not parsed.netloc) or (
        parsed.scheme == "https" and bool(parsed.netloc)
    )
    match = re.fullmatch(r"(?:/[^/?#]+)*/orders/([0-9]+)", parsed.path)
    if not valid_uri or parsed.query or parsed.fragment or match is None:
        return None
    return match.group(1)


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
    status_code = getattr(response, "status_code", None)
    valid_status_code = isinstance(status_code, int) and not isinstance(status_code, bool)
    if valid_status_code and status_code in (200, 201):
        location = response.headers.get("Location", "")
        order_id = _order_id_from_location(location)
        return ExecutionReport(
            symbol=order_intent.symbol,
            side=side,
            quantity=reported_quantity,
            status="accepted" if order_id else "unknown",
            broker_order_id=order_id,
            raw_payload={"status_code": status_code},
        )

    # A timeout or server failure does not establish that no order was accepted.
    # Preserve uncertainty before the submission journal observes the result.
    rejected = valid_status_code and 400 <= status_code < 500 and status_code != 408
    return ExecutionReport(
        symbol=order_intent.symbol,
        side=side,
        quantity=reported_quantity,
        status="rejected" if rejected else "unknown",
        raw_payload={
            "status_code": status_code,
            "detail": f"{status_code} {response.text}",
        },
    )


def fetch_order_status(api_client: Any, account_hash: str, order_id: str) -> dict[str, Any] | None:
    response = api_client.get_order(order_id, account_hash)
    status_code = getattr(response, "status_code", None)
    if status_code not in (200, 201):
        return None
    try:
        payload = response.json()
    except Exception:
        return None
    normalized = normalize_order_status_payload(payload)
    if normalized is None:
        return None
    if not normalized.get("broker_order_id"):
        normalized["broker_order_id"] = str(order_id or "").strip() or None
    return normalized
