from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import math
from typing import Any, Iterable

from quant_platform_kit.common.models import PortfolioSnapshot, Position
from .market_data import _request_with_retries, decode_response_json


def _payload_digest(payload: Any) -> str:
    """Bind a normalized snapshot to the broker response without retaining it."""

    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return sha256(canonical).hexdigest()


def _positive_finite_balance(balances: dict[str, Any], key: str) -> float | None:
    """Return an explicit broker account-value field only when usable."""

    try:
        value = float(balances.get(key))
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) and value > 0.0 else None


def fetch_account_snapshot(
    api_client: Any,
    *,
    strategy_symbols: Iterable[str] = (),
    expected_account_hash: str | None = None,
) -> PortfolioSnapshot:
    from schwab import client

    account_numbers = decode_response_json(
        _request_with_retries(api_client.get_account_numbers),
        "Account numbers",
    )
    account_hashes = {
        value.strip()
        for item in account_numbers
        if isinstance(item, dict)
        for value in [item.get("hashValue")]
        if isinstance(value, str) and value.strip()
    }
    if not account_hashes:
        raise ValueError("Schwab account numbers did not contain an account hash.")
    if expected_account_hash is None:
        if len(account_hashes) != 1:
            raise ValueError("Schwab snapshot requires an explicit account hash for multiple accounts.")
        account_hash = next(iter(account_hashes))
    elif expected_account_hash not in account_hashes:
        raise ValueError("The selected Schwab account hash is unavailable.")
    else:
        account_hash = expected_account_hash

    account_payload = decode_response_json(
        _request_with_retries(
            lambda: api_client.get_account(
                account_hash,
                fields=client.Client.Account.Fields.POSITIONS,
            )
        ),
        "Account positions",
    )
    account = account_payload["securitiesAccount"]
    balances = account.get("currentBalances", {})
    cash_for_equity = float(balances.get("cashAvailableForTrading", 0.0))
    raw_withdrawable = float(balances.get("cashAvailableForWithdrawal", 0.0))
    buying_power = max(0.0, cash_for_equity)

    allowed_symbols = set(strategy_symbols)
    positions = []
    all_position_market_value = 0.0
    for raw_position in account.get("positions", []):
        symbol = raw_position["instrument"]["symbol"]
        market_value = float(raw_position.get("marketValue", 0.0))
        all_position_market_value += market_value
        if allowed_symbols and symbol not in allowed_symbols:
            continue
        positions.append(
            Position(
                symbol=symbol,
                quantity=float(raw_position.get("longQuantity", 0)),
                market_value=market_value,
            )
        )

    liquidation_value = _positive_finite_balance(balances, "liquidationValue")
    if liquidation_value is not None:
        total_equity = liquidation_value
        total_equity_source = "broker_liquidation_value"
    else:
        # Strategy symbols only control the positions exposed to a strategy;
        # they must not silently change the account-level denominator used by
        # value-target risk controls.
        total_equity = cash_for_equity + all_position_market_value
        total_equity_source = "cash_available_plus_all_position_market_values"

    return PortfolioSnapshot(
        as_of=datetime.now(timezone.utc),
        total_equity=total_equity,
        buying_power=buying_power,
        cash_balance=cash_for_equity,
        positions=tuple(positions),
        metadata={
            "account_hash": account_hash,
            "cash_available_for_trading": cash_for_equity,
            "cash_available_for_withdrawal": raw_withdrawable,
            "total_equity_source": total_equity_source,
            "source_digest_sha256": _payload_digest(account_payload),
        },
    )
