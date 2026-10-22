"""Classify US equity intraday sessions in America/New_York.

This module only checks time of day. It does not determine trading days,
holidays, or early closes (half days). Callers must continue using their
existing exchange calendar to confirm whether the day is tradable and combine
that result, including any early close, with the session policy before allowing
execution. A session match alone never establishes weekend or holiday trading
eligibility.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, time
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
