from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable

from quant_platform_kit.common.models import PortfolioSnapshot, Position


def _normalize_account_ids(account_ids: Iterable[str] | str | None) -> tuple[str, ...]:
    if account_ids is None:
        return ()
    if isinstance(account_ids, str):
        candidates = [account_ids]
    else:
        candidates = list(account_ids)
    normalized = []
    for candidate in candidates:
        text = str(candidate or "").strip()
        if text:
            normalized.append(text)
    return tuple(dict.fromkeys(normalized))


def _matches_account(account_id: str | None, selected_account_ids: tuple[str, ...]) -> bool:
    if not selected_account_ids:
        return True
    return str(account_id or "").strip() in selected_account_ids


def fetch_portfolio_snapshot(
    ib: Any,
    *,
    account_ids: Iterable[str] | str | None = None,
    wait_seconds: float = 1.0,
) -> PortfolioSnapshot:
    selected_account_ids = _normalize_account_ids(account_ids)
    ib.reqPositions()
    if wait_seconds:
        import time as time_module

        time_module.sleep(wait_seconds)

    positions = []
    for raw_position in ib.positions():
        account_id = str(getattr(raw_position, "account", "") or "").strip() or None
        if not _matches_account(account_id, selected_account_ids):
            continue
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
                account_id=account_id,
            )
        )

    total_equity = 0.0
    buying_power = None
    for account_value in ib.accountValues():
        account_id = str(getattr(account_value, "account", "") or "").strip() or None
        if not _matches_account(account_id, selected_account_ids):
            continue
        if account_value.currency != "USD":
            continue
        if account_value.tag == "NetLiquidation":
            total_equity += float(account_value.value)
        elif account_value.tag == "AvailableFunds":
            value = float(account_value.value)
            buying_power = value if buying_power is None else buying_power + value

    return PortfolioSnapshot(
        as_of=datetime.utcnow(),
        total_equity=total_equity,
        buying_power=buying_power,
        positions=tuple(positions),
        metadata={"account_ids": selected_account_ids},
    )
