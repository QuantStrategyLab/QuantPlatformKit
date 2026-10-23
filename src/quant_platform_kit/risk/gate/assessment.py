"""Evidence-grade risk gate assessment entrypoints."""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any, Mapping

from quant_platform_kit.common.capital_base import (
    CapitalBaseBinding,
    CapitalBaseSnapshot,
    validate_capital_base,
)
from quant_platform_kit.common.risk_mandates import _TQQQ_ETF_ONLY_RESEARCH_MANDATE
from quant_platform_kit.common.strategy_contracts import PositionTarget, StrategyDecision
from quant_platform_kit.position_sizing import validate_reduce_only_normalization
from quant_platform_kit.risk.contracts import (
    CandidateRiskIdentity,
    RiskGateAssessment,
    RiskGateResult,
)

from .mandates import (
    _RETIRED_GLOBAL_ETF_RESEARCH_MANDATE,
    _TQQQ_EVIDENCE_MANDATE_SCHEMA,
    _budget_authority_errors,
    _candidate_binding_errors,
    _mandate_fields,
    _position_cap,
    _risk_control_fields,
    _tqqq_evidence_capital_errors,
    _tqqq_evidence_portfolio_fields,
)
from .static import _reject
from .support import (
    _bounded_nonnegative_int,
    _canonical_digest,
    _canonical_numeric_mapping,
    _canonical_string,
    _canonical_string_list,
    _capital_base_snapshot_commitment,
    _decision_metrics,
    _finite_number,
    _logical_evaluation_time,
    _safe_diagnostics,
    _sha256,
    _snapshot_metrics,
    _utc_timestamp,
)


_ASSESSMENT_CONTRACT_VERSION = "qsl.risk_gate_assessment.v2"


_ASSESSMENT_POLICY_ID = "qpk.risk_gate"


_ASSESSMENT_POLICY_VERSION = "v2"


_ALLOWED_SCOPES = frozenset({"MEMBER", "ACCOUNT"})


def _assess_with_evidence_static(
    decision: StrategyDecision,
    portfolio_snapshot: Any,
    *,
    scope: Any,
    mandate_provenance: Mapping[str, Any] | None,
    candidate_identity: CandidateRiskIdentity | None,
    normalization_origin_weights: Mapping[str, float] | None,
    risk_control_state: Mapping[str, Any] | None,
    capital_base: CapitalBaseSnapshot | Mapping[str, Any] | None,
    capital_base_binding: CapitalBaseBinding | Mapping[str, Any] | None,
    now: datetime,
    risk_action: Any,
    risk_engine_failed: bool,
) -> RiskGateResult:
    if type(decision) is not StrategyDecision:
        raise TypeError("invalid decision")
    evaluated_at = _utc_timestamp(now)
    normalized_scope, valid_scope = _canonical_string(scope)
    assessment_scope = (
        normalized_scope
        if valid_scope and normalized_scope in _ALLOWED_SCOPES
        else "MEMBER"
    )
    mandate, mandate_errors = _mandate_fields(mandate_provenance, now=now)
    reason_codes = set(mandate_errors)
    reason_codes.update(
        _candidate_binding_errors(
            mandate_provenance,
            mandate,
            candidate_identity,
        )
    )
    is_tqqq_evidence_mandate = (
        mandate.get("schema_version") == _TQQQ_EVIDENCE_MANDATE_SCHEMA
    )
    cap = mandate.get("effective_exposure_cap")
    snapshot_payload, observed, total_equity, snapshot_errors = _snapshot_metrics(
        portfolio_snapshot,
        now=now,
        max_snapshot_age_seconds=mandate.get("max_snapshot_age_seconds"),
        require_utc_whole_second=is_tqqq_evidence_mandate,
    )
    reason_codes.update(snapshot_errors)
    if is_tqqq_evidence_mandate:
        portfolio_fields, portfolio_errors = _tqqq_evidence_portfolio_fields(
            portfolio_snapshot,
            mandate=mandate,
        )
        reason_codes.update(portfolio_errors)
        if portfolio_fields:
            snapshot_payload.update(portfolio_fields)
    value_targets_present = any(
        type(position) is PositionTarget and position.target_value is not None
        for position in getattr(decision, "positions", ())
    )
    if value_targets_present or is_tqqq_evidence_mandate:
        capital_base_validation = validate_capital_base(
            capital_base,
            binding=capital_base_binding,
            now=now,
        )
        capital_base_payload = capital_base_validation.to_safe_dict()
        if (
            is_tqqq_evidence_mandate
            and capital_base_validation.is_valid
            and capital_base_validation.snapshot is not None
        ):
            capital_base_payload["snapshot_commitment_sha256"] = (
                _capital_base_snapshot_commitment(capital_base_validation.snapshot)
            )
        snapshot_payload["capital_base"] = capital_base_payload
        if not capital_base_validation.is_valid:
            reason_codes.update(capital_base_validation.findings)
        else:
            if (
                type(candidate_identity) is CandidateRiskIdentity
                and capital_base_validation.binding is not None
                and capital_base_validation.binding.strategy_scope
                != candidate_identity.strategy_profile
            ):
                reason_codes.add("capital_base_strategy_candidate_mismatch")
            if is_tqqq_evidence_mandate:
                reason_codes.update(
                    _tqqq_evidence_capital_errors(
                        capital_base_validation,
                        mandate=mandate,
                    )
                )
                if total_equity != capital_base_validation.target_equity:
                    reason_codes.add("capital_base_portfolio_equity_mismatch")
        total_equity = capital_base_validation.target_equity
    decision_payload, active_positions, decision_errors = _decision_metrics(
        decision,
        total_equity=total_equity,
    )
    reason_codes.update(decision_errors)
    diagnostics, valid_diagnostics = _safe_diagnostics(decision.diagnostics)
    risk_flags = (
        _canonical_string_list(decision.risk_flags)
        if type(decision.risk_flags) is tuple
        else None
    )
    if not valid_diagnostics or risk_flags is None:
        reason_codes.add("invalid_risk_metadata")
    if not valid_scope or normalized_scope not in _ALLOWED_SCOPES:
        reason_codes.add("invalid_scope")
    can_evaluate_policy = not reason_codes
    if mandate:
        reason_codes.update(_budget_authority_errors(decision, mandate))
    control_fields, control_errors = _risk_control_fields(
        risk_control_state,
        mandate=mandate,
        now=now,
        active_positions=active_positions,
    )
    reason_codes.update(control_errors)

    proposed: float | None = None
    normalization_origin_digest_sha256: str | None = None
    if can_evaluate_policy:
        factors = mandate["product_leverage_factors"]
        allowed_assets = mandate["allowed_nonzero_assets"]
        benchmark_only_assets = mandate.get("benchmark_only_assets", set())
        if is_tqqq_evidence_mandate:
            for position in decision_payload["positions"]:
                symbol = position["symbol"]
                if symbol in benchmark_only_assets:
                    reason_codes.add("benchmark_only_asset")
                elif symbol is not None and symbol not in allowed_assets:
                    reason_codes.add("asset_not_authorized")
        target_weights: dict[str, float] = {}
        for symbol, weight in active_positions:
            combined_weight = target_weights.get(symbol, 0.0) + weight
            if not math.isfinite(combined_weight):
                reason_codes.add("invalid_risk_metadata")
                continue
            target_weights[symbol] = combined_weight
        # Product caps apply to the combined holding, regardless of row/role.
        policy_positions = list(target_weights.items())
        weighted_exposure = 0.0
        if mandate_provenance is None and len(active_positions) > 1:
            reason_codes.add("fallback_position_count")
        if (
            mandate.get("mandate_id") == _TQQQ_ETF_ONLY_RESEARCH_MANDATE
            and len(active_positions) > mandate["max_nonzero_assets"]
        ):
            reason_codes.add("single_strategy_position_count")
        if (
            is_tqqq_evidence_mandate
            and len(target_weights) > mandate["max_nonzero_assets"]
        ):
            reason_codes.add("max_nonzero_assets")
        for symbol, weight in policy_positions:
            if symbol in benchmark_only_assets:
                reason_codes.add("benchmark_only_asset")
                continue
            if allowed_assets is not None and symbol not in allowed_assets:
                reason_codes.add("asset_not_authorized")
                continue
            factor = (
                1.0
                if mandate_provenance is None
                else _finite_number(factors.get(symbol))
            )
            if factor is None or not factor.is_integer() or factor < 1.0:
                reason_codes.add("invalid_leverage_classification")
                continue
            product_cap = _position_cap(
                mandate.get("product_caps", 1.0),
                symbol,
                factor,
            )
            nominal_cap = _position_cap(
                mandate.get("nominal_caps", 1.0),
                symbol,
                factor,
            )
            if product_cap is None or nominal_cap is None:
                reason_codes.add("invalid_product_cap")
                continue
            if weight > min(product_cap, nominal_cap):
                reason_codes.add("product_exposure_cap")
            product_effective_cap = _position_cap(
                mandate.get("product_effective_caps", 1.0),
                symbol,
                factor,
            )
            if (
                product_effective_cap is None
                or weight * factor > product_effective_cap + 1e-9
            ):
                reason_codes.add("product_effective_exposure_cap")
            if mandate.get("mandate_id") == _TQQQ_ETF_ONLY_RESEARCH_MANDATE:
                stop_distance = control_fields["stop_loss_distance"]
                drawdown_scalar = control_fields["drawdown_scalar"]
                loss_budget = mandate.get("loss_budget")
                if (
                    stop_distance is not None
                    and stop_distance > 0.0
                    and drawdown_scalar is not None
                    and loss_budget is not None
                    and weight > loss_budget * drawdown_scalar / stop_distance + 1e-9
                ):
                    reason_codes.add("risk_budget_exposure_cap")
            effective_weight = weight * factor
            if not math.isfinite(effective_weight):
                reason_codes.add("invalid_risk_metadata")
                continue
            weighted_exposure += effective_weight
            if not math.isfinite(weighted_exposure):
                reason_codes.add("invalid_risk_metadata")
                weighted_exposure = 0.0

        if is_tqqq_evidence_mandate:
            stress_distance = control_fields["modeled_stress_loss_distance"]
            drawdown_scalar = control_fields["drawdown_scalar"]
            loss_budget = mandate.get("loss_budget")
            total_nominal_weight = sum(target_weights.values())
            if (
                stress_distance is not None
                and drawdown_scalar is not None
                and loss_budget is not None
                and total_nominal_weight * stress_distance
                > loss_budget * drawdown_scalar + 1e-9
            ):
                reason_codes.add("risk_budget_exposure_cap")
        valid_normalization = False
        if normalization_origin_weights is not None:
            normalized_origin_material = _canonical_numeric_mapping(
                normalization_origin_weights,
                minimum=0.0,
            )
            if normalized_origin_material is None:
                reason_codes.update(
                    {"invalid_risk_metadata", "invalid_reduce_only_normalization"}
                )
            else:
                normalized_origin = {
                    symbol: float(weight)
                    for symbol, weight in sorted(normalized_origin_material.items())
                }
                valid_normalization = validate_reduce_only_normalization(
                    origin_weights=normalized_origin,
                    target_weights=target_weights,
                    product_leverage_factors=factors,
                    effective_exposure_cap=cap,
                    observed_effective_exposure=observed,
                    cash_only=(
                        mandate.get("mandate_id")
                        == _TQQQ_ETF_ONLY_RESEARCH_MANDATE
                    ),
                )
                if not valid_normalization:
                    reason_codes.add("invalid_reduce_only_normalization")
                else:
                    normalization_origin_digest_sha256 = _canonical_digest(
                        {"weights": normalized_origin}
                    )
        proposed = (
            weighted_exposure
            if valid_normalization
            else max(observed or 0.0, weighted_exposure)
        )
        if cap is None or observed is None or (
            observed > cap + 1e-9 and not valid_normalization
        ):
            reason_codes.add("observed_effective_exposure")
        if cap is None or proposed > cap + 1e-9:
            reason_codes.add("effective_exposure_cap")

    if not reason_codes:
        if risk_engine_failed:
            reason_codes.add("risk_engine_error")
        elif getattr(risk_action, "action", None) != "approve":
            reason_codes.add("risk_engine_non_approve")

    outcome = "REJECT" if reason_codes else "APPROVE"
    assessment = RiskGateAssessment(
        contract_version=_ASSESSMENT_CONTRACT_VERSION,
        scope=assessment_scope,
        evaluated_at=evaluated_at,
        policy_id=_ASSESSMENT_POLICY_ID,
        policy_version=_ASSESSMENT_POLICY_VERSION,
        qpk_source_revision=mandate.get("source_revision"),
        mandate_id=mandate.get("mandate_id"),
        mandate_version=mandate.get("mandate_version"),
        mandate_authority_receipt_sha256=mandate.get("authority_receipt_sha256"),
        mandate_scope=mandate.get("authority_scope"),
        candidate_identity_sha256=(
            candidate_identity.candidate_sha256
            if type(candidate_identity) is CandidateRiskIdentity
            and _sha256(candidate_identity.candidate_sha256) is not None
            else None
        ),
        decision_digest_sha256=_canonical_digest(decision_payload),
        portfolio_snapshot_digest_sha256=_canonical_digest(snapshot_payload),
        normalization_origin_digest_sha256=normalization_origin_digest_sha256,
        effective_exposure_cap=cap,
        observed_effective_exposure=observed,
        proposed_effective_exposure=proposed,
        outcome=outcome,
        reason_codes=tuple(sorted(reason_codes)),
        execution_authorized=False,
        stop_loss_distance=control_fields["stop_loss_distance"],
        stop_intent_ready=control_fields["stop_intent_ready"],
        strategy_breaker_triggered=control_fields["strategy_breaker_triggered"],
        account_breaker_triggered=control_fields["account_breaker_triggered"],
        account_drawdown_fraction=control_fields["account_drawdown_fraction"],
        drawdown_scalar=control_fields["drawdown_scalar"],
        risk_control_state_digest_sha256=control_fields[
            "risk_control_state_digest_sha256"
        ],
    )
    if outcome == "REJECT":
        return RiskGateResult(
            decision=_reject(
                decision,
                flag="rejected:risk_gate_assessment",
                reason=",".join(assessment.reason_codes),
                diagnostics=diagnostics,
            ),
            assessment=assessment,
        )
    return RiskGateResult(
        decision=StrategyDecision(
            positions=decision.positions,
            budgets=decision.budgets,
            risk_flags=tuple(risk_flags or ()) + ("risk_gate:passed",),
            diagnostics={**diagnostics, "risk_gate": "APPROVE"},
        ),
        assessment=assessment,
    )


def _invalid_assessment_result(
    decision: StrategyDecision,
    *,
    scope: Any,
    mandate_provenance: Mapping[str, Any] | None,
    candidate_identity: CandidateRiskIdentity | None,
    now: datetime,
    reason_codes: set[str] | None = None,
) -> RiskGateResult:
    normalized_reason_codes = set(reason_codes or {"invalid_risk_metadata"})
    try:
        if (
            isinstance(mandate_provenance, Mapping)
            and mandate_provenance.get("mandate_id")
            == _RETIRED_GLOBAL_ETF_RESEARCH_MANDATE
        ):
            normalized_reason_codes.add("retired_global_etf_research_mandate")
    except Exception:
        pass
    normalized_scope, valid_scope = _canonical_string(scope)
    assessment_scope = (
        normalized_scope
        if valid_scope and normalized_scope in _ALLOWED_SCOPES
        else "MEMBER"
    )
    candidate_sha256 = None
    try:
        if type(candidate_identity) is CandidateRiskIdentity:
            candidate_sha256 = _sha256(candidate_identity.candidate_sha256)
    except Exception:
        candidate_sha256 = None
    invalid_digest = _canonical_digest({"invalid_risk_metadata": True})
    assessment = RiskGateAssessment(
        contract_version=_ASSESSMENT_CONTRACT_VERSION,
        scope=assessment_scope,
        evaluated_at=_utc_timestamp(now),
        policy_id=_ASSESSMENT_POLICY_ID,
        policy_version=_ASSESSMENT_POLICY_VERSION,
        qpk_source_revision=None,
        mandate_id=None,
        mandate_version=None,
        mandate_authority_receipt_sha256=None,
        mandate_scope=None,
        candidate_identity_sha256=candidate_sha256,
        decision_digest_sha256=invalid_digest,
        portfolio_snapshot_digest_sha256=invalid_digest,
        normalization_origin_digest_sha256=None,
        effective_exposure_cap=None,
        observed_effective_exposure=None,
        proposed_effective_exposure=None,
        outcome="REJECT",
        reason_codes=tuple(sorted(normalized_reason_codes)),
        execution_authorized=False,
    )
    return RiskGateResult(
        decision=_reject(
            decision,
            flag="rejected:risk_gate_assessment",
            reason=",".join(assessment.reason_codes),
            diagnostics={},
        ),
        assessment=assessment,
    )


def assess_with_evidence(
    decision: StrategyDecision,
    portfolio_snapshot: Any,
    *,
    scope: str,
    mandate_provenance: Mapping[str, Any] | None,
    market_data: Mapping[str, Any],
    candidate_identity: CandidateRiskIdentity | None = None,
    normalization_origin_weights: Mapping[str, float] | None = None,
    risk_control_state: Mapping[str, Any] | None = None,
    capital_base: CapitalBaseSnapshot | Mapping[str, Any] | None = None,
    capital_base_binding: CapitalBaseBinding | Mapping[str, Any] | None = None,
    logical_evaluation_time: datetime | None = None,
) -> RiskGateResult:
    """Run the sole promotion/evidence-grade risk assessment API.

    ``mandate_provenance`` and a matching ``candidate_identity`` are required
    for an evidence-grade approval. Missing or invalid authority is rejected;
    the legacy :meth:`RiskEngine.assess` approval is never sufficient on its
    own. An explicit ``logical_evaluation_time`` must be a fresh UTC
    whole-second datetime; omitting it preserves wall-clock evaluation. The
    returned receipt is redacted and canonical.
    """
    try:
        from quant_platform_kit.risk import gate as _gate
        risk_action = _gate.build_risk_engine().assess(
            decision,
            portfolio_snapshot,
            market_data=market_data,
        )
    except Exception:
        risk_action = None
        risk_engine_failed = True
    else:
        risk_engine_failed = False
    wall_time = _gate._utc_now()
    now, logical_time_errors = _logical_evaluation_time(
        logical_evaluation_time,
        wall_time=wall_time,
    )
    if logical_time_errors:
        return _invalid_assessment_result(
            decision,
            scope=scope,
            mandate_provenance=mandate_provenance,
            candidate_identity=candidate_identity,
            now=wall_time,
            reason_codes=logical_time_errors,
        )
    try:
        return _assess_with_evidence_static(
            decision,
            portfolio_snapshot,
            scope=scope,
            mandate_provenance=mandate_provenance,
            candidate_identity=candidate_identity,
            normalization_origin_weights=normalization_origin_weights,
            risk_control_state=risk_control_state,
            capital_base=capital_base,
            capital_base_binding=capital_base_binding,
            now=now,
            risk_action=risk_action,
            risk_engine_failed=risk_engine_failed,
        )
    except Exception:
        return _invalid_assessment_result(
            decision,
            scope=scope,
            mandate_provenance=mandate_provenance,
            candidate_identity=candidate_identity,
            now=now,
        )


def enrich_decision_risk_diagnostics(
    decision: StrategyDecision,
    *,
    unrealized_pnl_pct: float | None = None,
    consecutive_losses: int | None = None,
) -> StrategyDecision:
    """Attach stop-loss / circuit-breaker diagnostics used by apply_risk_gate.

    Platforms should call this after computing portfolio PnL / trade streak,
    before ``apply_risk_gate``. Missing values are left unset (gate skips those
    checks).
    """
    diagnostics = dict(decision.diagnostics or {})
    if unrealized_pnl_pct is not None:
        normalized_pnl = _finite_number(unrealized_pnl_pct)
        diagnostics["unrealized_pnl_pct"] = (
            normalized_pnl if normalized_pnl is not None else unrealized_pnl_pct
        )
    if consecutive_losses is not None:
        normalized_losses = _bounded_nonnegative_int(consecutive_losses)
        diagnostics["consecutive_losses"] = (
            normalized_losses
            if normalized_losses is not None
            else consecutive_losses
        )
    if diagnostics == dict(decision.diagnostics or {}):
        return decision
    return StrategyDecision(
        positions=decision.positions,
        budgets=decision.budgets,
        risk_flags=decision.risk_flags,
        diagnostics=diagnostics,
    )
