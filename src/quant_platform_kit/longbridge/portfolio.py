from __future__ import annotations

from typing import Any, Iterable

from .market_data import fetch_last_price


def fetch_strategy_account_state(
    q_ctx: Any,
    t_ctx: Any,
    strategy_assets: Iterable[str],
) -> dict[str, Any]:
    available_cash = 0.0
    account_balance = t_ctx.account_balance()
    for account in account_balance:
        for cash_info in getattr(account, "cash_infos", []):
            if getattr(cash_info, "currency", None) == "USD":
                available_cash += float(getattr(cash_info, "available_cash", 0.0))

    assets = [str(symbol).strip().upper() for symbol in strategy_assets if str(symbol).strip()]
    market_values = {symbol: 0.0 for symbol in assets}
    quantities = {symbol: 0 for symbol in assets}
    sellable_quantities = {symbol: 0 for symbol in assets}
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
                    quantities[root_symbol] = 0
                    sellable_quantities[root_symbol] = 0

                last_price = fetch_last_price(q_ctx, full_symbol)
                if last_price is None:
                    continue

                quantity = int(getattr(position, "quantity", 0))
                available_quantity = int(getattr(position, "available_quantity", quantity))
                market_values[root_symbol] += quantity * last_price
                quantities[root_symbol] += quantity
                sellable_quantities[root_symbol] += available_quantity

    return {
        "available_cash": available_cash,
        "market_values": market_values,
        "quantities": quantities,
        "sellable_quantities": sellable_quantities,
        "total_strategy_equity": available_cash + sum(market_values.values()),
    }
