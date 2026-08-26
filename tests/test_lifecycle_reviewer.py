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
                sharpe_ratio=1.5, observation_count=500,
            ),
        )
        v = review_proposal(p)
        d = v.to_dict()
        self.assertIn("verdict", d)
        self.assertIn("dimensions", d)
        self.assertIn("requires_human", d)
        self.assertIn("overall_score", d)
        self.assertEqual(len(d["dimensions"]), 5)


if __name__ == "__main__":
    unittest.main()
