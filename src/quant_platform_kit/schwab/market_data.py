from __future__ import annotations

from datetime import datetime
from typing import Any

from quant_platform_kit.common.models import QuoteSnapshot


def decode_response_json(response: Any, context: str) -> Any:
    if response.status_code not in (200, 201):
        raise RuntimeError(f"{context} failed: {response.status_code} {response.text}")
    try:
        return response.json()
    except Exception as exc:
        raise RuntimeError(f"{context} invalid JSON: {response.text}") from exc


def fetch_default_daily_price_history_candles(api_client: Any, symbol: str) -> list[dict[str, Any]]:
    from schwab import client

    response = api_client.get_price_history(
        symbol,
        period_type=client.Client.PriceHistory.PeriodType.YEAR,
        period=client.Client.PriceHistory.Period.TWO_YEARS,
        frequency_type=client.Client.PriceHistory.FrequencyType.DAILY,
        frequency=client.Client.PriceHistory.Frequency.DAILY,
    )
    payload = decode_response_json(response, f"{symbol} history")
    candles = payload.get("candles")
    if candles is None:
        raise RuntimeError(f"{symbol} response missing candles: {payload}")
    return candles


def fetch_quotes(api_client: Any, symbols: list[str] | tuple[str, ...]) -> dict[str, QuoteSnapshot]:
    payload = decode_response_json(api_client.get_quotes(symbols), "Quotes")
    as_of = datetime.utcnow()
    snapshots: dict[str, QuoteSnapshot] = {}
    for symbol in symbols:
        symbol_payload = payload.get(symbol)
        quote = symbol_payload.get("quote") if symbol_payload else None
        if not quote or "lastPrice" not in quote or "askPrice" not in quote:
            raise RuntimeError(f"Incomplete quote for {symbol}: {quote}")
        snapshots[symbol] = QuoteSnapshot(
            symbol=symbol,
            as_of=as_of,
            last_price=float(quote["lastPrice"]),
            bid_price=float(quote["bidPrice"]) if quote.get("bidPrice") is not None else None,
            ask_price=float(quote["askPrice"]) if quote.get("askPrice") is not None else None,
        )
    return snapshots
