from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Callable, Optional

from quant_platform_kit.common.models import QuoteSnapshot

RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
DEFAULT_HTTP_MAX_ATTEMPTS = 4
DEFAULT_HTTP_BACKOFF_SECONDS = 1.0
DEFAULT_HTTP_MAX_BACKOFF_SECONDS = 8.0


def _env_int(name: str, default: int, *, minimum: int, maximum: int) -> int:
    raw_value = os.environ.get(name)
    if not raw_value:
        return default
    try:
        value = int(raw_value)
    except ValueError:
        return default
    return min(max(value, minimum), maximum)


def _env_float(name: str, default: float, *, minimum: float, maximum: float) -> float:
    raw_value = os.environ.get(name)
    if not raw_value:
        return default
    try:
        value = float(raw_value)
    except ValueError:
        return default
    return min(max(value, minimum), maximum)


def _header_value(headers: Any, name: str) -> Optional[str]:
    if not headers:
        return None
    if hasattr(headers, "get"):
        value = headers.get(name)
        if value is None:
            value = headers.get(name.lower())
        if value is None:
            value = headers.get(name.upper())
        return str(value).strip() if value is not None else None
    return None


def _retry_after_seconds(response: Any, fallback_seconds: float, max_seconds: float) -> float:
    raw_value = _header_value(getattr(response, "headers", None), "Retry-After")
    if not raw_value:
        return min(fallback_seconds, max_seconds)
    try:
        return min(max(float(raw_value), 0.0), max_seconds)
    except ValueError:
        pass

    try:
        retry_at = parsedate_to_datetime(raw_value)
    except (TypeError, ValueError):
        return min(fallback_seconds, max_seconds)
    if retry_at.tzinfo is None:
        retry_at = retry_at.replace(tzinfo=timezone.utc)
    wait_seconds = (retry_at - datetime.now(timezone.utc)).total_seconds()
    return min(max(wait_seconds, 0.0), max_seconds)


def _request_with_retries(request_fn: Callable[[], Any]) -> Any:
    max_attempts = _env_int("QPK_SCHWAB_HTTP_MAX_ATTEMPTS", DEFAULT_HTTP_MAX_ATTEMPTS, minimum=1, maximum=8)
    backoff_seconds = _env_float(
        "QPK_SCHWAB_HTTP_BACKOFF_SECONDS",
        DEFAULT_HTTP_BACKOFF_SECONDS,
        minimum=0.0,
        maximum=30.0,
    )
    max_backoff_seconds = _env_float(
        "QPK_SCHWAB_HTTP_MAX_BACKOFF_SECONDS",
        DEFAULT_HTTP_MAX_BACKOFF_SECONDS,
        minimum=0.0,
        maximum=60.0,
    )

    response = None
    for attempt in range(1, max_attempts + 1):
        response = request_fn()
        status_code = getattr(response, "status_code", None)
        if status_code not in RETRYABLE_STATUS_CODES or attempt >= max_attempts:
            return response

        fallback_seconds = backoff_seconds * (2 ** (attempt - 1))
        wait_seconds = _retry_after_seconds(response, fallback_seconds, max_backoff_seconds)
        if wait_seconds > 0:
            time.sleep(wait_seconds)

    return response


def decode_response_json(response: Any, context: str) -> Any:
    if response.status_code not in (200, 201):
        raise RuntimeError(f"{context} failed: {response.status_code} {response.text}")
    try:
        return response.json()
    except Exception as exc:
        raise RuntimeError(f"{context} invalid JSON: {response.text}") from exc


def fetch_default_daily_price_history_candles(api_client: Any, symbol: str) -> list[dict[str, Any]]:
    from schwab import client

    response = _request_with_retries(
        lambda: api_client.get_price_history(
            symbol,
            period_type=client.Client.PriceHistory.PeriodType.YEAR,
            period=client.Client.PriceHistory.Period.TWO_YEARS,
            frequency_type=client.Client.PriceHistory.FrequencyType.DAILY,
            frequency=client.Client.PriceHistory.Frequency.DAILY,
        )
    )
    payload = decode_response_json(response, f"{symbol} history")
    candles = payload.get("candles")
    if candles is None:
        raise RuntimeError(f"{symbol} response missing candles: {payload}")
    return candles


def fetch_quotes(api_client: Any, symbols: list[str] | tuple[str, ...]) -> dict[str, QuoteSnapshot]:
    payload = decode_response_json(_request_with_retries(lambda: api_client.get_quotes(symbols)), "Quotes")
    as_of = datetime.now(timezone.utc)
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
