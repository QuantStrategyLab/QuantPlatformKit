from __future__ import annotations

import unittest
from datetime import datetime, timezone
from unittest.mock import Mock, patch

from quant_platform_kit.common.models import PortfolioSnapshot
from quant_platform_kit.risk.contracts import ROUTE_BLOCKED, RiskAction, RiskSignal
from quant_platform_kit.risk.engine import RiskEngine
from quant_platform_kit.risk.gate import (
    assess_with_evidence,
    apply_risk_gate,
    enrich_decision_risk_diagnostics,
)
from quant_platform_kit.strategy_contracts import BudgetIntent, PositionTarget, StrategyDecision


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
    def test_no_mandate_does_not_allow_caller_to_expand_default_cap(self) -> None:
        decision = _decision(
            positions=(PositionTarget(symbol="SPY", target_weight=0.11),),
        )

        result = apply_risk_gate(
            decision,
            max_single_weight=0.50,
            max_positions=5,
            max_total_exposure=1.0,
        )

        self.assertEqual(result.positions, ())
        self.assertEqual(result.budgets, ())
        self.assertEqual(result.risk_flags, ("rejected:concentration",))

    def test_no_mandate_allows_exactly_ten_percent(self) -> None:
        result = apply_risk_gate(
            _decision(positions=(PositionTarget(symbol="SPY", target_weight=0.10),)),
        )

        self.assertEqual(len(result.positions), 1)
        self.assertIn("risk_gate:passed", result.risk_flags)

    def test_no_mandate_rejects_multiple_nonzero_positions(self) -> None:
        result = apply_risk_gate(
            _decision(
                positions=(
                    PositionTarget(symbol="SPY", target_weight=0.05),
                    PositionTarget(symbol="BOXX", target_weight=0.05),
                ),
            ),
        )

        self.assertEqual(result.positions, ())
        self.assertEqual(result.budgets, ())
        self.assertEqual(result.risk_flags, ("rejected:too_many_positions",))

    def test_unknown_mandate_remains_fail_closed(self) -> None:
        result = apply_risk_gate(
            _decision(positions=(PositionTarget(symbol="SPY", target_weight=0.10),)),
            risk_mandate_id="unapproved_mandate_v1",
        )

        self.assertEqual(result.positions, ())
        self.assertEqual(result.risk_flags, ("rejected:unknown_risk_mandate",))

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
            positions=(PositionTarget(symbol="SPY", target_weight=0.10),),
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

    def test_rejects_non_approve_risk_engine_action_and_clears_budgets(self) -> None:
        decision = StrategyDecision(
            positions=(PositionTarget(symbol="SPY", target_weight=0.10),),
            budgets=(BudgetIntent(name="risk_budget", amount=1.0),),
        )
        engine = Mock()
        engine.assess.return_value = RiskAction(action="watch", reason="not approved")

        with patch("quant_platform_kit.risk.gate.build_risk_engine", return_value=engine):
            gated = apply_risk_gate(
                decision,
                portfolio_snapshot={"total_equity": 100_000.0},
                market_data={},
            )

        self.assertEqual(gated.positions, ())
        self.assertEqual(gated.budgets, ())
        self.assertEqual(gated.risk_flags, ("rejected:risk_engine",))


class AssessWithEvidenceTests(unittest.TestCase):
    _NOW = datetime(2026, 8, 4, 4, 28, tzinfo=timezone.utc)

    @staticmethod
    def _mandate(**overrides: object) -> dict[str, object]:
        mandate: dict[str, object] = {
            "mandate_id": "binance_crypto_research_only_v1",
            "mandate_version": "2026-08-04.1",
            "authority_receipt_sha256": "a" * 64,
            "authority_scope": "RESEARCH_ONLY",
            "strategy_profile": "crypto_live_pool_rotation",
            "account_mode": "single_strategy_account_v1",
            "effective_at": "2026-08-04T04:27:55Z",
            "expires_at": "2026-09-03T15:59:59Z",
            "max_snapshot_age_seconds": 300,
            "effective_exposure_cap": 0.50,
            "loss_budget": 0.0,
            "product_caps": 1.0,
            "nominal_caps": 1.0,
            "product_leverage_factors": {"BTCUSDT": 1},
            "allowed_nonzero_assets": ["BTCUSDT"],
            "source_revision": "14b27d98bda18455439cbd6470c52a069befd002",
        }
        mandate.update(overrides)
        return mandate

    @staticmethod
    def _snapshot(**overrides: object) -> dict[str, object]:
        snapshot: dict[str, object] = {
            "as_of": "2026-08-04T04:27:55Z",
            "observed_effective_exposure": 0.10,
            "total_equity": 100_000.0,
            "account_id": "private-account-id",
            "positions": [{"symbol": "BTCUSDT", "quantity": 123.0}],
        }
        snapshot.update(overrides)
        return snapshot

    def test_approved_receipt_is_immutable_and_redacts_digest_inputs(self) -> None:
        decision = _decision(
            positions=(PositionTarget(symbol="BTCUSDT", target_weight=0.20),),
        )
        with patch("quant_platform_kit.risk.gate._utc_now", return_value=self._NOW):
            first = assess_with_evidence(
                decision,
                self._snapshot(),
                scope="MEMBER",
                mandate_provenance=self._mandate(),
                market_data={},
            )
            redacted_equivalent = assess_with_evidence(
                decision,
                self._snapshot(
                    account_id="another-private-account",
                    positions=[{"symbol": "BTCUSDT", "quantity": 999.0}],
                ),
                scope="MEMBER",
                mandate_provenance=self._mandate(),
                market_data={},
            )

        self.assertEqual(first.assessment.outcome, "APPROVE")
        self.assertEqual(first.assessment.effective_exposure_cap, 0.50)
        self.assertEqual(first.assessment.observed_effective_exposure, 0.10)
        self.assertEqual(first.assessment.proposed_effective_exposure, 0.20)
        self.assertEqual(first.assessment.assessment_sha256, redacted_equivalent.assessment.assessment_sha256)
        self.assertEqual(len(first.decision.positions), 1)

    def test_zero_cap_research_mandate_never_produces_order_authority(self) -> None:
        decision = StrategyDecision(
            positions=(PositionTarget(symbol="BTCUSDT", target_weight=0.10),),
            budgets=(BudgetIntent(name="risk_budget", amount=1.0),),
        )
        engine = Mock()
        engine.assess.return_value = RiskAction(action="approve", reason="passed")
        with (
            patch("quant_platform_kit.risk.gate._utc_now", return_value=self._NOW),
            patch("quant_platform_kit.risk.gate.build_risk_engine", return_value=engine),
        ):
            result = assess_with_evidence(
                decision,
                self._snapshot(),
                scope="ACCOUNT",
                mandate_provenance=self._mandate(
                    effective_exposure_cap=0.0,
                    allowed_nonzero_assets=[],
                ),
                market_data={},
            )

        self.assertEqual(result.assessment.outcome, "REJECT")
        self.assertEqual(result.decision.positions, ())
        self.assertEqual(result.decision.budgets, ())
        self.assertIn("effective_exposure_cap", result.assessment.reason_codes)
        engine.assess.assert_called_once()

    def test_invalid_scope_rejects_fail_closed(self) -> None:
        with patch("quant_platform_kit.risk.gate._utc_now", return_value=self._NOW):
            result = assess_with_evidence(
                _decision(positions=(PositionTarget(symbol="BTCUSDT", target_weight=0.10),)),
                self._snapshot(),
                scope="STRATEGY",
                mandate_provenance=self._mandate(),
                market_data={},
            )

        self.assertEqual(result.assessment.outcome, "REJECT")
        self.assertEqual(result.assessment.scope, "MEMBER")
        self.assertEqual(result.decision.positions, ())

    def test_unmapped_or_empty_product_caps_reject_fail_closed(self) -> None:
        decision = _decision(
            positions=(PositionTarget(symbol="BTCUSDT", target_weight=0.20),),
        )
        for cap_overrides in (
            {"product_caps": {"ETHUSDT": 0.10}},
            {"product_caps": {}},
            {"nominal_caps": {"ETHUSDT": 0.10}},
            {"nominal_caps": {}},
        ):
            with (
                self.subTest(cap_overrides=cap_overrides),
                patch("quant_platform_kit.risk.gate._utc_now", return_value=self._NOW),
            ):
                result = assess_with_evidence(
                    decision,
                    self._snapshot(),
                    scope="MEMBER",
                    mandate_provenance=self._mandate(**cap_overrides),
                    market_data={},
                )

            self.assertEqual(result.assessment.outcome, "REJECT")
            self.assertEqual(result.decision.positions, ())
            self.assertEqual(result.decision.budgets, ())

    def test_decision_digest_binds_position_and_budget_execution_fields(self) -> None:
        mandate = self._mandate(
            loss_budget=10.0,
            product_leverage_factors={"BTCUSDT": 1, "ETHUSDT": 1},
            allowed_nonzero_assets=["BTCUSDT", "ETHUSDT"],
        )
        decisions = (
            StrategyDecision(
                positions=(PositionTarget(symbol="BTCUSDT", target_weight=0.10),),
                budgets=(BudgetIntent(name="risk_budget", amount=1.0),),
            ),
            StrategyDecision(
                positions=(PositionTarget(symbol="ETHUSDT", target_weight=0.10),),
                budgets=(BudgetIntent(name="risk_budget", amount=1.0),),
            ),
            StrategyDecision(
                positions=(PositionTarget(symbol="BTCUSDT", target_weight=0.10),),
                budgets=(BudgetIntent(name="loss_budget", amount=2.0),),
            ),
        )
        with patch("quant_platform_kit.risk.gate._utc_now", return_value=self._NOW):
            results = tuple(
                assess_with_evidence(
                    decision,
                    self._snapshot(),
                    scope="MEMBER",
                    mandate_provenance=mandate,
                    market_data={},
                )
                for decision in decisions
            )

        digests = {result.assessment.decision_digest_sha256 for result in results}
        self.assertEqual(len(digests), len(decisions))
        self.assertTrue(all(result.assessment.outcome == "APPROVE" for result in results))
        self.assertNotIn("BTCUSDT", repr(results[0].assessment))
        self.assertNotIn("risk_budget", repr(results[0].assessment))

    def test_unmandated_fallback_rejects_stale_snapshot(self) -> None:
        with patch("quant_platform_kit.risk.gate._utc_now", return_value=self._NOW):
            result = assess_with_evidence(
                _decision(positions=(PositionTarget(symbol="SPY", target_weight=0.10),)),
                self._snapshot(as_of="2026-08-04T04:17:55Z"),
                scope="MEMBER",
                mandate_provenance=None,
                market_data={},
            )

        self.assertEqual(result.assessment.outcome, "REJECT")
        self.assertIn("stale_portfolio_snapshot", result.assessment.reason_codes)
        self.assertEqual(result.decision.positions, ())

    def test_risk_plugin_exception_rejects_without_exposing_exception(self) -> None:
        class CrashingPlugin:
            plugin_name = "crashing_plugin"
            schema_version = "test.v1"

            def evaluate(self, market_data):
                raise RuntimeError("private plugin exception detail")

        engine = RiskEngine(plugins=(CrashingPlugin(),))
        decision = _decision(
            positions=(PositionTarget(symbol="BTCUSDT", target_weight=0.10),),
        )
        self.assertEqual(engine.assess(decision, self._snapshot()).action, "reject")

        with (
            patch("quant_platform_kit.risk.gate._utc_now", return_value=self._NOW),
            patch("quant_platform_kit.risk.gate.build_risk_engine", return_value=engine),
        ):
            result = assess_with_evidence(
                decision,
                self._snapshot(),
                scope="MEMBER",
                mandate_provenance=self._mandate(),
                market_data={},
            )

        self.assertEqual(result.assessment.outcome, "REJECT")
        self.assertIn("risk_engine_non_approve", result.assessment.reason_codes)
        self.assertNotIn("private plugin exception detail", repr(result))

    def test_canonical_portfolio_snapshot_matches_mapping_normalization(self) -> None:
        canonical = PortfolioSnapshot(
            as_of=self._NOW.replace(minute=27, second=55),
            total_equity=100_000.0,
            metadata={"observed_effective_exposure": 0.10},
        )
        decision = _decision(
            positions=(PositionTarget(symbol="BTCUSDT", target_weight=0.20),),
        )
        with patch("quant_platform_kit.risk.gate._utc_now", return_value=self._NOW):
            canonical_result = assess_with_evidence(
                decision,
                canonical,
                scope="MEMBER",
                mandate_provenance=self._mandate(),
                market_data={},
            )
            mapping_result = assess_with_evidence(
                decision,
                self._snapshot(),
                scope="MEMBER",
                mandate_provenance=self._mandate(),
                market_data={},
            )

        self.assertEqual(canonical_result.assessment.outcome, "APPROVE")
        self.assertEqual(
            canonical_result.assessment.portfolio_snapshot_digest_sha256,
            mapping_result.assessment.portfolio_snapshot_digest_sha256,
        )

    def test_value_target_uses_positive_finite_snapshot_equity(self) -> None:
        decision = _decision(
            positions=(PositionTarget(symbol="BTCUSDT", target_value=20_000.0),),
        )
        with patch("quant_platform_kit.risk.gate._utc_now", return_value=self._NOW):
            approved = assess_with_evidence(
                decision,
                self._snapshot(total_equity=100_000.0),
                scope="MEMBER",
                mandate_provenance=self._mandate(),
                market_data={},
            )

        self.assertEqual(approved.assessment.outcome, "APPROVE")
        self.assertEqual(approved.assessment.proposed_effective_exposure, 0.20)
        for invalid_equity in (None, 0.0, float("inf")):
            snapshot = self._snapshot()
            if invalid_equity is None:
                snapshot.pop("total_equity")
            else:
                snapshot["total_equity"] = invalid_equity
            with (
                self.subTest(invalid_equity=invalid_equity),
                patch("quant_platform_kit.risk.gate._utc_now", return_value=self._NOW),
            ):
                rejected = assess_with_evidence(
                    decision,
                    snapshot,
                    scope="MEMBER",
                    mandate_provenance=self._mandate(),
                    market_data={},
                )
            self.assertEqual(rejected.assessment.outcome, "REJECT")
            self.assertEqual(rejected.decision.positions, ())

    def test_mandate_rejects_budget_only_decision_above_authority(self) -> None:
        decision = StrategyDecision(
            budgets=(BudgetIntent(name="risk_budget", amount=1.0),),
        )
        for authority in (
            {"effective_exposure_cap": 0.0, "loss_budget": 0.0},
            {"effective_exposure_cap": 0.50, "loss_budget": 0.50},
        ):
            with (
                self.subTest(authority=authority),
                patch("quant_platform_kit.risk.gate._utc_now", return_value=self._NOW),
            ):
                result = assess_with_evidence(
                    decision,
                    self._snapshot(observed_effective_exposure=0.0),
                    scope="MEMBER",
                    mandate_provenance=self._mandate(
                        **authority,
                        allowed_nonzero_assets=[],
                    ),
                    market_data={},
                )

            self.assertEqual(result.assessment.outcome, "REJECT")
            self.assertEqual(result.decision.positions, ())
            self.assertEqual(result.decision.budgets, ())
            self.assertIn("budget_authority_exceeded", result.assessment.reason_codes)


class BootstrapSmallAccountV2RiskGateTests(unittest.TestCase):
    _MANDATE = "bootstrap_small_account_v2"

    def _apply(
        self,
        positions: tuple[PositionTarget, ...],
        *,
        product_leverage_factors: dict[str, int] | None = None,
        available_account_exposure: float | None = 0.50,
    ) -> StrategyDecision:
        return apply_risk_gate(
            _decision(positions=positions),
            risk_mandate_id=self._MANDATE,
            product_leverage_factors=product_leverage_factors,
            available_account_exposure=available_account_exposure,
        )

    def test_approved_mandate_allows_one_classified_position_within_caps(self) -> None:
        result = self._apply(
            (PositionTarget(symbol="SPY", target_weight=0.20),),
            product_leverage_factors={"SPY": 1},
        )

        self.assertEqual(len(result.positions), 1)
        self.assertIn("risk_gate:passed", result.risk_flags)

    def test_approved_mandate_rejects_two_nonzero_targets(self) -> None:
        result = self._apply(
            (
                PositionTarget(symbol="SPY", target_weight=0.10),
                PositionTarget(symbol="BOXX", target_weight=0.10),
            ),
            product_leverage_factors={"SPY": 1, "BOXX": 1},
        )

        self.assertEqual(result.positions, ())
        self.assertEqual(result.risk_flags, ("rejected:too_many_positions",))

    def test_approved_mandate_does_not_grandfather_legacy_single_weight_limit(
        self,
    ) -> None:
        result = apply_risk_gate(
            _decision(positions=(PositionTarget(symbol="SPY", target_weight=0.51),)),
            risk_mandate_id=self._MANDATE,
            product_leverage_factors={"SPY": 1},
            available_account_exposure=0.50,
            max_single_weight=1.0,
        )

        self.assertEqual(result.positions, ())
        self.assertEqual(result.risk_flags, ("rejected:concentration",))

    def test_approved_mandate_rejects_missing_or_invalid_leverage_classification(
        self,
    ) -> None:
        decision = (PositionTarget(symbol="SPY", target_weight=0.20),)
        for factors in (None, {"SPY": 4}, {"QQQ": 1}):
            with self.subTest(factors=factors):
                result = self._apply(decision, product_leverage_factors=factors)
                self.assertEqual(result.positions, ())
                self.assertEqual(
                    result.risk_flags, ("rejected:leverage_classification",)
                )

    def test_approved_mandate_enforces_nominal_and_effective_exposure_caps(
        self,
    ) -> None:
        rejected = self._apply(
            (PositionTarget(symbol="TQQQ", target_weight=0.20),),
            product_leverage_factors={"TQQQ": 3},
        )
        approved = self._apply(
            (PositionTarget(symbol="QLD", target_weight=0.25),),
            product_leverage_factors={"QLD": 2},
        )

        self.assertEqual(rejected.positions, ())
        self.assertEqual(rejected.risk_flags, ("rejected:concentration",))
        self.assertEqual(len(approved.positions), 1)

    def test_approved_mandate_enforces_available_single_account_capacity(self) -> None:
        result = self._apply(
            (PositionTarget(symbol="SPY", target_weight=0.20),),
            product_leverage_factors={"SPY": 1},
            available_account_exposure=0.19,
        )

        self.assertEqual(result.positions, ())
        self.assertEqual(result.risk_flags, ("rejected:overexposed",))


if __name__ == "__main__":
    unittest.main()


class EnrichDecisionRiskDiagnosticsTests(unittest.TestCase):
    def test_enrich_sets_fields(self) -> None:
        decision = _decision(
            positions=(PositionTarget(symbol="SPY", target_weight=0.50),)
        )
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
        decision = _decision(
            positions=(PositionTarget(symbol="SPY", target_weight=0.50),)
        )
        enriched = enrich_decision_risk_diagnostics(decision, unrealized_pnl_pct=-0.25)
        result = apply_risk_gate(enriched)
        self.assertEqual(result.risk_flags, ("rejected:stop_loss",))
