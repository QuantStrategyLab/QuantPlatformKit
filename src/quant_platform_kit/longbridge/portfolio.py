from __future__ import annotations

from typing import Any, Callable, Iterable

from .market_data import fetch_last_price


def fetch_strategy_account_state(
    q_ctx: Any,
    t_ctx: Any,
    strategy_assets: Iterable[str],
    *,
    position_log_fn: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    available_cash = 0.0
    cash_by_currency: dict[str, float] = {}
    account_balance = t_ctx.account_balance()
    for account in account_balance:
        for cash_info in getattr(account, "cash_infos", []):
            currency = str(getattr(cash_info, "currency", "") or "").strip().upper()
            if not currency:
                continue
            cash_amount = float(getattr(cash_info, "available_cash", 0.0))
            cash_by_currency[currency] = cash_by_currency.get(currency, 0.0) + cash_amount
            if currency == "USD":
                available_cash += cash_amount

    assets = [str(symbol).strip().upper() for symbol in strategy_assets if str(symbol).strip()]
    market_values = {symbol: 0.0 for symbol in assets}
    quantities = {symbol: 0.0 for symbol in assets}
    sellable_quantities = {symbol: 0.0 for symbol in assets}
    filter_enabled = bool(assets)

    positions_response = t_ctx.stock_positions()
    if positions_response and hasattr(positions_response, "channels"):
        for channel in positions_response.channels:
            for position in getattr(channel, "positions", []):
                full_symbol = getattr(position, "symbol", "")
                root_symbol = full_symbol.split(".")[0].strip().upper()
                if filter_enabled and root_symbol not in market_values:
                    continue
                if root_symbol not in market_values:
                    market_values[root_symbol] = 0.0
                    quantities[root_symbol] = 0.0
                    sellable_quantities[root_symbol] = 0.0

                raw_quantity = getattr(position, "quantity", 0)
                raw_available_quantity = getattr(position, "available_quantity", raw_quantity)
                if raw_quantity is None:
                    raw_quantity = 0
                if raw_available_quantity is None:
                    raw_available_quantity = raw_quantity
                if position_log_fn is not None:
                    position_log_fn(
                        "[position_snapshot] raw "
                        f"symbol={root_symbol} full_symbol={full_symbol} "
                        f"quantity={raw_quantity} available_quantity={raw_available_quantity}"
                    )

                last_price = fetch_last_price(q_ctx, full_symbol)
                if last_price is None:
                    continue

                quantity = float(raw_quantity)
                available_quantity = float(raw_available_quantity)
                market_values[root_symbol] += quantity * last_price
                quantities[root_symbol] += quantity
                sellable_quantities[root_symbol] += available_quantity

    if position_log_fn is not None:
        for symbol in assets or tuple(sorted(quantities)):
            position_log_fn(
                "[position_snapshot] aggregate "
                f"symbol={symbol} quantity={quantities.get(symbol, 0.0)} "
                f"sellable_quantity={sellable_quantities.get(symbol, 0.0)} "
                f"market_value={market_values.get(symbol, 0.0):.2f}"
            )

    return {
        "available_cash": available_cash,
        "cash_by_currency": cash_by_currency,
        "market_values": market_values,
        "quantities": quantities,
        "sellable_quantities": sellable_quantities,
        "total_strategy_equity": available_cash + sum(market_values.values()),
    }
