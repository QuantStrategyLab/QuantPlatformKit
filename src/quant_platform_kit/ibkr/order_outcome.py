"""Read-only, identity-bound IBKR outcome observations; no execution authority."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import logging
from datetime import datetime, timezone
import math
from typing import Any, Callable, Literal


class OrderOutcomeReadError(RuntimeError):
    """A broker read failed; no partial snapshot may be treated as complete."""


@dataclass(frozen=True)
class OutcomeFill:
    execution_id: str
    quantity: float
    price: float


@dataclass(frozen=True)
class OrderOutcome:
    order_id: str
    status: Literal['filled', 'partially_filled', 'cancelled', 'rejected', 'pending', 'unknown']
    filled_qty: float | None = None
    remaining: float | None = None
    avg_price: float | None = None
    commission: float | None = None
    last_update: str | None = None
    terminal: bool = False
    fills: tuple[OutcomeFill, ...] = ()


def _number(value: Any) -> float:
    if isinstance(value, bool):
        raise ValueError('invalid_outcome_number')
    number = float(value)
    if not math.isfinite(number) or abs(number) >= 1e100:
        raise ValueError('invalid_outcome_number')
    return number


def _time(value: Any) -> datetime:
    instant = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise ValueError('aware_outcome_time_required')
    return instant.astimezone(timezone.utc)


class _QuietOutcomeLogger(logging.LoggerAdapter):
    def log(self, level, msg, *args, **kwargs):
        # SDK callback messages can embed complete account-bound executions.
        # The caller receives a fixed read failure instead of raw diagnostics.
        return


@contextmanager
def _quiet_reads(ib):
    originals = []
    failed = False
    def on_error(*args):
        nonlocal failed
        failed = True
    # The SDK can end a failed request with [] when RaiseRequestErrors=False.
    # Observe errors without changing caller configuration or retaining payloads.
    errors = getattr(ib, 'errorEvent', None)
    subscribed = False
    try:
        if errors is not None:
            errors += on_error
            subscribed = True
        for owner in (ib, getattr(ib, 'wrapper', None), getattr(ib, 'client', None)):
            logger = getattr(owner, '_logger', None)
            if logger is not None:
                originals.append((owner, logger))
                owner._logger = _QuietOutcomeLogger(logger, {})
        yield
        if failed:
            raise OrderOutcomeReadError('broker_outcome_read_failed')
    finally:
        if subscribed:
            errors -= on_error
        for owner, logger in reversed(originals):
            owner._logger = logger


def resolve_order_outcome(
    ib: Any, broker_order_id: str, *, account_id: str, client_id: int,
    symbol: str, side: str, quantity: float, submitted_at: datetime | str,
    execution_filter_factory: Callable[..., Any] | None = None,
    permanent_id: int | None = None,
) -> OrderOutcome:
    """Read all three broker sources and require the original order identity.

    API order IDs are client-scoped. Neither an empty open-order list nor an
    Inactive status proves cancellation/rejection. Transport errors raise a
    fixed error; missing, inconsistent or insufficient facts return unknown.
    The caller owns request deadlines on this connection. No submit/cancel API
    is called and no execution journal or risk reservation is changed.
    """
    order_id = str(broker_order_id)
    unknown = OrderOutcome(order_id, 'unknown')
    try:
        qty = _number(quantity)
        since = _time(submitted_at)
        if (not order_id.isdecimal() or int(order_id) <= 0 or not account_id
                or type(client_id) is not int or client_id < 0 or qty <= 0
                or side.lower() not in {'buy', 'sell'} or not symbol
                or (permanent_id is not None
                    and (type(permanent_id) is not int or permanent_id <= 0))):
            return unknown
    except (ValueError, TypeError, OverflowError):
        return unknown
    if execution_filter_factory is None:
        from ib_insync import ExecutionFilter
        execution_filter_factory = ExecutionFilter
    try:
        with _quiet_reads(ib):
            opened = list(ib.reqAllOpenOrders())
            completed = list(ib.reqCompletedOrders(apiOnly=False))
            executions = list(ib.reqExecutions(execution_filter_factory(acctCode=account_id)))
    except Exception:
        raise OrderOutcomeReadError('broker_outcome_read_failed') from None
    try:
        states = []
        state_times = []
        state_ids = []
        execution_ids = []
        identities = set()
        for trade in [*opened, *completed]:
            order = trade.order
            if str(order.orderId) != order_id:
                continue
            if order.account != account_id or order.clientId != client_id:
                continue
            if (trade.contract.symbol != symbol or order.action.upper() != side.upper()
                    or _number(order.totalQuantity) != qty):
                return unknown
            if permanent_id is not None and getattr(order, 'permId', None) != permanent_id:
                return unknown
            observed_id = getattr(order, 'permId', None)
            if observed_id:
                if type(observed_id) is not int or observed_id <= 0:
                    return unknown
                identities.add(observed_id)
            state_ids.append(observed_id)
            state = trade.orderStatus
            filled, remaining = _number(state.filled), _number(state.remaining)
            price = _number(state.avgFillPrice) if filled else None
            if filled == remaining == 0:
                # ib_insync order callbacks can construct an empty OrderStatus.
                # Its zero defaults are not broker fill/remaining observations.
                # Resolve these fields below from explicit filledQuantity and
                # executions, rather than accepting or rejecting those defaults.
                try:
                    explicit = _number(order.filledQuantity)
                    if not 0 <= explicit <= qty:
                        return unknown
                except (AttributeError, ValueError, TypeError):
                    explicit = None
                states.append((str(state.status), explicit, None, None))
            else:
                if (filled < 0 or remaining < 0 or not math.isclose(filled + remaining, qty)
                        or (filled > 0 and (price is None or price <= 0))):
                    return unknown
                states.append((str(state.status), filled, remaining, price))
            state_times.append([_time(entry.time) for entry in getattr(trade, 'log', ())
                                if getattr(entry, 'time', None)])
        fills: dict[str, tuple[OutcomeFill, tuple[float, str] | None, datetime]] = {}
        for item in executions:
            execution = item.execution
            if str(execution.orderId) != order_id:
                continue
            # Other client/account records with the same integer order ID are
            # not ours. A matching trade is also required to agree above.
            if execution.acctNumber != account_id or execution.clientId != client_id:
                continue
            if item.contract.symbol != symbol or execution.side.upper() != {'buy': 'BOT', 'sell': 'SLD'}[side.lower()]:
                return unknown
            if permanent_id is not None and getattr(execution, 'permId', None) != permanent_id:
                return unknown
            observed_id = getattr(execution, 'permId', None)
            if observed_id:
                if type(observed_id) is not int or observed_id <= 0:
                    return unknown
                identities.add(observed_id)
            execution_ids.append(observed_id)
            at = _time(execution.time)
            if at.replace(microsecond=0) < since.replace(microsecond=0):
                return unknown
            fill = OutcomeFill(str(execution.execId), _number(execution.shares), _number(execution.price))
            if not fill.execution_id or fill.quantity <= 0 or fill.price <= 0:
                return unknown
            commission = None
            try:
                report = item.commissionReport
                if (report.execId == fill.execution_id and isinstance(report.currency, str)
                        and report.currency.strip()):
                    commission = (_number(report.commission), report.currency)
            except (AttributeError, ValueError, TypeError):
                pass  # The broker can deliver commission later; never assume zero.
            record = (fill, commission, at)
            if fill.execution_id in fills and fills[fill.execution_id] != record:
                return unknown
            fills[fill.execution_id] = record
        if len(identities) > 1:
            return unknown
        observed = sum(row[0].quantity for row in fills.values())
        if observed > qty:
            return unknown
        for index, state in enumerate(states):
            raw, filled, remaining, price = state
            if remaining is not None:
                continue
            if filled is None:
                if not fills:
                    return unknown
                filled = observed
            if filled and not fills:
                return unknown  # No broker price is available on this source.
            price = (sum(row[0].quantity * row[0].price for row in fills.values()) / observed
                     if observed else None)
            states[index] = (raw, filled, qty - filled, price)
        terminal_indices = [index for index, row in enumerate(states)
                            if row[0] in {'Filled', 'Cancelled', 'ApiCancelled', 'Rejected'}]
        terminal_states = [states[index] for index in terminal_indices]
        for index in terminal_indices:
            # A different observation cannot supply freshness for this terminal.
            own_times = state_times[index]
            if own_times and max(own_times) < since:
                return unknown
            if not own_times:
                # A timeless terminal must bind to the caller's stable identity
                # or to every execution supplying its current fill evidence.
                state_id = state_ids[index]
                if (type(state_id) is not int or state_id <= 0
                        or not (state_id == permanent_id or
                                (execution_ids and all(type(value) is int and value == state_id
                                                       for value in execution_ids)))):
                    return unknown
        if terminal_states and len(set(terminal_states)) != 1:
            return unknown
        selected = terminal_states[0] if terminal_states else max(states, key=lambda row: row[1], default=None)
        if selected is None and not fills:
            return unknown
        filled = selected[1] if selected else observed
        remaining = selected[2] if selected else qty - observed
        price = selected[3] if selected else sum(row[0].quantity * row[0].price for row in fills.values()) / observed
        if fills and (not math.isclose(observed, filled) or not math.isclose(
                sum(row[0].quantity * row[0].price for row in fills.values()) / observed, price or 0, rel_tol=1e-6)):
            return unknown
        if selected and any(row[1] > filled for row in states):
            return unknown
        raw_status = selected[0] if selected else ''
        terminal = bool(terminal_states)
        if raw_status == 'Filled' and (filled != qty or remaining != 0):
            return unknown
        if raw_status == 'Rejected' and filled != 0:
            return unknown
        if raw_status in {'Cancelled', 'ApiCancelled'}:
            status = 'cancelled'
        elif raw_status == 'Rejected':
            status = 'rejected'
        elif filled == qty and (raw_status == 'Filled' or observed == qty):
            status, terminal = 'filled', True
        elif filled > 0 and (not selected or raw_status in {'Submitted', 'PreSubmitted', 'PartiallyFilled', 'Partial'}):
            status = 'partially_filled'
        elif selected and raw_status in {'Submitted', 'PreSubmitted', 'PendingSubmit', 'ApiPending', 'PendingCancel'}:
            status = 'pending'
        else:
            return unknown
        times = list(state_times[states.index(selected)]) if selected else []
        times.extend(row[2] for row in fills.values())
        if times and max(times).replace(microsecond=0) < since.replace(microsecond=0):
            return unknown
        if terminal and not times and permanent_id is None:
            return unknown  # An old reused integer ID cannot prove this order.
        fees = [row[1] for row in fills.values()]
        commission = (sum(fee[0] for fee in fees)
                      if fees and all(fee is not None for fee in fees)
                      and len({fee[1] for fee in fees}) == 1 else None)
        return OrderOutcome(order_id, status, filled, remaining, price, commission,
                            max(times).isoformat() if times else None, terminal,
                            tuple(row[0] for _, row in sorted(fills.items())))
    except (AttributeError, ValueError, TypeError, OverflowError, ZeroDivisionError):
        return unknown
