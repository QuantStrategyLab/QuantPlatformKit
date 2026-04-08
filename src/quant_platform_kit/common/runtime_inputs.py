from __future__ import annotations

from collections.abc import Collection, Iterable, Mapping
from datetime import datetime, timezone
from typing import Any, Callable

from .models import PortfolioSnapshot, Position


def _normalize_symbols(strategy_symbols: Iterable[str]) -> tuple[str, ...]:
    return tuple(
        str(symbol).strip().upper()
        for symbol in strategy_symbols
        if str(symbol).strip()
    )


def build_account_state_from_portfolio_snapshot(
    snapshot: Any,
    *,
    strategy_symbols: Iterable[str] = (),
    liquid_cash: float | None = None,
) -> dict[str, Any]:
    normalized_symbols = _normalize_symbols(strategy_symbols)
    filter_enabled = bool(normalized_symbols)

    if filter_enabled:
        market_values = {symbol: 0.0 for symbol in normalized_symbols}
        quantities = {symbol: 0 for symbol in normalized_symbols}
        sellable_quantities = {symbol: 0 for symbol in normalized_symbols}
    else:
        market_values: dict[str, float] = {}
        quantities: dict[str, int] = {}
        sellable_quantities: dict[str, int] = {}

    for position in getattr(snapshot, "positions", ()) or ():
        symbol = str(position.symbol).strip().upper()
        if filter_enabled and symbol not in market_values:
            continue
        if symbol not in market_values:
            market_values[symbol] = 0.0
            quantities[symbol] = 0
            sellable_quantities[symbol] = 0

        quantity = int(position.quantity)
        quantities[symbol] = quantity
        sellable_quantities[symbol] = quantity
        market_values[symbol] = float(position.market_value)

    resolved_liquid_cash = liquid_cash
    if resolved_liquid_cash is None:
        metadata = getattr(snapshot, "metadata", {}) or {}
        resolved_liquid_cash = metadata.get("cash_available_for_trading")
    if resolved_liquid_cash is None:
        resolved_liquid_cash = getattr(snapshot, "buying_power", None)
    if resolved_liquid_cash is None:
        resolved_liquid_cash = getattr(snapshot, "cash_balance", None)
    if resolved_liquid_cash is None:
        resolved_liquid_cash = 0.0

    return {
        "available_cash": float(resolved_liquid_cash),
        "market_values": market_values,
        "quantities": quantities,
        "sellable_quantities": sellable_quantities,
        "total_strategy_equity": float(snapshot.total_equity),
    }


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
        quantity = int(quantities.get(symbol, 0))
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
    return PortfolioSnapshot(
        as_of=as_of or datetime.now(timezone.utc),
        total_equity=float(account_state["total_strategy_equity"]),
        buying_power=available_cash,
        cash_balance=available_cash,
        positions=tuple(positions),
        metadata=dict(metadata or {}),
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
