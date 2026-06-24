import unittest

from quant_platform_kit.common.small_account_compatibility import (
    apply_small_account_cash_compatibility,
    build_small_account_allocation_drift_notes,
    format_small_account_allocation_drift_notes,
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

    def test_builds_projected_allocation_drift_notes_from_submitted_orders(self):
        notes = build_small_account_allocation_drift_notes(
            target_values={"SOXL": 218.19, "SOXX": 342.86},
            current_values={"SOXL": 0.0, "SOXX": 0.0},
            current_quantities={"SOXL": 0.0, "SOXX": 0.0},
            prices={"SOXL": 229.73, "SOXX": 603.0},
            submitted_orders=(
                {"symbol": "SOXL.US", "side": "buy", "quantity": 1, "limit_price": 233.18},
            ),
            total_value=623.39,
            min_abs_weight_drift=0.005,
        )

        self.assertEqual(notes[0]["symbol"], "SOXX")
        self.assertAlmostEqual(notes[0]["target_weight"], 342.86 / 623.39)
        self.assertAlmostEqual(notes[0]["projected_weight"], 0.0)
        self.assertEqual(notes[1]["symbol"], "SOXL")
        self.assertAlmostEqual(notes[1]["projected_weight"], 233.18 / 623.39)

    def test_skips_drift_notes_for_larger_accounts_by_default(self):
        notes = build_small_account_allocation_drift_notes(
            target_values={"AAA": 5000.0},
            current_values={"AAA": 0.0},
            prices={"AAA": 100.0},
            submitted_orders=({"symbol": "AAA", "side": "buy", "quantity": 49, "limit_price": 100.0},),
            total_value=50_000.0,
        )

        self.assertEqual(notes, ())

    def test_drift_notes_ignore_symbols_outside_reference_targets(self):
        notes = build_small_account_allocation_drift_notes(
            target_values={"SOXL": 500.0},
            current_values={"SOXL": 0.0, "BOXX": 1000.0},
            current_quantities={"SOXL": 0.0, "BOXX": 10.0},
            prices={"SOXL": 100.0, "BOXX": 100.0},
            submitted_orders=(
                {"symbol": "BOXX.US", "side": "buy", "quantity": 1, "limit_price": 100.0},
            ),
            total_value=1000.0,
        )

        self.assertEqual([note["symbol"] for note in notes], ["SOXL"])

    def test_formats_projected_allocation_drift_notes_through_i18n(self):
        messages = format_small_account_allocation_drift_notes(
            (
                {
                    "kind": "small_account_allocation_drift",
                    "symbol": "SOXL",
                    "projected_weight": 0.3740,
                    "target_weight": 0.3500,
                    "drift_weight": 0.0240,
                },
            ),
            translator=lambda key, **kwargs: {
                "small_account_allocation_drift": "📏 整数股偏离：若本轮订单全部成交，{details}",
                "small_account_allocation_drift_detail": (
                    "{symbol} 预计 {projected_weight} vs 目标 {target_weight}（{drift_weight}）"
                ),
            }.get(key, key).format(**kwargs),
        )

        self.assertEqual(
            messages,
            ("📏 整数股偏离：若本轮订单全部成交，SOXL.US 预计 37.4% vs 目标 35.0%（+2.4pp）",),
        )


if __name__ == "__main__":
    unittest.main()
