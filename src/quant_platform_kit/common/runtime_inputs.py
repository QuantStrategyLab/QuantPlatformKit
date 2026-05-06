from __future__ import annotations

from collections.abc import Collection, Iterable, Mapping
from datetime import datetime, timezone
from typing import Any, Callable

import pandas as pd

from .models import PortfolioSnapshot, Position


def _normalize_symbols(strategy_symbols: Iterable[str]) -> tuple[str, ...]:
    return tuple(
        str(symbol).strip().upper()
        for symbol in strategy_symbols
        if str(symbol).strip()
    )


def _normalize_numeric_history(
    history: Iterable[float] | pd.Series,
    *,
    label: str,
) -> pd.Series:
    normalized = pd.to_numeric(pd.Series(history), errors="coerce").dropna()
    if normalized.empty:
        raise ValueError(f"Semiconductor rotation inputs require non-empty {label} history")
    return normalized.astype(float)


def _compute_rsi(close: pd.Series, *, window: int = 14) -> pd.Series:
    delta = close.diff()
    gains = delta.clip(lower=0.0)
    losses = -delta.clip(upper=0.0)
    avg_gain = gains.ewm(alpha=1 / window, adjust=False, min_periods=window).mean()
    avg_loss = losses.ewm(alpha=1 / window, adjust=False, min_periods=window).mean()
    rs = avg_gain / avg_loss.replace(0.0, pd.NA)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    rsi = rsi.mask((avg_loss == 0.0) & (avg_gain > 0.0), 100.0)
    rsi = rsi.mask((avg_gain == 0.0) & (avg_loss > 0.0), 0.0)
    rsi = rsi.mask((avg_gain == 0.0) & (avg_loss == 0.0), 50.0)
    return rsi


def build_semiconductor_rotation_indicators_from_history(
    *,
    soxl_history: Iterable[float] | pd.Series,
    soxx_history: Iterable[float] | pd.Series,
    trend_ma_window: int = 140,
) -> dict[str, dict[str, float]]:
    window = int(trend_ma_window)
    if window <= 0:
        raise ValueError("trend_ma_window must be positive")

    soxl_close = _normalize_numeric_history(soxl_history, label="SOXL")
    soxx_close = _normalize_numeric_history(soxx_history, label="SOXX")
    if len(soxl_close) < window or len(soxx_close) < window:
        raise ValueError("Semiconductor rotation inputs require sufficient SOXL/SOXX history")

    soxl_ma_trend = float(soxl_close.rolling(window).mean().iloc[-1])
    soxx_ma_trend = float(soxx_close.rolling(window).mean().iloc[-1])
    soxx_ma20 = float(soxx_close.rolling(20).mean().iloc[-1])
    soxx_ma20_slope = float(soxx_close.rolling(20).mean().diff().iloc[-1])
    soxx_rsi14 = float(_compute_rsi(soxx_close, window=14).iloc[-1])
    soxx_bb_mid = float(soxx_close.rolling(20).mean().iloc[-1])
    soxx_bb_std = float(soxx_close.rolling(20).std(ddof=0).iloc[-1])
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
            "rsi14": soxx_rsi14,
            "bb_mid": soxx_bb_mid,
            "bb_upper": soxx_bb_mid + 2.0 * soxx_bb_std,
            "bb_lower": soxx_bb_mid - 2.0 * soxx_bb_std,
        },
    }


def build_semiconductor_rotation_inputs_from_history(
    *,
    soxl_history: Iterable[float] | pd.Series,
    soxx_history: Iterable[float] | pd.Series,
    trend_ma_window: int = 140,
) -> dict[str, dict[str, dict[str, float]]]:
    return {
        "derived_indicators": build_semiconductor_rotation_indicators_from_history(
            soxl_history=soxl_history,
            soxx_history=soxx_history,
            trend_ma_window=trend_ma_window,
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
