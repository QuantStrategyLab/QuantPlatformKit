from __future__ import annotations

import time
from typing import Any

import pandas as pd

from quant_platform_kit.common.runtime_inputs import (
    build_semiconductor_rotation_indicators_from_history,
    required_semiconductor_rotation_history_lookback,
)


def _normalize_symbol(symbol: str) -> str:
    return str(symbol or "").strip().upper()


def _is_rate_limit_exception(exc: Exception) -> bool:
    code = getattr(exc, "code", None)
    if str(code) == "301606":
        return True
    message = str(exc).lower()
    return "301606" in message or "request rate limit" in message


def _quote_with_retry(
    q_ctx: Any,
    symbols: list[str],
    *,
    max_attempts: int = 3,
    initial_delay_sec: float = 1.0,
) -> list[Any]:
    for attempt in range(max(1, max_attempts)):
        try:
            return list(q_ctx.quote(symbols) or [])
        except Exception as exc:
            if attempt >= max_attempts - 1 or not _is_rate_limit_exception(exc):
                raise
            time.sleep(initial_delay_sec * (2**attempt))
    return []


def fetch_last_price(q_ctx: Any, symbol: str) -> float | None:
    return fetch_last_prices(q_ctx, [symbol]).get(_normalize_symbol(symbol))


def fetch_last_prices(
    q_ctx: Any, symbols: list[str] | tuple[str, ...]
) -> dict[str, float]:
    normalized_symbols = []
    for symbol in symbols:
        normalized_symbol = _normalize_symbol(symbol)
        if normalized_symbol:
            normalized_symbols.append(normalized_symbol)
    normalized_symbols = list(dict.fromkeys(normalized_symbols))
    if not normalized_symbols:
        return {}

    quotes = _quote_with_retry(q_ctx, normalized_symbols)
    prices: dict[str, float] = {}
    for index, quote in enumerate(quotes):
        fallback_symbol = (
            normalized_symbols[index] if index < len(normalized_symbols) else ""
        )
        quoted_symbol = _normalize_symbol(
            getattr(quote, "symbol", "") or fallback_symbol
        )
        if not quoted_symbol:
            continue
        last_done = getattr(quote, "last_done", None)
        if last_done is None:
            continue
        try:
            prices[quoted_symbol] = float(last_done)
        except (TypeError, ValueError):
            continue
    return prices


def fetch_lot_sizes(q_ctx: Any, symbols: list[str]) -> dict[str, int]:
    """Fetch board lot size for each symbol from LongPort ``static_info``."""
    normalized = [s for s in (_normalize_symbol(s) for s in symbols) if s]
    normalized = list(dict.fromkeys(normalized))
    if not normalized:
        return {}
    lot_sizes: dict[str, int] = {}
    try:
        infos = q_ctx.static_info(normalized)
    except Exception:
        return {}
    for info in infos or []:
        symbol = _normalize_symbol(getattr(info, "symbol", ""))
        lot_size = getattr(info, "lot_size", None)
        if symbol and lot_size is not None:
            lot_sizes[symbol] = max(1, int(lot_size))
    return lot_sizes


def calculate_rotation_indicators(
    q_ctx: Any,
    *,
    trend_window: int,
    lookback: int | None = None,
    dynamic_rsi_quantile_window: int = 252,
    dynamic_volatility_delever_window: int = 10,
    dynamic_volatility_delever_quantile_window: int = 252,
) -> dict[str, dict[str, float]] | None:
    from longport.openapi import AdjustType, Period

    effective_lookback = (
        lookback
        if lookback is not None
        else required_semiconductor_rotation_history_lookback(
            trend_ma_window=trend_window,
            dynamic_rsi_quantile_window=dynamic_rsi_quantile_window,
            dynamic_volatility_delever_window=dynamic_volatility_delever_window,
            dynamic_volatility_delever_quantile_window=dynamic_volatility_delever_quantile_window,
        )
    )
    soxl_bars = q_ctx.candlesticks(
        "SOXL.US", Period.Day, effective_lookback, AdjustType.ForwardAdjust
    )
    soxx_bars = q_ctx.candlesticks(
        "SOXX.US", Period.Day, effective_lookback, AdjustType.ForwardAdjust
    )
    if not soxl_bars or not soxx_bars:
        return None

    df_soxl = pd.DataFrame([{"close": float(k.close)} for k in soxl_bars])
    df_soxx = pd.DataFrame([float(k.close) for k in soxx_bars], columns=["close"])
    if len(df_soxl) < trend_window or len(df_soxx) < trend_window:
        return None

    return build_semiconductor_rotation_indicators_from_history(
        soxl_history=df_soxl["close"],
        soxx_history=df_soxx["close"],
        trend_ma_window=trend_window,
        dynamic_rsi_quantile_window=dynamic_rsi_quantile_window,
        dynamic_volatility_delever_window=dynamic_volatility_delever_window,
        dynamic_volatility_delever_quantile_window=dynamic_volatility_delever_quantile_window,
    )
