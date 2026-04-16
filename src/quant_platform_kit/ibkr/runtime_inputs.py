from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pandas as pd

from quant_platform_kit.strategy_contracts import (
    StrategyEntrypoint,
    StrategyRuntimeAdapter,
    build_strategy_context_from_available_inputs,
    build_strategy_evaluation_inputs,
)


def build_market_history_inputs(
    historical_close_loader: Callable[..., Any],
) -> dict[str, Callable[..., Any]]:
    return {"market_history": historical_close_loader}


def build_benchmark_history_inputs(
    ib: Any,
    historical_candle_loader: Callable[..., Any],
    *,
    benchmark_symbol: str,
    duration: str = "2 Y",
    bar_size: str = "1 day",
) -> dict[str, Any]:
    return {
        "benchmark_history": historical_candle_loader(
            ib,
            benchmark_symbol,
            duration=duration,
            bar_size=bar_size,
        )
    }


def build_ibkr_strategy_context(
    *,
    entrypoint: StrategyEntrypoint,
    runtime_adapter: StrategyRuntimeAdapter | None,
    as_of: Any,
    market_inputs: dict[str, Any] | None = None,
    portfolio_snapshot: Any | None = None,
    runtime_config: dict[str, Any] | None = None,
    current_holdings=(),
    ib: Any | None = None,
):
    available_inputs = build_strategy_evaluation_inputs(
        available_inputs=frozenset(entrypoint.manifest.required_inputs),
        market_inputs=market_inputs,
        portfolio_snapshot=portfolio_snapshot,
    )
    capabilities = {}
    if ib is not None:
        capabilities["broker_client"] = ib
    return build_strategy_context_from_available_inputs(
        entrypoint=entrypoint,
        runtime_adapter=runtime_adapter,
        as_of=as_of,
        available_inputs=available_inputs,
        runtime_config=runtime_config,
        state={"current_holdings": tuple(current_holdings)},
        capabilities=capabilities,
    )


def build_semiconductor_rotation_indicators(
    ib: Any,
    historical_close_loader: Callable[..., Any],
    *,
    trend_ma_window: int = 140,
    lookback_buffer: int = 20,
) -> dict[str, dict[str, float]]:
    effective_lookback = max(220, int(trend_ma_window) + int(lookback_buffer))
    soxl_series = pd.Series(
        historical_close_loader(
            ib,
            "SOXL",
            duration=f"{effective_lookback} D",
            bar_size="1 day",
        )
    )
    soxx_series = pd.Series(
        historical_close_loader(
            ib,
            "SOXX",
            duration=f"{effective_lookback} D",
            bar_size="1 day",
        )
    )
    if soxl_series.empty or soxx_series.empty:
        raise ValueError("IBKR semiconductor runtime requires SOXL/SOXX price history")

    soxl_close = pd.to_numeric(soxl_series, errors="coerce").dropna()
    soxx_close = pd.to_numeric(soxx_series, errors="coerce").dropna()
    if len(soxl_close) < int(trend_ma_window) or len(soxx_close) < int(trend_ma_window):
        raise ValueError("IBKR semiconductor runtime requires sufficient SOXL/SOXX history")

    soxl_ma_trend = float(soxl_close.rolling(int(trend_ma_window)).mean().iloc[-1])
    soxx_ma_trend = float(soxx_close.rolling(int(trend_ma_window)).mean().iloc[-1])
    soxx_ma20 = float(soxx_close.rolling(20).mean().iloc[-1])
    soxx_ma20_slope = float(soxx_close.rolling(20).mean().diff().iloc[-1])
    return {
        "soxl": {
            "price": float(soxl_close.iloc[-1]),
            "ma_trend": soxl_ma_trend,
        },
        "soxx": {
            "price": float(soxx_close.iloc[-1]),
            "ma_trend": soxx_ma_trend,
            "ma20": soxx_ma20,
            "ma20_slope": soxx_ma20_slope,
        },
    }


def build_semiconductor_rotation_inputs(
    ib: Any,
    historical_close_loader: Callable[..., Any],
    *,
    trend_ma_window: int = 140,
    lookback_buffer: int = 20,
) -> dict[str, dict[str, dict[str, float]]]:
    return {
        "derived_indicators": build_semiconductor_rotation_indicators(
            ib,
            historical_close_loader,
            trend_ma_window=trend_ma_window,
            lookback_buffer=lookback_buffer,
        )
    }
