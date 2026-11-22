"""Unit tests for shared exchange market-open helpers."""

from __future__ import annotations

from datetime import datetime, timezone

from quant_platform_kit.markets import is_market_open_now, is_market_open_today


class _FakeSchedule:
    def __init__(self, empty: bool) -> None:
        self.empty = empty


class _FakeCalendar:
    def __init__(self, *, empty: bool = False, open_result=True, error: Exception | None = None) -> None:
        self._empty = empty
        self._open_result = open_result
        self._error = error
        self.seen_dates = []

    def schedule(self, *, start_date, end_date):
        self.seen_dates.append((start_date, end_date))
        return _FakeSchedule(self._empty)

    def open_at_time(self, schedule, dt):
        if self._error is not None:
            raise self._error
        return self._open_result


def test_is_market_open_now_returns_open_status():
    cal = _FakeCalendar(empty=False, open_result=True)
    is_open, err = is_market_open_now(
        calendar_name="NASDAQ",
        calendar_factory=lambda _name: cal,
        now=datetime(2026, 11, 20, 15, 0, tzinfo=timezone.utc),
    )
    assert is_open is True
    assert err is None


def test_is_market_open_now_handles_empty_schedule():
    cal = _FakeCalendar(empty=True)
    is_open, err = is_market_open_now(
        calendar_factory=lambda _name: cal,
        now=datetime(2026, 11, 22, 15, 0, tzinfo=timezone.utc),
    )
    assert is_open is False
    assert err is None


def test_is_market_open_now_treats_not_covered_by_schedule_as_closed():
    cal = _FakeCalendar(
        empty=False,
        error=ValueError("timestamp is not covered by the schedule"),
    )
    is_open, err = is_market_open_now(
        calendar_factory=lambda _name: cal,
        now=datetime(2026, 11, 20, 23, 0, tzinfo=timezone.utc),
    )
    assert is_open is False
    assert err is None


def test_is_market_open_now_returns_unexpected_errors():
    cal = _FakeCalendar(empty=False, error=RuntimeError("calendar failure"))
    is_open, err = is_market_open_now(
        calendar_factory=lambda _name: cal,
        now=datetime(2026, 11, 20, 15, 0, tzinfo=timezone.utc),
    )
    assert is_open is False
    assert isinstance(err, RuntimeError)


def test_is_market_open_today():
    assert (
        is_market_open_today(
            calendar_factory=lambda _name: _FakeCalendar(empty=False),
            now=datetime(2026, 11, 20, 15, 0, tzinfo=timezone.utc),
        )
        is True
    )
    assert (
        is_market_open_today(
            calendar_factory=lambda _name: _FakeCalendar(empty=True),
            now=datetime(2026, 11, 22, 15, 0, tzinfo=timezone.utc),
        )
        is False
    )
