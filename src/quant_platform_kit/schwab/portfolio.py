from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable

from quant_platform_kit.common.models import PortfolioSnapshot, Position
from .market_data import decode_response_json


def fetch_account_snapshot(
    api_client: Any,
    *,
    strategy_symbols: Iterable[str] = (),
) -> PortfolioSnapshot:
    from schwab import client

    account_numbers = decode_response_json(api_client.get_account_numbers(), "Account numbers")
    account_hash = account_numbers[0]["hashValue"]

    account_payload = decode_response_json(
        api_client.get_account(account_hash, fields=client.Client.Account.Fields.POSITIONS),
        "Account positions",
    )
    account = account_payload["securitiesAccount"]
    balances = account.get("currentBalances", {})
    cash_for_equity = float(balances.get("cashAvailableForTrading", 0.0))
    raw_withdrawable = float(balances.get("cashAvailableForWithdrawal", 0.0))
    buying_power = max(0.0, cash_for_equity)

    allowed_symbols = set(strategy_symbols)
    positions = []
    for raw_position in account.get("positions", []):
        symbol = raw_position["instrument"]["symbol"]
        if allowed_symbols and symbol not in allowed_symbols:
            continue
        positions.append(
            Position(
                symbol=symbol,
                quantity=float(raw_position.get("longQuantity", 0)),
                market_value=float(raw_position.get("marketValue", 0.0)),
            )
        )

    total_equity = cash_for_equity + sum(position.market_value for position in positions)

    return PortfolioSnapshot(
        as_of=datetime.utcnow(),
        total_equity=total_equity,
        buying_power=buying_power,
        cash_balance=cash_for_equity,
        positions=tuple(positions),
        metadata={
            "account_hash": account_hash,
            "cash_available_for_trading": cash_for_equity,
            "cash_available_for_withdrawal": raw_withdrawable,
        },
    )
