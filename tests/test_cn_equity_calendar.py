from __future__ import annotations

import unittest
from datetime import date

from quant_platform_kit.common.cn_equity_calendar import (
    add_cn_equity_trading_days,
    is_cn_equity_trading_day,
    month_end_cn_equity_trading_day,
    next_cn_equity_trading_day,
)
from quant_platform_kit.common.strategies import CN_EQUITY_DOMAIN


class CnEquityCalendarTests(unittest.TestCase):
    def test_cn_equity_domain_constant(self) -> None:
        self.assertEqual(CN_EQUITY_DOMAIN, "cn_equity")

    def test_weekend_is_not_trading_day(self) -> None:
        self.assertFalse(is_cn_equity_trading_day("2024-01-06"))

    def test_new_year_holiday_is_not_trading_day(self) -> None:
        self.assertFalse(is_cn_equity_trading_day("2024-01-01"))

    def test_regular_weekday_is_trading_day(self) -> None:
        self.assertTrue(is_cn_equity_trading_day("2024-01-02"))

    def test_next_trading_day_skips_weekend_and_holiday(self) -> None:
        self.assertEqual(next_cn_equity_trading_day("2024-02-08"), date(2024, 2, 19))

    def test_add_trading_days(self) -> None:
        self.assertEqual(add_cn_equity_trading_days("2024-01-02", 3), date(2024, 1, 5))

    def test_month_end_trading_day(self) -> None:
        self.assertEqual(month_end_cn_equity_trading_day("2024-01-15"), date(2024, 1, 31))
        self.assertEqual(month_end_cn_equity_trading_day("2024-02-01"), date(2024, 2, 29))


if __name__ == "__main__":
    unittest.main()
