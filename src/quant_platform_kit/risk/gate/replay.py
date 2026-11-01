"""Explicit-clock offline evaluation; results are records, not executable decisions."""
from __future__ import annotations

import inspect
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

from quant_platform_kit.common.strategy_contracts import StrategyDecision
from quant_platform_kit.risk import gate
from quant_platform_kit.risk.gate.support import _parse_utc_whole_second


@dataclass(frozen=True)
class ReplayRiskGateResult:
    evaluation_time: str
    decision_record: dict[str, Any]
    assessment_record: dict[str, Any] | None = None
    executable: bool = field(default=False, init=False)
    scope: str = field(default="research_only", init=False)
    provenance_status: str = field(default="unverified", init=False)


def _replay_time(value: datetime) -> datetime:
    parsed = _parse_utc_whole_second(value) if type(value) is datetime else None
    if parsed is None:
        raise ValueError("evaluation_time must be a UTC whole-second datetime")
    return parsed


def _engine(decision, snapshot, market_data):
    try:
        return gate.build_risk_engine().assess(decision, snapshot, market_data=market_data), False
    except Exception:
        return None, True


def replay_apply_risk_gate(decision: StrategyDecision, *, evaluation_time: datetime, **kwargs) -> ReplayRiskGateResult:
    """Evaluate the live static gate at a historical clock for offline analysis."""
    now = _replay_time(evaluation_time)
    if "observer" in kwargs:
        raise TypeError("offline replay does not invoke runtime observers")
    bound = inspect.signature(gate.apply_risk_gate).bind(decision, **kwargs)
    bound.apply_defaults()
    options = dict(bound.arguments)
    options.pop("decision")
    market_data = options.pop("market_data")
    options.pop("observer")
    if options.pop("logical_evaluation_time") is not None:
        raise TypeError("use evaluation_time for offline replay")
    action, failed = _engine(decision, options["portfolio_snapshot"], market_data)
    try:
        result = gate._apply_risk_gate_static(decision, **options, now=now,
                                              engine_action=action, engine_failed=failed)
    except Exception:
        from .static import _reject
        result = _reject(decision, flag="rejected:invalid_risk_metadata", reason="invalid_risk_metadata", diagnostics={})
    return ReplayRiskGateResult(now.isoformat(), asdict(result))


def replay_assess_with_evidence(
    decision: StrategyDecision, portfolio_snapshot: Any, *, evaluation_time: datetime, **kwargs,
) -> ReplayRiskGateResult:
    """Evaluate the live evidence gate at a historical clock without live authority."""
    now = _replay_time(evaluation_time)
    bound = inspect.signature(gate.assess_with_evidence).bind(decision, portfolio_snapshot, **kwargs)
    bound.apply_defaults()
    options = dict(bound.arguments)
    options.pop("decision")
    options.pop("portfolio_snapshot")
    if options.pop("logical_evaluation_time") is not None:
        raise TypeError("use evaluation_time for offline replay")
    market_data = options.pop("market_data")
    action, failed = _engine(decision, portfolio_snapshot, market_data)
    try:
        result = gate._assess_with_evidence_static(
            decision, portfolio_snapshot, **options, now=now, risk_action=action, risk_engine_failed=failed,
        )
    except Exception:
        from .assessment import _invalid_assessment_result
        result = _invalid_assessment_result(
            decision, scope=options["scope"], mandate_provenance=options["mandate_provenance"],
            candidate_identity=options["candidate_identity"], now=now,
        )
    return ReplayRiskGateResult(now.isoformat(), asdict(result.decision), asdict(result.assessment))
