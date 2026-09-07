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


def _finite_balance(balances: dict[str, Any], key: str) -> float:
    """Parse a required finite balance without hiding zero, debt, or bad input."""

    raw_value = balances.get(key)
    try:
        value = float(raw_value)
    except (TypeError, ValueError, OverflowError):
        raise ValueError(f"Invalid Schwab balance: {key}") from None
    if isinstance(raw_value, bool) or not math.isfinite(value):
        raise ValueError(f"Invalid Schwab balance: {key}")
    return value


def _optional_finite_balance(balances: dict[str, Any], key: str) -> float | None:
    """Parse an optional finite balance; absent keys stay unknown."""

    if key not in balances:
        return None
    return _finite_balance(balances, key)


def _resolve_buying_power(balances: dict[str, Any], *, cash_available_for_trading: float) -> tuple[float, str]:
    """Map broker buying-power fields without inventing leverage.

    Prefer dedicated broker fields when present. Cash accounts often omit them;
    only then fall back to cash available for trading. Never synthesize a
    leveraged multiple from cash. The snapshot buying_power used for sizing is
    floored at zero; raw broker values remain inspectable via source metadata.
    """

    for key, source in (
        ("buyingPower", "broker_buying_power"),
        ("availableFunds", "broker_available_funds"),
    ):
        value = _optional_finite_balance(balances, key)
        if value is not None:
            return max(0.0, value), source
    return max(0.0, cash_available_for_trading), "cash_available_for_trading_fallback"


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
    cash_for_equity = _finite_balance(balances, "cashAvailableForTrading")
    raw_withdrawable = (
        _finite_balance(balances, "cashAvailableForWithdrawal")
        if "cashAvailableForWithdrawal" in balances
        else None
    )
    buying_power, buying_power_source = _resolve_buying_power(
        balances, cash_available_for_trading=cash_for_equity
    )

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

    if "liquidationValue" in balances:
        total_equity = _finite_balance(balances, "liquidationValue")
        total_equity_source = "broker_liquidation_value"
    else:
        # Preserve the legacy fallback; it does not establish full margin equity.
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
            "buying_power_source": buying_power_source,
            "total_equity_source": total_equity_source,
            "source_digest_sha256": _payload_digest(account_payload),
        },
    )
