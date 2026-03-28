from __future__ import annotations

from datetime import datetime
from typing import Any

from quant_platform_kit.common.models import PortfolioSnapshot, Position


def fetch_portfolio_snapshot(ib: Any, *, wait_seconds: float = 1.0) -> PortfolioSnapshot:
    ib.reqPositions()
    if wait_seconds:
        import time as time_module

        time_module.sleep(wait_seconds)

    positions = []
    for raw_position in ib.positions():
        if raw_position.position == 0:
            continue
        quantity = float(raw_position.position)
        average_cost = float(raw_position.avgCost)
        positions.append(
            Position(
                symbol=raw_position.contract.symbol,
                quantity=quantity,
                market_value=quantity * average_cost,
                average_cost=average_cost,
            )
        )

    total_equity = 0.0
    buying_power = None
    for account_value in ib.accountValues():
        if account_value.currency != "USD":
            continue
        if account_value.tag == "NetLiquidation":
            total_equity = float(account_value.value)
        elif account_value.tag == "AvailableFunds":
            buying_power = float(account_value.value)

    return PortfolioSnapshot(
        as_of=datetime.utcnow(),
        total_equity=total_equity,
        buying_power=buying_power,
        positions=tuple(positions),
    )
