from __future__ import annotations

import unittest
from datetime import datetime, timezone
from unittest.mock import Mock, patch

from quant_platform_kit.common.models import PortfolioSnapshot
from quant_platform_kit.risk.contracts import (
    ROUTE_BLOCKED,
    CandidateRiskIdentity,
    RiskAction,
    RiskSignal,
)
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


def _portfolio_snapshot() -> dict[str, float]:
    return {"total_equity": 100_000.0}


class RiskEngineAssessmentTests(unittest.TestCase):
    def test_missing_or_invalid_portfolio_snapshot_rejects(self) -> None:
        decision = _decision(
            positions=(PositionTarget(symbol="SPY", target_weight=0.10),),
        )

        for snapshot, reason in (
            (None, "missing_portfolio_snapshot"),
            ({}, "invalid_portfolio_snapshot"),
            ({"total_equity": 0.0}, "invalid_portfolio_snapshot"),
            ({"total_equity": float("inf")}, "invalid_portfolio_snapshot"),
            (object(), "invalid_portfolio_snapshot"),
        ):
            with self.subTest(snapshot=snapshot):
                assessment = RiskEngine().assess(decision, snapshot)

            self.assertEqual(assessment.action, "reject")
            self.assertEqual(assessment.reason, reason)
            self.assertEqual(assessment.budget_scalar, 0.0)
            self.assertEqual(assessment.leverage_scalar, 0.0)
            self.assertEqual(assessment.risk_asset_scalar, 0.0)

    def test_finite_portfolio_snapshot_remains_approved(self) -> None:
        decision = _decision(
            positions=(PositionTarget(symbol="SPY", target_weight=0.10),),
        )
        canonical = PortfolioSnapshot(
            as_of=datetime(2026, 8, 5, tzinfo=timezone.utc),
            total_equity=100_000.0,
        )

        for snapshot in (_portfolio_snapshot(), canonical):
            with self.subTest(snapshot=snapshot):
                assessment = RiskEngine().assess(decision, snapshot)

            self.assertEqual(assessment.action, "approve")
            self.assertEqual(assessment.reason, "risk_engine_passed")


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
            product_leverage_factors={"SPY": 1},
            portfolio_snapshot=_portfolio_snapshot(),
        )

        self.assertEqual(len(result.positions), 1)
        self.assertIn("risk_gate:passed", result.risk_flags)

    def test_no_mandate_rejects_missing_or_leveraged_classification(self) -> None:
        decision = _decision(
            positions=(PositionTarget(symbol="SPY", target_weight=0.10),),
        )

        for factors in (None, {"SPY": 2}, {"QQQ": 1}):
            with self.subTest(factors=factors):
                result = apply_risk_gate(
                    decision,
                    product_leverage_factors=factors,
                    portfolio_snapshot=_portfolio_snapshot(),
                )

            self.assertEqual(result.positions, ())
            self.assertEqual(result.budgets, ())
            self.assertEqual(
                result.risk_flags,
                ("rejected:leverage_classification",),
            )

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
                product_leverage_factors={"SPY": 1},
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
                product_leverage_factors={"SPY": 1},
                portfolio_snapshot={"total_equity": 100_000.0},
                market_data={},
            )

        self.assertEqual(gated.positions, ())
        self.assertEqual(gated.budgets, ())
        self.assertEqual(gated.risk_flags, ("rejected:risk_engine",))
        engine.assess.assert_called_once_with(
            decision,
            _portfolio_snapshot(),
            market_data={},
        )

    def test_missing_snapshot_still_assesses_once_and_rejects(self) -> None:
        decision = _decision(
            positions=(PositionTarget(symbol="SPY", target_weight=0.10),),
        )
        engine = Mock(wraps=RiskEngine())

        with patch("quant_platform_kit.risk.gate.build_risk_engine", return_value=engine):
            gated = apply_risk_gate(
                decision,
                product_leverage_factors={"SPY": 1},
                portfolio_snapshot=None,
            )

        self.assertEqual(gated.positions, ())
        self.assertEqual(gated.budgets, ())
        self.assertEqual(gated.risk_flags, ("rejected:risk_engine",))
        self.assertEqual(
            gated.diagnostics.get("reason"),
            "missing_portfolio_snapshot",
        )
        engine.assess.assert_called_once_with(decision, None, market_data=None)

    def test_every_static_path_assesses_engine_exactly_once(self) -> None:
        cases = (
            (
                "empty",
                _decision(),
                {},
                ("risk_gate:passed",),
            ),
            (
                "concentration",
                _decision(
                    positions=(PositionTarget(symbol="SPY", target_weight=0.11),),
                ),
                {"product_leverage_factors": {"SPY": 1}},
                ("rejected:concentration",),
            ),
            (
                "invalid_weight",
                _decision(
                    positions=(PositionTarget(symbol="SPY", target_weight="invalid"),),
                ),
                {},
                ("rejected:invalid_weight",),
            ),
            (
                "unknown_mandate",
                _decision(
                    positions=(PositionTarget(symbol="SPY", target_weight=0.10),),
                ),
                {"risk_mandate_id": "unapproved_mandate_v1"},
                ("rejected:unknown_risk_mandate",),
            ),
            (
                "leverage",
                _decision(
                    positions=(PositionTarget(symbol="SPY", target_weight=0.20),),
                ),
                {
                    "risk_mandate_id": "bootstrap_small_account_v2",
                    "available_account_exposure": 0.50,
                },
                ("rejected:leverage_classification",),
            ),
            (
                "circuit_breaker",
                _decision(
                    positions=(PositionTarget(symbol="SPY", target_weight=0.10),),
                    diagnostics={"consecutive_losses": 6},
                ),
                {},
                ("rejected:circuit_breaker",),
            ),
        )
        for name, decision, kwargs, expected_flags in cases:
            engine = Mock()
            engine.assess.return_value = RiskAction(action="approve", reason="passed")
            with (
                self.subTest(name=name),
                patch(
                    "quant_platform_kit.risk.gate.build_risk_engine",
                    return_value=engine,
                ),
            ):
                gated = apply_risk_gate(
                    decision,
                    portfolio_snapshot=_portfolio_snapshot(),
                    **kwargs,
                )

            self.assertEqual(gated.risk_flags, expected_flags)
            engine.assess.assert_called_once_with(
                decision,
                _portfolio_snapshot(),
                market_data=None,
            )
            if expected_flags != ("risk_gate:passed",):
                self.assertEqual(gated.positions, ())
                self.assertEqual(gated.budgets, ())

    def test_risk_engine_exception_rejects_without_order_truth(self) -> None:
        decision = StrategyDecision(
            positions=(PositionTarget(symbol="SPY", target_weight=0.10),),
            budgets=(BudgetIntent(name="risk_budget", amount=1.0),),
        )
        engine = Mock()
        engine.assess.side_effect = RuntimeError("private engine failure")

        with patch("quant_platform_kit.risk.gate.build_risk_engine", return_value=engine):
            gated = apply_risk_gate(
                decision,
                product_leverage_factors={"SPY": 1},
                portfolio_snapshot=_portfolio_snapshot(),
            )

        self.assertEqual(gated.positions, ())
        self.assertEqual(gated.budgets, ())
        self.assertEqual(gated.risk_flags, ("rejected:risk_engine",))
        self.assertEqual(gated.diagnostics.get("reason"), "risk_engine_error")
        self.assertNotIn("private engine failure", repr(gated))
        engine.assess.assert_called_once()


class AssessWithEvidenceTests(unittest.TestCase):
    _NOW = datetime(2026, 8, 4, 4, 28, tzinfo=timezone.utc)

    @staticmethod
    def _candidate(**overrides: object) -> CandidateRiskIdentity:
        values: dict[str, object] = {
            "strategy_profile": "crypto_live_pool_rotation",
            "account_mode": "single_strategy_account_v1",
            "strategy_revision": "b" * 40,
            "runner_revision": "c" * 40,
            "config_sha256": "d" * 64,
            "input_manifest_sha256": "e" * 64,
            "authority_receipt_sha256": "a" * 64,
        }
        values.update(overrides)
        return CandidateRiskIdentity(**values)

    @classmethod
    def _mandate(
        cls,
        candidate: CandidateRiskIdentity | None = None,
        **overrides: object,
    ) -> dict[str, object]:
        candidate = candidate or cls._candidate()
        mandate: dict[str, object] = {
            "mandate_id": "binance_crypto_research_only_v1",
            "mandate_version": "2026-08-04.1",
            "authority_receipt_sha256": "a" * 64,
            "authority_scope": "RESEARCH_ONLY",
            "strategy_profile": candidate.strategy_profile,
            "account_mode": candidate.account_mode,
            "strategy_revision": candidate.strategy_revision,
            "runner_revision": candidate.runner_revision,
            "config_sha256": candidate.config_sha256,
            "input_manifest_sha256": candidate.input_manifest_sha256,
            "candidate_identity_sha256": candidate.candidate_sha256,
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
                candidate_identity=self._candidate(),
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
                candidate_identity=self._candidate(),
            )

        self.assertEqual(first.assessment.outcome, "APPROVE")
        self.assertEqual(first.assessment.effective_exposure_cap, 0.50)
        self.assertEqual(first.assessment.observed_effective_exposure, 0.10)
        self.assertEqual(first.assessment.proposed_effective_exposure, 0.20)
        self.assertEqual(
            first.assessment.candidate_identity_sha256,
            self._candidate().candidate_sha256,
        )
        self.assertEqual(first.assessment.assessment_sha256, redacted_equivalent.assessment.assessment_sha256)
        self.assertEqual(len(first.decision.positions), 1)

    def test_mandate_requires_typed_candidate_and_still_assesses_once(self) -> None:
        decision = _decision(
            positions=(PositionTarget(symbol="BTCUSDT", target_weight=0.10),),
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
                scope="MEMBER",
                mandate_provenance=self._mandate(),
                market_data={},
                candidate_identity=None,
            )

        self.assertEqual(result.assessment.outcome, "REJECT")
        self.assertIn("missing_candidate_identity", result.assessment.reason_codes)
        self.assertEqual(result.decision.positions, ())
        self.assertEqual(result.decision.budgets, ())
        engine.assess.assert_called_once_with(decision, self._snapshot(), market_data={})

    def test_mandate_is_bound_to_exact_candidate_fields_and_digest(self) -> None:
        decision = _decision(
            positions=(PositionTarget(symbol="BTCUSDT", target_weight=0.10),),
        )
        base_candidate = self._candidate()
        cases = (
            (
                "strategy",
                self._candidate(strategy_profile="soxl_soxx_trend_income"),
                self._mandate(),
                "candidate_strategy_profile_mismatch",
            ),
            (
                "account",
                self._candidate(account_mode="smart_portfolio_v1"),
                self._mandate(),
                "candidate_account_mode_mismatch",
            ),
            (
                "candidate_digest",
                base_candidate,
                self._mandate(candidate_identity_sha256="f" * 64),
                "candidate_identity_digest_mismatch",
            ),
            (
                "input_manifest",
                self._candidate(input_manifest_sha256="f" * 64),
                self._mandate(),
                "candidate_input_manifest_digest_mismatch",
            ),
        )
        for name, candidate, mandate, reason_code in cases:
            engine = Mock()
            engine.assess.return_value = RiskAction(action="approve", reason="passed")
            with (
                self.subTest(name=name),
                patch("quant_platform_kit.risk.gate._utc_now", return_value=self._NOW),
                patch(
                    "quant_platform_kit.risk.gate.build_risk_engine",
                    return_value=engine,
                ),
            ):
                result = assess_with_evidence(
                    decision,
                    self._snapshot(),
                    scope="MEMBER",
                    mandate_provenance=mandate,
                    market_data={},
                    candidate_identity=candidate,
                )

            self.assertEqual(result.assessment.outcome, "REJECT")
            self.assertIn(reason_code, result.assessment.reason_codes)
            self.assertEqual(
                result.assessment.candidate_identity_sha256,
                candidate.candidate_sha256,
            )
            self.assertEqual(result.decision.positions, ())
            self.assertEqual(result.decision.budgets, ())
            engine.assess.assert_called_once_with(
                decision,
                self._snapshot(),
                market_data={},
            )

    def test_reduce_only_normalization_can_exit_over_cap_origin_once(self) -> None:
        candidate = self._candidate(strategy_profile="soxl_soxx_trend_income")
        mandate = self._mandate(
            candidate,
            product_leverage_factors={"BOXX": 1, "SOXX": 1},
            allowed_nonzero_assets=["BOXX", "SOXX"],
            product_caps={"BOXX": 0.50, "SOXX": 0.50},
            nominal_caps={"BOXX": 0.50, "SOXX": 0.50},
            loss_budget=0.01,
        )
        decision = _decision(
            positions=(PositionTarget(symbol="BOXX", target_weight=0.50),),
        )
        engine = Mock()
        engine.assess.return_value = RiskAction(action="approve", reason="passed")

        with (
            patch("quant_platform_kit.risk.gate._utc_now", return_value=self._NOW),
            patch("quant_platform_kit.risk.gate.build_risk_engine", return_value=engine),
        ):
            result = assess_with_evidence(
                decision,
                self._snapshot(observed_effective_exposure=1.0),
                scope="MEMBER",
                mandate_provenance=mandate,
                market_data={},
                candidate_identity=candidate,
                normalization_origin_weights={"BOXX": 1.0},
            )

        self.assertEqual(result.assessment.outcome, "APPROVE")
        self.assertEqual(
            result.assessment.contract_version,
            "qsl.risk_gate_assessment.v2",
        )
        self.assertEqual(result.assessment.proposed_effective_exposure, 0.50)
        self.assertIsNotNone(result.assessment.normalization_origin_digest_sha256)
        engine.assess.assert_called_once_with(
            decision,
            self._snapshot(observed_effective_exposure=1.0),
            market_data={},
        )

    def test_invalid_reduce_only_normalization_rejects_and_assesses_once(self) -> None:
        candidate = self._candidate(strategy_profile="soxl_soxx_trend_income")
        mandate = self._mandate(
            candidate,
            product_leverage_factors={"BOXX": 1, "SOXX": 1},
            allowed_nonzero_assets=["BOXX", "SOXX"],
            product_caps={"BOXX": 0.50, "SOXX": 0.50},
            nominal_caps={"BOXX": 0.50, "SOXX": 0.50},
            loss_budget=0.01,
        )
        decision = _decision(
            positions=(
                PositionTarget(symbol="BOXX", target_weight=0.40),
                PositionTarget(symbol="SOXX", target_weight=0.10),
            ),
        )
        engine = Mock()
        engine.assess.return_value = RiskAction(action="approve", reason="passed")

        with (
            patch("quant_platform_kit.risk.gate._utc_now", return_value=self._NOW),
            patch("quant_platform_kit.risk.gate.build_risk_engine", return_value=engine),
        ):
            result = assess_with_evidence(
                decision,
                self._snapshot(observed_effective_exposure=1.0),
                scope="MEMBER",
                mandate_provenance=mandate,
                market_data={},
                candidate_identity=candidate,
                normalization_origin_weights={"BOXX": 1.0},
            )

        self.assertEqual(result.assessment.outcome, "REJECT")
        self.assertIn(
            "invalid_reduce_only_normalization",
            result.assessment.reason_codes,
        )
        self.assertEqual(result.decision.positions, ())
        self.assertEqual(result.decision.budgets, ())
        engine.assess.assert_called_once_with(
            decision,
            self._snapshot(observed_effective_exposure=1.0),
            market_data={},
        )

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
                candidate_identity=self._candidate(),
            )

        self.assertEqual(result.assessment.outcome, "REJECT")
        self.assertEqual(result.decision.positions, ())
        self.assertEqual(result.decision.budgets, ())
        self.assertIn("effective_exposure_cap", result.assessment.reason_codes)
        engine.assess.assert_called_once()

    def test_invalid_scope_rejects_fail_closed(self) -> None:
        engine = Mock()
        engine.assess.return_value = RiskAction(action="approve", reason="passed")
        with (
            patch("quant_platform_kit.risk.gate._utc_now", return_value=self._NOW),
            patch("quant_platform_kit.risk.gate.build_risk_engine", return_value=engine),
        ):
            result = assess_with_evidence(
                _decision(positions=(PositionTarget(symbol="BTCUSDT", target_weight=0.10),)),
                self._snapshot(),
                scope="STRATEGY",
                mandate_provenance=self._mandate(),
                market_data={},
                candidate_identity=self._candidate(),
            )

        self.assertEqual(result.assessment.outcome, "REJECT")
        self.assertEqual(result.assessment.scope, "MEMBER")
        self.assertEqual(result.decision.positions, ())
        engine.assess.assert_called_once()

    def test_invalid_snapshot_still_assesses_once_and_keeps_static_reason(self) -> None:
        decision = _decision(
            positions=(PositionTarget(symbol="BTCUSDT", target_weight=0.10),),
        )
        engine = Mock()
        engine.assess.return_value = RiskAction(
            action="reject",
            reason="missing_portfolio_snapshot",
        )
        with (
            patch("quant_platform_kit.risk.gate._utc_now", return_value=self._NOW),
            patch("quant_platform_kit.risk.gate.build_risk_engine", return_value=engine),
        ):
            result = assess_with_evidence(
                decision,
                None,
                scope="MEMBER",
                mandate_provenance=self._mandate(),
                market_data={},
                candidate_identity=self._candidate(),
            )

        self.assertEqual(result.assessment.outcome, "REJECT")
        self.assertEqual(
            result.assessment.reason_codes,
            ("invalid_portfolio_snapshot",),
        )
        self.assertEqual(result.decision.positions, ())
        self.assertEqual(result.decision.budgets, ())
        engine.assess.assert_called_once_with(decision, None, market_data={})

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
                    candidate_identity=self._candidate(),
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
                    candidate_identity=self._candidate(),
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
                candidate_identity=self._candidate(),
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
                candidate_identity=self._candidate(),
            )
            mapping_result = assess_with_evidence(
                decision,
                self._snapshot(),
                scope="MEMBER",
                mandate_provenance=self._mandate(),
                market_data={},
                candidate_identity=self._candidate(),
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
                candidate_identity=self._candidate(),
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
                    candidate_identity=self._candidate(),
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
                    candidate_identity=self._candidate(),
                )

            self.assertEqual(result.assessment.outcome, "REJECT")
            self.assertEqual(result.decision.positions, ())
            self.assertEqual(result.decision.budgets, ())
            self.assertIn("budget_authority_exceeded", result.assessment.reason_codes)


class TqqqEtfOnlyResearchMandateTests(unittest.TestCase):
    _NOW = datetime(2026, 8, 4, 4, 28, tzinfo=timezone.utc)
    _MANDATE_ID = "tqqq_etf_only_research_v1"
    _STRATEGY_PROFILE = "tqqq_etf_only_single_strategy_research_v1"

    @classmethod
    def _candidate(cls) -> CandidateRiskIdentity:
        return CandidateRiskIdentity(
            strategy_profile=cls._STRATEGY_PROFILE,
            account_mode="single_strategy_account_v1",
            strategy_revision="b" * 40,
            runner_revision="c" * 40,
            config_sha256="d" * 64,
            input_manifest_sha256="e" * 64,
            authority_receipt_sha256="a" * 64,
        )

    @classmethod
    def _mandate(cls, **overrides: object) -> dict[str, object]:
        candidate = cls._candidate()
        mandate: dict[str, object] = {
            "mandate_id": cls._MANDATE_ID,
            "mandate_version": "v1",
            "authority_receipt_sha256": candidate.authority_receipt_sha256,
            "authority_scope": "RESEARCH_ONLY",
            "strategy_profile": candidate.strategy_profile,
            "account_mode": candidate.account_mode,
            "strategy_revision": candidate.strategy_revision,
            "runner_revision": candidate.runner_revision,
            "config_sha256": candidate.config_sha256,
            "input_manifest_sha256": candidate.input_manifest_sha256,
            "candidate_identity_sha256": candidate.candidate_sha256,
            "effective_at": "2026-08-04T04:27:55Z",
            "expires_at": "2026-09-03T15:59:59Z",
            "max_snapshot_age_seconds": 300,
            "effective_exposure_cap": 0.50,
            "loss_budget": 0.01,
            "loss_budget_equity_reference": "completed_session_equity",
            "product_caps": {"TQQQ": 0.15, "BOXX": 0.50},
            "nominal_caps": {"TQQQ": 0.15, "BOXX": 0.50},
            "product_effective_caps": {"TQQQ": 0.45, "BOXX": 0.50},
            "product_leverage_factors": {"TQQQ": 3, "BOXX": 1},
            "allowed_nonzero_assets": ["TQQQ", "BOXX"],
            "max_nonzero_assets": 1,
            "broker_margin_factor": 1,
            "margin_stacking": False,
            "borrowing": False,
            "shorting": False,
            "income_sleeve_enabled": False,
            "option_overlay_enabled": False,
            "precommitted_executable_stop_distance": 0.05,
            "max_consecutive_completed_losing_exits": 5,
            "source_revision": "f" * 40,
        }
        mandate.update(overrides)
        return mandate

    @staticmethod
    def _snapshot(**overrides: object) -> dict[str, object]:
        snapshot: dict[str, object] = {
            "as_of": "2026-08-04T04:27:55Z",
            "observed_effective_exposure": 0.0,
            "total_equity": 100_000.0,
        }
        snapshot.update(overrides)
        return snapshot

    @classmethod
    def _risk_state(cls, **overrides: object) -> dict[str, object]:
        state: dict[str, object] = {
            "as_of": "2026-08-04T04:27:55Z",
            "mandate_id": cls._MANDATE_ID,
            "candidate_identity_sha256": cls._candidate().candidate_sha256,
            "stop_loss_distance": 0.05,
            "stop_intent_ready": True,
            "tqqq_entry_fill_identity_sha256": "1" * 64,
            "stop_entry_fill_identity_sha256": "1" * 64,
            "consecutive_completed_losing_exits": 0,
            "account_drawdown_fraction": 0.05,
            "drawdown_scalar": 1.0,
        }
        state.update(overrides)
        return state

    def _assess(
        self,
        decision: StrategyDecision,
        *,
        mandate: dict[str, object] | None = None,
        risk_state: dict[str, object] | None = None,
        snapshot: dict[str, object] | None = None,
        origin: dict[str, float] | None = None,
    ) -> tuple[object, Mock]:
        engine = Mock()
        engine.assess.return_value = RiskAction(action="approve", reason="passed")
        with (
            patch("quant_platform_kit.risk.gate._utc_now", return_value=self._NOW),
            patch("quant_platform_kit.risk.gate.build_risk_engine", return_value=engine),
        ):
            result = assess_with_evidence(
                decision,
                snapshot or self._snapshot(),
                scope="MEMBER",
                mandate_provenance=mandate or self._mandate(),
                market_data={},
                candidate_identity=self._candidate(),
                normalization_origin_weights=origin,
                risk_control_state=(
                    self._risk_state() if risk_state is None else risk_state
                ),
            )
        return result, engine

    def test_valid_research_mandate_approves_evidence_but_never_execution(self) -> None:
        decision = _decision(
            positions=(PositionTarget(symbol="TQQQ", target_weight=0.15),)
        )
        result, engine = self._assess(decision)

        self.assertEqual(result.assessment.outcome, "APPROVE")
        self.assertEqual(result.assessment.mandate_id, self._MANDATE_ID)
        self.assertAlmostEqual(result.assessment.proposed_effective_exposure, 0.45)
        self.assertEqual(result.assessment.stop_loss_distance, 0.05)
        self.assertTrue(result.assessment.stop_intent_ready)
        self.assertFalse(result.assessment.strategy_breaker_triggered)
        self.assertFalse(result.assessment.account_breaker_triggered)
        self.assertEqual(result.assessment.account_drawdown_fraction, 0.05)
        self.assertEqual(result.assessment.drawdown_scalar, 1.0)
        self.assertEqual(len(result.assessment.risk_control_state_digest_sha256), 64)
        self.assertFalse(result.assessment.execution_authorized)
        self.assertEqual(result.decision.positions, decision.positions)
        engine.assess.assert_called_once_with(decision, self._snapshot(), market_data={})

    def test_assessment_identity_is_bound_to_risk_control_state(self) -> None:
        decision = _decision(
            positions=(PositionTarget(symbol="TQQQ", target_weight=0.15),)
        )
        first, first_engine = self._assess(
            decision,
            risk_state=self._risk_state(account_drawdown_fraction=0.04),
        )
        second, second_engine = self._assess(
            decision,
            risk_state=self._risk_state(account_drawdown_fraction=0.05),
        )

        self.assertEqual(first.assessment.outcome, "APPROVE")
        self.assertEqual(second.assessment.outcome, "APPROVE")
        self.assertEqual(
            first.assessment.decision_digest_sha256,
            second.assessment.decision_digest_sha256,
        )
        self.assertNotEqual(
            first.assessment.risk_control_state_digest_sha256,
            second.assessment.risk_control_state_digest_sha256,
        )
        self.assertNotEqual(
            first.assessment.assessment_sha256,
            second.assessment.assessment_sha256,
        )
        first_engine.assess.assert_called_once()
        second_engine.assess.assert_called_once()

    def test_exact_mandate_values_and_exclusions_are_fail_closed(self) -> None:
        decision = _decision(
            positions=(PositionTarget(symbol="TQQQ", target_weight=0.15),)
        )
        invalid_cases = (
            {"authority_scope": "PAPER"},
            {"strategy_profile": "other"},
            {"account_mode": "smart_portfolio"},
            {"effective_exposure_cap": 0.51},
            {"loss_budget": 0.011},
            {"loss_budget_equity_reference": "current_equity"},
            {"product_caps": {"TQQQ": 0.16, "BOXX": 0.50}},
            {"product_effective_caps": {"TQQQ": 0.46, "BOXX": 0.50}},
            {"product_leverage_factors": {"TQQQ": 2, "BOXX": 1}},
            {"allowed_nonzero_assets": ["TQQQ", "BOXX", "QQQ"]},
            {"max_nonzero_assets": 2},
            {"broker_margin_factor": 2},
            {"margin_stacking": True},
            {"borrowing": True},
            {"shorting": True},
            {"income_sleeve_enabled": True},
            {"option_overlay_enabled": True},
            {"precommitted_executable_stop_distance": 0.06},
            {"max_consecutive_completed_losing_exits": 6},
        )
        for overrides in invalid_cases:
            with self.subTest(overrides=overrides):
                result, engine = self._assess(
                    decision,
                    mandate=self._mandate(**overrides),
                )
                self.assertEqual(result.assessment.outcome, "REJECT")
                self.assertIn(
                    "invalid_tqqq_research_mandate",
                    result.assessment.reason_codes,
                )
                self.assertEqual(result.decision.positions, ())
                engine.assess.assert_called_once()

    def test_missing_stale_nonfinite_or_mismatched_control_state_rejects(self) -> None:
        decision = _decision(
            positions=(PositionTarget(symbol="TQQQ", target_weight=0.15),)
        )
        invalid_cases = (
            {},
            self._risk_state(as_of="2026-08-04T04:17:55Z"),
            self._risk_state(account_drawdown_fraction=float("nan")),
            self._risk_state(candidate_identity_sha256="0" * 64),
            self._risk_state(mandate_id="other"),
            self._risk_state(stop_loss_distance=0.06),
            self._risk_state(stop_intent_ready=False),
            self._risk_state(stop_entry_fill_identity_sha256="2" * 64),
            self._risk_state(drawdown_scalar=0.50),
        )
        for risk_state in invalid_cases:
            with self.subTest(risk_state=risk_state):
                result, engine = self._assess(decision, risk_state=risk_state)
                self.assertEqual(result.assessment.outcome, "REJECT")
                self.assertEqual(result.decision.positions, ())
                engine.assess.assert_called_once()

    def test_drawdown_and_strategy_breaker_boundaries(self) -> None:
        decision = _decision(
            positions=(PositionTarget(symbol="TQQQ", target_weight=0.15),)
        )
        approved_cases = (
            (
                decision,
                self._risk_state(account_drawdown_fraction=0.05, drawdown_scalar=1.0),
            ),
            (
                _decision(
                    positions=(PositionTarget(symbol="TQQQ", target_weight=0.10),)
                ),
                self._risk_state(
                    account_drawdown_fraction=0.050001,
                    drawdown_scalar=0.50,
                ),
            ),
            (
                _decision(
                    positions=(PositionTarget(symbol="TQQQ", target_weight=0.10),)
                ),
                self._risk_state(
                    account_drawdown_fraction=0.10,
                    drawdown_scalar=0.50,
                ),
            ),
            (decision, self._risk_state(consecutive_completed_losing_exits=4)),
        )
        for approved_decision, state in approved_cases:
            with self.subTest(state=state):
                result, engine = self._assess(
                    approved_decision,
                    risk_state=state,
                )
                self.assertEqual(result.assessment.outcome, "APPROVE")
                engine.assess.assert_called_once()

        breaker_cases = (
            (
                self._risk_state(consecutive_completed_losing_exits=5),
                "strategy_breaker_triggered",
            ),
            (
                self._risk_state(
                    account_drawdown_fraction=0.100001,
                    drawdown_scalar=0.0,
                ),
                "account_breaker_triggered",
            ),
        )
        for state, reason in breaker_cases:
            with self.subTest(state=state):
                result, engine = self._assess(decision, risk_state=state)
                self.assertEqual(result.assessment.outcome, "REJECT")
                self.assertIn(reason, result.assessment.reason_codes)
                self.assertEqual(result.decision.positions, ())
                engine.assess.assert_called_once()

    def test_single_strategy_rule_and_product_caps_reject_excess(self) -> None:
        invalid_decisions = (
            _decision(
                positions=(
                    PositionTarget(symbol="TQQQ", target_weight=0.10),
                    PositionTarget(symbol="BOXX", target_weight=0.10),
                )
            ),
            _decision(positions=(PositionTarget(symbol="TQQQ", target_weight=0.151),)),
            _decision(positions=(PositionTarget(symbol="BOXX", target_weight=0.201),)),
            _decision(positions=(PositionTarget(symbol="BOXX", target_weight=0.501),)),
            _decision(positions=(PositionTarget(symbol="QQQ", target_weight=0.10),)),
        )
        for decision in invalid_decisions:
            with self.subTest(decision=decision):
                result, engine = self._assess(decision)
                self.assertEqual(result.assessment.outcome, "REJECT")
                self.assertEqual(result.decision.positions, ())
                engine.assess.assert_called_once()

    def test_over_cap_normalization_must_reduce_to_cash_and_binds_origin(self) -> None:
        snapshot = self._snapshot(observed_effective_exposure=0.60)
        cash_result, cash_engine = self._assess(
            _decision(),
            snapshot=snapshot,
            origin={"TQQQ": 0.20},
        )
        partial_result, partial_engine = self._assess(
            _decision(positions=(PositionTarget(symbol="TQQQ", target_weight=0.10),)),
            snapshot=snapshot,
            origin={"TQQQ": 0.20},
        )

        self.assertEqual(cash_result.assessment.outcome, "APPROVE")
        self.assertEqual(len(cash_result.assessment.normalization_origin_digest_sha256), 64)
        self.assertEqual(partial_result.assessment.outcome, "REJECT")
        self.assertIn(
            "invalid_reduce_only_normalization",
            partial_result.assessment.reason_codes,
        )
        cash_engine.assess.assert_called_once()
        partial_engine.assess.assert_called_once()


class GlobalEtfRotationResearchMandateTests(unittest.TestCase):
    _NOW = datetime(2026, 8, 9, 2, 0, tzinfo=timezone.utc)
    _MANDATE_ID = "global_etf_rotation_etf_only_research_v1"
    _STRATEGY_PROFILE = "global_etf_rotation_etf_only_single_strategy_research_v1"
    _ACCOUNT_MODE = "single_strategy_research_v1"
    _ALLOWED_ASSETS = (
        "EWY",
        "EWT",
        "INDA",
        "FXI",
        "EWJ",
        "VGK",
        "VOO",
        "XLK",
        "SMH",
        "GLD",
        "SLV",
        "USO",
        "DBA",
        "XLE",
        "XLF",
        "ITA",
        "XLP",
        "XLU",
        "XLV",
        "IHI",
        "VNQ",
        "KRE",
        "BIL",
    )

    @classmethod
    def _candidate(cls) -> CandidateRiskIdentity:
        return CandidateRiskIdentity(
            strategy_profile=cls._STRATEGY_PROFILE,
            account_mode=cls._ACCOUNT_MODE,
            strategy_revision="1" * 40,
            runner_revision="2" * 40,
            config_sha256="3" * 64,
            input_manifest_sha256="4" * 64,
            authority_receipt_sha256="5" * 64,
        )

    @classmethod
    def _mandate(cls, **overrides: object) -> dict[str, object]:
        candidate = cls._candidate()
        caps = {symbol: 0.50 for symbol in cls._ALLOWED_ASSETS}
        mandate: dict[str, object] = {
            "mandate_id": cls._MANDATE_ID,
            "mandate_version": "v1",
            "authority_receipt_sha256": candidate.authority_receipt_sha256,
            "authority_scope": "RESEARCH_ONLY",
            "strategy_profile": candidate.strategy_profile,
            "account_mode": candidate.account_mode,
            "strategy_revision": candidate.strategy_revision,
            "runner_revision": candidate.runner_revision,
            "config_sha256": candidate.config_sha256,
            "input_manifest_sha256": candidate.input_manifest_sha256,
            "candidate_identity_sha256": candidate.candidate_sha256,
            "effective_at": "2026-08-09T01:59:55Z",
            "expires_at": "2026-09-08T01:59:55Z",
            "max_snapshot_age_seconds": 300,
            "effective_exposure_cap": 0.50,
            "loss_budget": 0.01,
            "loss_budget_equity_reference": "completed_session_equity",
            "product_caps": caps,
            "nominal_caps": caps,
            "product_effective_caps": caps,
            "product_leverage_factors": {
                symbol: 1 for symbol in cls._ALLOWED_ASSETS
            },
            "allowed_nonzero_assets": list(cls._ALLOWED_ASSETS),
            "max_nonzero_assets": 2,
            "broker_margin_factor": 1,
            "margin_stacking": False,
            "borrowing": False,
            "shorting": False,
            "income_sleeve_enabled": False,
            "option_overlay_enabled": False,
            "ai_overlay_enabled": False,
            "market_regime_overlay_enabled": False,
            "precommitted_executable_stop_distance": 0.05,
            "stop_fill_policy": "gap_aware_min_open_or_stop_v1",
            "max_consecutive_completed_losing_exits": 5,
            "source_revision": "6" * 40,
        }
        mandate.update(overrides)
        return mandate

    @staticmethod
    def _snapshot(**overrides: object) -> dict[str, object]:
        snapshot: dict[str, object] = {
            "as_of": "2026-08-09T01:59:55Z",
            "observed_effective_exposure": 0.0,
            "total_equity": 100_000.0,
        }
        snapshot.update(overrides)
        return snapshot

    @classmethod
    def _risk_state(
        cls,
        *symbols: str,
        position_stop_states: dict[str, object] | None = None,
        **overrides: object,
    ) -> dict[str, object]:
        stops = {
            symbol: {
                "stop_intent_ready": True,
                "entry_fill_identity_sha256": str(index + 1) * 64,
                "stop_entry_fill_identity_sha256": str(index + 1) * 64,
            }
            for index, symbol in enumerate(symbols)
        }
        state: dict[str, object] = {
            "as_of": "2026-08-09T01:59:55Z",
            "mandate_id": cls._MANDATE_ID,
            "candidate_identity_sha256": cls._candidate().candidate_sha256,
            "stop_loss_distance": 0.05,
            "stop_fill_policy": "gap_aware_min_open_or_stop_v1",
            "position_stop_states": (
                stops if position_stop_states is None else position_stop_states
            ),
            "consecutive_completed_losing_exits": 0,
            "account_drawdown_fraction": 0.05,
            "drawdown_scalar": 1.0,
        }
        state.update(overrides)
        return state

    def _assess(
        self,
        decision: StrategyDecision,
        *,
        mandate: dict[str, object] | None = None,
        risk_state: dict[str, object] | None = None,
        snapshot: dict[str, object] | None = None,
        engine_action: str = "approve",
        engine_error: Exception | None = None,
    ) -> tuple[object, Mock]:
        active_symbols = tuple(
            position.symbol
            for position in decision.positions
            if (position.target_weight or 0.0) > 0.0
        )
        engine = Mock()
        if engine_error is not None:
            engine.assess.side_effect = engine_error
        else:
            engine.assess.return_value = RiskAction(
                action=engine_action,
                reason="test",
            )
        actual_snapshot = snapshot if snapshot is not None else self._snapshot()
        with (
            patch("quant_platform_kit.risk.gate._utc_now", return_value=self._NOW),
            patch("quant_platform_kit.risk.gate.build_risk_engine", return_value=engine),
        ):
            result = assess_with_evidence(
                decision,
                actual_snapshot,
                scope="MEMBER",
                mandate_provenance=(
                    mandate if mandate is not None else self._mandate()
                ),
                market_data={},
                candidate_identity=self._candidate(),
                risk_control_state=(
                    risk_state
                    if risk_state is not None
                    else self._risk_state(*active_symbols)
                ),
            )
        engine.assess.assert_called_once_with(
            decision,
            actual_snapshot,
            market_data={},
        )
        return result, engine

    @staticmethod
    def _two_position_decision(
        first: float = 0.15,
        second: float = 0.05,
    ) -> StrategyDecision:
        return _decision(
            positions=(
                PositionTarget(symbol="XLK", target_weight=first),
                PositionTarget(symbol="BIL", target_weight=second),
            )
        )

    def test_valid_research_decision_approves_but_never_authorizes_execution(
        self,
    ) -> None:
        decision = self._two_position_decision()

        result, _engine = self._assess(decision)

        self.assertEqual(result.assessment.outcome, "APPROVE")
        self.assertEqual(result.assessment.mandate_id, self._MANDATE_ID)
        self.assertEqual(result.assessment.proposed_effective_exposure, 0.20)
        self.assertEqual(result.assessment.stop_loss_distance, 0.05)
        self.assertTrue(result.assessment.stop_intent_ready)
        self.assertFalse(result.assessment.strategy_breaker_triggered)
        self.assertFalse(result.assessment.account_breaker_triggered)
        self.assertEqual(result.assessment.drawdown_scalar, 1.0)
        self.assertEqual(len(result.assessment.risk_control_state_digest_sha256), 64)
        self.assertFalse(result.assessment.execution_authorized)
        self.assertEqual(result.decision.positions, decision.positions)

    def test_exact_mandate_shape_is_fail_closed(self) -> None:
        decision = self._two_position_decision()
        caps = {symbol: 0.50 for symbol in self._ALLOWED_ASSETS}
        invalid_cases = (
            {"authority_scope": "PAPER"},
            {"strategy_profile": "global_etf_rotation"},
            {"account_mode": "single_strategy_account_v1"},
            {"effective_exposure_cap": 0.51},
            {"loss_budget": 0.011},
            {"loss_budget_equity_reference": "current_equity"},
            {"product_caps": {**caps, "XLK": 0.51}},
            {"product_leverage_factors": {"XLK": 1, "BIL": 1}},
            {"allowed_nonzero_assets": [*self._ALLOWED_ASSETS, "SPY"]},
            {"max_nonzero_assets": 3},
            {"broker_margin_factor": 2},
            {"margin_stacking": True},
            {"borrowing": True},
            {"shorting": True},
            {"income_sleeve_enabled": True},
            {"option_overlay_enabled": True},
            {"ai_overlay_enabled": True},
            {"market_regime_overlay_enabled": True},
            {"precommitted_executable_stop_distance": 0.06},
            {"stop_fill_policy": "stop_price_only"},
            {"max_consecutive_completed_losing_exits": 6},
            {"expires_at": "2027-08-09T01:59:55Z"},
        )
        for overrides in invalid_cases:
            with self.subTest(overrides=overrides):
                result, _engine = self._assess(
                    decision,
                    mandate=self._mandate(**overrides),
                )
                self.assertEqual(result.assessment.outcome, "REJECT")
                self.assertIn(
                    "invalid_global_etf_research_mandate",
                    result.assessment.reason_codes,
                )
                self.assertEqual(result.decision.positions, ())

    def test_position_count_assets_caps_and_aggregate_risk_budget_fail_closed(
        self,
    ) -> None:
        cases = (
            (
                _decision(
                    positions=(
                        PositionTarget(symbol="XLK", target_weight=0.05),
                        PositionTarget(symbol="BIL", target_weight=0.05),
                        PositionTarget(symbol="GLD", target_weight=0.05),
                    )
                ),
                None,
                "single_strategy_position_count",
            ),
            (
                _decision(
                    positions=(PositionTarget(symbol="SPY", target_weight=0.10),)
                ),
                None,
                "asset_not_authorized",
            ),
            (
                _decision(
                    positions=(PositionTarget(symbol="XLK", target_weight=0.501),)
                ),
                None,
                "product_exposure_cap",
            ),
            (
                self._two_position_decision(first=0.151, second=0.05),
                None,
                "risk_budget_exposure_cap",
            ),
            (
                self._two_position_decision(first=0.06, second=0.05),
                self._risk_state(
                    "XLK",
                    "BIL",
                    account_drawdown_fraction=0.050001,
                    drawdown_scalar=0.50,
                ),
                "risk_budget_exposure_cap",
            ),
        )
        for decision, state, reason in cases:
            with self.subTest(reason=reason):
                result, _engine = self._assess(decision, risk_state=state)
                self.assertEqual(result.assessment.outcome, "REJECT")
                self.assertIn(reason, result.assessment.reason_codes)
                self.assertEqual(result.decision.positions, ())

    def test_per_position_gap_aware_stop_state_is_fail_closed(self) -> None:
        decision = self._two_position_decision()
        valid_stops = self._risk_state("XLK", "BIL")["position_stop_states"]
        assert isinstance(valid_stops, dict)
        mismatched_fill = {
            **valid_stops,
            "XLK": {
                **valid_stops["XLK"],
                "stop_entry_fill_identity_sha256": "9" * 64,
            },
        }
        not_ready = {
            **valid_stops,
            "BIL": {**valid_stops["BIL"], "stop_intent_ready": False},
        }
        invalid_cases = (
            {},
            self._risk_state("XLK", "BIL", as_of="2026-08-09T01:49:55Z"),
            self._risk_state("XLK", "BIL", as_of="2026-08-09T02:00:01Z"),
            self._risk_state(
                "XLK",
                "BIL",
                account_drawdown_fraction=float("nan"),
            ),
            self._risk_state("XLK", "BIL", candidate_identity_sha256="0" * 64),
            self._risk_state("XLK", "BIL", mandate_id="other"),
            self._risk_state("XLK", "BIL", stop_loss_distance=0.06),
            self._risk_state("XLK", "BIL", stop_fill_policy="stop_price_only"),
            self._risk_state(
                "XLK",
                position_stop_states={"XLK": valid_stops["XLK"]},
            ),
            self._risk_state(
                "XLK",
                "BIL",
                position_stop_states=mismatched_fill,
            ),
            self._risk_state("XLK", "BIL", position_stop_states=not_ready),
            self._risk_state("XLK", "BIL", drawdown_scalar=0.50),
        )
        for state in invalid_cases:
            with self.subTest(state=state):
                result, _engine = self._assess(decision, risk_state=state)
                self.assertEqual(result.assessment.outcome, "REJECT")
                self.assertEqual(result.decision.positions, ())

    def test_drawdown_and_strategy_breaker_boundaries(self) -> None:
        approved_cases = (
            (
                self._two_position_decision(),
                self._risk_state("XLK", "BIL"),
            ),
            (
                self._two_position_decision(first=0.075, second=0.025),
                self._risk_state(
                    "XLK",
                    "BIL",
                    account_drawdown_fraction=0.050001,
                    drawdown_scalar=0.50,
                ),
            ),
            (
                self._two_position_decision(first=0.075, second=0.025),
                self._risk_state(
                    "XLK",
                    "BIL",
                    account_drawdown_fraction=0.10,
                    drawdown_scalar=0.50,
                ),
            ),
            (
                self._two_position_decision(),
                self._risk_state(
                    "XLK",
                    "BIL",
                    consecutive_completed_losing_exits=4,
                ),
            ),
        )
        for decision, state in approved_cases:
            with self.subTest(state=state):
                result, _engine = self._assess(decision, risk_state=state)
                self.assertEqual(result.assessment.outcome, "APPROVE")

        breaker_cases = (
            (
                self._risk_state(
                    "XLK",
                    "BIL",
                    consecutive_completed_losing_exits=5,
                ),
                "strategy_breaker_triggered",
            ),
            (
                self._risk_state(
                    "XLK",
                    "BIL",
                    account_drawdown_fraction=0.100001,
                    drawdown_scalar=0.0,
                ),
                "account_breaker_triggered",
            ),
        )
        for state, reason in breaker_cases:
            with self.subTest(reason=reason):
                result, _engine = self._assess(
                    self._two_position_decision(),
                    risk_state=state,
                )
                self.assertEqual(result.assessment.outcome, "REJECT")
                self.assertIn(reason, result.assessment.reason_codes)
                self.assertEqual(result.decision.positions, ())

    def test_engine_is_exactly_once_for_static_reject_error_and_nonapprove(
        self,
    ) -> None:
        decision = self._two_position_decision()
        static_reject, _static_engine = self._assess(
            decision,
            mandate=self._mandate(authority_scope="PAPER"),
            engine_error=RuntimeError("redacted"),
        )
        engine_error, _error_engine = self._assess(
            decision,
            engine_error=RuntimeError("redacted"),
        )
        nonapprove, _nonapprove_engine = self._assess(
            decision,
            engine_action="reject",
        )

        self.assertEqual(static_reject.assessment.outcome, "REJECT")
        self.assertNotIn("risk_engine_error", static_reject.assessment.reason_codes)
        self.assertIn("risk_engine_error", engine_error.assessment.reason_codes)
        self.assertIn("risk_engine_non_approve", nonapprove.assessment.reason_codes)
        self.assertFalse(static_reject.assessment.execution_authorized)
        self.assertFalse(engine_error.assessment.execution_authorized)
        self.assertFalse(nonapprove.assessment.execution_authorized)


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
            portfolio_snapshot=_portfolio_snapshot(),
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
            portfolio_snapshot=_portfolio_snapshot(),
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
