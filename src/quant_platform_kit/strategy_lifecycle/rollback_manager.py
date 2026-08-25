"""Rollback monitor — records no-order rollback proposals on degradation."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np

from quant_platform_kit.strategy_lifecycle.audit_log import record_audit_entry
from quant_platform_kit.strategy_lifecycle.contracts import UpdateStage
from quant_platform_kit.strategy_lifecycle.performance_store import PerformanceStore
from quant_platform_kit.strategy_lifecycle.update_policy import UpdatePolicy

class RollbackManager:
    """Monitors post-update performance and records rollback proposals.

    This class has no deployment, runtime-target, broker, or order adapter.
    A performance breach is therefore an auditable proposal, not an executed
    rollback.  A platform-specific, owner-authorized control path must provide
    any actual rollback separately.

    Usage::

        mgr = RollbackManager(store=store, policy=policy)
        decision = mgr.evaluate("global_etf_rotation", domain="us_equity")
        if decision["should_rollback"]:
            mgr.propose_rollback(...)
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
            Dict with a rollback recommendation and an explicit
            ``rollback_execution_authorized=False`` boundary.
        """
        # Get latest live performance
        latest_snapshot = self._store.load_latest_snapshot(domain, strategy_profile)
        if latest_snapshot is None:
            return {
                "should_rollback": False,
                "reason": "No live performance data available",
                "rollback_execution_authorized": False,
            }

        ref_window = latest_snapshot.windows.get(126) or latest_snapshot.windows.get(252)
        if ref_window is None:
            return {
                "should_rollback": False,
                "reason": "No window metrics available",
                "rollback_execution_authorized": False,
            }

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
            "rollback_execution_authorized": False,
        }

    def propose_rollback(
        self,
        strategy_profile: str,
        *,
        domain: str,
        param_version_from: int,
        param_version_to: int,
        params_before: Mapping[str, Any],
        params_after: Mapping[str, Any],
        reason: str = "Rollback proposal due to post-deployment performance degradation",
    ) -> dict[str, Any]:
        """Record a rollback proposal without changing any external state."""
        entry = record_audit_entry(
            strategy_profile=strategy_profile,
            domain=domain,
            stage=UpdateStage.ROLLBACK_PROPOSED,
            operator="rollback_monitor",
            param_version_from=param_version_from,
            param_version_to=param_version_to,
            params_before=params_before,
            params_after=params_after,
            reason=reason,
            approval_source="not_authorized",
            store=self._store,
        )

        return {
            "proposal_recorded": True,
            "rolled_back": False,
            "rollback_executed": False,
            "execution_authorized": False,
            "requires_owner_approval": True,
            "stage": UpdateStage.ROLLBACK_PROPOSED.value,
            "strategy_profile": strategy_profile,
            "from_version": param_version_from,
            "to_version": param_version_to,
            "entry_id": entry.entry_id,
            "reason": reason,
        }

    def rollback(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        """Compatibility alias for :meth:`propose_rollback`.

        Kept so callers do not fail at import time, but it never claims or
        performs an external rollback.  Consumers must check
        ``rollback_executed`` rather than treating an audit record as runtime
        evidence.
        """
        return self.propose_rollback(*args, **kwargs)
