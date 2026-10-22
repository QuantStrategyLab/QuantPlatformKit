from __future__ import annotations

import unittest
from dataclasses import FrozenInstanceError
from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo

from quant_platform_kit import common
from quant_platform_kit.common.us_equity_sessions import (
    DEFAULT_US_EQUITY_SESSION_WINDOWS,
    US_EQUITY_TIMEZONE,
    Session,
    SessionWindow,
    classify_session,
    session_enabled,
    session_gate,
)


ET = ZoneInfo("America/New_York")


class USEquitySessionsTests(unittest.TestCase):
    def test_half_open_boundaries(self) -> None:
        cases = (
            (time(20, 59, 59), Session.CLOSED),
            (time(21), Session.OVERNIGHT),
            (time(23, 59), Session.OVERNIGHT),
            (time(0), Session.OVERNIGHT),
            (time(3, 59), Session.OVERNIGHT),
            (time(4), Session.PRE_MARKET),
            (time(9, 29), Session.PRE_MARKET),
            (time(9, 30), Session.REGULAR),
            (time(15, 59), Session.REGULAR),
            (time(16), Session.POST_MARKET),
            (time(19, 59), Session.POST_MARKET),
            (time(20), Session.CLOSED),
            (time(9, 29, 59, 999999), Session.PRE_MARKET),
            (time(15, 59, 59, 999999), Session.REGULAR),
        )
        for clock, expected in cases:
            with self.subTest(clock=clock):
                now = datetime.combine(datetime(2026, 10, 22).date(), clock, ET)
                self.assertEqual(classify_session(now), expected)

    def test_dst_dates_keep_et_boundaries(self) -> None:
        for month, day in ((3, 8), (11, 1)):
            for hour, minute, expected in (
                (21, 0, Session.OVERNIGHT),
                (4, 0, Session.PRE_MARKET),
                (9, 30, Session.REGULAR),
                (16, 0, Session.POST_MARKET),
            ):
                with self.subTest(month=month, day=day, hour=hour, minute=minute):
                    now = datetime(2026, month, day, hour, minute, tzinfo=ET)
                    self.assertEqual(classify_session(now), expected)
                    self.assertEqual(classify_session(now.astimezone(timezone.utc)), expected)

    def test_repeated_dst_hour_is_overnight(self) -> None:
        for fold in (0, 1):
            with self.subTest(fold=fold):
                now = datetime(2026, 11, 1, 1, 30, tzinfo=ET, fold=fold)
                self.assertEqual(classify_session(now), Session.OVERNIGHT)

    def test_naive_datetime_is_rejected(self) -> None:
        for function in (classify_session, session_gate):
            with self.subTest(function=function.__name__):
                with self.assertRaises(ValueError):
                    function(datetime(2026, 10, 22, 9, 30))

    def test_default_enabled_sessions(self) -> None:
        for session in Session:
            with self.subTest(session=session):
                self.assertEqual(session_enabled(session), session == Session.REGULAR)

    def test_custom_enabled_sessions_and_closed(self) -> None:
        enabled = frozenset({Session.OVERNIGHT, Session.PRE_MARKET, Session.CLOSED})
        for session in Session:
            with self.subTest(session=session):
                self.assertEqual(
                    session_enabled(session, enabled),
                    session in {Session.OVERNIGHT, Session.PRE_MARKET},
                )
                self.assertFalse(session_enabled(session, frozenset()))
        self.assertFalse(session_enabled(Session.CLOSED, frozenset(Session)))

    def test_session_gate_returns_classification_and_permission(self) -> None:
        for hour, minute, expected in (
            (0, 0, Session.OVERNIGHT),
            (4, 0, Session.PRE_MARKET),
            (9, 30, Session.REGULAR),
            (16, 0, Session.POST_MARKET),
            (20, 0, Session.CLOSED),
        ):
            with self.subTest(session=expected):
                now = datetime(2026, 10, 22, hour, minute, tzinfo=ET)
                self.assertEqual(session_gate(now), (expected, expected == Session.REGULAR))
                self.assertEqual(
                    session_gate(now, frozenset(Session)),
                    (expected, expected != Session.CLOSED),
                )

    def test_custom_windows_and_unmatched_times(self) -> None:
        windows = (SessionWindow(Session.REGULAR, time(10), time(12)),)
        for hour, expected in ((9, Session.CLOSED), (10, Session.REGULAR), (12, Session.CLOSED)):
            with self.subTest(hour=hour):
                now = datetime(2026, 10, 22, hour, tzinfo=ET)
                self.assertEqual(classify_session(now, windows), expected)
                self.assertEqual(classify_session(now, ()), Session.CLOSED)

    def test_default_windows_partition_entire_day_without_overlap(self) -> None:
        intervals = []
        for window in DEFAULT_US_EQUITY_SESSION_WINDOWS:
            start = window.start.hour * 3600 + window.start.minute * 60 + window.start.second
            end = window.end.hour * 3600 + window.end.minute * 60 + window.end.second
            if window.crosses_midnight:
                intervals.extend(((0, end), (start, 24 * 3600)))
            else:
                intervals.append((start, end))
        cursor = 0
        for start, end in sorted(intervals):
            self.assertEqual(start, cursor, "gap or overlap in default windows")
            self.assertGreater(end, start)
            cursor = end
        self.assertEqual(cursor, 24 * 3600)
        self.assertEqual(
            {window.session for window in DEFAULT_US_EQUITY_SESSION_WINDOWS}, set(Session)
        )
        closed = [w for w in DEFAULT_US_EQUITY_SESSION_WINDOWS if w.session == Session.CLOSED]
        self.assertEqual(closed, [SessionWindow(Session.CLOSED, time(20), time(21))])

    def test_window_is_frozen_and_derives_midnight_crossing(self) -> None:
        window = SessionWindow(Session.OVERNIGHT, time(21), time(4))
        self.assertTrue(window.crosses_midnight)
        self.assertFalse(SessionWindow(Session.REGULAR, time(9, 30), time(16)).crosses_midnight)
        with self.assertRaises(FrozenInstanceError):
            window.start = time(22)

    def test_common_exports(self) -> None:
        self.assertEqual(US_EQUITY_TIMEZONE, "America/New_York")
        for name in (
            "US_EQUITY_TIMEZONE",
            "DEFAULT_US_EQUITY_SESSION_WINDOWS",
            "Session",
            "SessionWindow",
            "classify_session",
            "session_enabled",
            "session_gate",
        ):
            with self.subTest(name=name):
                self.assertIn(name, common.__all__)
                self.assertIs(getattr(common, name), globals()[name])
