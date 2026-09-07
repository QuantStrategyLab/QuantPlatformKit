"""Synthetic combo evidence stays research-only and fail-closed."""

from __future__ import annotations

import socket
import unittest
from unittest.mock import patch

from quant_platform_kit.risk.synthetic_combo_evidence import (
    PairwiseCorrelationEstimate,
    SyntheticComboMember,
    evaluate_synthetic_combo_evidence,
)


class SyntheticComboEvidenceTests(unittest.TestCase):
    def test_missing_correlation_fails_closed(self) -> None:
        evidence = evaluate_synthetic_combo_evidence(
            [
                SyntheticComboMember(strategy_id="alpha", target_weight=0.40, combined_scale=0.50),
                SyntheticComboMember(strategy_id="beta", target_weight=0.40, combined_scale=0.50),
            ],
            pairwise_correlation=None,
        )
        self.assertTrue(evidence.fail_closed)
        self.assertIn("MISSING_CORRELATION_ESTIMATE_FAIL_CLOSED", evidence.reason_codes)
        self.assertEqual(evidence.combined_risk_sleeve, 0.0)
        self.assertEqual(
            [member.post_haircut_risk_sleeve for member in evidence.members],
            [0.0, 0.0],
        )

    def test_correlated_group_cap_applies_proportional_haircut(self) -> None:
        evidence = evaluate_synthetic_combo_evidence(
            [
                SyntheticComboMember(strategy_id="alpha", risk_sleeve=0.60),
                SyntheticComboMember(strategy_id="beta", risk_sleeve=0.40),
                SyntheticComboMember(strategy_id="gamma", risk_sleeve=0.30),
            ],
            pairwise_correlation={
                "alpha": {"beta": 0.95, "gamma": 0.10},
                "beta": {"gamma": 0.20},
            },
            correlation_threshold=0.80,
            correlated_group_cap=0.50,
        )
        self.assertFalse(evidence.fail_closed)
        self.assertIn("CORRELATED_GROUP_CAP_APPLIED", evidence.reason_codes)
        self.assertAlmostEqual(evidence.pre_haircut_combined_risk_sleeve, 1.30)
        self.assertAlmostEqual(evidence.combined_risk_sleeve, 0.80)
        sleeves = {
            member.strategy_id: member.post_haircut_risk_sleeve for member in evidence.members
        }
        self.assertAlmostEqual(sleeves["alpha"], 0.30)
        self.assertAlmostEqual(sleeves["beta"], 0.20)
        self.assertAlmostEqual(sleeves["gamma"], 0.30)
        self.assertEqual(len(evidence.correlated_groups), 1)
        self.assertAlmostEqual(evidence.correlated_groups[0].post_haircut_sleeve, 0.50)

    def test_learning_only_flags_are_always_research_only(self) -> None:
        evidence = evaluate_synthetic_combo_evidence(
            [
                SyntheticComboMember(strategy_id="alpha", target_weight=0.50, combined_scale=0.80),
                SyntheticComboMember(strategy_id="beta", target_weight=0.25, combined_scale=0.80),
            ],
            pairwise_correlation=[
                PairwiseCorrelationEstimate(
                    left_strategy_id="alpha",
                    right_strategy_id="beta",
                    correlation=0.30,
                )
            ],
        )
        self.assertTrue(evidence.learning_only)
        self.assertFalse(evidence.promotion_eligible)
        self.assertFalse(evidence.live_ready)
        self.assertTrue(evidence.synthetic)
        self.assertFalse(evidence.live_authority_granted)

    def test_evaluation_does_not_touch_network(self) -> None:
        with patch.object(
            socket,
            "create_connection",
            side_effect=AssertionError("network should not be used"),
        ):
            evidence = evaluate_synthetic_combo_evidence(
                [
                    SyntheticComboMember(strategy_id="alpha", risk_sleeve=0.35),
                    SyntheticComboMember(strategy_id="beta", risk_sleeve=0.25),
                ],
                pairwise_correlation=[
                    {
                        "left_strategy_id": "alpha",
                        "right_strategy_id": "beta",
                        "correlation": 0.90,
                    }
                ],
                correlated_group_cap=0.70,
            )
        self.assertFalse(evidence.fail_closed)
        self.assertAlmostEqual(evidence.combined_risk_sleeve, 0.60)


if __name__ == "__main__":
    unittest.main()
