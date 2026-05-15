from __future__ import annotations

import time
from typing import Any, Callable, Iterable

from .market_data import fetch_last_prices


def fetch_strategy_account_state(
    q_ctx: Any,
    t_ctx: Any,
    strategy_assets: Iterable[str],
    *,
    position_log_fn: Callable[[str], None] | None = None,
    warning_log_fn: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    def warn(message: str) -> None:
        if warning_log_fn is not None:
            warning_log_fn(message)

    def load_account_balance() -> tuple[Any, ...]:
        attempts = (
            ("all", {}),
            ("USD", {"currency": "USD"}),
            ("HKD", {"currency": "HKD"}),
            ("CNH", {"currency": "CNH"}),
        )
        errors: list[str] = []
        for label, kwargs in attempts:
            for attempt in range(1, 4):
                try:
                    account_balance = t_ctx.account_balance(**kwargs)
                except TypeError as exc:
                    errors.append(f"{label}=TypeError:{exc}")
                    break
                except Exception as exc:
                    errors.append(f"{label}[attempt={attempt}]={type(exc).__name__}:{exc}")
                    if attempt < 3:
                        warn(
                            "[longbridge_account_balance_retrying] "
                            f"currency={label} attempt={attempt}/3 error_type={type(exc).__name__}"
                        )
                        time.sleep(0.5 * attempt)
                        continue
                    break

                if kwargs:
                    warn(f"[longbridge_account_balance_retry_succeeded] currency={label}")
                return tuple(account_balance or ())

        if errors:
            warn("[longbridge_account_balance_failed] " + " | ".join(errors))
        return ()

    available_cash = 0.0
    cash_by_currency: dict[str, float] = {}
    account_balance = load_account_balance()
    for account in account_balance:
        account_buy_power = max(0.0, float(getattr(account, "buy_power", 0.0) or 0.0))
        account_usd_cash = 0.0
        for cash_info in getattr(account, "cash_infos", []):
            currency = str(getattr(cash_info, "currency", "") or "").strip().upper()
            if not currency:
                continue
            cash_amount = float(getattr(cash_info, "available_cash", 0.0))
            cash_by_currency[currency] = cash_by_currency.get(currency, 0.0) + cash_amount
            if currency == "USD":
                account_usd_cash += cash_amount
        available_cash += max(account_buy_power, account_usd_cash)

    assets = [str(symbol).strip().upper() for symbol in strategy_assets if str(symbol).strip()]
    market_values = {symbol: 0.0 for symbol in assets}
    quantities = {symbol: 0.0 for symbol in assets}
    sellable_quantities = {symbol: 0.0 for symbol in assets}
    filter_enabled = bool(assets)

    position_rows: list[tuple[str, str, Any, Any]] = []
    positions_response = None
    position_errors: list[str] = []
    for attempt in range(1, 4):
        try:
            positions_response = t_ctx.stock_positions()
            break
        except Exception as exc:
            position_errors.append(f"attempt={attempt} {type(exc).__name__}:{exc}")
            if attempt < 3:
                warn(
                    "[longbridge_stock_positions_retrying] "
                    f"attempt={attempt}/3 error_type={type(exc).__name__}"
                )
                time.sleep(0.5 * attempt)
                continue
            warn(
                "[longbridge_stock_positions_failed] "
                f"errors={' | '.join(position_errors)}"
            )
    if positions_response and hasattr(positions_response, "channels"):
        for channel in positions_response.channels:
            for position in getattr(channel, "positions", []):
                full_symbol = str(getattr(position, "symbol", "") or "").strip().upper()
                if not full_symbol:
                    continue
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

                position_rows.append((root_symbol, full_symbol, raw_quantity, raw_available_quantity))

    prices = fetch_last_prices(q_ctx, [full_symbol for _root_symbol, full_symbol, _quantity, _available in position_rows])
    for root_symbol, full_symbol, raw_quantity, raw_available_quantity in position_rows:
        last_price = prices.get(full_symbol)
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
