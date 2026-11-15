"""Unit tests for US Dec 2026 23x5, HK equities, and CME futures session/instrument contracts."""

from __future__ import annotations

import unittest
from datetime import date, datetime, time, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from quant_platform_kit.common.exchange_full_day_closures_2026 import (
    XHKG_FULL_DAY_CLOSURES_2026,
    XNYS_FULL_DAY_CLOSURES_2026,
)
from quant_platform_kit.common.us_equity_sessions import (
    Session,
    resolve_us_equity_23x5_session,
)
from quant_platform_kit.markets import (
    AssetClass,
    InstrumentSpec,
    MarginMode,
    MarketPhase,
    MarketProfileId,
    evaluate_market_session,
)

ET = ZoneInfo("America/New_York")
HKT = ZoneInfo("Asia/Hong_Kong")
ALL_US_SESSIONS = frozenset(Session)


def us_calendar(holidays: set[date] | None = None):
    closed = holidays or set()

    def _is_trading_day(day: date) -> bool:
        return day.weekday() < 5 and day not in closed

    return _is_trading_day


class USEquity23x5Tests(unittest.TestCase):
    def test_sunday_open_and_friday_close_boundaries(self) -> None:
        cal = us_calendar()
        # Sunday Dec 6, 2026 20:59 ET -> weekend closed; 21:00 ET -> Monday effective date
        before_open = resolve_us_equity_23x5_session(
            datetime(2026, 12, 6, 20, 59, tzinfo=ET),
            is_trading_day=cal,
            enabled_sessions=ALL_US_SESSIONS,
        )
        self.assertEqual(before_open.session, Session.CLOSED)
        self.assertFalse(before_open.is_tradable)
        self.assertEqual(before_open.reason, "weekend_closed")

        at_open = resolve_us_equity_23x5_session(
            datetime(2026, 12, 6, 21, 0, tzinfo=ET),
            is_trading_day=cal,
            enabled_sessions=ALL_US_SESSIONS,
        )
        self.assertEqual(at_open.session, Session.OVERNIGHT)
        self.assertTrue(at_open.is_tradable)
        self.assertEqual(at_open.effective_trade_date, date(2026, 12, 7))
        self.assertFalse(at_open.allow_market_orders)
        self.assertTrue(at_open.require_limit_orders)

        # Friday Dec 11, 2026 19:59 ET -> post-market; >= 20:00 ET -> weekend closed
        fri_post = resolve_us_equity_23x5_session(
            datetime(2026, 12, 11, 19, 59, tzinfo=ET),
            is_trading_day=cal,
            enabled_sessions=ALL_US_SESSIONS,
        )
        self.assertEqual(fri_post.session, Session.POST_MARKET)
        self.assertEqual(fri_post.effective_trade_date, date(2026, 12, 11))

        for hour, minute in ((20, 0), (21, 30)):
            with self.subTest(hour=hour, minute=minute):
                fri_closed = resolve_us_equity_23x5_session(
                    datetime(2026, 12, 11, hour, minute, tzinfo=ET),
                    is_trading_day=cal,
                    enabled_sessions=ALL_US_SESSIONS,
                )
                self.assertEqual(fri_closed.session, Session.CLOSED)
                self.assertFalse(fri_closed.is_tradable)
                self.assertEqual(fri_closed.reason, "weekend_closed")

        sat_closed = resolve_us_equity_23x5_session(
            datetime(2026, 12, 12, 10, 0, tzinfo=ET),
            is_trading_day=cal,
            enabled_sessions=ALL_US_SESSIONS,
        )
        self.assertEqual(sat_closed.session, Session.CLOSED)
        self.assertEqual(sat_closed.reason, "weekend_closed")

    def test_cross_midnight_t_plus_1_and_daily_pause(self) -> None:
        cal = us_calendar()
        mon_early = resolve_us_equity_23x5_session(
            datetime(2026, 12, 7, 2, 0, tzinfo=ET),
            is_trading_day=cal,
            enabled_sessions=ALL_US_SESSIONS,
        )
        self.assertEqual(mon_early.session, Session.OVERNIGHT)
        self.assertEqual(mon_early.effective_trade_date, date(2026, 12, 7))
        self.assertFalse(mon_early.allow_market_orders)
        self.assertTrue(mon_early.require_limit_orders)

        mon_pause = evaluate_market_session(
            MarketProfileId.US_EQUITY_23X5,
            datetime(2026, 12, 7, 20, 30, tzinfo=ET),
            is_trading_day=cal,
        )
        self.assertEqual(mon_pause.phase, MarketPhase.MAINTENANCE_HALT)
        self.assertFalse(mon_pause.is_open)
        self.assertEqual(mon_pause.reason, "daily_maintenance_pause")

        tue_night = resolve_us_equity_23x5_session(
            datetime(2026, 12, 8, 21, 30, tzinfo=ET),
            is_trading_day=cal,
            enabled_sessions=ALL_US_SESSIONS,
        )
        self.assertEqual(tue_night.session, Session.OVERNIGHT)
        self.assertEqual(tue_night.effective_trade_date, date(2026, 12, 9))

        # Default enabled_sessions keeps overnight policy disabled unless explicitly opted in
        default_policy = resolve_us_equity_23x5_session(
            datetime(2026, 12, 8, 21, 30, tzinfo=ET),
            is_trading_day=cal,
        )
        self.assertEqual(default_policy.session, Session.OVERNIGHT)
        self.assertFalse(default_policy.is_tradable)

    def test_holidays_and_early_close_and_dst_transitions(self) -> None:
        holidays = {
            date(2026, 9, 7),   # Labor Day Monday
            date(2026, 4, 3),   # Good Friday
        }
        cal = us_calendar(holidays)

        # Sunday night before Monday holiday is closed
        sun_holiday_eve = resolve_us_equity_23x5_session(
            datetime(2026, 9, 6, 21, 30, tzinfo=ET),
            is_trading_day=cal,
            enabled_sessions=ALL_US_SESSIONS,
        )
        self.assertEqual(sun_holiday_eve.session, Session.CLOSED)
        self.assertEqual(sun_holiday_eve.reason, "next_day_holiday_closed")

        # Thursday night before Good Friday is closed
        thu_good_fri_eve = resolve_us_equity_23x5_session(
            datetime(2026, 4, 2, 21, 30, tzinfo=ET),
            is_trading_day=cal,
            enabled_sessions=ALL_US_SESSIONS,
        )
        self.assertEqual(thu_good_fri_eve.session, Session.CLOSED)
        self.assertEqual(thu_good_fri_eve.reason, "next_day_holiday_closed")

        # Labor Day daytime is holiday closed
        mon_holiday = resolve_us_equity_23x5_session(
            datetime(2026, 9, 7, 10, 0, tzinfo=ET),
            is_trading_day=cal,
            enabled_sessions=ALL_US_SESSIONS,
        )
        self.assertEqual(mon_holiday.session, Session.CLOSED)
        self.assertEqual(mon_holiday.reason, "holiday_closed")

        # Black Friday half-day (early close 13:00 ET, post-market ends 17:00 ET)
        early_closes = {date(2026, 11, 27): time(13, 0)}
        half_day_post = resolve_us_equity_23x5_session(
            datetime(2026, 11, 27, 13, 30, tzinfo=ET),
            is_trading_day=cal,
            enabled_sessions=ALL_US_SESSIONS,
            early_close_by_date=early_closes.get,
        )
        self.assertEqual(half_day_post.session, Session.POST_MARKET)
        half_day_ended = resolve_us_equity_23x5_session(
            datetime(2026, 11, 27, 17, 0, tzinfo=ET),
            is_trading_day=cal,
            enabled_sessions=ALL_US_SESSIONS,
            early_close_by_date=early_closes.get,
        )
        self.assertEqual(half_day_ended.session, Session.CLOSED)
        self.assertEqual(half_day_ended.reason, "early_close_ended")

        # DST spring-forward (Sun 2026-03-08 21:00 EDT == 2026-03-09T01:00Z) & fall-back (Sun 2026-11-01 21:00 EST == 2026-11-02T02:00Z)
        spring = resolve_us_equity_23x5_session(
            datetime(2026, 3, 9, 1, 0, tzinfo=timezone.utc),
            is_trading_day=cal,
            enabled_sessions=ALL_US_SESSIONS,
        )
        self.assertEqual(spring.session, Session.OVERNIGHT)
        self.assertEqual(spring.effective_trade_date, date(2026, 3, 9))

        fall = resolve_us_equity_23x5_session(
            datetime(2026, 11, 2, 2, 0, tzinfo=timezone.utc),
            is_trading_day=cal,
            enabled_sessions=ALL_US_SESSIONS,
        )
        self.assertEqual(fall.session, Session.OVERNIGHT)
        self.assertEqual(fall.effective_trade_date, date(2026, 11, 2))


class HKEquityAndFuturesTests(unittest.TestCase):
    def test_hk_equity_intraday_phases_and_half_day(self) -> None:
        cal = us_calendar({date(2026, 10, 1)})
        half_days = {date(2026, 12, 24): time(12, 0)}

        pos = evaluate_market_session(
            MarketProfileId.HK_EQUITY,
            datetime(2026, 12, 7, 9, 15, tzinfo=HKT),
            is_trading_day=cal,
        )
        self.assertEqual(pos.phase, MarketPhase.PRE_OPEN_AUCTION)
        self.assertTrue(pos.is_open)
        self.assertFalse(pos.allow_market_orders)
        self.assertTrue(pos.require_limit_orders)

        morning = evaluate_market_session(
            MarketProfileId.HK_EQUITY,
            datetime(2026, 12, 7, 10, 30, tzinfo=HKT),
            is_trading_day=cal,
        )
        self.assertEqual(morning.phase, MarketPhase.MORNING_CONTINUOUS)
        self.assertFalse(morning.allow_market_orders)
        self.assertTrue(morning.require_limit_orders)

        pre_open_blocking = evaluate_market_session(
            MarketProfileId.HK_EQUITY,
            datetime(2026, 12, 7, 9, 25, tzinfo=HKT),
            is_trading_day=cal,
        )
        self.assertEqual(pre_open_blocking.phase, MarketPhase.PRE_OPEN_BLOCKING)
        self.assertFalse(pre_open_blocking.is_open)
        self.assertFalse(pre_open_blocking.allow_market_orders)
        self.assertFalse(pre_open_blocking.require_limit_orders)
        self.assertFalse(pre_open_blocking.allow_cancel_only)
        self.assertEqual(pre_open_blocking.reason, "hkex_pre_open_blocking")

        lunch_early = evaluate_market_session(
            MarketProfileId.HK_EQUITY,
            datetime(2026, 12, 7, 12, 15, tzinfo=HKT),
            is_trading_day=cal,
        )
        self.assertEqual(lunch_early.phase, MarketPhase.LUNCH_BREAK)
        self.assertFalse(lunch_early.is_open)
        self.assertFalse(lunch_early.allow_cancel_only)

        lunch_cancel = evaluate_market_session(
            MarketProfileId.HK_EQUITY,
            datetime(2026, 12, 7, 12, 30, tzinfo=HKT),
            is_trading_day=cal,
        )
        self.assertEqual(lunch_cancel.phase, MarketPhase.LUNCH_BREAK)
        self.assertFalse(lunch_cancel.is_open)
        self.assertTrue(lunch_cancel.allow_cancel_only)

        afternoon = evaluate_market_session(
            MarketProfileId.HK_EQUITY,
            datetime(2026, 12, 7, 14, 0, tzinfo=HKT),
            is_trading_day=cal,
        )
        self.assertEqual(afternoon.phase, MarketPhase.AFTERNOON_CONTINUOUS)
        self.assertTrue(afternoon.is_open)
        self.assertFalse(afternoon.allow_market_orders)
        self.assertTrue(afternoon.require_limit_orders)

        cas_fixing = evaluate_market_session(
            MarketProfileId.HK_EQUITY,
            datetime(2026, 12, 7, 16, 0, 30, tzinfo=HKT),
            is_trading_day=cal,
        )
        self.assertEqual(cas_fixing.phase, MarketPhase.CLOSING_AUCTION)
        self.assertFalse(cas_fixing.is_open)
        self.assertFalse(cas_fixing.allow_market_orders)
        self.assertFalse(cas_fixing.require_limit_orders)
        self.assertFalse(cas_fixing.allow_cancel_only)
        self.assertEqual(cas_fixing.reason, "hkex_closing_reference_price_fixing")

        cas = evaluate_market_session(
            MarketProfileId.HK_EQUITY,
            datetime(2026, 12, 7, 16, 5, tzinfo=HKT),
            is_trading_day=cal,
        )
        self.assertEqual(cas.phase, MarketPhase.CLOSING_AUCTION)
        self.assertTrue(cas.is_open)
        self.assertTrue(cas.require_limit_orders)

        # Half-day Christmas Eve
        xmas_cas_fixing = evaluate_market_session(
            MarketProfileId.HK_EQUITY,
            datetime(2026, 12, 24, 12, 0, 30, tzinfo=HKT),
            is_trading_day=cal,
            early_close_by_date=half_days.get,
        )
        self.assertEqual(xmas_cas_fixing.phase, MarketPhase.CLOSING_AUCTION)
        self.assertFalse(xmas_cas_fixing.is_open)
        self.assertFalse(xmas_cas_fixing.allow_market_orders)
        self.assertFalse(xmas_cas_fixing.require_limit_orders)
        self.assertFalse(xmas_cas_fixing.allow_cancel_only)
        self.assertEqual(xmas_cas_fixing.reason, "hkex_closing_reference_price_fixing")

        xmas_cas = evaluate_market_session(
            MarketProfileId.HK_EQUITY,
            datetime(2026, 12, 24, 12, 5, tzinfo=HKT),
            is_trading_day=cal,
            early_close_by_date=half_days.get,
        )
        self.assertEqual(xmas_cas.phase, MarketPhase.CLOSING_AUCTION)
        self.assertTrue(xmas_cas.is_open)
        self.assertTrue(xmas_cas.require_limit_orders)
        xmas_closed = evaluate_market_session(
            MarketProfileId.HK_EQUITY,
            datetime(2026, 12, 24, 13, 30, tzinfo=HKT),
            is_trading_day=cal,
            early_close_by_date=half_days.get,
        )
        self.assertEqual(xmas_closed.phase, MarketPhase.CLOSED)

    def test_cme_futures_23x5_sessions(self) -> None:
        cal = us_calendar({date(2026, 12, 25)})

        sun_open = evaluate_market_session(
            MarketProfileId.CME_FUTURES_23X5,
            datetime(2026, 12, 6, 18, 0, tzinfo=ET),
            is_trading_day=cal,
        )
        self.assertEqual(sun_open.phase, MarketPhase.OVERNIGHT)
        self.assertTrue(sun_open.is_open)
        self.assertEqual(sun_open.effective_trade_date, date(2026, 12, 7))
        self.assertTrue(sun_open.require_limit_orders)

        wed_halt = evaluate_market_session(
            MarketProfileId.CME_FUTURES_23X5,
            datetime(2026, 12, 9, 17, 30, tzinfo=ET),
            is_trading_day=cal,
        )
        self.assertEqual(wed_halt.phase, MarketPhase.MAINTENANCE_HALT)
        self.assertFalse(wed_halt.is_open)

        fri_close = evaluate_market_session(
            MarketProfileId.CME_FUTURES_23X5,
            datetime(2026, 12, 11, 17, 0, tzinfo=ET),
            is_trading_day=cal,
        )
        self.assertEqual(fri_close.phase, MarketPhase.CLOSED)
        self.assertFalse(fri_close.is_open)

        cme_half_days = {date(2026, 11, 27): time(13, 0)}
        cme_before_cutoff = evaluate_market_session(
            MarketProfileId.CME_FUTURES_23X5,
            datetime(2026, 11, 27, 12, 0, tzinfo=ET),
            is_trading_day=cal,
            early_close_by_date=cme_half_days.get,
        )
        self.assertEqual(cme_before_cutoff.phase, MarketPhase.REGULAR)
        self.assertTrue(cme_before_cutoff.is_open)

        for cutoff_hour in (13, 14):
            with self.subTest(cutoff_hour=cutoff_hour):
                cme_after_cutoff = evaluate_market_session(
                    MarketProfileId.CME_FUTURES_23X5,
                    datetime(2026, 11, 27, cutoff_hour, 0, tzinfo=ET),
                    is_trading_day=cal,
                    early_close_by_date=cme_half_days.get,
                )
                self.assertEqual(cme_after_cutoff.phase, MarketPhase.CLOSED)
                self.assertFalse(cme_after_cutoff.is_open)
                self.assertEqual(cme_after_cutoff.reason, "early_close_ended")

    def test_exchange_profiles_require_explicit_calendar_and_block_holidays(self) -> None:
        sample_now = datetime(2026, 12, 25, 10, 0, tzinfo=ET)
        for profile in (
            MarketProfileId.US_EQUITY_23X5,
            MarketProfileId.HK_EQUITY,
            MarketProfileId.CME_FUTURES_23X5,
        ):
            with self.subTest(profile=profile), self.assertRaisesRegex(
                ValueError, "is_trading_day calendar is required"
            ):
                evaluate_market_session(profile, sample_now)

        crypto = evaluate_market_session(MarketProfileId.CRYPTO_24X7, sample_now)
        self.assertTrue(crypto.is_open)

        us_closed = evaluate_market_session(
            MarketProfileId.US_EQUITY_23X5,
            datetime(2026, 12, 25, 10, 0, tzinfo=ET),
            is_trading_day=lambda d: d.weekday() < 5 and d.isoformat() not in XNYS_FULL_DAY_CLOSURES_2026,
        )
        self.assertEqual(us_closed.phase, MarketPhase.CLOSED)
        self.assertFalse(us_closed.is_open)

        hk_closed = evaluate_market_session(
            MarketProfileId.HK_EQUITY,
            datetime(2026, 12, 25, 10, 0, tzinfo=HKT),
            is_trading_day=lambda d: d.weekday() < 5 and d.isoformat() not in XHKG_FULL_DAY_CLOSURES_2026,
        )
        self.assertEqual(hk_closed.phase, MarketPhase.CLOSED)
        self.assertFalse(hk_closed.is_open)

    def test_instrument_spec_hk_board_lots_and_futures_multiplier(self) -> None:
        hk_stock = InstrumentSpec(
            symbol="0700.HK",
            market="HK",
            asset_class=AssetClass.EQUITY,
            currency="HKD",
            lot_size=Decimal("100"),
            tick_size=Decimal("0.20"),
        )
        self.assertEqual(hk_stock.round_quantity_to_lot(350), Decimal("300"))
        self.assertEqual(hk_stock.validate_order_quantity(400), Decimal("400"))
        with self.assertRaisesRegex(ValueError, "multiple of lot_size"):
            hk_stock.validate_order_quantity(150)

        es_future = InstrumentSpec(
            symbol="ESZ6",
            market="CME",
            asset_class=AssetClass.FUTURE,
            currency="USD",
            lot_size=Decimal("1"),
            multiplier=Decimal("50"),
            tick_size=Decimal("0.25"),
            margin_mode=MarginMode.FUTURES_SPAN,
            allow_short=True,
            expiry_date=date(2026, 12, 18),
            roll_days_before_expiry=5,
        )
        self.assertEqual(es_future.notional_value(2, 5000), Decimal("500000"))
        self.assertFalse(es_future.should_roll(date(2026, 12, 10)))
        self.assertTrue(es_future.should_roll(date(2026, 12, 13)))

        with self.assertRaisesRegex(ValueError, "expiry_date is required"):
            InstrumentSpec(
                symbol="NQZ6",
                market="CME",
                asset_class=AssetClass.FUTURE,
                currency="USD",
            )


if __name__ == "__main__":
    unittest.main()
