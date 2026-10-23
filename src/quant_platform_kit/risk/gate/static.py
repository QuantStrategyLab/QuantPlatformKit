"""Static risk gate checks, decision application, and rejection helpers."""

from __future__ import annotations

import logging
import math
from datetime import datetime
from typing import Any, Mapping

from quant_platform_kit.common.capital_base import (
    CapitalBaseBinding,
    CapitalBaseSnapshot,
    CapitalBaseValidation,
    validate_capital_base,
)
from quant_platform_kit.common.risk_mandates import (
    _APPROVED_BOOTSTRAP_MANDATE,
    _BOOTSTRAP_EFFECTIVE_EXPOSURE_CAP,
    _BOOTSTRAP_NOMINAL_CAPS,
)
from quant_platform_kit.common.strategy_contracts import (
    BudgetIntent,
    PositionTarget,
    StrategyDecision,
)
from quant_platform_kit.risk.contracts import RuntimeRiskLimits, SmallAccountRiskHoldPolicy

from .mandates import _DEFAULT_MAX_SINGLE_WEIGHT, _value_target_exposure_audit
from .support import (
    _MAX_MATERIAL_ITEMS,
    _bounded_nonnegative_int,
    _canonical_numeric_mapping,
    _canonical_string,
    _canonical_string_list,
    _finite_number,
    _normalized_weight_map,
    _observe,
    _portfolio_current_weights,
    _runtime_risk_limits_rejection,
    _safe_diagnostics,
    _static_gate_total_equity,
)

logger = logging.getLogger("quant_platform_kit.risk.gate")


_STOP_LOSS_THRESHOLD = -0.20


_MAX_CONSECUTIVE_LOSSES = 5


def _apply_risk_gate_static(
    decision: StrategyDecision,
    *,
    risk_mandate_id: Any,
    product_leverage_factors: Any,
    available_account_exposure: Any,
    max_single_weight: Any,
    max_positions: Any,
    max_total_exposure: Any,
    portfolio_snapshot: Any,
    enforce_value_target_exposure: Any,
    capital_base: CapitalBaseSnapshot | Mapping[str, Any] | None,
    capital_base_binding: CapitalBaseBinding | Mapping[str, Any] | None,
    runtime_risk_limits: RuntimeRiskLimits | None,
    small_account_hold_policy: SmallAccountRiskHoldPolicy | None,
    current_portfolio_weights: Mapping[str, float] | None,
    cash_only_execution: bool | None,
    now: datetime,
    engine_action: Any,
    engine_failed: bool,
    observer=None,
) -> StrategyDecision:
    if type(decision) is not StrategyDecision:
        raise TypeError("invalid decision")
    diagnostics, valid_diagnostics = _safe_diagnostics(decision.diagnostics)
    static_rejection: tuple[str, str] | None = None
    if not valid_diagnostics:
        static_rejection = (
            "rejected:invalid_risk_metadata",
            "invalid_risk_metadata",
        )

    normalized_risk_flags = (
        _canonical_string_list(decision.risk_flags)
        if type(decision.risk_flags) is tuple
        else None
    )
    raw_positions = decision.positions
    raw_budgets = decision.budgets
    if (
        normalized_risk_flags is None
        or type(raw_positions) is not tuple
        or len(raw_positions) > _MAX_MATERIAL_ITEMS
        or type(raw_budgets) is not tuple
        or len(raw_budgets) > _MAX_MATERIAL_ITEMS
    ):
        static_rejection = static_rejection or (
            "rejected:invalid_risk_metadata",
            "invalid_risk_metadata",
        )

    mandate_id, valid_mandate_id = _canonical_string(
        risk_mandate_id,
        optional=True,
    )
    requested_single_weight = _finite_number(max_single_weight)
    position_limit = _bounded_nonnegative_int(max_positions)
    total_exposure_limit = _finite_number(max_total_exposure)
    value_target_exposure_enforced = type(enforce_value_target_exposure) is bool and bool(
        enforce_value_target_exposure
    )
    available_exposure = (
        None
        if available_account_exposure is None
        else _finite_number(available_account_exposure)
    )
    factors = (
        None
        if product_leverage_factors is None
        else _canonical_numeric_mapping(
            product_leverage_factors,
            integer=True,
            minimum=1.0,
        )
    )
    if (
        not valid_mandate_id
        or requested_single_weight is None
        or requested_single_weight < 0.0
        or position_limit is None
        or total_exposure_limit is None
        or total_exposure_limit < 0.0
        or type(enforce_value_target_exposure) is not bool
        or (
            available_account_exposure is not None
            and available_exposure is None
        )
        or (product_leverage_factors is not None and factors is None)
    ):
        static_rejection = static_rejection or (
            "rejected:invalid_risk_metadata",
            "invalid_risk_metadata",
        )

    for position in raw_positions if type(raw_positions) is tuple else ():
        if type(position) is not PositionTarget:
            static_rejection = static_rejection or (
                "rejected:invalid_risk_metadata",
                "invalid_risk_metadata",
            )
            continue
        symbol, valid_symbol = _canonical_string(position.symbol)
        _role, valid_role = _canonical_string(position.role, optional=True)
        _preference, valid_preference = _canonical_string(
            position.order_preference,
            optional=True,
        )
        target_value = _finite_number(position.target_value)
        if (
            not valid_symbol
            or symbol is None
            or not valid_role
            or not valid_preference
            or (position.target_value is not None and target_value is None)
        ):
            static_rejection = static_rejection or (
                "rejected:invalid_risk_metadata",
                "invalid_risk_metadata",
            )

    for budget in raw_budgets if type(raw_budgets) is tuple else ():
        if type(budget) is not BudgetIntent:
            static_rejection = static_rejection or (
                "rejected:invalid_risk_metadata",
                "invalid_risk_metadata",
            )
            continue
        _name, valid_name = _canonical_string(budget.name)
        _symbol, valid_symbol = _canonical_string(budget.symbol, optional=True)
        _unit, valid_unit = _canonical_string(budget.unit)
        _purpose, valid_purpose = _canonical_string(budget.purpose, optional=True)
        amount = _finite_number(budget.amount)
        if (
            not valid_name
            or not valid_symbol
            or not valid_unit
            or not valid_purpose
            or amount is None
            or amount < 0.0
        ):
            static_rejection = static_rejection or (
                "rejected:invalid_risk_metadata",
                "invalid_risk_metadata",
            )

    pnl_pct_value = diagnostics.get("unrealized_pnl_pct")
    if pnl_pct_value is not None:
        pnl_pct = _finite_number(pnl_pct_value)
        if pnl_pct is None:
            diagnostics.pop("unrealized_pnl_pct", None)
            static_rejection = static_rejection or (
                "rejected:invalid_risk_metadata",
                "invalid_risk_metadata",
            )
        elif static_rejection is None and pnl_pct < _STOP_LOSS_THRESHOLD:
            logger.warning(
                "risk_gate REJECT stop_loss: unrealized_pnl_pct=%.2f%%",
                pnl_pct * 100,
            )
            static_rejection = (
                "rejected:stop_loss",
                f"未实现亏损 {pnl_pct:.1%} < {_STOP_LOSS_THRESHOLD:.0%} 止损线",
            )

    losses_value = diagnostics.get("consecutive_losses")
    if losses_value is not None:
        consecutive_losses = _bounded_nonnegative_int(losses_value)
        if consecutive_losses is None:
            diagnostics.pop("consecutive_losses", None)
            static_rejection = static_rejection or (
                "rejected:invalid_risk_metadata",
                "invalid_risk_metadata",
            )
        elif (
            static_rejection is None
            and consecutive_losses > _MAX_CONSECUTIVE_LOSSES
        ):
            logger.warning(
                "risk_gate REJECT circuit_breaker: consecutive_losses=%d",
                consecutive_losses,
            )
            static_rejection = (
                "rejected:circuit_breaker",
                f"连续亏损 {consecutive_losses} 笔 > {_MAX_CONSECUTIVE_LOSSES} 熔断",
            )

    if (
        static_rejection is None
        and mandate_id not in {None, _APPROVED_BOOTSTRAP_MANDATE}
    ):
        static_rejection = (
            "rejected:unknown_risk_mandate",
            "风险授权未获批准",
        )

    positions = raw_positions if type(raw_positions) is tuple else ()
    value_target_total_equity = _static_gate_total_equity(portfolio_snapshot)
    value_targets_present = any(
        position.target_value is not None
        for position in positions
        if type(position) is PositionTarget
    )
    capital_base_validation: CapitalBaseValidation | None = None
    if value_targets_present and value_target_exposure_enforced:
        capital_base_validation = validate_capital_base(
            capital_base,
            binding=capital_base_binding,
            now=now,
        )
        value_target_total_equity = capital_base_validation.target_equity
        if not capital_base_validation.is_valid:
            static_rejection = static_rejection or (
                "rejected:capital_base",
                ",".join(capital_base_validation.findings),
            )
    if value_targets_present:
        diagnostics["value_target_exposure_policy"] = (
            "enforced" if value_target_exposure_enforced else "legacy_compatibility"
        )
        audit = _value_target_exposure_audit(
            positions,
            total_equity=value_target_total_equity,
            enforced=value_target_exposure_enforced,
            capital_base_validation=capital_base_validation,
        )
        if audit is not None:
            diagnostics["value_target_exposure_audit"] = audit
    weights: list[tuple[PositionTarget, float]] = []
    if static_rejection is None:
        for position in positions:
            raw_weight = position.target_weight
            if raw_weight is not None:
                normalized_weight = _finite_number(raw_weight)
                if normalized_weight is None:
                    if type(raw_weight) is str:
                        static_rejection = (
                            "rejected:invalid_weight",
                            f"{position.symbol} 目标仓位无效",
                        )
                    else:
                        static_rejection = (
                            "rejected:invalid_risk_metadata",
                            "invalid_risk_metadata",
                        )
                    break
                weight = abs(normalized_weight)
            elif value_target_exposure_enforced:
                target_value = _finite_number(position.target_value)
                if target_value is None or value_target_total_equity is None:
                    static_rejection = (
                        "rejected:invalid_decision_exposure",
                        "金额目标缺少有效账户净值",
                    )
                    break
                normalized_weight = target_value / value_target_total_equity
                if not math.isfinite(normalized_weight) or normalized_weight < 0.0:
                    static_rejection = (
                        "rejected:invalid_decision_exposure",
                        f"{position.symbol} 金额目标无效",
                    )
                    break
                weight = normalized_weight
            else:
                # Existing value-target strategies must explicitly opt in to
                # enforcement.  This preserves their validated execution
                # contract while surfacing the migration state in diagnostics.
                continue
            if weight > 0.0:
                weights.append((position, weight))

    if static_rejection is None and runtime_risk_limits is not None:
        hold_diagnostics: dict[str, Any] = {}
        verified_nav = None
        if isinstance(capital_base, CapitalBaseSnapshot):
            try:
                verified_nav = float(capital_base.target_equity)
            except (TypeError, ValueError, AttributeError):
                verified_nav = None
        elif isinstance(capital_base, Mapping):
            verified_nav = _finite_number(capital_base.get("reported_equity"))
            fx = _finite_number(capital_base.get("fx_rate_to_target"))
            if verified_nav is not None and fx is not None:
                verified_nav = verified_nav * fx
        resolved_current_weights = _normalized_weight_map(current_portfolio_weights)
        if resolved_current_weights is None:
            resolved_current_weights = _portfolio_current_weights(
                portfolio_snapshot,
                verified_nav=verified_nav,
            )
        runtime_rejection = _runtime_risk_limits_rejection(
            runtime_risk_limits,
            positions=positions,
            budgets=raw_budgets,
            weights=weights,
            value_target_exposure_enforced=value_target_exposure_enforced,
            hold_policy=small_account_hold_policy,
            verified_nav=verified_nav,
            current_weights=resolved_current_weights,
            cash_only_execution=cash_only_execution,
            hold_diagnostics=hold_diagnostics,
            **({"observer": observer} if observer is not None else {}),
        )
        _observe(observer, "limits", "RETURNED")
        _observe(observer, "limits_check", "REJECT" if runtime_rejection is not None else "PASS")
        if runtime_rejection is not None:
            static_rejection = runtime_rejection
        elif hold_diagnostics:
            diagnostics.update(hold_diagnostics)
    else:
        _observe(observer, "limits", "NOT_REACHED")
    if (
        static_rejection is None
        and positions
        and mandate_id == _APPROVED_BOOTSTRAP_MANDATE
    ):
        if len(weights) > 1:
            static_rejection = (
                "rejected:too_many_positions",
                "bootstrap_small_account_v2 仅允许一个非零持仓",
            )
        elif available_exposure is None or not (
            0.0 <= available_exposure <= _BOOTSTRAP_EFFECTIVE_EXPOSURE_CAP
        ):
            static_rejection = (
                "rejected:overexposed",
                "可用账户仓位容量无效",
            )
        elif weights:
            active_symbols = {position.symbol for position, _ in weights}
            if factors is None or set(factors) != active_symbols:
                static_rejection = (
                    "rejected:leverage_classification",
                    "缺少或不一致的产品杠杆分类",
                )
            else:
                position, weight = weights[0]
                leverage_factor = factors[position.symbol]
                if leverage_factor not in _BOOTSTRAP_NOMINAL_CAPS:
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
                    elif weight > available_exposure + 1e-9:
                        static_rejection = (
                            "rejected:overexposed",
                            f"名义仓位 {weight:.1%} > 可用账户容量",
                        )
    elif static_rejection is None and positions and runtime_risk_limits is None:
        effective_single_weight = min(
            requested_single_weight,
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
        elif len(positions) > position_limit:
            logger.warning(
                "risk_gate REJECT position_count: %d > %d",
                len(positions),
                position_limit,
            )
            static_rejection = (
                "rejected:too_many_positions",
                f"{len(positions)} 个持仓 > {position_limit} 上限",
            )
        else:
            total_weight = sum(weight for _, weight in weights)
            if total_weight > total_exposure_limit + 1e-9:
                logger.warning(
                    "risk_gate REJECT total_exposure: %.2f%% > %.0f%%",
                    total_weight * 100,
                    total_exposure_limit * 100,
                )
                static_rejection = (
                    "rejected:overexposed",
                    f"总仓位 {total_weight:.1%} > {total_exposure_limit:.0%}",
                )
            elif weights:
                active_symbols = {position.symbol for position, _ in weights}
                if (
                    factors is None
                    or set(factors) != active_symbols
                    or any(factor != 1 for factor in factors.values())
                ):
                    static_rejection = (
                        "rejected:leverage_classification",
                        "未获授权的风险配置必须明确为无杠杆产品",
                    )

    engine_rejection: tuple[str, str] | None
    if engine_failed:
        engine_rejection = ("rejected:risk_engine", "risk_engine_error")
    elif getattr(engine_action, "action", None) != "approve":
        raw_reason = getattr(engine_action, "reason", None)
        reason, valid_reason = _canonical_string(raw_reason)
        engine_rejection = (
            "rejected:risk_engine",
            reason if valid_reason and reason is not None else "risk_engine_non_approve",
        )
    else:
        engine_rejection = None

    rejection = static_rejection or engine_rejection
    if rejection is not None:
        rejection_diagnostics = (
            {} if rejection[0] == "rejected:invalid_risk_metadata" else diagnostics
        )
        return _reject(
            decision,
            flag=rejection[0],
            reason=rejection[1],
            diagnostics=rejection_diagnostics,
        )

    return StrategyDecision(
        positions=decision.positions,
        budgets=decision.budgets,
        risk_flags=tuple(normalized_risk_flags or ()) + ("risk_gate:passed",),
        diagnostics={**diagnostics, "risk_gate": "APPROVE"},
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
    enforce_value_target_exposure: bool = False,
    capital_base: CapitalBaseSnapshot | Mapping[str, Any] | None = None,
    capital_base_binding: CapitalBaseBinding | Mapping[str, Any] | None = None,
    runtime_risk_limits: RuntimeRiskLimits | None = None,
    small_account_hold_policy: SmallAccountRiskHoldPolicy | None = None,
    current_portfolio_weights: Mapping[str, float] | None = None,
    cash_only_execution: bool | None = None,
    observer=None,
) -> StrategyDecision:
    """Apply hard checks and call RiskEngine.assess exactly once.

    Weight targets are always assessed.  A caller that enables
    ``enforce_value_target_exposure`` must provide a fresh ``capital_base``
    bound to the same account/runtime/strategy scope via
    ``capital_base_binding``; otherwise value targets fail closed.  Until a
    legacy value-target strategy is migrated, the default path records
    ``value_target_exposure_policy=legacy_compatibility`` in diagnostics.
    """
    _observe(observer, "gate", "ENTERED")
    try:
        from quant_platform_kit.risk import gate as _gate
        engine_action = _gate.build_risk_engine().assess(
            decision,
            portfolio_snapshot,
            market_data=market_data,
        )
    except Exception:
        engine_action = None
        engine_failed = True
    else:
        engine_failed = False
    now = _gate._utc_now()
    try:
        result = _gate._apply_risk_gate_static(
            decision,
            risk_mandate_id=risk_mandate_id,
            product_leverage_factors=product_leverage_factors,
            available_account_exposure=available_account_exposure,
            max_single_weight=max_single_weight,
            max_positions=max_positions,
            max_total_exposure=max_total_exposure,
            portfolio_snapshot=portfolio_snapshot,
            enforce_value_target_exposure=enforce_value_target_exposure,
            capital_base=capital_base,
            capital_base_binding=capital_base_binding,
            runtime_risk_limits=runtime_risk_limits,
            small_account_hold_policy=small_account_hold_policy,
            current_portfolio_weights=current_portfolio_weights,
            cash_only_execution=cash_only_execution,
            now=now,
            engine_action=engine_action,
            engine_failed=engine_failed,
            **({"observer": observer} if observer is not None else {}),
        )
    except Exception:
        result = _reject(
            decision,
            flag="rejected:invalid_risk_metadata",
            reason="invalid_risk_metadata",
            diagnostics={},
        )
    _observe(observer, "gate", "RETURNED")
    if observer is not None:
        try:
            outcome = result.diagnostics.get("risk_gate")
        except BaseException:
            outcome = None
        if type(outcome) is str and outcome in ("APPROVE", "REJECT"):
            _observe(observer, "gate_outcome", outcome)
    return result


def _reject(
    decision: StrategyDecision,
    *,
    flag: str,
    reason: str,
    diagnostics: Mapping[str, Any] | None = None,
) -> StrategyDecision:
    safe_diagnostics: dict[str, Any] = {}
    if diagnostics is not None:
        try:
            safe_diagnostics, valid = _safe_diagnostics(diagnostics)
        except Exception:
            valid = False
        if not valid:
            safe_diagnostics = {}
    else:
        try:
            safe_diagnostics, valid = _safe_diagnostics(decision.diagnostics)
        except Exception:
            valid = False
        if not valid:
            safe_diagnostics = {}
    return StrategyDecision(
        positions=(),
        budgets=(),
        risk_flags=(flag,),
        diagnostics={
            **safe_diagnostics,
            "risk_gate": "REJECT",
            "reason": reason,
        },
    )
