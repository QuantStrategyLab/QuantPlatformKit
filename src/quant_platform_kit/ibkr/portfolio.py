from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
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


def _broker_net_liquidation_evidence(
    account_values: Iterable[Any],
    *,
    selected_account_ids: tuple[str, ...],
) -> tuple[float | None, str | None]:
    """Return an account-scope USD NetLiquidation value and its source digest.

    A caller that did not explicitly select account ids may still use the
    snapshot for compatibility, but it cannot obtain strict capital evidence:
    the exact account scope would be ambiguous.  Each selected account must
    provide exactly one finite, positive USD ``NetLiquidation`` observation.
    """

    if not selected_account_ids:
        return None, None
    rows: list[dict[str, object]] = []
    for account_value in account_values:
        account_id = str(getattr(account_value, "account", "") or "").strip()
        if account_id not in selected_account_ids:
            continue
        if str(getattr(account_value, "tag", "") or "").strip() != "NetLiquidation":
            continue
        if str(getattr(account_value, "currency", "") or "").strip().upper() != "USD":
            continue
        try:
            value = float(getattr(account_value, "value", None))
        except (TypeError, ValueError):
            return None, None
        if not math.isfinite(value) or value <= 0.0:
            return None, None
        rows.append({"account_id": account_id, "currency": "USD", "value": value})

    if len(rows) != len(selected_account_ids):
        return None, None
    if {str(row["account_id"]) for row in rows} != set(selected_account_ids):
        return None, None
    canonical_rows = sorted(rows, key=lambda row: str(row["account_id"]))
    source_digest = hashlib.sha256(
        json.dumps(
            canonical_rows,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()
    return sum(float(row["value"]) for row in canonical_rows), source_digest


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
    option_positions = []
    for raw_position in ib.positions():
        account_id = str(getattr(raw_position, "account", "") or "").strip() or None
        if not _matches_account(account_id, selected_account_ids):
            continue
        if raw_position.position == 0:
            continue
        contract = raw_position.contract
        quantity = float(raw_position.position)
        average_cost = float(raw_position.avgCost)
        if str(getattr(contract, "secType", "") or "").strip().upper() == "OPT":
            option_positions.append(
                {
                    "underlier": str(getattr(contract, "symbol", "") or "").strip().upper(),
                    "local_symbol": str(getattr(contract, "localSymbol", "") or "").strip(),
                    "expiration": str(getattr(contract, "lastTradeDateOrContractMonth", "") or "").strip(),
                    "right": str(getattr(contract, "right", "") or "").strip().upper(),
                    "strike": float(getattr(contract, "strike", 0.0) or 0.0),
                    "quantity": quantity,
                    "average_cost": average_cost,
                    "cost_basis": abs(quantity * average_cost),
                    "account_id": account_id,
                }
            )
            continue
        positions.append(
            Position(
                symbol=contract.symbol,
                quantity=quantity,
                market_value=quantity * average_cost,
                average_cost=average_cost,
                account_id=account_id,
            )
        )

    account_values = tuple(ib.accountValues())
    total_equity = 0.0
    buying_power = None
    for account_value in account_values:
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

    verified_total_equity, source_digest = _broker_net_liquidation_evidence(
        account_values,
        selected_account_ids=selected_account_ids,
    )
    if verified_total_equity is not None:
        total_equity = verified_total_equity

    return PortfolioSnapshot(
        as_of=datetime.now(timezone.utc),
        total_equity=total_equity,
        buying_power=buying_power,
        positions=tuple(positions),
        metadata={
            "account_ids": selected_account_ids,
            "option_positions": tuple(option_positions),
            "total_equity_source": (
                "broker_net_liquidation"
                if source_digest is not None
                else "unverified_net_liquidation"
            ),
            **(
                {"source_digest_sha256": source_digest}
                if source_digest is not None
                else {}
            ),
        },
    )
