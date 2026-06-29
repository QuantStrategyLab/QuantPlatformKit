"""Rollback manager — monitors post-deployment performance and auto-rolls back on degradation."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime, timezone
from typing import Any

import numpy as np

from quant_platform_kit.strategy_lifecycle.audit_log import record_audit_entry
from quant_platform_kit.strategy_lifecycle.contracts import UpdateStage
from quant_platform_kit.strategy_lifecycle.performance_store import PerformanceStore
from quant_platform_kit.strategy_lifecycle.update_policy import UpdatePolicy


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class RollbackManager:
    """Monitors post-update performance and triggers rollback if needed.

    Usage::

        mgr = RollbackManager(store=store, policy=policy)
        decision = mgr.evaluate("global_etf_rotation", domain="us_equity")
        if decision["should_rollback"]:
            mgr.rollback(...)
    """

    def __init__(
        self,
        *,
        store: PerformanceStore | None = None,
        policy: UpdatePolicy | None = None,
    ):
        self._store = store or PerformanceStore.from_env()
        self._policy = policy or UpdatePolicy.load_default()

    def evaluate(
        self,
        strategy_profile: str,
        *,
        domain: str,
        deployed_params: Mapping[str, Any] | None = None,
        deployed_sharpe: float | None = None,
        deployed_max_dd: float | None = None,
    ) -> dict[str, Any]:
        """Evaluate whether a recently-deployed update should be rolled back.

        Compares current live performance against the pre-deployment baseline.
        Triggers rollback if:
        - Sharpe ratio has declined by more than rollback_sharpe_decline
        - Max drawdown has worsened by more than rollback_drawdown_multiplier

        Args:
            strategy_profile: The strategy to evaluate.
            domain: Market domain.
            deployed_params: Parameters that were deployed.
            deployed_sharpe: Sharpe ratio at time of deployment.
            deployed_max_dd: Max drawdown at time of deployment.

        Returns:
            Dict with "should_rollback", "reason", "live_sharpe", "live_max_dd".
        """
        # Get latest live performance
        latest_snapshot = self._store.load_latest_snapshot(domain, strategy_profile)
        if latest_snapshot is None:
            return {"should_rollback": False, "reason": "No live performance data available"}

        ref_window = latest_snapshot.windows.get(126) or latest_snapshot.windows.get(252)
        if ref_window is None:
            return {"should_rollback": False, "reason": "No window metrics available"}

        live_sharpe = ref_window.sharpe_ratio
        live_max_dd = ref_window.max_drawdown

        reasons: list[str] = []

        # Check sharpe decline
        if deployed_sharpe is not None and not np.isnan(live_sharpe):
            sharpe_decline = deployed_sharpe - live_sharpe
            if sharpe_decline > self._policy.rollback_sharpe_decline:
                reasons.append(
                    f"Sharpe declined from {deployed_sharpe:.2f} to {live_sharpe:.2f} "
                    f"(decline={sharpe_decline:.2f}, threshold={self._policy.rollback_sharpe_decline:.2f})"
                )

        # Check drawdown worsening
        if deployed_max_dd is not None and not np.isnan(live_max_dd):
            dd_ratio = abs(live_max_dd) / max(abs(deployed_max_dd), 0.001)
            if dd_ratio > self._policy.rollback_drawdown_multiplier:
                reasons.append(
                    f"Max drawdown worsened from {deployed_max_dd:.2%} to {live_max_dd:.2%} "
                    f"(ratio={dd_ratio:.2f}, threshold={self._policy.rollback_drawdown_multiplier:.2f})"
                )

        should_rollback = len(reasons) > 0
        return {
            "should_rollback": should_rollback,
            "reason": "; ".join(reasons) if reasons else "Performance within acceptable range",
            "live_sharpe": live_sharpe,
            "live_max_dd": live_max_dd,
        }

    def rollback(
        self,
        strategy_profile: str,
        *,
        domain: str,
        param_version_from: int,
        param_version_to: int,
        params_before: Mapping[str, Any],
        params_after: Mapping[str, Any],
        reason: str = "Auto-rollback due to post-deployment performance degradation",
    ) -> dict[str, Any]:
        """Execute a rollback and record it in the audit log."""
        entry = record_audit_entry(
            strategy_profile=strategy_profile,
            domain=domain,
            stage=UpdateStage.ROLLED_BACK,
            operator="auto_optimizer",
            param_version_from=param_version_from,
            param_version_to=param_version_to,
            params_before=params_before,
            params_after=params_after,
            reason=reason,
            approval_source="auto",
        )

        return {
            "rolled_back": True,
            "strategy_profile": strategy_profile,
            "from_version": param_version_from,
            "to_version": param_version_to,
            "entry_id": entry.entry_id,
            "reason": reason,
        }
