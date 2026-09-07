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
    probe_production_drift_health,
    probe_production_drift_health_from_store,
)
from quant_platform_kit.strategy_lifecycle.research_promotion_cycle import (
    ResearchPromotionBudget,
    ResearchPromotionTicket,
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
    from_store: bool = False,
    store: Any | None = None,
    optimize: Callable[[DriftResult, ResearchPromotionBudget], Any] | None = None,
    record_shadow: Callable[[Any], Mapping[str, Any]] | None = None,
    enforce_backtest_gates: Callable[[Any], Any] | None = None,
    cycle: Callable[..., ResearchPromotionTicket] | None = None,
) -> dict[str, Any]:
    """Run promotion exactly once only for REVIEW/CRITICAL drift."""

    if from_store:
        if drift_score is not None:
            raise InvalidDriftInput("use either drift_score or from_store, not both")
        try:
            health = probe_production_drift_health_from_store(
                strategy_profile=strategy_profile,
                domain=domain,
                as_of=as_of,
                store=store,
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
            )
        except (TypeError, ValueError) as exc:
            raise InvalidDriftInput(str(exc)) from exc

    if not health["actionable"]:
        return {
            **health,
            "drift_status": health["status"],
            "status": "parked",
            "reason": health.get("reason", "drift_not_actionable"),
        }

    resolved_as_of = (
        date.fromisoformat(as_of) if isinstance(as_of, str) else as_of or date.today()
    )
    drift = DriftResult(
        strategy_profile=strategy_profile,
        domain=domain,
        as_of=resolved_as_of,
        drift_score=float(health["score"]),
        status=DriftStatus(str(health["status"])),
    )
    budget = ResearchPromotionBudget(allow_live_enablement=False)
    ticket = (cycle or run_research_promotion_cycle)(
        drift,
        optimize=optimize or _bounded_optimize,
        record_shadow=record_shadow or _non_live_shadow,
        enforce_backtest_gates=enforce_backtest_gates,
        budget=budget,
    )
    if ticket.live_authority_granted:
        raise ValueError("promotion runner refused live_authority_granted=true")
    return {
        **health,
        "status": ticket.state.value,
        "reason": "promotion_cycle_invoked",
        "ticket": ticket.to_dict(),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strategy-profile", required=True)
    parser.add_argument("--domain", required=True)
    parser.add_argument("--as-of", default=None, help="ISO date (YYYY-MM-DD)")
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
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
