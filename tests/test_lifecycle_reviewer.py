"""Tests for strategy_lifecycle.ai_reviewer — rule-based review logic."""

from __future__ import annotations

from datetime import date
import unittest

from quant_platform_kit.strategy_lifecycle.contracts import (
    BacktestResult,
    DriftResult,
    DriftStatus,
    OptimizationProposal,
)
from quant_platform_kit.strategy_lifecycle.ai_reviewer import (
    AiReviewVerdict,
    _resolve_multi_consensus,
    review_proposal,
    llm_enhanced_review,
)


def _make_proposal(
    *,
    current_params: dict | None = None,
    proposed_params: dict | None = None,
    proposed_metrics: BacktestResult | None = None,
    improvement: float = 0.10,
    confidence: float = 0.85,
    recommendation: str = "promote",
    regressing: tuple[str, ...] = (),
) -> OptimizationProposal:
    """Build an OptimizationProposal with explicit parameters."""
    return OptimizationProposal(
        strategy_profile="t", domain="us",
        current_params=current_params or {},
        proposed_params=proposed_params or {},
        current_metrics=BacktestResult(
            strategy_profile="t", domain="us",
            param_set_id="cur", params=current_params or {},
        ),
        proposed_metrics=proposed_metrics,
        improvement_score=improvement,
        confidence=confidence,
        recommendation=recommendation,
        regressing_dimensions=regressing,
    )


class AiReviewerTests(unittest.TestCase):

    def test_candidate_readiness_requires_both_independent_reviewers(self) -> None:
        proposal = _make_proposal()
        base = review_proposal(proposal)
        primary = AiReviewVerdict(
            proposal=proposal,
            verdict="approve",
            overall_score=0.9,
            dimensions=(),
            summary="primary approves",
            requires_human=True,
            confidence=0.95,
        )

        result = _resolve_multi_consensus(proposal, base, primary, None, None)

        self.assertEqual(result.verdict, "escalate")
        self.assertEqual(result.recommended_action, "escalate")
        self.assertIn("DUAL_REVIEW_INCOMPLETE", result.summary)

    def test_two_independent_approvals_can_become_candidate_ready(self) -> None:
        # This positive case represents a numerically valid research proposal.
        proposal = _make_proposal(proposed_metrics=BacktestResult(
            strategy_profile="t", domain="us", param_set_id="p", params={},
            sharpe_ratio=1.5, max_drawdown=-0.12, observation_count=500,
        ))
        base = review_proposal(proposal)
        primary = AiReviewVerdict(
            proposal=proposal,
            verdict="approve",
            overall_score=0.9,
            dimensions=(),
            summary="primary approves",
            requires_human=True,
            confidence=0.95,
        )
        secondary = AiReviewVerdict(
            proposal=proposal,
            verdict="approve",
            overall_score=0.8,
            dimensions=(),
            summary="secondary approves",
            requires_human=True,
            confidence=0.9,
        )

        result = _resolve_multi_consensus(proposal, base, primary, secondary, None)

        self.assertEqual(result.verdict, "approve")
        self.assertEqual(result.recommended_action, "candidate_ready")

    # ── Approve cases ─────────────────────────────────────────────

    def test_good_proposal_approves(self) -> None:
        p = _make_proposal(
            proposed_params={"n": 4},
            proposed_metrics=BacktestResult(
                strategy_profile="t", domain="us",
                param_set_id="p", params={"n": 4},
                sharpe_ratio=1.5, calmar_ratio=0.9, max_drawdown=-0.12,
                cagr=0.18, volatility=0.20, observation_count=500,
                oos_sharpe=1.2, walk_forward_stability=0.75,
            ),
        )
        v = review_proposal(p)
        self.assertEqual(v.verdict, "approve")
        self.assertTrue(v.requires_human)

    def test_excellent_proposal_high_score(self) -> None:
        p = _make_proposal(
            proposed_params={"n": 5},
            proposed_metrics=BacktestResult(
                strategy_profile="t", domain="us",
                param_set_id="p", params={"n": 5},
                sharpe_ratio=2.0, calmar_ratio=1.2, max_drawdown=-0.05,
                cagr=0.25, volatility=0.15, observation_count=800,
                oos_sharpe=1.8, walk_forward_stability=0.9,
            ),
            confidence=0.95,
        )
        v = review_proposal(p)
        self.assertEqual(v.verdict, "approve")
        self.assertGreaterEqual(v.overall_score, 0.75)

    # ── Escalate cases ────────────────────────────────────────────

    def test_marginal_proposal_escalates(self) -> None:
        """Only ~2 dims pass + overall ~0.35 → escalate."""
        p = _make_proposal(
            proposed_params={"n": 2},
            proposed_metrics=BacktestResult(
                strategy_profile="t", domain="us",
                param_set_id="p", params={"n": 2},
                sharpe_ratio=0.2, calmar_ratio=0.08, max_drawdown=-0.42,
                cagr=0.01, volatility=0.35, observation_count=45,
                oos_sharpe=-0.3, walk_forward_stability=0.3,
            ),
            improvement=0.0, confidence=0.2, recommendation="needs_review",
        )
        v = review_proposal(p)
        self.assertEqual(v.verdict, "escalate")
        self.assertTrue(v.requires_human)

    def test_drift_context_escalates(self) -> None:
        """Drift context + marginal proposal → escalate."""
        p = _make_proposal(
            current_params={"a": 1.0}, proposed_params={"a": 1.8},
            proposed_metrics=BacktestResult(
                strategy_profile="t", domain="us",
                param_set_id="p", params={"a": 1.8},
                sharpe_ratio=0.3, calmar_ratio=0.1, max_drawdown=-0.35,
                cagr=0.02, volatility=0.30, observation_count=35,
                oos_sharpe=-0.1, walk_forward_stability=0.3,
            ),
            improvement=0.0, confidence=0.2, recommendation="needs_review",
            regressing=("sharpe", "calmar", "max_dd"),
        )
        drift = DriftResult(
            strategy_profile="t", domain="us", as_of=date(2026, 6, 1),
            drift_score=0.7, status=DriftStatus.CRITICAL,
        )
        v = review_proposal(p, drift=drift)
        self.assertEqual(v.verdict, "escalate")

    # ── Reject cases ──────────────────────────────────────────────

    def test_bad_proposal_rejected(self) -> None:
        """0-1 dims pass, overall < 0.35 → reject."""
        p = _make_proposal(
            current_params={"n": 1.0}, proposed_params={"n": 10.0},
            proposed_metrics=BacktestResult(
                strategy_profile="t", domain="us",
                param_set_id="p", params={"n": 10.0},
                sharpe_ratio=-0.5, calmar_ratio=-0.2, max_drawdown=-0.75,
                cagr=-0.10, volatility=0.80, observation_count=5,
                oos_sharpe=-1.0, walk_forward_stability=0.1,
            ),
            improvement=-0.1, confidence=0.02, recommendation="reject",
            regressing=("a", "b", "c", "d", "e"),
        )
        v = review_proposal(p)
        self.assertEqual(v.verdict, "reject")

    def test_no_metrics_rejected_or_escalated(self) -> None:
        """No proposed metrics → can't be approve."""
        p = _make_proposal(
            proposed_params={}, proposed_metrics=None,
            improvement=0.0, confidence=0.0, recommendation="reject",
        )
        v = review_proposal(p)
        self.assertIn(v.verdict, ("reject", "escalate"))

    # ── Dry run ──────────────────────────────────────────────────

    def test_dry_run_returns_rule_based_result(self) -> None:
        """Dry run should not call AI, return rule-based escalate."""
        p = _make_proposal(
            current_params={"a": 1.0}, proposed_params={"a": 3.0},
            proposed_metrics=BacktestResult(
                strategy_profile="t", domain="us",
                param_set_id="p", params={"a": 3.0},
                sharpe_ratio=0.1, max_drawdown=-0.50, observation_count=10,
                oos_sharpe=-0.3, walk_forward_stability=0.2,
            ),
            improvement=0.0, confidence=0.1, recommendation="reject",
            regressing=("s", "m"),
        )
        v = llm_enhanced_review(p, dry_run=True)
        self.assertEqual(v.verdict, "escalate")

    # ── Result structure ──────────────────────────────────────────

    def test_verdict_has_all_fields(self) -> None:
        p = _make_proposal(
            proposed_params={"n": 4},
            proposed_metrics=BacktestResult(
                strategy_profile="t", domain="us",
                param_set_id="p", params={"n": 4},
                sharpe_ratio=1.5, max_drawdown=-0.12, observation_count=500,
            ),
        )
        v = review_proposal(p)
        d = v.to_dict()
        self.assertIn("verdict", d)
        self.assertIn("dimensions", d)
        self.assertIn("requires_human", d)
        self.assertIn("overall_score", d)
        self.assertEqual(len(d["dimensions"]), 5)


class ReviewBoundaryTests(unittest.TestCase):
    def setUp(self):
        from dataclasses import replace
        self.replace = replace
        self.metrics = BacktestResult(
            strategy_profile="t", domain="us", param_set_id="p", params={},
            sharpe_ratio=1.5, max_drawdown=-0.12, observation_count=500,
        )
        self.proposal = _make_proposal(proposed_metrics=self.metrics)

    def result(self, provider, **payload):
        import json
        from quant_platform_kit.strategy_lifecycle.ai_provider import AiCallResult
        return AiCallResult(provider=provider, success=True, output=json.dumps(payload))

    def parse(self, **payload):
        from quant_platform_kit.strategy_lifecycle.ai_reviewer import _parse_reviewer_result
        return _parse_reviewer_result(self.proposal, [self.result("GPT", **payload)], "GPT")

    def test_gateway_aliases_and_legacy_labels(self):
        from quant_platform_kit.strategy_lifecycle.ai_reviewer import _parse_reviewer_result
        for provider, label in [("openai", "GPT"), ("gpt", "GPT"), ("GPT", "GPT"),
                                ("anthropic", "Claude"), ("claude", "Claude"), ("Claude", "Claude")]:
            with self.subTest(provider=provider):
                parsed = _parse_reviewer_result(self.proposal, [self.result(
                    provider, verdict="approve", overall_score=0.8)], label)
                self.assertIsNotNone(parsed)
                self.assertEqual(parsed.confidence, 0.5)
                self.assertTrue(parsed.requires_human)
        self.assertIsNone(_parse_reviewer_result(self.proposal, [self.result(
            "openai", verdict="approve", overall_score=0.8)], "Claude"))

    def test_gateway_response_flows_through_client_into_dual_review(self):
        from types import SimpleNamespace
        from unittest.mock import Mock, patch
        from quant_platform_kit.strategy_lifecycle import ai_provider
        from quant_platform_kit.strategy_lifecycle.ai_reviewer import _parse_reviewer_result
        config = ai_provider.AiServiceConfig.safety(reviewers=[
            ai_provider.AiProviderConfig.claude(), ai_provider.AiProviderConfig.gpt(),
        ])
        gateway = Mock()
        gateway.review.return_value = SimpleNamespace(results=[
            self.result("anthropic", verdict="approve", overall_score=0.8, confidence=0.9),
            self.result("openai", verdict="approve", overall_score=0.9, confidence=0.9),
        ])
        with (patch.object(ai_provider, "_HAS_GATEWAY_CLIENT", True),
              patch.object(ai_provider, "GatewayConfig", create=True),
              patch.object(ai_provider, "AiGatewayClient", return_value=gateway, create=True)):
            results = ai_provider.AiServiceClient(config).review("synthetic review")
        primary = _parse_reviewer_result(self.proposal, results, "Claude")
        secondary = _parse_reviewer_result(self.proposal, results, "GPT")
        verdict = _resolve_multi_consensus(self.proposal, review_proposal(self.proposal), primary, secondary, None)
        self.assertEqual(verdict.recommended_action, "candidate_ready")
        self.assertTrue(verdict.requires_human)
        gateway.review.assert_called_once()

    def test_parser_rejects_explicit_invalid_numeric_fields(self):
        for field in ("overall_score", "confidence"):
            for value in (None, True, "0.8", float("nan"), float("inf"), -float("inf"), -0.1, 1.1, 10 ** 400):
                with self.subTest(field=field, value=value):
                    data = {"verdict": "approve", "overall_score": 0.8, "confidence": 0.8}
                    data[field] = value
                    self.assertIsNone(self.parse(**data))
        for verdict in (None, "verified", "unknown", True):
            with self.subTest(verdict=verdict):
                self.assertIsNone(self.parse(verdict=verdict))

    def test_codex_claims_are_advisory_not_verification(self):
        from quant_platform_kit.strategy_lifecycle.ai_reviewer import _parse_codex_result
        for claim in ("verified", "mismatch"):
            with self.subTest(claim=claim):
                parsed = _parse_codex_result(self.proposal, self.result("codex", verdict=claim))
                self.assertIsNotNone(parsed)
                self.assertEqual(parsed.verdict, "escalate")
                self.assertEqual(parsed.recommended_action, "notify" if claim == "verified" else "escalate")
                self.assertTrue(parsed.requires_human)
                self.assertIn("advisory", parsed.summary.lower())
                self.assertIn(claim, parsed.summary.lower())

    def test_codex_advisory_disagreement_is_not_silently_lost(self):
        from quant_platform_kit.strategy_lifecycle.ai_reviewer import _parse_codex_result
        primary = self.parse(verdict="approve", overall_score=0.9, confidence=0.9)
        for claim, expected in (("verified", "approve"), ("mismatch", "escalate")):
            with self.subTest(claim=claim):
                codex = _parse_codex_result(self.proposal, self.result("codex", verdict=claim))
                verdict = _resolve_multi_consensus(self.proposal, review_proposal(self.proposal), primary, primary, codex)
                self.assertEqual(verdict.verdict, expected)
                self.assertTrue(verdict.requires_human)
                self.assertIn("advisory", verdict.summary.lower())
                self.assertNotIn("VPS verified]", verdict.summary)

    def test_codex_invalid_values_and_missing_reviewers(self):
        from types import SimpleNamespace
        from quant_platform_kit.strategy_lifecycle.ai_reviewer import _parse_codex_result
        self.assertIsNone(_parse_codex_result(self.proposal, SimpleNamespace(output=None)))
        for field in ("reproduced_sharpe", "reproduced_max_dd", "reproduced_cagr", "confidence", "overall_score"):
            for value in (None, True, "0.1", float("nan"), float("inf")):
                with self.subTest(field=field, value=value):
                    for claim in ("verified", "mismatch"):
                        parsed = _parse_codex_result(self.proposal, self.result("codex", verdict=claim, **{field: value}))
                        self.assertEqual(parsed.verdict, "escalate")
                        self.assertEqual(parsed.recommended_action, "escalate")
                        self.assertIn("Invalid numeric", parsed.summary)
                        self.assertTrue(parsed.requires_human)
        claim = _parse_codex_result(self.proposal, self.result("codex", verdict="mismatch"))
        verdict = _resolve_multi_consensus(self.proposal, review_proposal(self.proposal), None, None, claim)
        self.assertEqual(verdict.verdict, "escalate")
        self.assertIn("mismatch", verdict.summary)
        self.assertTrue(verdict.requires_human)

    def test_invalid_or_failed_risk_inputs_do_not_call_provider(self):
        from unittest.mock import patch
        for metrics in (None, self.replace(self.metrics, max_drawdown=-1.0)):
            with self.subTest(metrics=metrics):
                with patch("quant_platform_kit.strategy_lifecycle.ai_provider.AiServiceClient") as client:
                    result = llm_enhanced_review(self.replace(self.proposal, proposed_metrics=metrics))
                client.assert_not_called()
                self.assertEqual(result.verdict, "escalate")

    def test_invalid_inputs_cannot_be_compensated_by_scores_or_ai(self):
        for field, values in {
            "sharpe_ratio": (None, float("nan"), float("inf")),
            "max_drawdown": (None, float("nan"), float("inf")),
            "observation_count": (None, float("nan"), -1, 2.5),
            "oos_sharpe": (float("nan"),),
            "walk_forward_stability": (float("inf"),),
            "calmar_ratio": (float("nan"),),
            "volatility": (float("inf"),),
        }.items():
            for value in values:
                with self.subTest(field=field, value=value):
                    proposal = self.replace(self.proposal, proposed_metrics=self.replace(self.metrics, **{field: value}))
                    base = review_proposal(proposal)
                    self.assertEqual(base.verdict, "escalate")
                    self.assertTrue(base.requires_human)
                    self.assertIn("invalid", base.summary.lower())
                    primary = self.parse(verdict="approve", overall_score=0.9, confidence=0.9)
                    self.assertNotEqual(_resolve_multi_consensus(proposal, base, primary, primary, None).verdict, "approve")

    def test_drawdown_threshold_is_not_compensated_and_learning_remains_valid(self):
        for drawdown, expected in ((-0.399, "approve"), (-0.40, "approve"), (-0.401, "escalate"), (-1.0, "escalate")):
            with self.subTest(drawdown=drawdown):
                proposal = self.replace(self.proposal, recommendation="research_candidate", proposed_metrics=self.replace(self.metrics, max_drawdown=drawdown))
                base = review_proposal(proposal)
                self.assertEqual(base.verdict, expected)
                self.assertTrue(base.requires_human)
                risk = next(d for d in base.dimensions if d.name == "risk_profile")
                self.assertEqual(risk.passed, expected == "approve")
                if expected != "approve":
                    primary = self.parse(verdict="approve", overall_score=0.9, confidence=0.9)
                    self.assertNotEqual(_resolve_multi_consensus(proposal, base, primary, primary, None).verdict, "approve")

    def test_invalid_proposal_confidence_is_not_high_confidence(self):
        for value in (None, True, float("nan"), float("inf"), -0.1, 1.1):
            with self.subTest(value=value):
                result = review_proposal(self.replace(self.proposal, confidence=value))
                self.assertEqual(result.verdict, "escalate")
                self.assertTrue(result.requires_human)


if __name__ == "__main__":
    unittest.main()
