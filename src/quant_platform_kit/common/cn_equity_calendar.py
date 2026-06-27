from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Iterable, Iterator

CN_EQUITY_TIMEZONE = "Asia/Shanghai"

# Weekday holidays on SSE/SZSE calendars (2024-01-01 .. 2026-12-31), sourced from AkShare trade-date history.
CN_EQUITY_HOLIDAYS: frozenset[str] = frozenset(
    {
        "2024-01-01",
        "2024-02-09",
        "2024-02-12",
        "2024-02-13",
        "2024-02-14",
        "2024-02-15",
        "2024-02-16",
        "2024-04-04",
        "2024-04-05",
        "2024-05-01",
        "2024-05-02",
        "2024-05-03",
        "2024-06-10",
        "2024-09-16",
        "2024-09-17",
        "2024-10-01",
        "2024-10-02",
        "2024-10-03",
        "2024-10-04",
        "2024-10-07",
        "2025-01-01",
        "2025-01-28",
        "2025-01-29",
        "2025-01-30",
        "2025-01-31",
        "2025-02-03",
        "2025-02-04",
        "2025-04-04",
        "2025-05-01",
        "2025-05-02",
        "2025-05-05",
        "2025-06-02",
        "2025-10-01",
        "2025-10-02",
        "2025-10-03",
        "2025-10-06",
        "2025-10-07",
        "2025-10-08",
        "2026-01-01",
        "2026-01-02",
        "2026-02-16",
        "2026-02-17",
        "2026-02-18",
        "2026-02-19",
        "2026-02-20",
        "2026-02-23",
        "2026-04-06",
        "2026-05-01",
        "2026-05-04",
        "2026-05-05",
        "2026-06-19",
        "2026-09-25",
        "2026-10-01",
        "2026-10-02",
        "2026-10-05",
        "2026-10-06",
        "2026-10-07",
    }
)


def normalize_cn_equity_date(value: date | datetime | str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text:
        raise ValueError("date value is required")
    return date.fromisoformat(text[:10])


def is_cn_equity_weekday(value: date | datetime | str) -> bool:
    return normalize_cn_equity_date(value).weekday() < 5


def is_cn_equity_holiday(value: date | datetime | str, *, holidays: Iterable[str] | None = None) -> bool:
    normalized = normalize_cn_equity_date(value).isoformat()
    holiday_set = frozenset(holidays) if holidays is not None else CN_EQUITY_HOLIDAYS
    return normalized in holiday_set


def is_cn_equity_trading_day(value: date | datetime | str, *, holidays: Iterable[str] | None = None) -> bool:
    normalized = normalize_cn_equity_date(value)
    return is_cn_equity_weekday(normalized) and not is_cn_equity_holiday(normalized, holidays=holidays)


def next_cn_equity_trading_day(
    value: date | datetime | str,
    *,
    holidays: Iterable[str] | None = None,
) -> date:
    current = normalize_cn_equity_date(value)
    while True:
        current += timedelta(days=1)
        if is_cn_equity_trading_day(current, holidays=holidays):
            return current


def add_cn_equity_trading_days(
    value: date | datetime | str,
    count: int,
    *,
    holidays: Iterable[str] | None = None,
) -> date:
    if count < 0:
        raise ValueError("count must be non-negative")
    current = normalize_cn_equity_date(value)
    if count == 0:
        return current
    remaining = count
    while remaining > 0:
        current = next_cn_equity_trading_day(current, holidays=holidays)
        remaining -= 1
    return current


def iter_cn_equity_trading_days(
    start: date | datetime | str,
    end: date | datetime | str,
    *,
    holidays: Iterable[str] | None = None,
) -> Iterator[date]:
    current = normalize_cn_equity_date(start)
    last = normalize_cn_equity_date(end)
    if last < current:
        return
    while current <= last:
        if is_cn_equity_trading_day(current, holidays=holidays):
            yield current
        current += timedelta(days=1)


def month_end_cn_equity_trading_day(
    value: date | datetime | str,
    *,
    holidays: Iterable[str] | None = None,
) -> date:
    current = normalize_cn_equity_date(value)
    if current.month == 12:
        probe = date(current.year + 1, 1, 1) - timedelta(days=1)
    else:
        probe = date(current.year, current.month + 1, 1) - timedelta(days=1)
    while probe.month == current.month:
        if is_cn_equity_trading_day(probe, holidays=holidays):
            return probe
        probe -= timedelta(days=1)
    raise ValueError(f"no trading day found for month {current.year}-{current.month:02d}")


__all__ = [
    "CN_EQUITY_HOLIDAYS",
    "CN_EQUITY_TIMEZONE",
    "add_cn_equity_trading_days",
    "is_cn_equity_holiday",
    "is_cn_equity_trading_day",
    "is_cn_equity_weekday",
    "iter_cn_equity_trading_days",
    "month_end_cn_equity_trading_day",
    "next_cn_equity_trading_day",
    "normalize_cn_equity_date",
]
