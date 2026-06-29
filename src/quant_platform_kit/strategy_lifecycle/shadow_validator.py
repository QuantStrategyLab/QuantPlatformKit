"""Shadow validator — compare proposed params against current in shadow mode."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import numpy as np

from quant_platform_kit.strategy_lifecycle.contracts import OptimizationProposal
from quant_platform_kit.strategy_lifecycle.performance_store import PerformanceStore


class ShadowValidator:
    """Run shadow validation for proposed parameters.

    Shadow validation means running the proposed parameters alongside the current
    parameters for a period (typically 5-10 trading days) and comparing results.
    If the shadow underperforms, the proposal is rejected.

    Usage::

        validator = ShadowValidator(store=store)
        result = validator.validate(proposal, domain="us_equity", shadow_days=5)
        if result["passed"]:
            ...  # approve
    """

    def __init__(self, *, store: PerformanceStore | None = None):
        self._store = store or PerformanceStore.from_env()

    def validate(
        self,
        proposal: OptimizationProposal,
        *,
        domain: str,
        shadow_days: int = 5,
    ) -> dict[str, Any]:
        """Validate a proposal over a shadow period.

        In a production system, this would actually run the strategy with the
        proposed parameters in shadow mode (no real orders) and compare daily
        returns. For the current implementation, it validates using recent
        performance snapshots as a proxy.

        Args:
            proposal: The optimization proposal to validate.
            domain: Market domain.
            shadow_days: Minimum trading days for the shadow period.

        Returns:
            Dict with "passed", "reason", "shadow_metrics", "days_evaluated".
        """
        # Collect recent snapshots for the strategy
        snapshots = self._collect_recent_snapshots(proposal.strategy_profile, domain, days=shadow_days + 5)
        if len(snapshots) < shadow_days:
            return {
                "passed": False,
                "reason": f"Insufficient shadow data: need {shadow_days} days, got {len(snapshots)}",
                "shadow_metrics": None,
                "days_evaluated": len(snapshots),
            }

        # Compare the most recent window metrics against the proposal expectations
        latest_126 = None
        for snap in reversed(snapshots):
            w = snap.windows.get(126)
            if w is not None:
                latest_126 = w
                break

        if latest_126 is None:
            return {"passed": False, "reason": "No 126-day window data available", "shadow_metrics": None, "days_evaluated": len(snapshots)}

        # Check if recent performance is consistent with proposed backtest
        proposed = proposal.proposed_metrics
        if proposed is None:
            return {"passed": False, "reason": "No proposed metrics to validate against", "shadow_metrics": None, "days_evaluated": len(snapshots)}

        checks: dict[str, bool] = {}
        reasons: list[str] = []

        # Sharpe check
        if proposed.sharpe_ratio is not None and not np.isnan(latest_126.sharpe_ratio):
            sharpe_ok = latest_126.sharpe_ratio >= proposed.sharpe_ratio * 0.7
            checks["sharpe"] = sharpe_ok
            if not sharpe_ok:
                reasons.append(f"Live Sharpe ({latest_126.sharpe_ratio:.2f}) << proposed ({proposed.sharpe_ratio:.2f})")

        # Drawdown check
        if proposed.max_drawdown is not None and not np.isnan(latest_126.max_drawdown):
            dd_ok = abs(latest_126.max_drawdown) <= abs(proposed.max_drawdown) * 1.3
            checks["max_drawdown"] = dd_ok
            if not dd_ok:
                reasons.append(f"Live max DD ({latest_126.max_drawdown:.2%}) >> proposed ({proposed.max_drawdown:.2%})")

        all_passed = all(checks.values()) if checks else True
        return {
            "passed": all_passed,
            "reason": "; ".join(reasons) if reasons else "All shadow checks passed",
            "shadow_metrics": {
                "sharpe_ratio": latest_126.sharpe_ratio,
                "max_drawdown": latest_126.max_drawdown,
                "cagr": latest_126.cagr,
            },
            "days_evaluated": len(snapshots),
        }

    def _collect_recent_snapshots(self, strategy_profile: str, domain: str, *, days: int) -> list:
        """Collect recent performance snapshots for a strategy."""
        from quant_platform_kit.strategy_lifecycle.contracts import StrategyPerformanceSnapshot

        snapshots: list[StrategyPerformanceSnapshot] = []
        today = date.today()
        for offset in range(days):
            as_of = today - timedelta(days=offset)
            snap = self._store.load_snapshot(domain, strategy_profile, as_of)
            if snap is not None:
                snapshots.append(snap)
        return snapshots
