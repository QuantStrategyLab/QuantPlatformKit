"""Calendar-aware multi-market session policy (US 23x5, HK equities, CME futures, crypto)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from enum import Enum
from zoneinfo import ZoneInfo

from quant_platform_kit.common.us_equity_sessions import (
    US_EQUITY_TIMEZONE,
    Session,
    resolve_us_equity_23x5_session,
)

HK_EQUITY_TIMEZONE = "Asia/Hong_Kong"
CME_FUTURES_TIMEZONE = "America/New_York"


class MarketProfileId(str, Enum):
    """Supported market session policy profiles."""

    US_EQUITY_23X5 = "us_equity_23x5"
    HK_EQUITY = "hk_equity"
    CME_FUTURES_23X5 = "cme_futures_23x5"
    CRYPTO_24X7 = "crypto_24x7"


class MarketPhase(str, Enum):
    """Normalized execution phases across asset classes and exchanges."""

    OVERNIGHT = "overnight"
    PRE_MARKET = "pre_market"
    PRE_OPEN_AUCTION = "pre_open_auction"
    PRE_OPEN_BLOCKING = "pre_open_blocking"
    REGULAR = "regular"
    MORNING_CONTINUOUS = "morning_continuous"
    LUNCH_BREAK = "lunch_break"
    AFTERNOON_CONTINUOUS = "afternoon_continuous"
    CLOSING_AUCTION = "closing_auction"
    POST_MARKET = "post_market"
    MAINTENANCE_HALT = "maintenance_halt"
    CLOSED = "closed"


@dataclass(frozen=True)
class MarketSessionDecision:
    """Resolved execution gate decision for a market at an instant."""

    profile: MarketProfileId
    phase: MarketPhase
    is_open: bool
    effective_trade_date: date | None
    allow_market_orders: bool
    require_limit_orders: bool
    allow_cancel_only: bool
    timezone: str
    reason: str | None = None


def _evaluate_us_equity_23x5(
    now: datetime,
    is_trading_day: Callable[[date], bool],
    early_close_by_date: Callable[[date], time | None] | None,
) -> MarketSessionDecision:
    res = resolve_us_equity_23x5_session(
        now,
        is_trading_day=is_trading_day,
        enabled_sessions=frozenset(Session),
        early_close_by_date=early_close_by_date,
    )
    if res.reason == "daily_maintenance_pause":
        return MarketSessionDecision(
            profile=MarketProfileId.US_EQUITY_23X5,
            phase=MarketPhase.MAINTENANCE_HALT,
            is_open=False,
            effective_trade_date=None,
            allow_market_orders=False,
            require_limit_orders=False,
            allow_cancel_only=False,
            timezone=US_EQUITY_TIMEZONE,
            reason=res.reason,
        )
    phase_map = {
        Session.OVERNIGHT: MarketPhase.OVERNIGHT,
        Session.PRE_MARKET: MarketPhase.PRE_MARKET,
        Session.REGULAR: MarketPhase.REGULAR,
        Session.POST_MARKET: MarketPhase.POST_MARKET,
        Session.CLOSED: MarketPhase.CLOSED,
    }
    phase = phase_map[res.session]
    return MarketSessionDecision(
        profile=MarketProfileId.US_EQUITY_23X5,
        phase=phase,
        is_open=phase != MarketPhase.CLOSED,
        effective_trade_date=res.effective_trade_date,
        allow_market_orders=res.allow_market_orders,
        require_limit_orders=res.require_limit_orders,
        allow_cancel_only=False,
        timezone=US_EQUITY_TIMEZONE,
        reason=res.reason,
    )


def _evaluate_hk_equity(
    now: datetime,
    is_trading_day: Callable[[date], bool],
    early_close_by_date: Callable[[date], time | None] | None,
) -> MarketSessionDecision:
    local_dt = now.astimezone(ZoneInfo(HK_EQUITY_TIMEZONE))
    local_date = local_dt.date()
    local_time = local_dt.time()

    def make_decision(
        phase: MarketPhase,
        *,
        is_open: bool,
        trade_date: date | None,
        allow_market: bool = False,
        require_limit: bool = False,
        allow_cancel_only: bool = False,
        reason: str | None = None,
    ) -> MarketSessionDecision:
        return MarketSessionDecision(
            profile=MarketProfileId.HK_EQUITY,
            phase=phase,
            is_open=is_open,
            effective_trade_date=trade_date,
            allow_market_orders=allow_market,
            require_limit_orders=require_limit,
            allow_cancel_only=allow_cancel_only,
            timezone=HK_EQUITY_TIMEZONE,
            reason=reason,
        )

    if local_date.weekday() >= 5:
        return make_decision(MarketPhase.CLOSED, is_open=False, trade_date=None, reason="weekend_closed")
    if not is_trading_day(local_date):
        return make_decision(MarketPhase.CLOSED, is_open=False, trade_date=None, reason="holiday_closed")

    if local_time < time(9, 0):
        return make_decision(MarketPhase.CLOSED, is_open=False, trade_date=None, reason="outside_hours")
    if local_time < time(9, 20):
        return make_decision(
            MarketPhase.PRE_OPEN_AUCTION,
            is_open=True,
            trade_date=local_date,
            allow_market=False,
            require_limit=True,
        )
    if local_time < time(9, 30):
        return make_decision(
            MarketPhase.PRE_OPEN_BLOCKING,
            is_open=False,
            trade_date=local_date,
            allow_market=False,
            require_limit=False,
            allow_cancel_only=False,
            reason="hkex_pre_open_blocking",
        )
    if local_time < time(12, 0):
        return make_decision(
            MarketPhase.MORNING_CONTINUOUS,
            is_open=True,
            trade_date=local_date,
            allow_market=False,
            require_limit=True,
        )

    early_close = early_close_by_date(local_date) if early_close_by_date is not None else None
    if early_close == time(12, 0):
        if local_time < time(12, 10):
            return make_decision(
                MarketPhase.CLOSING_AUCTION,
                is_open=True,
                trade_date=local_date,
                allow_market=False,
                require_limit=True,
            )
        return make_decision(
            MarketPhase.CLOSED,
            is_open=False,
            trade_date=None,
            reason="early_close_ended",
        )

    if local_time < time(13, 0):
        return make_decision(
            MarketPhase.LUNCH_BREAK,
            is_open=False,
            trade_date=local_date,
            allow_cancel_only=(local_time >= time(12, 30)),
            reason="hkex_lunch_break",
        )
    if local_time < time(16, 0):
        return make_decision(
            MarketPhase.AFTERNOON_CONTINUOUS,
            is_open=True,
            trade_date=local_date,
            allow_market=False,
            require_limit=True,
        )
    if local_time < time(16, 10):
        return make_decision(
            MarketPhase.CLOSING_AUCTION,
            is_open=True,
            trade_date=local_date,
            allow_market=False,
            require_limit=True,
        )
    return make_decision(MarketPhase.CLOSED, is_open=False, trade_date=None, reason="outside_hours")


def _evaluate_cme_futures_23x5(
    now: datetime,
    is_trading_day: Callable[[date], bool],
    early_close_by_date: Callable[[date], time | None] | None = None,
) -> MarketSessionDecision:
    local_dt = now.astimezone(ZoneInfo(CME_FUTURES_TIMEZONE))
    local_date = local_dt.date()
    local_time = local_dt.time()
    weekday = local_date.weekday()

    def make_decision(
        phase: MarketPhase,
        *,
        is_open: bool,
        trade_date: date | None,
        allow_market: bool = False,
        require_limit: bool = False,
        reason: str | None = None,
    ) -> MarketSessionDecision:
        return MarketSessionDecision(
            profile=MarketProfileId.CME_FUTURES_23X5,
            phase=phase,
            is_open=is_open,
            effective_trade_date=trade_date,
            allow_market_orders=allow_market,
            require_limit_orders=require_limit,
            allow_cancel_only=False,
            timezone=CME_FUTURES_TIMEZONE,
            reason=reason,
        )

    if weekday == 5:
        return make_decision(MarketPhase.CLOSED, is_open=False, trade_date=None, reason="weekend_closed")
    if weekday == 4 and local_time >= time(17, 0):
        return make_decision(MarketPhase.CLOSED, is_open=False, trade_date=None, reason="weekend_closed")
    if weekday == 6 and local_time < time(18, 0):
        return make_decision(MarketPhase.CLOSED, is_open=False, trade_date=None, reason="weekend_closed")

    if weekday in {0, 1, 2, 3} and time(17, 0) <= local_time < time(18, 0):
        return make_decision(
            MarketPhase.MAINTENANCE_HALT,
            is_open=False,
            trade_date=None,
            reason="cme_daily_maintenance",
        )

    if (weekday == 6 or weekday in {0, 1, 2, 3}) and local_time >= time(18, 0):
        next_day = local_date + timedelta(days=1)
        if not is_trading_day(next_day):
            return make_decision(
                MarketPhase.CLOSED,
                is_open=False,
                trade_date=None,
                reason="next_day_holiday_closed",
            )
        return make_decision(
            MarketPhase.OVERNIGHT,
            is_open=True,
            trade_date=next_day,
            allow_market=False,
            require_limit=True,
        )

    if not is_trading_day(local_date):
        return make_decision(MarketPhase.CLOSED, is_open=False, trade_date=None, reason="holiday_closed")

    early_close = early_close_by_date(local_date) if early_close_by_date is not None else None
    if early_close is not None:
        if early_close > time(17, 0):
            raise ValueError("early_close cannot exceed 17:00 on CME 23x5")
        if local_time >= early_close:
            return make_decision(
                MarketPhase.CLOSED,
                is_open=False,
                trade_date=None,
                reason="early_close_ended",
            )

    if time(9, 30) <= local_time < time(16, 15):
        return make_decision(
            MarketPhase.REGULAR,
            is_open=True,
            trade_date=local_date,
            allow_market=True,
            require_limit=False,
        )
    return make_decision(
        MarketPhase.OVERNIGHT,
        is_open=True,
        trade_date=local_date,
        allow_market=False,
        require_limit=True,
    )


def evaluate_market_session(
    profile: MarketProfileId,
    now: datetime,
    *,
    is_trading_day: Callable[[date], bool] | None = None,
    early_close_by_date: Callable[[date], time | None] | None = None,
) -> MarketSessionDecision:
    """Evaluate normalized session phase, effective trade date, and order rules."""
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be a timezone-aware datetime")

    if profile == MarketProfileId.CRYPTO_24X7:
        return MarketSessionDecision(
            profile=MarketProfileId.CRYPTO_24X7,
            phase=MarketPhase.REGULAR,
            is_open=True,
            effective_trade_date=now.astimezone(timezone.utc).date(),
            allow_market_orders=True,
            require_limit_orders=False,
            allow_cancel_only=False,
            timezone="UTC",
            reason=None,
        )
    if is_trading_day is None:
        raise ValueError(f"is_trading_day calendar is required for {profile.value}")
    if profile == MarketProfileId.US_EQUITY_23X5:
        return _evaluate_us_equity_23x5(now, is_trading_day, early_close_by_date)
    if profile == MarketProfileId.HK_EQUITY:
        return _evaluate_hk_equity(now, is_trading_day, early_close_by_date)
    if profile == MarketProfileId.CME_FUTURES_23X5:
        return _evaluate_cme_futures_23x5(now, is_trading_day, early_close_by_date)
    raise ValueError(f"Unsupported market profile: {profile!r}")
