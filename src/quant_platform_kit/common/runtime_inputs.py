from __future__ import annotations

from collections.abc import Collection, Iterable, Mapping
from datetime import datetime, timezone
from math import isnan, sqrt
from typing import Any, Callable

from .models import PortfolioSnapshot, Position


DEFAULT_SEMICONDUCTOR_ROTATION_HISTORY_LOOKBACK = 420


def _normalize_symbols(strategy_symbols: Iterable[str]) -> tuple[str, ...]:
    return tuple(
        str(symbol).strip().upper()
        for symbol in strategy_symbols
        if str(symbol).strip()
    )


def _normalize_numeric_history(
    history: Iterable[float],
    *,
    label: str,
) -> tuple[float, ...]:
    normalized: list[float] = []
    for value in history:
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            continue
        if isnan(numeric):
            continue
        normalized.append(numeric)
    if not normalized:
        raise ValueError(f"Semiconductor rotation inputs require non-empty {label} history")
    return tuple(normalized)


def _mean(values: Iterable[float]) -> float:
    values = tuple(values)
    if not values:
        raise ValueError("mean requires at least one value")
    return float(sum(values) / len(values))


def _std(values: Iterable[float]) -> float:
    values = tuple(values)
    if not values:
        raise ValueError("std requires at least one value")
    mean_value = _mean(values)
    variance = sum((value - mean_value) ** 2 for value in values) / len(values)
    return float(sqrt(variance))


def _sample_std(values: Iterable[float]) -> float:
    values = tuple(values)
    if len(values) < 2:
        raise ValueError("sample std requires at least two values")
    mean_value = _mean(values)
    variance = sum((value - mean_value) ** 2 for value in values) / (len(values) - 1)
    return float(sqrt(variance))


def _tail_mean(values: tuple[float, ...], window: int) -> float:
    if len(values) < window:
        raise ValueError("insufficient history for rolling mean")
    return _mean(values[-window:])


def _tail_std(values: tuple[float, ...], window: int) -> float:
    if len(values) < window:
        raise ValueError("insufficient history for rolling std")
    return _std(values[-window:])


def _tail_realized_volatility(values: tuple[float, ...], window: int) -> float:
    if len(values) < window + 1:
        raise ValueError("insufficient history for realized volatility")
    tail_values = values[-(window + 1):]
    returns: list[float] = []
    for previous, current in zip(tail_values, tail_values[1:]):
        if previous == 0.0:
            raise ValueError("realized volatility requires non-zero prices")
        returns.append((current / previous) - 1.0)
    return float(_sample_std(returns) * sqrt(252))


def _compute_rsi(values: tuple[float, ...], *, window: int = 14) -> tuple[float, ...]:
    if len(values) < window + 1:
        raise ValueError("insufficient history for RSI")
    rsis = [50.0] * len(values)
    gains = 0.0
    losses = 0.0
    for index in range(1, window + 1):
        delta = values[index] - values[index - 1]
        gains += max(delta, 0.0)
        losses += max(-delta, 0.0)
    avg_gain = gains / window
    avg_loss = losses / window

    def _rsi_from_avg(avg_gain_value: float, avg_loss_value: float) -> float:
        if avg_gain_value == 0.0 and avg_loss_value == 0.0:
            return 50.0
        if avg_loss_value == 0.0:
            return 100.0
        if avg_gain_value == 0.0:
            return 0.0
        rs = avg_gain_value / avg_loss_value
        return 100.0 - (100.0 / (1.0 + rs))

    rsis[window] = _rsi_from_avg(avg_gain, avg_loss)
    alpha = 1.0 / window
    for index in range(window + 1, len(values)):
        delta = values[index] - values[index - 1]
        gain = max(delta, 0.0)
        loss = max(-delta, 0.0)
        avg_gain = (1.0 - alpha) * avg_gain + alpha * gain
        avg_loss = (1.0 - alpha) * avg_loss + alpha * loss
        rsis[index] = _rsi_from_avg(avg_gain, avg_loss)
    return tuple(rsis)


def _rolling_quantile(values: tuple[float, ...], *, window: int, quantile: float) -> tuple[float | None, ...]:
    if window <= 0:
        raise ValueError("window must be positive")
    if not 0.0 < quantile < 1.0:
        raise ValueError("quantile must be between 0 and 1")
    result: list[float | None] = [None] * len(values)
    for index in range(window - 1, len(values)):
        chunk = sorted(values[index - window + 1 : index + 1])
        if not chunk:
            continue
        position = (len(chunk) - 1) * quantile
        lower_index = int(position)
        upper_index = min(lower_index + 1, len(chunk) - 1)
        fraction = position - lower_index
        result[index] = chunk[lower_index] * (1.0 - fraction) + chunk[upper_index] * fraction
    return tuple(result)


def build_semiconductor_rotation_indicators_from_history(
    *,
    soxl_history: Iterable[float],
    soxx_history: Iterable[float],
    trend_ma_window: int = 140,
    dynamic_rsi_quantile_window: int = 252,
    dynamic_rsi_quantile: float = 0.90,
    dynamic_rsi_floor: float = 70.0,
) -> dict[str, dict[str, float]]:
    window = int(trend_ma_window)
    if window <= 0:
        raise ValueError("trend_ma_window must be positive")
    rsi_quantile_window = int(dynamic_rsi_quantile_window)
    if rsi_quantile_window <= 0:
        raise ValueError("dynamic_rsi_quantile_window must be positive")
    rsi_quantile = float(dynamic_rsi_quantile)
    if not 0.0 < rsi_quantile < 1.0:
        raise ValueError("dynamic_rsi_quantile must be between 0 and 1")

    soxl_close = _normalize_numeric_history(soxl_history, label="SOXL")
    soxx_close = _normalize_numeric_history(soxx_history, label="SOXX")
    if len(soxl_close) < window or len(soxx_close) < window:
        raise ValueError("Semiconductor rotation inputs require sufficient SOXL/SOXX history")

    soxl_ma_trend = _tail_mean(soxl_close, window)
    soxx_ma_trend = _tail_mean(soxx_close, window)
    soxx_ma20 = _tail_mean(soxx_close, 20)
    soxx_ma20_prev = _tail_mean(soxx_close[:-1], 20)
    soxx_ma20_slope = float(soxx_ma20 - soxx_ma20_prev)
    soxx_rsi_history = _compute_rsi(soxx_close, window=14)
    soxx_rsi14 = float(soxx_rsi_history[-1])
    rsi_threshold_history = _rolling_quantile(
        soxx_rsi_history,
        window=rsi_quantile_window,
        quantile=rsi_quantile,
    )
    previous_threshold = rsi_threshold_history[-2] if len(rsi_threshold_history) >= 2 else None
    soxx_dynamic_rsi_threshold = float(
        max(
            float(dynamic_rsi_floor),
            float(previous_threshold) if previous_threshold is not None else float(dynamic_rsi_floor),
        )
    )
    soxx_bb_mid = _tail_mean(soxx_close, 20)
    soxx_bb_std = _tail_std(soxx_close, 20)
    soxx_realized_volatility_10 = _tail_realized_volatility(soxx_close, 10)
    soxx_realized_volatility_20 = _tail_realized_volatility(soxx_close, 20)
    return {
        "soxl": {
            "price": float(soxl_close[-1]),
            "ma_trend": soxl_ma_trend,
        },
        "soxx": {
            "price": float(soxx_close[-1]),
            "ma_trend": soxx_ma_trend,
            "ma20": soxx_ma20,
            "ma20_slope": soxx_ma20_slope,
            "rsi14": soxx_rsi14,
            "rsi14_dynamic_threshold": soxx_dynamic_rsi_threshold,
            "bb_mid": soxx_bb_mid,
            "bb_upper": soxx_bb_mid + 2.0 * soxx_bb_std,
            "bb_lower": soxx_bb_mid - 2.0 * soxx_bb_std,
            "realized_volatility": soxx_realized_volatility_20,
            "realized_volatility_10": soxx_realized_volatility_10,
            "realized_volatility_20": soxx_realized_volatility_20,
        },
    }


def required_semiconductor_rotation_history_lookback(
    *,
    trend_ma_window: int = 140,
    dynamic_rsi_quantile_window: int = 252,
    minimum_lookback: int = DEFAULT_SEMICONDUCTOR_ROTATION_HISTORY_LOOKBACK,
) -> int:
    return max(
        int(minimum_lookback),
        int(trend_ma_window) + 20,
        int(dynamic_rsi_quantile_window) + 28,
    )


def build_semiconductor_rotation_inputs_from_history(
    *,
    soxl_history: Iterable[float],
    soxx_history: Iterable[float],
    trend_ma_window: int = 140,
    dynamic_rsi_quantile_window: int = 252,
    dynamic_rsi_quantile: float = 0.90,
    dynamic_rsi_floor: float = 70.0,
) -> dict[str, dict[str, dict[str, float]]]:
    return {
        "derived_indicators": build_semiconductor_rotation_indicators_from_history(
            soxl_history=soxl_history,
            soxx_history=soxx_history,
            trend_ma_window=trend_ma_window,
            dynamic_rsi_quantile_window=dynamic_rsi_quantile_window,
            dynamic_rsi_quantile=dynamic_rsi_quantile,
            dynamic_rsi_floor=dynamic_rsi_floor,
        )
    }


def build_account_state_from_portfolio_snapshot(
    snapshot: Any,
    *,
    strategy_symbols: Iterable[str] = (),
    liquid_cash: float | None = None,
) -> dict[str, Any]:
    metadata = getattr(snapshot, "metadata", {}) or {}
    raw_sellable_quantities = metadata.get("sellable_quantities") if isinstance(metadata, Mapping) else None
    resolved_sellable_quantities: dict[str, float] = {}
    if isinstance(raw_sellable_quantities, Mapping):
        resolved_sellable_quantities = {
            str(symbol).strip().upper(): float(quantity)
            for symbol, quantity in raw_sellable_quantities.items()
            if str(symbol).strip()
        }
    normalized_symbols = _normalize_symbols(strategy_symbols)
    filter_enabled = bool(normalized_symbols)

    if filter_enabled:
        market_values = {symbol: 0.0 for symbol in normalized_symbols}
        quantities = {symbol: 0.0 for symbol in normalized_symbols}
        sellable_quantities = {symbol: 0.0 for symbol in normalized_symbols}
    else:
        market_values: dict[str, float] = {}
        quantities: dict[str, float] = {}
        sellable_quantities: dict[str, float] = {}

    for position in getattr(snapshot, "positions", ()) or ():
        symbol = str(position.symbol).strip().upper()
        if filter_enabled and symbol not in market_values:
            continue
        if symbol not in market_values:
            market_values[symbol] = 0.0
            quantities[symbol] = 0.0
            sellable_quantities[symbol] = 0.0

        quantity = float(position.quantity)
        quantities[symbol] = quantity
        sellable_quantities[symbol] = float(resolved_sellable_quantities.get(symbol, quantity))
        market_values[symbol] = float(position.market_value)

    resolved_liquid_cash = liquid_cash
    if resolved_liquid_cash is None:
        resolved_liquid_cash = metadata.get("cash_available_for_trading")
    if resolved_liquid_cash is None:
        resolved_liquid_cash = getattr(snapshot, "buying_power", None)
    if resolved_liquid_cash is None:
        resolved_liquid_cash = getattr(snapshot, "cash_balance", None)
    if resolved_liquid_cash is None:
        resolved_liquid_cash = 0.0

    account_state = {
        "available_cash": float(resolved_liquid_cash),
        "market_values": market_values,
        "quantities": quantities,
        "sellable_quantities": sellable_quantities,
        "total_strategy_equity": float(snapshot.total_equity),
    }
    raw_cash_by_currency = metadata.get("cash_by_currency") if isinstance(metadata, Mapping) else None
    if isinstance(raw_cash_by_currency, Mapping):
        account_state["cash_by_currency"] = {
            str(currency).strip().upper(): float(amount)
            for currency, amount in raw_cash_by_currency.items()
            if str(currency).strip()
        }
    return account_state


def build_portfolio_snapshot_from_account_state(
    account_state: Mapping[str, Any],
    *,
    strategy_symbols: Iterable[str] = (),
    as_of: datetime | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> PortfolioSnapshot:
    normalized_symbols = _normalize_symbols(strategy_symbols)
    market_values = dict(account_state["market_values"])
    quantities = dict(account_state["quantities"])
    symbols = normalized_symbols or tuple(sorted(str(symbol) for symbol in market_values))

    positions: list[Position] = []
    for symbol in symbols:
        quantity = float(quantities.get(symbol, 0.0))
        market_value = float(market_values.get(symbol, 0.0))
        if quantity <= 0 and market_value <= 0.0:
            continue
        positions.append(
            Position(
                symbol=symbol,
                quantity=quantity,
                market_value=market_value,
            )
        )

    available_cash = float(account_state["available_cash"])
    snapshot_metadata = dict(metadata or {})
    if normalized_symbols:
        snapshot_metadata.setdefault("strategy_symbols", normalized_symbols)
    snapshot_metadata.setdefault("cash_available_for_trading", available_cash)
    raw_cash_by_currency = account_state.get("cash_by_currency")
    if isinstance(raw_cash_by_currency, Mapping):
        cash_by_currency = {
            str(currency).strip().upper(): float(amount)
            for currency, amount in raw_cash_by_currency.items()
            if str(currency).strip()
        }
        if cash_by_currency:
            snapshot_metadata.setdefault("cash_by_currency", cash_by_currency)
    raw_sellable_quantities = account_state.get("sellable_quantities")
    if isinstance(raw_sellable_quantities, Mapping):
        sellable_quantities = {
            str(symbol).strip().upper(): float(quantity)
            for symbol, quantity in raw_sellable_quantities.items()
            if str(symbol).strip()
        }
        if sellable_quantities:
            snapshot_metadata.setdefault("sellable_quantities", sellable_quantities)
    return PortfolioSnapshot(
        as_of=as_of or datetime.now(timezone.utc),
        total_equity=float(account_state["total_strategy_equity"]),
        buying_power=available_cash,
        cash_balance=available_cash,
        positions=tuple(positions),
        metadata=snapshot_metadata,
    )


def build_strategy_evaluation_inputs(
    *,
    available_inputs: Collection[str],
    market_inputs: Mapping[str, Any] | None = None,
    portfolio_snapshot: Any | None = None,
    account_state: Mapping[str, Any] | None = None,
    translator: Callable[[str], str] | None = None,
    signal_text_fn: Callable[[str], str] | None = None,
) -> dict[str, Any]:
    resolved_available_inputs = {
        str(input_name).strip()
        for input_name in available_inputs
        if str(input_name).strip()
    }
    evaluation_inputs: dict[str, Any] = {}
    if translator is not None:
        evaluation_inputs["translator"] = translator
    if signal_text_fn is not None:
        evaluation_inputs["signal_text_fn"] = signal_text_fn

    for input_name, value in dict(market_inputs or {}).items():
        if input_name in resolved_available_inputs:
            evaluation_inputs[input_name] = value

    if portfolio_snapshot is not None:
        if "portfolio_snapshot" in resolved_available_inputs:
            evaluation_inputs["portfolio_snapshot"] = portfolio_snapshot
        if "snapshot" in resolved_available_inputs:
            evaluation_inputs["snapshot"] = portfolio_snapshot

    if account_state is not None and "account_state" in resolved_available_inputs:
        evaluation_inputs["account_state"] = account_state

    return evaluation_inputs
