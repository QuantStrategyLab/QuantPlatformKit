import unittest

from quant_platform_kit.common.small_account_compatibility import (
    apply_small_account_cash_compatibility,
    format_small_account_cash_substitution_notes,
    project_unbuyable_value_targets_to_cash,
)


class SmallAccountCompatibilityTests(unittest.TestCase):
    def test_projects_value_targets_below_one_share_to_cash(self):
        adjusted, substituted = project_unbuyable_value_targets_to_cash(
            {"SOXL": 541.58, "SOXX": 154.74, "BOXX": 0.0},
            {"SOXL": 191.15, "SOXX": 536.88, "BOXX": 100.0},
        )

        self.assertEqual(adjusted["SOXL"], 541.58)
        self.assertEqual(adjusted["SOXX"], 0.0)
        self.assertEqual(adjusted["BOXX"], 0.0)
        self.assertEqual(substituted, ("SOXX",))

    def test_keeps_targets_that_can_buy_one_quantity_step(self):
        adjusted, substituted = project_unbuyable_value_targets_to_cash(
            {"AAA": 100.0, "BBB": 99.99},
            {"AAA": 50.0, "BBB": 50.0},
            quantity_step=2.0,
        )

        self.assertEqual(adjusted["AAA"], 100.0)
        self.assertEqual(adjusted["BBB"], 0.0)
        self.assertEqual(substituted, ("BBB",))

    def test_projects_safe_haven_to_cash_when_only_risk_target_is_unbuyable(self):
        result = apply_small_account_cash_compatibility(
            {"SOXX": 163.14, "BOXX": 1224.46},
            {"SOXX": 504.60, "BOXX": 116.59},
            candidate_symbols=("SOXX",),
            safe_haven_cash_symbols=("BOXX",),
            cash_substitute_limit_usd=2000.0,
        )

        self.assertEqual(result.targets["SOXX"], 0.0)
        self.assertEqual(result.targets["BOXX"], 0.0)
        self.assertEqual(result.whole_share_substituted_symbols, ("SOXX",))
        self.assertEqual(result.safe_haven_cash_substituted_symbols, ("BOXX",))
        self.assertEqual(
            result.cash_substitution_notes,
            (
                {
                    "symbol": "SOXX",
                    "target_value": 163.14,
                    "price": 504.60,
                    "cash_symbols": ("BOXX",),
                },
            ),
        )

    def test_keeps_safe_haven_when_cash_projection_exceeds_small_account_limit(self):
        result = apply_small_account_cash_compatibility(
            {"SOXX": 163.14, "BOXX": 5000.0},
            {"SOXX": 504.60, "BOXX": 116.59},
            candidate_symbols=("SOXX",),
            safe_haven_cash_symbols=("BOXX",),
            cash_substitute_limit_usd=2000.0,
        )

        self.assertEqual(result.targets["SOXX"], 0.0)
        self.assertEqual(result.targets["BOXX"], 5000.0)
        self.assertEqual(result.whole_share_substituted_symbols, ("SOXX",))
        self.assertEqual(result.safe_haven_cash_substituted_symbols, ())
        self.assertEqual(
            result.cash_substitution_notes,
            (
                {
                    "symbol": "SOXX",
                    "target_value": 163.14,
                    "price": 504.60,
                    "cash_symbols": (),
                },
            ),
        )

    def test_formats_cash_substitution_notes_through_i18n(self):
        messages = format_small_account_cash_substitution_notes(
            (
                {
                    "symbol": "SOXX",
                    "target_value": 163.14,
                    "price": 504.60,
                    "cash_symbols": ("BOXX",),
                },
            ),
            translator=lambda key, **kwargs: {
                "cash_label": "现金",
                "buy_deferred": "ℹ️ [买入说明] {detail}",
                "buy_deferred_small_account_cash_substitution": (
                    "{symbol} 目标金额 ${diff} 低于 1 股价格 ${price}；"
                    "为避免超过目标仓位，本轮保留现金（现金替代：{cash_symbols}）"
                ),
            }.get(key, key).format(**kwargs),
        )

        self.assertEqual(
            messages,
            (
                "ℹ️ [买入说明] SOXX.US 目标金额 $163.14 低于 1 股价格 $504.60；"
                "为避免超过目标仓位，本轮保留现金（现金替代：BOXX.US）",
            ),
        )


if __name__ == "__main__":
    unittest.main()
