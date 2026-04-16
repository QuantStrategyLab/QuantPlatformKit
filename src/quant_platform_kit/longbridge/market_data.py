from __future__ import annotations

from typing import Any

import pandas as pd


def fetch_last_price(q_ctx: Any, symbol: str) -> float | None:
    quotes = q_ctx.quote([symbol])
    if not quotes:
        return None
    return float(quotes[0].last_done)


def calculate_rotation_indicators(
    q_ctx: Any,
    *,
    trend_window: int,
    lookback: int | None = None,
) -> dict[str, dict[str, float]] | None:
    from longport.openapi import AdjustType, Period

    effective_lookback = lookback if lookback is not None else max(220, trend_window + 20)
    soxl_bars = q_ctx.candlesticks("SOXL.US", Period.Day, effective_lookback, AdjustType.ForwardAdjust)
    soxx_bars = q_ctx.candlesticks("SOXX.US", Period.Day, effective_lookback, AdjustType.ForwardAdjust)
    if not soxl_bars or not soxx_bars:
        return None

    df_soxl = pd.DataFrame([{"close": float(k.close)} for k in soxl_bars])
    df_soxx = pd.DataFrame([float(k.close) for k in soxx_bars], columns=["close"])
    if len(df_soxl) < trend_window or len(df_soxx) < trend_window:
        return None

    df_soxl["ma_trend"] = df_soxl["close"].rolling(trend_window).mean()
    df_soxx["ma_trend"] = df_soxx["close"].rolling(trend_window).mean()
    df_soxx["ma20"] = df_soxx["close"].rolling(20).mean()
    df_soxx["ma20_slope"] = df_soxx["ma20"].diff()
    return {
        "soxl": {
            "price": float(df_soxl["close"].iloc[-1]),
            "ma_trend": float(df_soxl["ma_trend"].iloc[-1]),
        },
        "soxx": {
            "price": float(df_soxx["close"].iloc[-1]),
            "ma_trend": float(df_soxx["ma_trend"].iloc[-1]),
            "ma20": float(df_soxx["ma20"].iloc[-1]),
            "ma20_slope": float(df_soxx["ma20_slope"].iloc[-1]),
        },
    }
