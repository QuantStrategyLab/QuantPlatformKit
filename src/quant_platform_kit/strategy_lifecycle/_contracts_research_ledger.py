"""Research trial ledger, position marks, and option-ledger validation."""

from __future__ import annotations

import enum
import math
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any, Mapping

from ._contracts_observation import validate_periods_per_year

# ── Research trial ledger ───────────────────────────────────────────
# Independent of BacktestResult / promotion. Synthetic storage is not a grant.


_IDENTITY_PLACEHOLDERS = frozenset({"unknown", "default", "none", "null", "na", "n/a"})
_RESEARCH_NON_SUCCESS = frozenset({"failed", "rejected", "aborted"})


class ResearchTrialStatus(str, enum.Enum):
    """Lifecycle of one research attempt. Terminal states do not promote."""

    STARTED = "started"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REJECTED = "rejected"
    ABORTED = "aborted"


def _reject_identity_placeholder(value: str) -> None:
    if value.casefold() in _IDENTITY_PLACEHOLDERS:
        raise ValueError("identity_placeholder")


def _label(value: object) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError("identity")
    if len(value) > 200 or any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ValueError("identity")
    _reject_identity_placeholder(value)
    return value


def _raw_identity(value: object) -> str:
    if not isinstance(value, str) or not value or any(char.isspace() for char in value):
        raise ValueError("identity")
    if len(value) > 500 or any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ValueError("identity")
    _reject_identity_placeholder(value)
    return value


def _run_identity(value: object) -> str:
    """Backtest run ids may contain internal spaces; they are not reason text."""

    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError("identity")
    if len(value) > 500 or any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ValueError("identity")
    if any(char.isspace() and char != " " for char in value):
        raise ValueError("identity")
    _reject_identity_placeholder(value)
    return value


def _require_date(value: object) -> date:
    if type(value) is not date:
        raise ValueError("window")
    return value


def _finite_number(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("invalid_number")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("invalid_number")
    return number


def _reason_code(value: object, *, allow_empty: bool) -> str:
    if not isinstance(value, str):
        raise ValueError("reason_code")
    if value == "" and allow_empty:
        return ""
    alphabet = "abcdefghijklmnopqrstuvwxyz0123456789_"
    if (
        not value
        or len(value) > 64
        or value[0] not in "abcdefghijklmnopqrstuvwxyz"
        or any(char not in alphabet for char in value)
    ):
        raise ValueError("reason_code")
    return value


def _cost_inputs(value: object, *, allow_empty: bool) -> dict[str, float]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Mapping):
        raise ValueError("cost_inputs")
    parsed: dict[str, float] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not key or any(char.isspace() for char in key):
            raise ValueError("cost_inputs")
        number = _finite_number(item)
        if number < 0:
            raise ValueError("cost_inputs")
        parsed[key] = number
    if not parsed and not allow_empty:
        raise ValueError("cost_inputs")
    return parsed


def _symbol(value: object) -> str:
    if not isinstance(value, str) or not value or len(value) > 32:
        raise ValueError("position_mark")
    if any(not (char.isalnum() or char in "._-") for char in value):
        raise ValueError("position_mark")
    return value


@dataclass(frozen=True)
class ResearchPositionMark:
    """One equity or option contract position and its signed marked value."""

    symbol: str
    quantity: float
    valuation: float
    option_underlying: str | None = None
    option_right: str | None = None
    option_strike: float | None = None
    option_expiration: date | None = None
    option_multiplier: float | None = None
    option_premium_cashflow: float | None = None

    def __post_init__(self) -> None:
        symbol = _symbol(self.symbol)
        quantity = _finite_number(self.quantity)
        valuation = _finite_number(self.valuation)
        option_values = (
            self.option_underlying, self.option_right, self.option_strike,
            self.option_expiration, self.option_multiplier, self.option_premium_cashflow,
        )
        if all(value is None for value in option_values):
            if (quantity == 0.0) != (valuation == 0.0):
                raise ValueError("position_mark")
        elif any(value is None for value in option_values):
            raise ValueError("option_position")
        else:
            underlying = _symbol(self.option_underlying)
            right = self.option_right
            if right not in {"call", "put"} or quantity == 0.0 or (
                valuation != 0.0 and quantity * valuation < 0
            ):
                raise ValueError("option_position")
            strike = _finite_number(self.option_strike)
            multiplier = _finite_number(self.option_multiplier)
            premium_cashflow = _finite_number(self.option_premium_cashflow)
            expiration = _require_date(self.option_expiration)
            if strike <= 0 or multiplier <= 0 or quantity * premium_cashflow >= 0:
                raise ValueError("option_position")
            object.__setattr__(self, "option_underlying", underlying)
            object.__setattr__(self, "option_right", right)
            object.__setattr__(self, "option_strike", strike)
            object.__setattr__(self, "option_expiration", expiration)
            object.__setattr__(self, "option_multiplier", multiplier)
            object.__setattr__(self, "option_premium_cashflow", premium_cashflow)
        object.__setattr__(self, "symbol", symbol)
        object.__setattr__(self, "quantity", quantity)
        object.__setattr__(self, "valuation", valuation)

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "symbol": self.symbol,
            "quantity": self.quantity,
            "valuation": self.valuation,
        }
        if self.option_underlying is not None:
            payload.update({
                "option_underlying": self.option_underlying,
                "option_right": self.option_right,
                "option_strike": self.option_strike,
                "option_expiration": self.option_expiration.isoformat(),
                "option_multiplier": self.option_multiplier,
                "option_premium_cashflow": self.option_premium_cashflow,
            })
        return payload


def _position_marks(value: object) -> tuple[ResearchPositionMark, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, (tuple, list)):
        raise ValueError("position_mark")
    marks: list[ResearchPositionMark] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, ResearchPositionMark):
            raise ValueError("position_mark")
        if item.symbol in seen:
            raise ValueError("position_mark")
        seen.add(item.symbol)
        marks.append(item)
    return tuple(marks)


def _option_collateral_requirement(positions: tuple[ResearchPositionMark, ...]) -> float:
    groups: dict[tuple[str, str, date, float], list[ResearchPositionMark]] = {}
    for mark in positions:
        if mark.option_underlying is not None:
            key = (mark.option_underlying, mark.option_right, mark.option_expiration, mark.option_multiplier)
            groups.setdefault(key, []).append(mark)
    required = 0.0
    for (_, right, _, multiplier), marks in groups.items():
        shorts = sorted(
            (mark for mark in marks if mark.quantity < 0),
            key=lambda mark: mark.option_strike,
            reverse=right == "put",
        )
        longs = {mark.symbol: mark.quantity for mark in marks if mark.quantity > 0}
        gross_risk = 0.0
        for short in shorts:
            remaining = abs(short.quantity)
            if right == "put":
                protective = sorted(
                    (mark for mark in marks if mark.quantity > 0 and mark.option_strike < short.option_strike),
                    key=lambda mark: mark.option_strike,
                    reverse=True,
                )
            else:
                protective = sorted(
                    (mark for mark in marks if mark.quantity > 0 and mark.option_strike > short.option_strike),
                    key=lambda mark: mark.option_strike,
                )
            for long in protective:
                matched = min(remaining, longs[long.symbol])
                if matched <= 0:
                    continue
                gross_risk += abs(short.option_strike - long.option_strike) * matched * multiplier
                remaining -= matched
                longs[long.symbol] -= matched
                if remaining <= 1e-9:
                    break
            if remaining > 1e-9:
                raise ValueError("option_naked_short")
        if shorts:
            net_premium_credit = sum(mark.option_premium_cashflow for mark in marks)
            required += max(0.0, gross_risk - net_premium_credit)
    return required


def _equity_trade_quantities(value: object) -> dict[str, float] | None:
    if value is None:
        return None
    if isinstance(value, (str, bytes)) or not isinstance(value, Mapping):
        raise ValueError("ledger_equity_trade_quantity")
    quantities: dict[str, float] = {}
    for raw_symbol, raw_quantity in value.items():
        symbol = _symbol(raw_symbol)
        quantity = _finite_number(raw_quantity)
        if quantity == 0.0 or symbol in quantities:
            raise ValueError("ledger_equity_trade_quantity")
        quantities[symbol] = quantity
    return dict(sorted(quantities.items()))


def _validate_option_ledger(
    initial_positions: tuple[ResearchPositionMark, ...],
    days: tuple[ResearchLedgerDay, ...],
    initial_cash: float,
    initial_restricted_cash: float,
) -> None:
    previous = {mark.symbol: mark for mark in initial_positions}
    previous_cash = initial_cash
    previous_restricted = initial_restricted_cash
    if initial_restricted_cash + 1e-9 < _option_collateral_requirement(initial_positions):
        raise ValueError("ledger_option_collateral")
    for day in days:
        current = {mark.symbol: mark for mark in day.positions}
        previous_options = {key: mark for key, mark in previous.items() if mark.option_underlying is not None}
        current_options = {key: mark for key, mark in current.items() if mark.option_underlying is not None}
        option_trade_events = [event for event in day.events if event.event_type == "option_trade"]
        if len({event.symbol for event in option_trade_events}) != len(option_trade_events):
            raise ValueError("ledger_option_trade")
        option_changes = set(previous_options) ^ set(current_options)
        expiring_symbols = {
            symbol for symbol, mark in previous_options.items() if mark.option_expiration == day.session_date
        }
        trade_changes = option_changes - expiring_symbols
        if {event.symbol for event in option_trade_events} != trade_changes:
            raise ValueError("ledger_option_trade")
        if trade_changes:
            option_trade_cashflow = sum(event.amount for event in option_trade_events)
            equity_quantity_changed = False
            for symbol in set(previous) | set(current):
                before, after = previous.get(symbol), current.get(symbol)
                before_quantity = 0.0 if before is None or before.option_underlying is not None else before.quantity
                after_quantity = 0.0 if after is None or after.option_underlying is not None else after.quantity
                if before_quantity != after_quantity:
                    equity_quantity_changed = True
            if equity_quantity_changed and day.equity_trade_cashflow is None:
                raise ValueError("ledger_equity_trade_cashflow")
            equity_trade_cashflow = day.equity_trade_cashflow or 0.0
            if not math.isclose(
                day.trade_net_cashflow, option_trade_cashflow + equity_trade_cashflow,
                rel_tol=0.0, abs_tol=1e-9,
            ):
                raise ValueError("ledger_option_trade")
            for symbol in trade_changes:
                event = next(event for event in option_trade_events if event.symbol == symbol)
                before, after = previous_options.get(symbol), current_options.get(symbol)
                if after is not None:
                    if after.option_expiration <= day.session_date or not math.isclose(
                        event.amount, after.option_premium_cashflow, rel_tol=0.0, abs_tol=1e-9
                    ):
                        raise ValueError("ledger_option_trade")
                elif before is not None and before.option_expiration <= day.session_date:
                    raise ValueError("ledger_option_settlement")
                elif before is not None and event.amount * before.quantity <= 0:
                    raise ValueError("ledger_option_trade")
        for symbol in set(previous_options) & set(current_options):
            before, after = previous_options[symbol], current_options[symbol]
            if (
                before.quantity != after.quantity
                or before.option_underlying != after.option_underlying
                or before.option_right != after.option_right
                or before.option_strike != after.option_strike
                or before.option_expiration != after.option_expiration
                or before.option_multiplier != after.option_multiplier
                or before.option_premium_cashflow != after.option_premium_cashflow
            ):
                raise ValueError("ledger_option_trade")

        settlements = [event for event in day.events if event.event_type == "option_settlement"]
        settlement_by_underlying = {event.symbol: event for event in settlements}
        if len(settlement_by_underlying) != len(settlements):
            raise ValueError("ledger_option_settlement")
        if not settlements and (day.equity_trade_quantities is not None or day.equity_trade_phase is not None):
            raise ValueError("ledger_equity_trade_phase")
        expiring: dict[str, list[ResearchPositionMark]] = {}
        for mark in previous_options.values():
            if mark.option_expiration < day.session_date:
                raise ValueError("ledger_option_expiration")
            if mark.option_expiration == day.session_date:
                if mark.symbol in current_options:
                    raise ValueError("ledger_option_settlement")
                expiring.setdefault(mark.option_underlying, []).append(mark)
        if set(settlement_by_underlying) != set(expiring):
            raise ValueError("ledger_option_settlement")
        settlement_cashflow = 0.0
        deliveries: dict[str, float] = {}
        for underlying, legs in expiring.items():
            spot = settlement_by_underlying[underlying].settlement_price
            for leg in legs:
                intrinsic = (
                    max(spot - leg.option_strike, 0.0)
                    if leg.option_right == "call"
                    else max(leg.option_strike - spot, 0.0)
                )
                if intrinsic == 0.0:
                    continue
                signed_contracts = leg.quantity * leg.option_multiplier
                if leg.option_right == "call":
                    settlement_cashflow -= signed_contracts * leg.option_strike
                    deliveries[underlying] = deliveries.get(underlying, 0.0) + signed_contracts
                else:
                    settlement_cashflow += signed_contracts * leg.option_strike
                    deliveries[underlying] = deliveries.get(underlying, 0.0) - signed_contracts
            current_equity = next((
                mark for mark in current.values()
                if mark.symbol == underlying and mark.option_underlying is None
            ), None)
            current_shares = 0.0 if current_equity is None else current_equity.quantity
            if current_equity is not None and not math.isclose(
                current_equity.valuation, current_shares * spot, rel_tol=0.0, abs_tol=1e-9
            ):
                raise ValueError("ledger_option_delivery")
        if settlements:
            if day.equity_trade_quantities is not None and day.equity_trade_cashflow is None:
                raise ValueError("ledger_equity_trade_quantity")
            if day.equity_trade_cashflow is not None and day.equity_trade_quantities is None:
                raise ValueError("ledger_equity_trade_quantity")
            option_trade_cashflow = sum(event.amount for event in option_trade_events)
            equity_trade_cashflow = day.equity_trade_cashflow or 0.0
            if not math.isclose(
                day.trade_net_cashflow, option_trade_cashflow + equity_trade_cashflow,
                rel_tol=0.0, abs_tol=1e-9,
            ):
                raise ValueError("ledger_option_settlement")
            declared_quantities = day.equity_trade_quantities or {}
            previous_equity = {
                symbol: mark.quantity for symbol, mark in previous.items() if mark.option_underlying is None
            }
            current_equity = {
                symbol: mark.quantity for symbol, mark in current.items() if mark.option_underlying is None
            }
            for symbol in set(previous_equity) | set(current_equity) | set(deliveries) | set(declared_quantities):
                actual = current_equity.get(symbol, 0.0) - previous_equity.get(symbol, 0.0)
                trade_quantity = declared_quantities.get(symbol, 0.0)
                if (
                    day.equity_trade_phase == "before_settlement"
                    and previous_equity.get(symbol, 0.0) + trade_quantity < -1e-9
                ):
                    raise ValueError("ledger_equity_trade_quantity")
                expected = deliveries.get(symbol, 0.0) + trade_quantity
                if not math.isclose(actual, expected, rel_tol=0.0, abs_tol=1e-9):
                    raise ValueError("ledger_equity_trade_quantity")
        if not math.isclose(day.option_settlement_cashflow, settlement_cashflow, rel_tol=0.0, abs_tol=1e-9):
            raise ValueError("ledger_option_settlement")
        collateral_change = sum(
            event.amount for event in day.events if event.event_type == "collateral_change"
        )
        if not math.isclose(
            day.restricted_cash, previous_restricted + collateral_change, rel_tol=0.0, abs_tol=1e-9
        ):
            raise ValueError("ledger_collateral")
        if day.restricted_cash + 1e-9 < _option_collateral_requirement(day.positions):
            raise ValueError("ledger_option_collateral")
        if settlements and day.restricted_cash > _option_collateral_requirement(day.positions) + 1e-9:
            raise ValueError("ledger_collateral_release")
        if settlement_cashflow < 0:
            option_trade_cashflow = sum(event.amount for event in option_trade_events)
            equity_cash_before_settlement = (
                (day.equity_trade_cashflow or 0.0)
                if day.equity_trade_phase == "before_settlement" else 0.0
            )
            fees_before_settlement = day.fees if day.equity_trade_phase == "before_settlement" else 0.0
            cash_before_settlement = (
                previous_cash
                + option_trade_cashflow + equity_cash_before_settlement - fees_before_settlement
                + day.income_cashflow + day.external_cashflow
            )
            collateral_release = max(0.0, previous_restricted - day.restricted_cash)
            available = cash_before_settlement - previous_restricted + collateral_release
            if -settlement_cashflow > available + 1e-9:
                raise ValueError("ledger_option_funding")
        previous = current
        previous_cash = day.cash
        previous_restricted = day.restricted_cash


@dataclass(frozen=True)
class ResearchLedgerEvent:
    """One explicitly identified corporate-action, option, or collateral event."""

    event_id: str
    event_type: str
    symbol: str
    amount: float | None = None
    per_share: float | None = None
    ratio: float | None = None
    reference_event_id: str | None = None
    settlement_price: float | None = None

    def __post_init__(self) -> None:
        event_id = _raw_identity(self.event_id)
        event_type = _label(self.event_type)
        symbol = _label(self.symbol)
        if event_type == "dividend_accrual":
            if (
                self.amount is not None or self.ratio is not None or self.reference_event_id is not None
                or self.settlement_price is not None
            ):
                raise ValueError("ledger_event_fields")
            per_share = _finite_number(self.per_share)
            if per_share <= 0:
                raise ValueError("ledger_event_fields")
        elif event_type == "dividend_payment":
            if (
                self.per_share is not None or self.ratio is not None or self.settlement_price is not None
                or not self.reference_event_id
            ):
                raise ValueError("ledger_event_fields")
            amount = _finite_number(self.amount)
            if amount <= 0:
                raise ValueError("ledger_event_fields")
            object.__setattr__(self, "amount", amount)
            object.__setattr__(self, "reference_event_id", _raw_identity(self.reference_event_id))
        elif event_type == "split":
            if (
                self.amount is not None or self.per_share is not None or self.reference_event_id is not None
                or self.settlement_price is not None
            ):
                raise ValueError("ledger_event_fields")
            ratio = _finite_number(self.ratio)
            if ratio <= 0:
                raise ValueError("ledger_event_fields")
            object.__setattr__(self, "ratio", ratio)
        elif event_type == "option_trade":
            if any(value is not None for value in (self.per_share, self.ratio, self.reference_event_id, self.settlement_price)):
                raise ValueError("ledger_event_fields")
            amount = _finite_number(self.amount)
            if amount == 0.0:
                raise ValueError("ledger_event_fields")
            symbol = _symbol(symbol)
            object.__setattr__(self, "amount", amount)
        elif event_type == "option_settlement":
            if any(value is not None for value in (self.amount, self.per_share, self.ratio, self.reference_event_id)):
                raise ValueError("ledger_event_fields")
            settlement_price = _finite_number(self.settlement_price)
            if settlement_price <= 0:
                raise ValueError("ledger_event_fields")
            symbol = _symbol(symbol)
            object.__setattr__(self, "settlement_price", settlement_price)
        elif event_type == "collateral_change":
            if any(value is not None for value in (self.per_share, self.ratio, self.reference_event_id, self.settlement_price)):
                raise ValueError("ledger_event_fields")
            amount = _finite_number(self.amount)
            if amount == 0.0 or symbol != "CASH":
                raise ValueError("ledger_event_fields")
            object.__setattr__(self, "amount", amount)
        else:
            raise ValueError("ledger_event_type")
        object.__setattr__(self, "event_id", event_id)
        object.__setattr__(self, "event_type", event_type)
        object.__setattr__(self, "symbol", symbol)
        if event_type == "dividend_accrual":
            object.__setattr__(self, "per_share", per_share)

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "symbol": self.symbol,
        }
        if self.amount is not None:
            payload["amount"] = self.amount
        if self.per_share is not None:
            payload["per_share"] = self.per_share
        if self.ratio is not None:
            payload["ratio"] = self.ratio
        if self.reference_event_id is not None:
            payload["reference_event_id"] = self.reference_event_id
        if self.settlement_price is not None:
            payload["settlement_price"] = self.settlement_price
        return payload


@dataclass(frozen=True)
class ResearchLedgerDay:
    """End-of-session book with events ordered split, accrual, payment, trade, valuation."""

    session_date: date
    cash: float
    positions: tuple[ResearchPositionMark, ...]
    trade_net_cashflow: float
    fees: float
    nav: float
    daily_return: float
    income_cashflow: float = 0.0
    external_cashflow: float = 0.0
    dividend_receivable: float = 0.0
    declared_event_ids: tuple[str, ...] | None = None
    events: tuple[ResearchLedgerEvent, ...] = ()
    restricted_cash: float = 0.0
    option_settlement_cashflow: float = 0.0
    equity_trade_cashflow: float | None = None
    equity_trade_quantities: Mapping[str, float] | None = None
    equity_trade_phase: str | None = None

    def __post_init__(self) -> None:
        session_date = _require_date(self.session_date)
        cash = _finite_number(self.cash)
        positions = _position_marks(self.positions)
        trade_net_cashflow = _finite_number(self.trade_net_cashflow)
        income_cashflow = _finite_number(self.income_cashflow)
        external_cashflow = _finite_number(self.external_cashflow)
        dividend_receivable = _finite_number(self.dividend_receivable)
        restricted_cash = _finite_number(self.restricted_cash)
        option_settlement_cashflow = _finite_number(self.option_settlement_cashflow)
        equity_trade_cashflow = (
            None if self.equity_trade_cashflow is None else _finite_number(self.equity_trade_cashflow)
        )
        equity_trade_quantities = _equity_trade_quantities(self.equity_trade_quantities)
        equity_trade_phase = self.equity_trade_phase
        if equity_trade_phase is not None and (
            not isinstance(equity_trade_phase, str)
            or equity_trade_phase not in {"before_settlement", "after_settlement"}
        ):
            raise ValueError("ledger_equity_trade_phase")
        if (equity_trade_quantities is None) != (equity_trade_phase is None):
            raise ValueError("ledger_equity_trade_phase")
        fees = _finite_number(self.fees)
        if fees < 0:
            raise ValueError("ledger_fee")
        nav = _finite_number(self.nav)
        if nav <= 0 or dividend_receivable < 0 or restricted_cash < 0 or restricted_cash > max(cash, 0.0) + 1e-9:
            raise ValueError("ledger_nav")
        daily_return = _finite_number(self.daily_return)
        expected_nav = cash + sum(mark.valuation for mark in positions) + dividend_receivable
        if not math.isclose(nav, expected_nav, rel_tol=0.0, abs_tol=1e-9):
            raise ValueError("ledger_nav")
        if self.declared_event_ids is None:
            declared_event_ids = None
        else:
            if isinstance(self.declared_event_ids, (str, bytes)) or not isinstance(self.declared_event_ids, (tuple, list)):
                raise ValueError("ledger_event_set")
            declared_event_ids = tuple(_raw_identity(item) for item in self.declared_event_ids)
            if len(set(declared_event_ids)) != len(declared_event_ids):
                raise ValueError("ledger_event_set")
        if isinstance(self.events, (str, bytes)) or not isinstance(self.events, (tuple, list)):
            raise ValueError("ledger_event")
        events = tuple(self.events)
        if any(not isinstance(event, ResearchLedgerEvent) for event in events):
            raise ValueError("ledger_event")
        if len({event.event_id for event in events}) != len(events):
            raise ValueError("ledger_event_duplicate")
        object.__setattr__(self, "session_date", session_date)
        object.__setattr__(self, "cash", cash)
        object.__setattr__(self, "positions", positions)
        object.__setattr__(self, "trade_net_cashflow", trade_net_cashflow)
        object.__setattr__(self, "income_cashflow", income_cashflow)
        object.__setattr__(self, "external_cashflow", external_cashflow)
        object.__setattr__(self, "dividend_receivable", dividend_receivable)
        object.__setattr__(self, "declared_event_ids", declared_event_ids)
        object.__setattr__(self, "events", events)
        object.__setattr__(self, "restricted_cash", restricted_cash)
        object.__setattr__(self, "option_settlement_cashflow", option_settlement_cashflow)
        object.__setattr__(self, "equity_trade_cashflow", equity_trade_cashflow)
        object.__setattr__(self, "equity_trade_quantities", equity_trade_quantities)
        object.__setattr__(self, "equity_trade_phase", equity_trade_phase)
        object.__setattr__(self, "fees", fees)
        object.__setattr__(self, "nav", nav)
        object.__setattr__(self, "daily_return", daily_return)

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "session_date": self.session_date.isoformat(),
            "cash": self.cash,
            "positions": [mark.to_dict() for mark in self.positions],
            "trade_net_cashflow": self.trade_net_cashflow,
            "fees": self.fees,
            "nav": self.nav,
            "daily_return": self.daily_return,
        }
        if self.income_cashflow != 0.0:
            payload["income_cashflow"] = self.income_cashflow
        if self.external_cashflow != 0.0:
            payload["external_cashflow"] = self.external_cashflow
        if self.dividend_receivable != 0.0:
            payload["dividend_receivable"] = self.dividend_receivable
        if self.declared_event_ids is not None:
            payload["declared_event_ids"] = list(self.declared_event_ids)
        if self.events:
            payload["events"] = [event.to_dict() for event in self.events]
        if self.restricted_cash != 0.0:
            payload["restricted_cash"] = self.restricted_cash
        if self.option_settlement_cashflow != 0.0:
            payload["option_settlement_cashflow"] = self.option_settlement_cashflow
        if self.equity_trade_cashflow is not None:
            payload["equity_trade_cashflow"] = self.equity_trade_cashflow
        if self.equity_trade_quantities is not None:
            payload["equity_trade_quantities"] = dict(self.equity_trade_quantities)
            payload["equity_trade_phase"] = self.equity_trade_phase
        return payload


@dataclass(frozen=True)
class ResearchDailyLedger:
    """Complete daily book for one research trial.

    ``initial_session_date`` is the first marked session. Its cash, positions,
    and NAV are not a return observation. ``days`` are strictly later sessions
    and each carries that session's return. ``window_start`` is the initial
    session; ``observation_count`` counts only those later return days.
    """

    trial_id: str
    domain: str
    strategy_profile: str
    run_id: str
    param_version: int
    input_id: str
    calendar_id: str
    periods_per_year: float
    cost_source: str
    cost_inputs: Mapping[str, float]
    initial_session_date: date
    initial_nav: float
    initial_cash: float
    initial_positions: tuple[ResearchPositionMark, ...]
    days: tuple[ResearchLedgerDay, ...]
    synthetic: bool
    initial_restricted_cash: float = 0.0

    def __post_init__(self) -> None:
        trial_id = _raw_identity(self.trial_id)
        domain = _label(self.domain)
        strategy_profile = _label(self.strategy_profile)
        run_id = _run_identity(self.run_id)
        if type(self.param_version) is not int or self.param_version <= 0:
            raise ValueError("param_version")
        input_id = _raw_identity(self.input_id)
        calendar_id = _label(self.calendar_id)
        number = _finite_number(self.periods_per_year)
        try:
            periods = validate_periods_per_year(number)
        except ValueError as exc:
            raise ValueError("periods_per_year") from exc
        cost_source = _raw_identity(self.cost_source)
        cost_inputs = _cost_inputs(self.cost_inputs, allow_empty=False)
        initial_session_date = _require_date(self.initial_session_date)
        initial_nav = _finite_number(self.initial_nav)
        initial_cash = _finite_number(self.initial_cash)
        initial_restricted_cash = _finite_number(self.initial_restricted_cash)
        initial_positions = _position_marks(self.initial_positions)
        if initial_nav <= 0:
            raise ValueError("ledger_nav")
        expected_initial = initial_cash + sum(mark.valuation for mark in initial_positions)
        if not math.isclose(initial_nav, expected_initial, rel_tol=0.0, abs_tol=1e-9):
            raise ValueError("ledger_nav")
        if initial_restricted_cash < 0 or initial_restricted_cash > max(initial_cash, 0.0) + 1e-9:
            raise ValueError("ledger_collateral")
        if isinstance(self.days, (str, bytes)) or not isinstance(self.days, (tuple, list)) or not self.days:
            raise ValueError("ledger_dates")
        days = tuple(self.days)
        previous_date = initial_session_date
        for day in days:
            if not isinstance(day, ResearchLedgerDay):
                raise ValueError("ledger_dates")
            if day.session_date <= previous_date:
                raise ValueError("ledger_dates")
            previous_date = day.session_date
        if type(self.synthetic) is not bool:
            raise ValueError("synthetic")
        previous_cash = initial_cash
        previous_nav = initial_nav
        previous_receivable = 0.0
        previous_quantities = {mark.symbol: mark.quantity for mark in initial_positions}
        seen_event_ids: set[str] = set()
        open_dividends: dict[str, tuple[str, float]] = {}
        complete_event_mode = any(
            day.declared_event_ids is not None or day.events or day.dividend_receivable != 0.0 for day in days
        )
        if complete_event_mode and any(day.declared_event_ids is None for day in days):
            raise ValueError("ledger_event_set")
        for day in days:
            expected_cash = (
                previous_cash + day.trade_net_cashflow - day.fees + day.income_cashflow + day.external_cashflow
                + day.option_settlement_cashflow
            )
            if not math.isclose(day.cash, expected_cash, rel_tol=0.0, abs_tol=1e-9):
                raise ValueError("ledger_cash")
            return_basis = previous_nav + day.external_cashflow
            if return_basis <= 0:
                raise ValueError("ledger_return")
            expected_return = day.nav / return_basis - 1.0
            if day.daily_return != expected_return:
                raise ValueError("ledger_return")
            event_ids = {event.event_id for event in day.events}
            if seen_event_ids.intersection(event_ids):
                raise ValueError("ledger_event_duplicate")
            seen_event_ids.update(event_ids)
            if day.declared_event_ids is not None and set(day.declared_event_ids) != event_ids:
                raise ValueError("ledger_event_set")
            phases = {
                "split": 0, "dividend_accrual": 1, "dividend_payment": 2,
                "option_trade": 3, "option_settlement": 4, "collateral_change": 5,
            }
            event_phases = [phases[event.event_type] for event in day.events]
            if event_phases != sorted(event_phases):
                raise ValueError("ledger_event_order")
            if any(event.event_type == "split" for event in day.events) and (
                day.trade_net_cashflow != 0.0 or day.fees != 0.0
            ):
                raise ValueError("ledger_split_trade")
            quantities = dict(previous_quantities)
            split_symbols: set[str] = set()
            for event in day.events:
                if event.event_type == "split":
                    old_quantity = quantities.get(event.symbol, 0.0)
                    if old_quantity <= 0:
                        raise ValueError("ledger_split_quantity")
                    if event.symbol in split_symbols:
                        raise ValueError("ledger_split_quantity")
                    split_symbols.add(event.symbol)
                    quantities[event.symbol] = old_quantity * event.ratio
            if split_symbols:
                current_quantities = {mark.symbol: mark.quantity for mark in day.positions}
                for symbol in set(previous_quantities) | set(current_quantities):
                    expected_quantity = quantities.get(symbol, 0.0)
                    if not math.isclose(
                        current_quantities.get(symbol, 0.0), expected_quantity, rel_tol=0.0, abs_tol=1e-9
                    ):
                        raise ValueError("ledger_split_quantity")
            expected_receivable = previous_receivable
            payment_total = 0.0
            for event in day.events:
                if event.event_type == "dividend_accrual":
                    quantity = quantities.get(event.symbol, 0.0)
                    if quantity <= 0:
                        raise ValueError("ledger_dividend_quantity")
                    amount = quantity * event.per_share
                    expected_receivable += amount
                    open_dividends[event.event_id] = (event.symbol, amount)
                elif event.event_type == "dividend_payment":
                    accrued = open_dividends.get(event.reference_event_id)
                    if accrued is None or accrued[0] != event.symbol or not math.isclose(
                        accrued[1], event.amount, rel_tol=0.0, abs_tol=1e-9
                    ):
                        raise ValueError("ledger_dividend_pair")
                    del open_dividends[event.reference_event_id]
                    expected_receivable -= event.amount
                    payment_total += event.amount
            if complete_event_mode and not math.isclose(
                payment_total, day.income_cashflow, rel_tol=0.0, abs_tol=1e-9
            ):
                raise ValueError("ledger_dividend_cashflow")
            if not math.isclose(day.dividend_receivable, expected_receivable, rel_tol=0.0, abs_tol=1e-9):
                raise ValueError("ledger_dividend_receivable")
            previous_cash = day.cash
            previous_nav = day.nav
            previous_receivable = day.dividend_receivable
            previous_quantities = {mark.symbol: mark.quantity for mark in day.positions}
        object.__setattr__(self, "trial_id", trial_id)
        object.__setattr__(self, "domain", domain)
        object.__setattr__(self, "strategy_profile", strategy_profile)
        object.__setattr__(self, "run_id", run_id)
        object.__setattr__(self, "input_id", input_id)
        object.__setattr__(self, "calendar_id", calendar_id)
        object.__setattr__(self, "periods_per_year", periods)
        object.__setattr__(self, "cost_source", cost_source)
        object.__setattr__(self, "cost_inputs", cost_inputs)
        object.__setattr__(self, "initial_session_date", initial_session_date)
        object.__setattr__(self, "initial_nav", initial_nav)
        object.__setattr__(self, "initial_cash", initial_cash)
        object.__setattr__(self, "initial_positions", initial_positions)
        object.__setattr__(self, "days", days)
        object.__setattr__(self, "initial_restricted_cash", initial_restricted_cash)
        _validate_option_ledger(initial_positions, days, initial_cash, initial_restricted_cash)

    @property
    def window_start(self) -> date:
        return self.initial_session_date

    @property
    def window_end(self) -> date:
        return self.days[-1].session_date

    @property
    def observation_count(self) -> int:
        return len(self.days)

    @property
    def events_complete(self) -> bool:
        """Whether every return day declares its complete event-ID set."""
        return all(day.declared_event_ids is not None for day in self.days)

    @property
    def total_return(self) -> float:
        if all(day.external_cashflow == 0.0 for day in self.days):
            return self.days[-1].nav / self.initial_nav - 1.0
        return math.prod(1.0 + day.daily_return for day in self.days) - 1.0

    @property
    def total_fees(self) -> float:
        return float(sum(day.fees for day in self.days))

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "trial_id": self.trial_id,
            "domain": self.domain,
            "strategy_profile": self.strategy_profile,
            "run_id": self.run_id,
            "param_version": self.param_version,
            "input_id": self.input_id,
            "calendar_id": self.calendar_id,
            "periods_per_year": self.periods_per_year,
            "cost_source": self.cost_source,
            "cost_inputs": dict(self.cost_inputs),
            "initial_session_date": self.initial_session_date.isoformat(),
            "initial_nav": self.initial_nav,
            "initial_cash": self.initial_cash,
            "initial_positions": [mark.to_dict() for mark in self.initial_positions],
            "days": [day.to_dict() for day in self.days],
            "synthetic": self.synthetic,
        }
        if self.initial_restricted_cash != 0.0:
            payload["initial_restricted_cash"] = self.initial_restricted_cash
        return payload


