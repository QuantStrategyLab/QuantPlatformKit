from __future__ import annotations

from typing import Any

import pandas as pd

from quant_platform_kit.common.runtime_inputs import (
    build_semiconductor_rotation_indicators_from_history,
)


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

    return build_semiconductor_rotation_indicators_from_history(
        soxl_history=df_soxl["close"],
        soxx_history=df_soxx["close"],
        trend_ma_window=trend_window,
    )
