"""Explicit, drift-actionable research promotion runner.

This module is an on-demand caller only. It is not a calendar scheduler and
never grants live enablement.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Callable, Mapping, Sequence
from datetime import date
from typing import Any

from quant_platform_kit.strategy_lifecycle.contracts import DriftResult, DriftStatus
from quant_platform_kit.strategy_lifecycle.production_drift_health_probe import (
    DEFAULT_MAX_AGE_DAYS,
    probe_production_drift_health,
    probe_production_drift_health_from_store,
)
from quant_platform_kit.strategy_lifecycle.research_promotion_cycle import (
    ResearchPromotionBudget,
    ResearchPromotionTicket,
    make_console_research_promotion_sync,
    run_research_promotion_cycle,
)


class InvalidDriftInput(ValueError):
    """Raised when drift input cannot produce a trusted probe result."""


def _bounded_optimize(
    drift: DriftResult,
    budget: ResearchPromotionBudget,
) -> Any:
    from quant_platform_kit.strategy_lifecycle.param_optimizer import run_optimization

    return run_optimization(
        drift.strategy_profile,
        domain=drift.domain,
        max_combinations=budget.max_search_iterations,
    )


def _non_live_shadow(proposal: Any) -> Mapping[str, Any]:
    from quant_platform_kit.strategy_lifecycle.paired_shadow_adapter import (
        resolve_promotion_shadow_record,
    )

    return resolve_promotion_shadow_record(
        proposal=proposal,
        allow_proxy_fallback=False,
    )


def run_actionable_research_promotion(
    *,
    strategy_profile: str,
    domain: str,
    as_of: date | str | None = None,
    drift_score: float | None = None,
    source_revision: str | None = None,
    from_store: bool = False,
    evaluation_date: date | str | None = None,
    max_age_days: int = DEFAULT_MAX_AGE_DAYS,
    store: Any | None = None,
    optimize: Callable[[DriftResult, ResearchPromotionBudget], Any] | None = None,
    record_shadow: Callable[[Any], Mapping[str, Any]] | None = None,
    enforce_backtest_gates: Callable[[Any], Any] | None = None,
    sync_console: Callable[[ResearchPromotionTicket], bool] | None = None,
    cycle: Callable[..., ResearchPromotionTicket] | None = None,
) -> dict[str, Any]:
    """Run promotion once for REVIEW/CRITICAL drift and require paired shadow.

    The existing gate and shadow callbacks consume the isolated candidate's
    evidence. Missing evidence still parks the cycle. Only awaiting tickets
    reach the existing QRT sync adapter; ``console_synced`` distinguishes a
    confirmed sync from a skipped/failed sync (False) or no attempt (None).
    """

    if from_store:
        if drift_score is not None:
            raise InvalidDriftInput("use either drift_score or from_store, not both")
        try:
            health = probe_production_drift_health_from_store(
                strategy_profile=strategy_profile,
                domain=domain,
                as_of=as_of,
                store=store,
                evaluation_date=evaluation_date,
                max_age_days=max_age_days,
            )
        except (TypeError, ValueError) as exc:
            raise InvalidDriftInput(str(exc)) from exc
    else:
        if drift_score is None:
            raise InvalidDriftInput(
                "drift_score is required unless from_store is set"
            )
        if as_of is None:
            raise InvalidDriftInput("as_of is required unless from_store is set")
        try:
            health = probe_production_drift_health(
                strategy_profile=strategy_profile,
                domain=domain,
                as_of=as_of,
                drift_score=drift_score,
                evaluation_date=evaluation_date,
                max_age_days=max_age_days,
            )
        except (TypeError, ValueError) as exc:
            raise InvalidDriftInput(str(exc)) from exc

    if not from_store:
        health["source_revision"] = source_revision
    if not health["actionable"]:
        return {
            **health,
            "drift_status": health["status"],
            "status": "parked",
            "reason": health.get("reason", "drift_not_actionable"),
        }

    missing_bindings = [
        name
        for name, binding in (
            ("enforce_backtest_gates", enforce_backtest_gates),
            ("record_shadow", record_shadow),
        )
        if not callable(binding)
    ]
    if missing_bindings:
        return {
            **health,
            "drift_status": health["status"],
            "status": "parked",
            "reason": "research_bindings_unavailable",
            "missing_bindings": missing_bindings,
            "console_synced": None,
        }

    resolved_as_of = date.fromisoformat(health["as_of"])
    drift = DriftResult(
        strategy_profile=strategy_profile,
        domain=domain,
        as_of=resolved_as_of,
        drift_score=float(health["score"]),
        status=DriftStatus(str(health["status"])),
        source_revision=health.get("source_revision") or "",
        baseline_artifact_id=health.get("baseline_artifact_id"),
        baseline_param_set_id=health.get("baseline_param_set_id"),
        baseline_param_version=health.get("baseline_param_version"),
    )
    budget = ResearchPromotionBudget(
        allow_live_enablement=False, require_paired_shadow=True,
    )
    console_synced: bool | None = None
    sender = (
        sync_console
        if sync_console is not None
        else make_console_research_promotion_sync()
    )

    def deliver_to_console(ticket: ResearchPromotionTicket) -> bool:
        nonlocal console_synced
        try:
            console_synced = sender(ticket) is True
        except Exception:
            # An uncertain write must not be retried or expose provider details.
            console_synced = False
        return console_synced

    ticket = (cycle or run_research_promotion_cycle)(
        drift,
        optimize=optimize or _bounded_optimize,
        record_shadow=record_shadow or _non_live_shadow,
        enforce_backtest_gates=enforce_backtest_gates,
        sync_console=deliver_to_console,
        budget=budget,
    )
    if ticket.live_authority_granted:
        raise ValueError("promotion runner refused live_authority_granted=true")
    return {
        **health,
        "status": ticket.state.value,
        "reason": "promotion_cycle_invoked",
        "console_synced": console_synced,
        "ticket": ticket.to_dict(),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strategy-profile", required=True)
    parser.add_argument("--domain", required=True)
    parser.add_argument("--as-of", default=None, help="ISO date (YYYY-MM-DD)")
    parser.add_argument("--evaluation-date", default=None, help="Explicit historical replay clock")
    parser.add_argument("--max-age-days", type=int, default=DEFAULT_MAX_AGE_DAYS)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--drift-score", type=float)
    source.add_argument("--from-store", action="store_true")
    args = parser.parse_args(argv)

    try:
        summary = run_actionable_research_promotion(
            strategy_profile=args.strategy_profile,
            domain=args.domain,
            as_of=args.as_of,
            drift_score=args.drift_score,
            from_store=args.from_store,
            evaluation_date=args.evaluation_date,
            max_age_days=args.max_age_days,
        )
    except InvalidDriftInput:
        print(
            json.dumps(
                {
                    "actionable": False,
                    "reason": "invalid_drift_input",
                    "status": "parked",
                },
                sort_keys=True,
            )
        )
        return 2
    print(json.dumps(summary, sort_keys=True))
    return 2 if summary.get("reason") == "research_bindings_unavailable" else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
