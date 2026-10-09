"""B06: execution vs presentation facade — behavior-equivalent payloads."""

from __future__ import annotations

import unittest

from quant_platform_kit.common.execution_translation import (
    ValueTargetPortfolioInputs,
    build_value_target_execution_runtime_plan,
    build_value_target_runtime_plan,
)
from quant_platform_kit.common.presentation import (
    ValueTargetDisplayAnnotations,
    ValueTargetExecutionSemantics,
    ValueTargetPlanPresentation,
    display_annotations_from_execution_annotations,
    execution_semantics_from_annotations,
    merge_value_target_execution_annotations,
)
from quant_platform_kit.common.strategy_contracts import (
    PositionTarget,
    StrategyDecision,
    ValueTargetExecutionAnnotations,
)


def _decision() -> StrategyDecision:
    return StrategyDecision(
        positions=(
            PositionTarget(symbol="SOXL", target_value=100.0),
            PositionTarget(symbol="BOXX", target_value=50.0, role="safe_haven"),
        ),
        diagnostics={
            "execution_annotations": {
                "trade_threshold_value": 25.0,
                "reserved_cash": 10.0,
                "signal_display": "risk-on",
                "dashboard_text": "line-a\nline-b",
            }
        },
    )


def _inputs() -> ValueTargetPortfolioInputs:
    return ValueTargetPortfolioInputs(
        market_values={"SOXL": 80.0, "BOXX": 40.0},
        quantities={"SOXL": 1.0, "BOXX": 2.0},
        total_equity=200.0,
        liquid_cash=70.0,
    )


class ValueTargetPresentationFacadeTests(unittest.TestCase):
    def test_compat_runtime_plan_matches_execution_api_with_same_presentation(self) -> None:
        decision = _decision()
        inputs = _inputs()
        annotations = ValueTargetExecutionAnnotations(
            trade_threshold_value=25.0,
            reserved_cash=10.0,
            signal_display="risk-on",
            dashboard_text="line-a\nline-b",
        )
        legacy = build_value_target_runtime_plan(
            decision,
            strategy_profile="soxl_soxx_trend_income",
            portfolio_inputs=inputs,
            portfolio_rows_layout=("risk_safe", "income"),
            annotations=annotations,
        )
        modern = build_value_target_execution_runtime_plan(
            decision,
            strategy_profile="soxl_soxx_trend_income",
            portfolio_inputs=inputs,
            annotations=annotations,
            presentation=ValueTargetPlanPresentation(
                portfolio_rows_layout=("risk_safe", "income"),
            ),
        )
        self.assertEqual(legacy, modern)
        self.assertEqual(legacy["execution"]["signal_display"], "risk-on")
        self.assertEqual(legacy["execution"]["trade_threshold_value"], 25.0)

    def test_execution_api_omits_layout_kwargs_and_uses_default_presentation(self) -> None:
        payload = build_value_target_execution_runtime_plan(
            _decision(),
            strategy_profile="soxl_soxx_trend_income",
            portfolio_inputs=_inputs(),
            annotations=ValueTargetExecutionAnnotations(
                trade_threshold_value=25.0,
                reserved_cash=0.0,
            ),
        )
        self.assertIn("portfolio", payload)
        self.assertIn("execution", payload)
        # Default layout still produces portfolio_rows (structural, not dashboard copy).
        self.assertIn("portfolio_rows", payload["portfolio"])

    def test_semantics_display_round_trip(self) -> None:
        original = ValueTargetExecutionAnnotations(
            trade_threshold_value=12.5,
            reserved_cash=3.0,
            signal_display="hold",
            dashboard_text="dash",
            separator="|",
            signal_date="2026-10-08",
        )
        merged = merge_value_target_execution_annotations(
            execution_semantics_from_annotations(original),
            display_annotations_from_execution_annotations(original),
        )
        self.assertEqual(merged, original)
        self.assertIsInstance(
            execution_semantics_from_annotations(original),
            ValueTargetExecutionSemantics,
        )
        self.assertIsInstance(
            display_annotations_from_execution_annotations(original),
            ValueTargetDisplayAnnotations,
        )


if __name__ == "__main__":
    unittest.main()
