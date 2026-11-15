"""Classify US equity intraday sessions in America/New_York.

This module only checks time of day. It does not determine trading days,
holidays, or early closes (half days). Callers must continue using their
existing exchange calendar to confirm whether the day is tradable and combine
that result, including any early close, with the session policy before allowing
execution. A session match alone never establishes weekend or holiday trading
eligibility.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from enum import Enum
from zoneinfo import ZoneInfo


US_EQUITY_TIMEZONE = "America/New_York"


class Session(str, Enum):
    """US equity time-of-day classifications, independent of the trading date."""

    OVERNIGHT = "overnight"
    PRE_MARKET = "pre_market"
    REGULAR = "regular"
    POST_MARKET = "post_market"
    CLOSED = "closed"


@dataclass(frozen=True)
class SessionWindow:
    """An immutable half-open [start, end) window in New York local time."""

    session: Session
    start: time
    end: time

    @property
    def crosses_midnight(self) -> bool:
        """Whether the window continues into the following local day."""
        return self.start > self.end


DEFAULT_US_EQUITY_SESSION_WINDOWS = (
    SessionWindow(Session.OVERNIGHT, time(21), time(4)),
    SessionWindow(Session.PRE_MARKET, time(4), time(9, 30)),
    SessionWindow(Session.REGULAR, time(9, 30), time(16)),
    SessionWindow(Session.POST_MARKET, time(16), time(20)),
    SessionWindow(Session.CLOSED, time(20), time(21)),
)


def classify_session(
    now: datetime,
    windows: Sequence[SessionWindow] = DEFAULT_US_EQUITY_SESSION_WINDOWS,
) -> Session:
    """Classify an aware instant by ET time of day using half-open windows.

    Raises ValueError for naive datetimes. Unmatched times are CLOSED. This
    function does not check trading days, holidays, or early closes; callers
    must separately consult their existing exchange calendar.
    """
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be a timezone-aware datetime")
    local_time = now.astimezone(ZoneInfo(US_EQUITY_TIMEZONE)).time()
    for window in windows:
        if window.crosses_midnight:
            matches = local_time >= window.start or local_time < window.end
        else:
            matches = window.start <= local_time < window.end
        if matches:
            return window.session
    return Session.CLOSED


def session_enabled(
    session: Session,
    enabled_sessions: frozenset[Session] = frozenset({Session.REGULAR}),
) -> bool:
    """Check the intraday policy only; CLOSED is never enabled.

    Only REGULAR is enabled by default. Calendar eligibility must be checked
    separately before execution.
    """
    return session != Session.CLOSED and session in enabled_sessions


def session_gate(
    now: datetime,
    enabled_sessions: frozenset[Session] = frozenset({Session.REGULAR}),
) -> tuple[Session, bool]:
    """Return the actual session and its intraday policy permission.

    The boolean is not trading-day approval: callers must combine it with
    their existing exchange calendar's trading-day, holiday, and early-close
    checks before allowing execution. Naive datetimes raise ValueError.
    """
    session = classify_session(now)
    return session, session_enabled(session, enabled_sessions)


@dataclass(frozen=True)
class US23x5SessionResolution:
    """Calendar-aware US equity 23x5 session state and order constraints."""

    session: Session
    is_tradable: bool
    effective_trade_date: date | None
    allow_market_orders: bool
    require_limit_orders: bool
    reason: str | None = None


def resolve_us_equity_23x5_session(
    now: datetime,
    *,
    is_trading_day: Callable[[date], bool],
    enabled_sessions: frozenset[Session] = frozenset({Session.REGULAR}),
    early_close_by_date: Callable[[date], time | None] | None = None,
) -> US23x5SessionResolution:
    """Resolve US equity 23x5 session (Sun 21:00 ET - Fri 20:00 ET) with trade date mapping.

    Overnight [21:00, 24:00) ET belongs to the next trading day's effective trade date.
    Extended/overnight sessions require limit orders and forbid market orders.
    """
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be a timezone-aware datetime")

    local_dt = now.astimezone(ZoneInfo(US_EQUITY_TIMEZONE))
    local_date = local_dt.date()
    local_time = local_dt.time()
    weekday = local_date.weekday()  # 0=Mon .. 4=Fri, 5=Sat, 6=Sun

    def closed(reason: str) -> US23x5SessionResolution:
        return US23x5SessionResolution(
            session=Session.CLOSED,
            is_tradable=False,
            effective_trade_date=None,
            allow_market_orders=False,
            require_limit_orders=False,
            reason=reason,
        )

    if weekday == 5:
        return closed("weekend_closed")
    if weekday == 4 and local_time >= time(20, 0):
        return closed("weekend_closed")

    if weekday == 6:
        if local_time < time(21, 0):
            return closed("weekend_closed")
        next_day = local_date + timedelta(days=1)
        if not is_trading_day(next_day):
            return closed("next_day_holiday_closed")
        return US23x5SessionResolution(
            session=Session.OVERNIGHT,
            is_tradable=session_enabled(Session.OVERNIGHT, enabled_sessions),
            effective_trade_date=next_day,
            allow_market_orders=False,
            require_limit_orders=True,
            reason=None,
        )

    if weekday in {0, 1, 2, 3} and time(20, 0) <= local_time < time(21, 0):
        return closed("daily_maintenance_pause")

    if weekday in {0, 1, 2, 3} and local_time >= time(21, 0):
        next_day = local_date + timedelta(days=1)
        if not is_trading_day(next_day):
            return closed("next_day_holiday_closed")
        return US23x5SessionResolution(
            session=Session.OVERNIGHT,
            is_tradable=session_enabled(Session.OVERNIGHT, enabled_sessions),
            effective_trade_date=next_day,
            allow_market_orders=False,
            require_limit_orders=True,
            reason=None,
        )

    if not is_trading_day(local_date):
        return closed("holiday_closed")

    early_close = early_close_by_date(local_date) if early_close_by_date is not None else None
    if local_time < time(4, 0):
        session = Session.OVERNIGHT
    elif local_time < time(9, 30):
        session = Session.PRE_MARKET
    else:
        close_time = early_close or time(16, 0)
        post_end = time(17, 0) if early_close == time(13, 0) else time(20, 0)
        if local_time < close_time:
            session = Session.REGULAR
        elif local_time < post_end:
            session = Session.POST_MARKET
        else:
            return closed("early_close_ended")

    is_regular = session == Session.REGULAR
    return US23x5SessionResolution(
        session=session,
        is_tradable=session_enabled(session, enabled_sessions),
        effective_trade_date=local_date,
        allow_market_orders=is_regular,
        require_limit_orders=not is_regular,
        reason=None,
    )
