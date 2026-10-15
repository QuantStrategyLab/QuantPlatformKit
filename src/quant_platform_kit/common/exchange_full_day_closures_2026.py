"""Published 2026 full-day exchange closures for live observation continuity.

Dates were supplied by the audit lead from official public calendars
(retrieved 2026-09-19). This module covers calendar year 2026 only and does
not track ad-hoc closures after publication.

Half-day sessions are intentionally absent: they remain expected observation
sessions.
"""

from __future__ import annotations

from datetime import date

# https://www.nyse.com/trade/hours-calendars — 2026 full-day closures.
XNYS_HOLIDAY_SOURCE_2026 = "https://www.nyse.com/trade/hours-calendars"
XNYS_HOLIDAY_COVERAGE_2026 = (date(2026, 1, 1), date(2026, 12, 31))
XNYS_FULL_DAY_CLOSURES_2026: frozenset[str] = frozenset(
    {
        "2026-01-01",
        "2026-01-19",
        "2026-02-16",
        "2026-04-03",
        "2026-05-25",
        "2026-06-19",
        "2026-07-03",
        "2026-09-07",
        "2026-11-26",
        "2026-12-25",
    }
)
# Half days (still sessions): 2026-11-27, 2026-12-24.

# HKEX Securities Market circular CT/075/25 (published 2025-06-02).
XHKG_HOLIDAY_SOURCE_2026 = (
    "https://www.hkex.com.hk/-/media/HKEX-Market/Services/Circulars-and-Notices/"
    "Participant-and-Members-Circulars/SEHK/2025/ce_SEHK_CT_075_2025.pdf"
)
XHKG_HOLIDAY_COVERAGE_2026 = (date(2026, 1, 1), date(2026, 12, 31))
XHKG_FULL_DAY_CLOSURES_2026: frozenset[str] = frozenset(
    {
        "2026-01-01",
        "2026-02-17",
        "2026-02-18",
        "2026-02-19",
        "2026-04-03",
        "2026-04-06",
        "2026-04-07",
        "2026-05-01",
        "2026-05-25",
        "2026-06-19",
        "2026-07-01",
        "2026-10-01",
        "2026-10-19",
        "2026-12-25",
    }
)
# Half days (still sessions): 2026-02-16, 2026-12-24, 2026-12-31.

__all__ = [
    "XHKG_FULL_DAY_CLOSURES_2026",
    "XHKG_HOLIDAY_COVERAGE_2026",
    "XHKG_HOLIDAY_SOURCE_2026",
    "XNYS_FULL_DAY_CLOSURES_2026",
    "XNYS_HOLIDAY_COVERAGE_2026",
    "XNYS_HOLIDAY_SOURCE_2026",
]
