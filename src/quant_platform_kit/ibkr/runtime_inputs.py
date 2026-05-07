from __future__ import annotations

from collections.abc import Callable
from typing import Any

from quant_platform_kit.strategy_contracts import (
    StrategyEntrypoint,
    StrategyRuntimeAdapter,
    build_strategy_context_from_available_inputs,
    build_strategy_evaluation_inputs,
)
from quant_platform_kit.common.runtime_inputs import (
    build_semiconductor_rotation_indicators_from_history,
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
    dynamic_rsi_quantile_window: int = 252,
) -> dict[str, dict[str, float]]:
    effective_lookback = max(
        420,
        int(trend_ma_window) + int(lookback_buffer),
        int(dynamic_rsi_quantile_window) + int(lookback_buffer) + 90,
    )
    soxl_history = historical_close_loader(
        ib,
        "SOXL",
        duration=f"{effective_lookback} D",
        bar_size="1 day",
    )
    soxx_history = historical_close_loader(
        ib,
        "SOXX",
        duration=f"{effective_lookback} D",
        bar_size="1 day",
    )
    return build_semiconductor_rotation_indicators_from_history(
        soxl_history=soxl_history,
        soxx_history=soxx_history,
        trend_ma_window=trend_ma_window,
        dynamic_rsi_quantile_window=dynamic_rsi_quantile_window,
    )


def build_semiconductor_rotation_inputs(
    ib: Any,
    historical_close_loader: Callable[..., Any],
    *,
    trend_ma_window: int = 140,
    lookback_buffer: int = 20,
    dynamic_rsi_quantile_window: int = 252,
) -> dict[str, dict[str, dict[str, float]]]:
    return {
        "derived_indicators": build_semiconductor_rotation_indicators(
            ib,
            historical_close_loader,
            trend_ma_window=trend_ma_window,
            lookback_buffer=lookback_buffer,
            dynamic_rsi_quantile_window=dynamic_rsi_quantile_window,
        )
    }
