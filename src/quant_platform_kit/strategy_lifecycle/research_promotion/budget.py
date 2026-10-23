"""Research optimization budget and promotion backtest gates."""

from __future__ import annotations

import calendar
from collections.abc import Mapping
from datetime import date, timedelta
from typing import Any

from quant_platform_kit.strategy_lifecycle.contracts import (
    OptimizationProposal,
    PromotionBacktestRun,
)

from .models import ResearchPromotionBudget


def enforce_optimization_budget(
    proposal: OptimizationProposal,
    budget: ResearchPromotionBudget,
) -> tuple[bool, str]:
    """Return (ok, reason) for a proposal against hard research caps."""
    if proposal.search_iterations > budget.max_search_iterations:
        return (
            False,
            (
                f"search_iterations={proposal.search_iterations} exceeds "
                f"budget max_search_iterations={budget.max_search_iterations}"
            ),
        )
    param_keys = len(dict(proposal.proposed_params or {}))
    if param_keys > budget.max_param_keys:
        return (
            False,
            (
                f"proposed_params keys={param_keys} exceeds "
                f"budget max_param_keys={budget.max_param_keys}"
            ),
        )
    return True, "within_budget"


def _add_calendar_months(value: date, months: int) -> date:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _promotion_backtest_evidence_mapping(
    evidence: PromotionBacktestRun | Mapping[str, Any],
) -> Mapping[str, Any]:
    if isinstance(evidence, PromotionBacktestRun):
        return {
            "status": "PASS",
            "orchestrator": "BacktestOrchestrator",
            "protocol": "purged_walk_forward.v1",
            "locked_independent_oos": {
                "locked": True,
                "independent": True,
                "reused_for_selection": False,
            },
            "promotion_run": evidence.to_dict(),
        }
    return evidence


def enforce_promotion_backtest_gates(
    proposal: OptimizationProposal,
    evidence: PromotionBacktestRun | Mapping[str, Any] | None,
) -> tuple[bool, str]:
    """Validate the strict orchestrator/WFA/OOS summary before shadow.

    Callers may return the existing ``PromotionBacktestRun`` contract directly
    or an evidence-package-compatible backtest summary. Missing or malformed
    evidence always parks the candidate.
    """
    if evidence is None:
        return False, "missing_promotion_backtest_evidence"
    if not isinstance(evidence, (PromotionBacktestRun, Mapping)):
        return False, "invalid_promotion_backtest_evidence_type"

    summary = _promotion_backtest_evidence_mapping(evidence)
    if summary.get("status") != "PASS":
        return False, "promotion_backtest_status_not_pass"
    if summary.get("orchestrator") != "BacktestOrchestrator":
        return False, "promotion_backtest_orchestrator_required"
    if summary.get("protocol") != "purged_walk_forward.v1":
        return False, "purged_walk_forward_protocol_required"

    locked = summary.get("locked_independent_oos")
    if not isinstance(locked, Mapping):
        return False, "locked_independent_oos_required"
    if (
        locked.get("locked") is not True
        or locked.get("independent") is not True
        or locked.get("reused_for_selection") is not False
    ):
        return False, "locked_independent_oos_failed"

    run = summary.get("promotion_run")
    if not isinstance(run, Mapping):
        return False, "promotion_run_required"
    if run.get("strategy_profile") != proposal.strategy_profile:
        return False, "promotion_run_strategy_profile_mismatch"
    if run.get("domain") != proposal.domain:
        return False, "promotion_run_domain_mismatch"
    folds = run.get("folds")
    if not isinstance(folds, (list, tuple)) or len(folds) < 3:
        return False, "promotion_run_requires_three_folds"
    for field_name in ("purge_days", "embargo_days"):
        value = run.get(field_name)
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            return False, f"promotion_run_{field_name}_must_be_positive"
    purge_days = int(run["purge_days"])
    embargo_days = int(run["embargo_days"])
    previous_test_end: date | None = None
    for index, fold in enumerate(folds):
        if not isinstance(fold, Mapping):
            return False, f"promotion_run_fold_{index}_invalid"
        try:
            train_start = date.fromisoformat(str(fold.get("train_start") or ""))
            train_end = date.fromisoformat(str(fold.get("train_end") or ""))
            test_start = date.fromisoformat(str(fold.get("test_start") or ""))
            test_end = date.fromisoformat(str(fold.get("test_end") or ""))
        except ValueError:
            return False, f"promotion_run_fold_{index}_dates_invalid"
        if train_start > train_end or test_start > test_end:
            return False, f"promotion_run_fold_{index}_dates_reversed"
        if train_end + timedelta(days=purge_days) >= test_start:
            return False, f"promotion_run_fold_{index}_purge_failed"
        if (
            previous_test_end is not None
            and previous_test_end + timedelta(days=embargo_days) >= train_start
        ):
            return False, f"promotion_run_fold_{index}_embargo_failed"
        previous_test_end = test_end
    try:
        oos_start = date.fromisoformat(str(run.get("locked_oos_start") or ""))
        oos_end = date.fromisoformat(str(run.get("locked_oos_end") or ""))
    except ValueError:
        return False, "promotion_run_locked_oos_dates_invalid"
    if (
        previous_test_end is None
        or previous_test_end + timedelta(days=embargo_days) >= oos_start
    ):
        return False, "promotion_run_locked_oos_embargo_failed"
    if oos_end < _add_calendar_months(oos_start, 12):
        return False, "promotion_run_locked_oos_under_12_months"
    return True, "promotion_backtest_gates_passed"
