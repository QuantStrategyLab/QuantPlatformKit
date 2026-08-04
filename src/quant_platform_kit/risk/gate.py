"""Unified risk gate — hard checks before any StrategyDecision is returned.

Consolidates the lightweight gate from CnEquityStrategies entrypoints with
optional RiskEngine integration and circuit-breaker diagnostics (task 8 prep).
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import logging
import math
from typing import Any, Mapping

from quant_platform_kit.common.models import PortfolioSnapshot
from quant_platform_kit.risk.contracts import RiskGateAssessment, RiskGateResult
from quant_platform_kit.risk.engine import build_risk_engine
from quant_platform_kit.strategy_contracts import StrategyDecision

logger = logging.getLogger(__name__)

_STOP_LOSS_THRESHOLD = -0.20
_MAX_CONSECUTIVE_LOSSES = 5
_DEFAULT_MAX_SINGLE_WEIGHT = 0.10
_APPROVED_BOOTSTRAP_MANDATE = "bootstrap_small_account_v2"
_BOOTSTRAP_EFFECTIVE_EXPOSURE_CAP = 0.50
_BOOTSTRAP_NOMINAL_CAPS = {1: 0.50, 2: 0.25, 3: 0.15}
_ASSESSMENT_CONTRACT_VERSION = "qsl.risk_gate_assessment.v1"
_ASSESSMENT_POLICY_ID = "qpk.risk_gate"
_ASSESSMENT_POLICY_VERSION = "v1"
_FALLBACK_MAX_SNAPSHOT_AGE_SECONDS_V1 = 300.0
_ALLOWED_SCOPES = frozenset({"MEMBER", "ACCOUNT"})
_ALLOWED_MANDATE_SCOPES = frozenset({"RESEARCH_ONLY", "PAPER", "LIVE"})


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canonical_digest(value: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _finite_number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _parse_utc_timestamp(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.endswith("Z"):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    return parsed.astimezone(timezone.utc) if parsed.tzinfo is not None else None


def _valid_cap_value(value: Any) -> bool:
    if isinstance(value, Mapping):
        return bool(value) and all(
            isinstance(key, str)
            and bool(key)
            and _valid_cap_value(candidate)
            for key, candidate in value.items()
        )
    cap = _finite_number(value)
    return cap is not None and 0.0 <= cap <= 1.0


def _sha256(value: Any) -> str | None:
    if not isinstance(value, str) or len(value) != 64:
        return None
    return value if all(character in "0123456789abcdef" for character in value) else None


def _decision_metrics(
    decision: StrategyDecision,
    *,
    total_equity: float | None,
) -> tuple[dict[str, Any], list[tuple[str, float]], set[str]]:
    active: list[tuple[str, float]] = []
    reason_codes: set[str] = set()
    position_payloads: list[dict[str, Any]] = []
    for position in decision.positions or ():
        symbol = getattr(position, "symbol", None)
        weight = _finite_number(getattr(position, "target_weight", None))
        target_value = _finite_number(getattr(position, "target_value", None))
        position_payloads.append(
            {
                "symbol": symbol if isinstance(symbol, str) else None,
                "target_weight": weight,
                "target_value": target_value,
                "role": getattr(position, "role", None),
                "order_preference": getattr(position, "order_preference", None),
            }
        )
        if (
            not isinstance(symbol, str)
            or not symbol
            or (weight is None) == (target_value is None)
        ):
            reason_codes.add("invalid_decision_exposure")
            continue
        normalized_weight = weight
        if target_value is not None:
            if total_equity is None or total_equity <= 0.0:
                reason_codes.add("invalid_decision_exposure")
                continue
            normalized_weight = target_value / total_equity
        if normalized_weight is None or normalized_weight < 0.0:
            reason_codes.add("invalid_decision_exposure")
            continue
        if normalized_weight > 0.0:
            active.append((symbol, normalized_weight))
    budget_payloads: list[dict[str, Any]] = []
    for budget in decision.budgets or ():
        budget_payloads.append(
            {
                "name": getattr(budget, "name", None),
                "symbol": getattr(budget, "symbol", None),
                "amount": _finite_number(getattr(budget, "amount", None)),
                "unit": getattr(budget, "unit", None),
                "purpose": getattr(budget, "purpose", None),
            }
        )
    return {
        "positions": position_payloads,
        "budgets": budget_payloads,
    }, active, reason_codes


def _snapshot_metrics(
    portfolio_snapshot: Any,
    *,
    now: datetime,
    max_snapshot_age_seconds: float | None,
) -> tuple[dict[str, Any], float | None, float | None, set[str]]:
    if isinstance(portfolio_snapshot, Mapping):
        as_of_value = portfolio_snapshot.get("as_of")
        observed_value = portfolio_snapshot.get("observed_effective_exposure")
        total_equity_value = portfolio_snapshot.get("total_equity")
    elif isinstance(portfolio_snapshot, PortfolioSnapshot):
        metadata = portfolio_snapshot.metadata
        as_of_value = portfolio_snapshot.as_of
        observed_value = metadata.get("observed_effective_exposure")
        total_equity_value = portfolio_snapshot.total_equity
    else:
        return {}, None, None, {"invalid_portfolio_snapshot"}
    as_of = _parse_utc_timestamp(as_of_value)
    observed = _finite_number(observed_value)
    total_equity = _finite_number(total_equity_value)
    if (
        as_of is None
        or observed is None
        or observed < 0.0
        or total_equity is None
        or total_equity <= 0.0
    ):
        return {}, observed, total_equity, {"invalid_portfolio_snapshot"}
    age_seconds = (now - as_of).total_seconds()
    if age_seconds < 0.0 or (
        max_snapshot_age_seconds is not None and age_seconds > max_snapshot_age_seconds
    ):
        return {}, observed, total_equity, {"stale_portfolio_snapshot"}
    return {
        "as_of": _utc_timestamp(as_of),
        "observed_effective_exposure": observed,
        "total_equity": total_equity,
    }, observed, total_equity, set()


def _mandate_fields(
    mandate_provenance: Mapping[str, Any] | None,
    *,
    now: datetime,
) -> tuple[dict[str, Any], set[str]]:
    if mandate_provenance is None:
        return {
            "mandate_id": None,
            "mandate_version": None,
            "authority_receipt_sha256": None,
            "authority_scope": None,
            "source_revision": None,
            "effective_exposure_cap": _DEFAULT_MAX_SINGLE_WEIGHT,
            "max_snapshot_age_seconds": _FALLBACK_MAX_SNAPSHOT_AGE_SECONDS_V1,
            "loss_budget": 0.0,
            "product_leverage_factors": {},
            "allowed_nonzero_assets": None,
        }, set()
    if not isinstance(mandate_provenance, Mapping):
        return {}, {"invalid_mandate"}
    required = (
        "mandate_id",
        "mandate_version",
        "authority_receipt_sha256",
        "authority_scope",
        "strategy_profile",
        "account_mode",
        "effective_at",
        "expires_at",
        "max_snapshot_age_seconds",
        "effective_exposure_cap",
        "loss_budget",
        "product_caps",
        "nominal_caps",
        "product_leverage_factors",
        "allowed_nonzero_assets",
        "source_revision",
    )
    if any(
        field not in mandate_provenance
        or mandate_provenance[field] is None
        or mandate_provenance[field] == ""
        for field in required
    ):
        return {}, {"invalid_mandate"}
    authority_scope = mandate_provenance["authority_scope"]
    receipt_sha256 = _sha256(mandate_provenance["authority_receipt_sha256"])
    effective_at = _parse_utc_timestamp(mandate_provenance["effective_at"])
    expires_at = _parse_utc_timestamp(mandate_provenance["expires_at"])
    max_snapshot_age_seconds = _finite_number(mandate_provenance["max_snapshot_age_seconds"])
    cap = _finite_number(mandate_provenance["effective_exposure_cap"])
    loss_budget = _finite_number(mandate_provenance["loss_budget"])
    if (
        not isinstance(mandate_provenance["mandate_id"], str)
        or not isinstance(mandate_provenance["mandate_version"], str)
        or not isinstance(mandate_provenance["source_revision"], str)
        or not isinstance(mandate_provenance["strategy_profile"], str)
        or not isinstance(mandate_provenance["account_mode"], str)
        or authority_scope not in _ALLOWED_MANDATE_SCOPES
        or receipt_sha256 is None
        or effective_at is None
        or expires_at is None
        or max_snapshot_age_seconds is None
        or max_snapshot_age_seconds <= 0.0
        or cap is None
        or not 0.0 <= cap <= 1.0
        or loss_budget is None
        or loss_budget < 0.0
    ):
        return {}, {"invalid_mandate"}
    if effective_at > now or expires_at < now or expires_at <= effective_at:
        return {}, {"expired_mandate"}
    factors = mandate_provenance.get("product_leverage_factors", {})
    allowed_assets = mandate_provenance.get("allowed_nonzero_assets")
    if (
        not isinstance(factors, Mapping)
        or not _valid_cap_value(mandate_provenance["product_caps"])
        or not _valid_cap_value(mandate_provenance["nominal_caps"])
        or (
            allowed_assets is not None
            and (
                not isinstance(allowed_assets, (list, tuple))
                or not all(isinstance(asset, str) and asset for asset in allowed_assets)
            )
        )
    ):
        return {}, {"invalid_mandate"}
    return {
        "mandate_id": mandate_provenance["mandate_id"],
        "mandate_version": mandate_provenance["mandate_version"],
        "authority_receipt_sha256": receipt_sha256,
        "authority_scope": authority_scope,
        "source_revision": mandate_provenance["source_revision"],
        "effective_exposure_cap": cap,
        "max_snapshot_age_seconds": max_snapshot_age_seconds,
        "loss_budget": loss_budget,
        "product_leverage_factors": factors,
        "product_caps": mandate_provenance["product_caps"],
        "nominal_caps": mandate_provenance["nominal_caps"],
        "allowed_nonzero_assets": set(allowed_assets) if allowed_assets is not None else None,
    }, set()


def _position_cap(value: Any, symbol: str, leverage_factor: float) -> float | None:
    if isinstance(value, Mapping):
        leverage_class = str(int(leverage_factor))
        if symbol in value:
            value = value[symbol]
        elif leverage_class in value:
            value = value[leverage_class]
        else:
            return None
    cap = _finite_number(value)
    return cap if cap is not None and 0.0 <= cap <= 1.0 else None


def _budget_authority_errors(
    decision: StrategyDecision,
    mandate: Mapping[str, Any],
) -> set[str]:
    requested_budget = 0.0
    for budget in decision.budgets or ():
        amount = _finite_number(getattr(budget, "amount", None))
        if amount is None or amount < 0.0:
            return {"invalid_decision_budget"}
        requested_budget += amount
    authorized_budget = _finite_number(mandate.get("loss_budget"))
    if requested_budget > 0.0 and (
        mandate.get("effective_exposure_cap") == 0.0
        or authorized_budget is None
        or requested_budget > authorized_budget + 1e-9
    ):
        return {"budget_authority_exceeded"}
    return set()


def assess_with_evidence(
    decision: StrategyDecision,
    portfolio_snapshot: Any,
    *,
    scope: str,
    mandate_provenance: Mapping[str, Any] | None,
    market_data: Mapping[str, Any],
) -> RiskGateResult:
    """Assess exactly once and fail closed with a redacted canonical receipt."""
    now = _utc_now()
    evaluated_at = _utc_timestamp(now)
    assessment_scope = scope if scope in _ALLOWED_SCOPES else "MEMBER"
    mandate, mandate_errors = _mandate_fields(mandate_provenance, now=now)
    reason_codes = set(mandate_errors)
    cap = mandate.get("effective_exposure_cap")
    snapshot_payload, observed, total_equity, snapshot_errors = _snapshot_metrics(
        portfolio_snapshot,
        now=now,
        max_snapshot_age_seconds=mandate.get("max_snapshot_age_seconds"),
    )
    reason_codes.update(snapshot_errors)
    decision_payload, active_positions, decision_errors = _decision_metrics(
        decision,
        total_equity=total_equity,
    )
    reason_codes.update(decision_errors)
    if scope not in _ALLOWED_SCOPES:
        reason_codes.add("invalid_scope")
    can_evaluate_policy = not reason_codes
    if mandate:
        reason_codes.update(_budget_authority_errors(decision, mandate))

    proposed: float | None = None
    if can_evaluate_policy:
        factors = mandate["product_leverage_factors"]
        allowed_assets = mandate["allowed_nonzero_assets"]
        weighted_exposure = 0.0
        if mandate_provenance is None and len(active_positions) > 1:
            reason_codes.add("fallback_position_count")
        for symbol, weight in active_positions:
            if allowed_assets is not None and symbol not in allowed_assets:
                reason_codes.add("asset_not_authorized")
                continue
            factor = 1.0 if mandate_provenance is None else _finite_number(factors.get(symbol))
            if factor is None or not factor.is_integer() or factor < 1.0:
                reason_codes.add("invalid_leverage_classification")
                continue
            product_cap = _position_cap(mandate.get("product_caps", 1.0), symbol, factor)
            nominal_cap = _position_cap(mandate.get("nominal_caps", 1.0), symbol, factor)
            if product_cap is None or nominal_cap is None:
                reason_codes.add("invalid_product_cap")
                continue
            if weight > min(product_cap, nominal_cap):
                reason_codes.add("product_exposure_cap")
            weighted_exposure += weight * factor
        proposed = max(observed or 0.0, weighted_exposure)
        if cap is None or observed is None or observed > cap + 1e-9:
            reason_codes.add("observed_effective_exposure")
        if cap is None or proposed > cap + 1e-9:
            reason_codes.add("effective_exposure_cap")

    has_static_rejection = bool(reason_codes)
    try:
        risk_action = build_risk_engine().assess(
            decision,
            portfolio_snapshot,
            market_data=market_data,
        )
    except Exception:
        if not has_static_rejection:
            reason_codes.add("risk_engine_error")
    else:
        if risk_action.action != "approve" and not has_static_rejection:
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
        decision_digest_sha256=_canonical_digest(decision_payload),
        portfolio_snapshot_digest_sha256=_canonical_digest(snapshot_payload),
        effective_exposure_cap=cap,
        observed_effective_exposure=observed,
        proposed_effective_exposure=proposed,
        outcome=outcome,
        reason_codes=tuple(sorted(reason_codes)),
    )
    if outcome == "REJECT":
        return RiskGateResult(
            decision=_reject(
                decision,
                flag="rejected:risk_gate_assessment",
                reason=",".join(assessment.reason_codes),
            ),
            assessment=assessment,
        )
    risk_flags = tuple(decision.risk_flags or ()) + ("risk_gate:passed",)
    return RiskGateResult(
        decision=StrategyDecision(
            positions=decision.positions,
            budgets=decision.budgets,
            risk_flags=risk_flags,
            diagnostics={**(decision.diagnostics or {}), "risk_gate": "APPROVE"},
        ),
        assessment=assessment,
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
        diagnostics["unrealized_pnl_pct"] = float(unrealized_pnl_pct)
    if consecutive_losses is not None:
        diagnostics["consecutive_losses"] = int(consecutive_losses)
    if diagnostics == dict(decision.diagnostics or {}):
        return decision
    return StrategyDecision(
        positions=decision.positions,
        budgets=decision.budgets,
        risk_flags=decision.risk_flags,
        diagnostics=diagnostics,
    )


def apply_risk_gate(
    decision: StrategyDecision,
    *,
    risk_mandate_id: str | None = None,
    product_leverage_factors: Mapping[str, int] | None = None,
    available_account_exposure: float | None = None,
    max_single_weight: float = _DEFAULT_MAX_SINGLE_WEIGHT,
    max_positions: int = 20,
    max_total_exposure: float = 1.0,
    portfolio_snapshot: Any | None = None,
    market_data: Mapping[str, Any] | None = None,
) -> StrategyDecision:
    """Apply hard risk checks to a strategy decision.

    Checks (in order):
    1. Circuit breaker from diagnostics (unrealized_pnl_pct, consecutive_losses)
    2. Mandate-specific single-account and leverage classification limits
    3. Legacy caller-supplied concentration limits when no mandate is supplied
    4. Legacy position-count and total-exposure limits
    5. RiskEngine.assess() exactly once; missing/invalid snapshots reject

    Returns an empty-position StrategyDecision on REJECT.
    """
    diagnostics = dict(decision.diagnostics or {})
    static_rejection: tuple[str, str] | None = None

    pnl_pct = diagnostics.get("unrealized_pnl_pct")
    if pnl_pct is not None and float(pnl_pct) < _STOP_LOSS_THRESHOLD:
        logger.warning(
            "risk_gate REJECT stop_loss: unrealized_pnl_pct=%.2f%%",
            float(pnl_pct) * 100,
        )
        static_rejection = (
            "rejected:stop_loss",
            f"未实现亏损 {float(pnl_pct):.1%} < {_STOP_LOSS_THRESHOLD:.0%} 止损线",
        )

    consecutive_losses = diagnostics.get("consecutive_losses")
    if (
        static_rejection is None
        and consecutive_losses is not None
        and int(consecutive_losses) > _MAX_CONSECUTIVE_LOSSES
    ):
        logger.warning(
            "risk_gate REJECT circuit_breaker: consecutive_losses=%d",
            int(consecutive_losses),
        )
        static_rejection = (
            "rejected:circuit_breaker",
            f"连续亏损 {int(consecutive_losses)} 笔 > {_MAX_CONSECUTIVE_LOSSES} 熔断",
        )

    if (
        static_rejection is None
        and risk_mandate_id not in {None, _APPROVED_BOOTSTRAP_MANDATE}
    ):
        static_rejection = (
            "rejected:unknown_risk_mandate",
            "风险授权未获批准",
        )

    positions = decision.positions or ()
    weights: list[tuple[Any, float]] = []
    if static_rejection is None:
        for position in positions:
            raw_weight = position.target_weight
            if raw_weight is None:
                weight = 0.0
            elif isinstance(raw_weight, bool) or not isinstance(
                raw_weight,
                (int, float),
            ):
                static_rejection = (
                    "rejected:invalid_weight",
                    f"{position.symbol} 目标仓位无效",
                )
                break
            else:
                weight = abs(float(raw_weight))
                if not math.isfinite(weight):
                    static_rejection = (
                        "rejected:invalid_weight",
                        f"{position.symbol} 目标仓位无效",
                    )
                    break
            if weight > 0.0:
                weights.append((position, weight))

    if (
        static_rejection is None
        and positions
        and risk_mandate_id == _APPROVED_BOOTSTRAP_MANDATE
    ):
        if len(weights) > 1:
            static_rejection = (
                "rejected:too_many_positions",
                "bootstrap_small_account_v2 仅允许一个非零持仓",
            )
        elif available_account_exposure is None or (
            isinstance(available_account_exposure, bool)
            or not isinstance(available_account_exposure, (int, float))
            or not math.isfinite(float(available_account_exposure))
            or not 0.0
            <= float(available_account_exposure)
            <= _BOOTSTRAP_EFFECTIVE_EXPOSURE_CAP
        ):
            static_rejection = (
                "rejected:overexposed",
                "可用账户仓位容量无效",
            )
        elif weights:
            active_symbols = {position.symbol for position, _ in weights}
            if (
                product_leverage_factors is None
                or set(product_leverage_factors) != active_symbols
            ):
                static_rejection = (
                    "rejected:leverage_classification",
                    "缺少或不一致的产品杠杆分类",
                )
            else:
                position, weight = weights[0]
                leverage_factor = product_leverage_factors[position.symbol]
                if (
                    isinstance(leverage_factor, bool)
                    or not isinstance(leverage_factor, int)
                    or leverage_factor not in _BOOTSTRAP_NOMINAL_CAPS
                ):
                    static_rejection = (
                        "rejected:leverage_classification",
                        "产品杠杆分类无效",
                    )
                else:
                    nominal_cap = _BOOTSTRAP_NOMINAL_CAPS[leverage_factor]
                    effective_exposure = weight * leverage_factor
                    if weight > nominal_cap:
                        static_rejection = (
                            "rejected:concentration",
                            f"{position.symbol} {weight:.1%} > {nominal_cap:.0%} 上限",
                        )
                    elif effective_exposure > _BOOTSTRAP_EFFECTIVE_EXPOSURE_CAP + 1e-9:
                        static_rejection = (
                            "rejected:overexposed",
                            f"有效敞口 {effective_exposure:.1%} > 50%",
                        )
                    elif weight > float(available_account_exposure) + 1e-9:
                        static_rejection = (
                            "rejected:overexposed",
                            f"名义仓位 {weight:.1%} > 可用账户容量",
                        )
    elif static_rejection is None and positions:
        requested_single_weight = _finite_number(max_single_weight)
        effective_single_weight = min(
            requested_single_weight
            if requested_single_weight is not None and requested_single_weight >= 0.0
            else _DEFAULT_MAX_SINGLE_WEIGHT,
            _DEFAULT_MAX_SINGLE_WEIGHT,
        )
        if len(weights) > 1:
            static_rejection = (
                "rejected:too_many_positions",
                "未获授权的风险配置仅允许一个非零持仓",
            )
        elif weights and weights[0][1] > effective_single_weight:
            position, weight = weights[0]
            logger.warning(
                "risk_gate REJECT concentration: symbol=%s weight=%.2f%% limit=%.0f%%",
                position.symbol,
                weight * 100,
                effective_single_weight * 100,
            )
            static_rejection = (
                "rejected:concentration",
                f"{position.symbol} {weight:.1%} > {effective_single_weight:.0%} 上限",
            )
        elif len(positions) > max_positions:
            logger.warning(
                "risk_gate REJECT position_count: %d > %d",
                len(positions),
                max_positions,
            )
            static_rejection = (
                "rejected:too_many_positions",
                f"{len(positions)} 个持仓 > {max_positions} 上限",
            )
        else:
            total_weight = sum(weight for _, weight in weights)
            if total_weight > max_total_exposure + 1e-9:
                logger.warning(
                    "risk_gate REJECT total_exposure: %.2f%% > %.0f%%",
                    total_weight * 100,
                    max_total_exposure * 100,
                )
                static_rejection = (
                    "rejected:overexposed",
                    f"总仓位 {total_weight:.1%} > {max_total_exposure:.0%}",
                )
            elif weights:
                active_symbols = {position.symbol for position, _ in weights}
                if (
                    product_leverage_factors is None
                    or set(product_leverage_factors) != active_symbols
                    or any(
                        isinstance(factor, bool)
                        or not isinstance(factor, int)
                        or factor != 1
                        for factor in product_leverage_factors.values()
                    )
                ):
                    static_rejection = (
                        "rejected:leverage_classification",
                        "未获授权的风险配置必须明确为无杠杆产品",
                    )

    try:
        assessment = build_risk_engine().assess(
            decision,
            portfolio_snapshot,
            market_data=market_data,
        )
    except Exception:
        engine_rejection = ("rejected:risk_engine", "risk_engine_error")
    else:
        if assessment.action != "approve":
            logger.warning("risk_gate REJECT risk_engine: %s", assessment.reason)
            engine_rejection = ("rejected:risk_engine", assessment.reason)
        else:
            engine_rejection = None

    rejection = static_rejection or engine_rejection
    if rejection is not None:
        return _reject(decision, flag=rejection[0], reason=rejection[1])

    risk_flags = list(decision.risk_flags or ())
    risk_flags.append("risk_gate:passed")
    return StrategyDecision(
        positions=decision.positions,
        budgets=decision.budgets,
        risk_flags=tuple(risk_flags),
        diagnostics={**diagnostics, "risk_gate": "APPROVE"},
    )


def _reject(
    decision: StrategyDecision,
    *,
    flag: str,
    reason: str,
) -> StrategyDecision:
    return StrategyDecision(
        positions=(),
        budgets=(),
        risk_flags=(flag,),
        diagnostics={
            **(decision.diagnostics or {}),
            "risk_gate": "REJECT",
            "reason": reason,
        },
    )
