from __future__ import annotations

import unittest
from unittest.mock import patch

from quant_platform_kit.strategy_lifecycle.contracts import BacktestResult, OptimizationProposal
from quant_platform_kit.strategy_lifecycle.update_orchestrator import process_update_from_proposal


def _proposal() -> OptimizationProposal:
    proposed = BacktestResult(
        strategy_profile="global_etf_rotation",
        domain="us_equity",
        param_set_id="candidate",
        params={"lookback": 120},
        param_version=1,
        sharpe_ratio=1.4,
        calmar_ratio=1.0,
        max_drawdown=-0.12,
        cagr=0.18,
        volatility=0.2,
        win_rate=0.56,
    )
    return OptimizationProposal(
        strategy_profile="global_etf_rotation",
        domain="us_equity",
        current_params={"lookback": 90},
        current_metrics=proposed,
        proposed_params={"lookback": 120},
        proposed_metrics=proposed,
        improvement_score=0.12,
        confidence=0.8,
        winning_dimensions=("sharpe_ratio",),
        recommendation="promote",
        optimization_method="grid_search",
    )


class UpdateOrchestratorTests(unittest.TestCase):
    def test_process_update_creates_patch_instead_of_marking_deployed(self) -> None:
        with patch(
            "quant_platform_kit.strategy_lifecycle.update_orchestrator._check_cooldown",
            return_value=None,
        ), patch(
            "quant_platform_kit.strategy_lifecycle.update_orchestrator._run_shadow_validation",
            return_value=None,
        ), patch(
            "quant_platform_kit.strategy_lifecycle.update_orchestrator._check_approval",
            return_value=(True, None),
        ):
            result = process_update_from_proposal(_proposal(), auto_approve=True)

        self.assertEqual(result["stage"], "patch_created")
        self.assertIn("patch", result)
        self.assertIn("runtime confirmation", result["reason"].lower())


if __name__ == "__main__":
    unittest.main()
