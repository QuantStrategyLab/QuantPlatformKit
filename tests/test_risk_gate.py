from __future__ import annotations

import unittest
from unittest.mock import patch

from quant_platform_kit.risk.contracts import ROUTE_BLOCKED, RiskSignal
from quant_platform_kit.risk.engine import RiskEngine
from quant_platform_kit.risk.gate import apply_risk_gate, enrich_decision_risk_diagnostics
from quant_platform_kit.strategy_contracts import PositionTarget, StrategyDecision


def _decision(
    *,
    positions: tuple[PositionTarget, ...] = (),
    diagnostics: dict | None = None,
) -> StrategyDecision:
    return StrategyDecision(
        positions=positions,
        diagnostics=diagnostics or {},
    )


class ApplyRiskGateTests(unittest.TestCase):
    def test_approve_within_limits(self) -> None:
        decision = _decision(
            positions=(
                PositionTarget(symbol="SPY", target_weight=0.40),
                PositionTarget(symbol="QQQ", target_weight=0.30),
            ),
        )

        result = apply_risk_gate(
            decision,
            max_single_weight=0.50,
            max_positions=5,
            max_total_exposure=1.0,
        )

        self.assertEqual(len(result.positions), 2)
        self.assertIn("risk_gate:passed", result.risk_flags)
        self.assertEqual(result.diagnostics.get("risk_gate"), "APPROVE")

    def test_reject_concentration(self) -> None:
        decision = _decision(
            positions=(PositionTarget(symbol="AAPL", target_weight=0.25),),
        )

        result = apply_risk_gate(decision, max_single_weight=0.10)

        self.assertEqual(result.positions, ())
        self.assertEqual(result.risk_flags, ("rejected:concentration",))
        self.assertEqual(result.diagnostics.get("risk_gate"), "REJECT")
        self.assertIn("AAPL", result.diagnostics.get("reason", ""))

    def test_reject_circuit_breaker(self) -> None:
        decision = _decision(
            positions=(PositionTarget(symbol="SPY", target_weight=0.50),),
            diagnostics={"consecutive_losses": 6},
        )

        result = apply_risk_gate(decision)

        self.assertEqual(result.positions, ())
        self.assertEqual(result.risk_flags, ("rejected:circuit_breaker",))
        self.assertEqual(result.diagnostics.get("risk_gate"), "REJECT")

    def test_reject_stop_loss_from_diagnostics(self) -> None:
        decision = _decision(
            positions=(PositionTarget(symbol="SPY", target_weight=0.50),),
            diagnostics={"unrealized_pnl_pct": -0.25},
        )

        result = apply_risk_gate(decision)

        self.assertEqual(result.positions, ())
        self.assertEqual(result.risk_flags, ("rejected:stop_loss",))
        self.assertEqual(result.diagnostics.get("risk_gate"), "REJECT")

    def test_reject_when_risk_engine_blocks(self) -> None:
        class BlockingPlugin:
            plugin_name = "test_blocker"
            schema_version = "test.v1"

            def evaluate(self, market_data):
                return RiskSignal(
                    plugin=self.plugin_name,
                    schema_version=self.schema_version,
                    route=ROUTE_BLOCKED,
                    confidence=1.0,
                    suggested_action="blocked",
                    as_of="2026-07-08",
                )

        decision = _decision(
            positions=(PositionTarget(symbol="SPY", target_weight=0.50),),
        )
        engine = RiskEngine(plugins=(BlockingPlugin(),))
        assessment = engine.assess(decision, {"total_equity": 100_000.0})
        self.assertEqual(assessment.action, "reject")

        with patch(
            "quant_platform_kit.risk.gate.build_risk_engine",
            return_value=engine,
        ):
            gated = apply_risk_gate(
                decision,
                portfolio_snapshot={"total_equity": 100_000.0},
                market_data={},
            )
        self.assertEqual(gated.positions, ())
        self.assertEqual(gated.risk_flags, ("rejected:risk_engine",))


if __name__ == "__main__":
    unittest.main()


class EnrichDecisionRiskDiagnosticsTests(unittest.TestCase):
    def test_enrich_sets_fields(self) -> None:
        decision = _decision(positions=(PositionTarget(symbol="SPY", target_weight=0.50),))
        enriched = enrich_decision_risk_diagnostics(
            decision,
            unrealized_pnl_pct=-0.05,
            consecutive_losses=2,
        )
        self.assertEqual(enriched.diagnostics.get("unrealized_pnl_pct"), -0.05)
        self.assertEqual(enriched.diagnostics.get("consecutive_losses"), 2)
        self.assertEqual(len(enriched.positions), 1)

    def test_enrich_noop_when_unset(self) -> None:
        decision = _decision()
        enriched = enrich_decision_risk_diagnostics(decision)
        self.assertIs(enriched, decision)

    def test_enrich_then_gate_rejects_stop_loss(self) -> None:
        decision = _decision(positions=(PositionTarget(symbol="SPY", target_weight=0.50),))
        enriched = enrich_decision_risk_diagnostics(decision, unrealized_pnl_pct=-0.25)
        result = apply_risk_gate(enriched)
        self.assertEqual(result.risk_flags, ("rejected:stop_loss",))
