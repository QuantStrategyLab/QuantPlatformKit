"""Shared timestamp, normalization, parsing, and numeric helpers for the risk gate."""

from __future__ import annotations

import hashlib
import json
import math
import unicodedata
from datetime import datetime, timezone
from typing import Any, Mapping

from quant_platform_kit.common.capital_base import CapitalBaseSnapshot
from quant_platform_kit.common.models import PortfolioSnapshot
from quant_platform_kit.risk.contracts import (
    DEFAULT_SMALL_ACCOUNT_HOLD_POLICY,
    RuntimeRiskLimits,
    SmallAccountRiskHoldPolicy,
)
from quant_platform_kit.common.strategy_contracts import (
    BudgetIntent,
    PositionTarget,
    StrategyDecision,
)


_TQQQ_EVIDENCE_MAX_AGE_SECONDS = 300.0


_MAX_JSON_SAFE_INTEGER = (1 << 53) - 1


_MAX_MATERIAL_ITEMS = 1_000


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


def _capital_base_snapshot_commitment(snapshot: CapitalBaseSnapshot) -> str:
    return _canonical_digest(
        {
            **snapshot.to_safe_dict(),
            "target_equity": snapshot.target_equity,
        }
    )


def _finite_number(value: Any) -> float | None:
    if type(value) not in (int, float):
        return None
    if type(value) is int and abs(value) > _MAX_JSON_SAFE_INTEGER:
        return None
    try:
        number = float(value)
    except (OverflowError, TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _bounded_nonnegative_int(value: Any) -> int | None:
    if type(value) is not int or not 0 <= value <= _MAX_JSON_SAFE_INTEGER:
        return None
    return value


def _canonical_string(
    value: Any,
    *,
    optional: bool = False,
) -> tuple[str | None, bool]:
    if value is None:
        return None, optional
    if type(value) is not str or not value or value != value.strip():
        return None, False
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        return None, False
    if unicodedata.normalize("NFC", value) != value:
        return None, False
    return value, True


def _canonical_string_list(value: Any) -> list[str] | None:
    if type(value) not in (list, tuple) or len(value) > _MAX_MATERIAL_ITEMS:
        return None
    result: list[str] = []
    for candidate in value:
        normalized, valid = _canonical_string(candidate)
        if not valid or normalized is None:
            return None
        result.append(normalized)
    return result


def _canonical_numeric_mapping(
    value: Any,
    *,
    integer: bool = False,
    minimum: float = 0.0,
    maximum: float | None = None,
) -> dict[str, int | float] | None:
    if not isinstance(value, Mapping) or len(value) > _MAX_MATERIAL_ITEMS:
        return None
    result: dict[str, int | float] = {}
    for item_count, (raw_key, raw_value) in enumerate(value.items(), start=1):
        if item_count > _MAX_MATERIAL_ITEMS:
            return None
        key, valid_key = _canonical_string(raw_key)
        if not valid_key or key is None:
            return None
        if integer:
            number = _bounded_nonnegative_int(raw_value)
        else:
            number = _finite_number(raw_value)
        if (
            number is None
            or number < minimum
            or (maximum is not None and number > maximum)
        ):
            return None
        result[key] = number
    return result


def _normalized_weight_map(raw: Mapping[str, Any] | None) -> dict[str, float] | None:
    if raw is None:
        return None
    if not isinstance(raw, Mapping):
        return None
    result: dict[str, float] = {}
    for key, value in raw.items():
        symbol = str(key or "").strip().upper()
        number = _finite_number(value)
        if not symbol or number is None or number < 0.0:
            return None
        if number > 0.0:
            result[symbol] = float(number)
    return result or None


def _portfolio_current_weights(
    portfolio_snapshot: Any,
    *,
    verified_nav: float | None,
) -> dict[str, float] | None:
    if portfolio_snapshot is None or verified_nav is None or verified_nav <= 0.0:
        return None
    positions = getattr(portfolio_snapshot, "positions", None)
    if positions is None:
        return None
    weights: dict[str, float] = {}
    try:
        for position in positions:
            symbol = str(getattr(position, "symbol", "") or "").strip().upper()
            market_value = _finite_number(getattr(position, "market_value", None))
            if not symbol or market_value is None or market_value <= 0.0:
                continue
            weights[symbol] = weights.get(symbol, 0.0) + float(market_value) / verified_nav
    except TypeError:
        return None
    return weights or None


def _resolve_small_account_hold_policy(
    hold_policy: SmallAccountRiskHoldPolicy | None,
) -> SmallAccountRiskHoldPolicy:
    """Default-enable hold for RRL paths; explicit policy (incl. disabled) wins."""
    if hold_policy is None:
        return DEFAULT_SMALL_ACCOUNT_HOLD_POLICY
    return hold_policy


def _small_account_hold_allows_overrun(
    *,
    limits: RuntimeRiskLimits,
    target_weights: list[tuple[PositionTarget, float]],
    overrun_codes: tuple[str, ...],
    hold_policy: SmallAccountRiskHoldPolicy | None,
    verified_nav: float | None,
    current_weights: Mapping[str, float] | None,
    cash_only_execution: bool | None,
) -> bool:
    hold_policy = _resolve_small_account_hold_policy(hold_policy)
    if type(hold_policy) is not SmallAccountRiskHoldPolicy or not hold_policy.enabled:
        return False
    if verified_nav is None or not math.isfinite(verified_nav) or verified_nav <= 0.0:
        return False
    if verified_nav >= hold_policy.hold_below_nav:
        return False
    if hold_policy.require_cash_only and cash_only_execution is not True:
        return False
    current = _normalized_weight_map(current_weights)
    if current is None:
        return False

    target_by_symbol = {position.symbol: float(weight) for position, weight in target_weights}
    for position, weight in target_weights:
        factor = limits.product_leverage_factors.get(position.symbol)
        nominal_cap = limits.nominal_caps.get(position.symbol)
        if factor is None or nominal_cap is None:
            return False
        if weight > nominal_cap + 1e-9:
            if weight > current.get(position.symbol, 0.0) + 1e-9:
                return False

    target_nominal = sum(target_by_symbol.values())
    target_effective = sum(
        weight * float(limits.product_leverage_factors[symbol])
        for symbol, weight in target_by_symbol.items()
    )
    current_nominal = sum(current.values())
    current_effective = 0.0
    for symbol, weight in current.items():
        factor = limits.product_leverage_factors.get(symbol)
        if factor is None:
            # Unknown leverage on an existing book cannot prove non-worsening.
            return False
        current_effective += weight * float(factor)

    if "total_nominal_cap_exceeded" in overrun_codes and target_nominal > current_nominal + 1e-9:
        return False
    if "total_effective_cap_exceeded" in overrun_codes and target_effective > current_effective + 1e-9:
        return False
    if not overrun_codes:
        return False
    return True


def _observe(observer, key, value):
    if observer is not None:
        try:
            observer.emit(key, value)
        except BaseException:
            try:
                object.__setattr__(observer, "_faulted", True)
            except BaseException:
                pass


def _runtime_risk_limits_rejection(
    limits: RuntimeRiskLimits,
    *,
    positions: tuple[PositionTarget, ...],
    budgets: tuple[BudgetIntent, ...],
    weights: list[tuple[PositionTarget, float]],
    value_target_exposure_enforced: bool,
    hold_policy: SmallAccountRiskHoldPolicy | None = None,
    verified_nav: float | None = None,
    current_weights: Mapping[str, float] | None = None,
    cash_only_execution: bool | None = None,
    hold_diagnostics: dict[str, Any] | None = None,
    observer=None,
) -> tuple[str, str] | None:
    _observe(observer, "limits", "ENTERED")
    if observer is not None:
        try:
            same = limits is object.__getattribute__(observer, "_prepared_limits")
        except BaseException:
            same = None
        _observe(observer, "same_prepared_object", same)
    try:
        """Return a fail-closed finding for an explicit runtime limit set."""
        if type(limits) is not RuntimeRiskLimits:
            return ("rejected:runtime_risk_limits", "invalid_runtime_risk_limits")

        from quant_platform_kit.risk import gate as _gate
        allowed = getattr(_gate, "set", set)(limits.allowed_symbols)
        seen_symbols: set[str] = set()
        for position in positions:
            if type(position) is not PositionTarget:
                return ("rejected:runtime_risk_limits", "invalid_runtime_risk_limits")
            if position.symbol not in allowed:
                return ("rejected:runtime_risk_limits", "symbol_not_allowed")
            if position.symbol in seen_symbols:
                return ("rejected:runtime_risk_limits", "duplicate_symbol")
            seen_symbols.add(position.symbol)
            if position.target_weight is not None and position.target_value is not None:
                return ("rejected:runtime_risk_limits", "conflicting_target_modes")
            if position.target_weight is not None and (
                _finite_number(position.target_weight) is None
                or float(position.target_weight) < 0.0
            ):
                return ("rejected:runtime_risk_limits", "negative_weight_not_allowed")
            if position.target_value is not None and not value_target_exposure_enforced:
                return ("rejected:runtime_risk_limits", "value_target_enforcement_required")

        if budgets:
            return ("rejected:runtime_risk_limits", "budgets_not_supported")

        if len(weights) > limits.max_positions:
            return ("rejected:runtime_risk_limits", "max_positions_exceeded")

        nominal_total = 0.0
        effective_total = 0.0
        overrun_codes: list[str] = []
        for position, weight in weights:
            factor = limits.product_leverage_factors.get(position.symbol)
            nominal_cap = limits.nominal_caps.get(position.symbol)
            if factor is None or nominal_cap is None:
                return ("rejected:runtime_risk_limits", "asset_limit_missing")
            if weight > nominal_cap:
                overrun_codes.append("nominal_cap_exceeded")
            nominal_total += weight
            effective_total += weight * factor
        if nominal_total > limits.total_nominal_exposure_cap + 1e-9:
            overrun_codes.append("total_nominal_cap_exceeded")
        if effective_total > limits.total_effective_exposure_cap + 1e-9:
            overrun_codes.append("total_effective_cap_exceeded")
        if not overrun_codes:
            return None

        primary = overrun_codes[0]
        if _small_account_hold_allows_overrun(
            limits=limits,
            target_weights=weights,
            overrun_codes=tuple(dict.fromkeys(overrun_codes)),
            hold_policy=hold_policy,
            verified_nav=verified_nav,
            current_weights=current_weights,
            cash_only_execution=cash_only_execution,
        ):
            if hold_diagnostics is not None:
                hold_diagnostics["runtime_risk_small_account_hold"] = True
                hold_diagnostics["runtime_risk_small_account_hold_overruns"] = tuple(
                    dict.fromkeys(overrun_codes)
                )
                hold_diagnostics["runtime_risk_small_account_hold_nav"] = float(verified_nav or 0.0)
            return None
        return ("rejected:runtime_risk_limits", primary)
    except BaseException:
        _observe(observer, "limits", "RAISED")
        raise


def _canonical_cap_material(
    value: Any,
    *,
    _depth: int = 0,
    _item_count: list[int] | None = None,
) -> Any:
    number = _finite_number(value)
    if number is not None:
        return number if 0.0 <= number <= 1.0 else None
    if (
        _depth >= 8
        or not isinstance(value, Mapping)
        or not value
        or len(value) > _MAX_MATERIAL_ITEMS
    ):
        return None
    item_count = _item_count if _item_count is not None else [0]
    result: dict[str, Any] = {}
    for raw_key, raw_value in value.items():
        item_count[0] += 1
        key, valid_key = _canonical_string(raw_key)
        if (
            item_count[0] > _MAX_MATERIAL_ITEMS
            or not valid_key
            or key is None
        ):
            return None
        candidate = _canonical_cap_material(
            raw_value,
            _depth=_depth + 1,
            _item_count=item_count,
        )
        if candidate is None:
            return None
        result[key] = candidate
    return result


def _safe_diagnostics(value: Any) -> tuple[dict[str, Any], bool]:
    if not isinstance(value, Mapping) or len(value) > _MAX_MATERIAL_ITEMS:
        return {}, False
    result: dict[str, Any] = {}
    for item_count, (raw_key, raw_value) in enumerate(value.items(), start=1):
        if item_count > _MAX_MATERIAL_ITEMS:
            return {}, False
        key, valid = _canonical_string(raw_key)
        if not valid or key is None:
            return {}, False
        result[key] = raw_value
    return result, True


def _parse_utc_timestamp(value: Any) -> datetime | None:
    if type(value) is datetime:
        parsed = value
    else:
        timestamp, valid = _canonical_string(value)
        if not valid or timestamp is None or not timestamp.endswith("Z"):
            return None
        try:
            parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except (OverflowError, TypeError, ValueError):
            return None
    return parsed.astimezone(timezone.utc) if parsed.tzinfo is not None else None


def _parse_utc_whole_second(value: Any) -> datetime | None:
    if type(value) is datetime:
        try:
            offset = value.utcoffset()
        except Exception:
            return None
        if offset is None or offset.total_seconds() != 0.0 or value.microsecond != 0:
            return None
        return value.astimezone(timezone.utc)
    timestamp, valid = _canonical_string(value)
    if not valid or timestamp is None or not timestamp.endswith("Z"):
        return None
    try:
        parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except (OverflowError, TypeError, ValueError):
        return None
    if parsed.microsecond != 0 or _utc_timestamp(parsed) != timestamp:
        return None
    return parsed.astimezone(timezone.utc)


def _exact_mapping(value: Any, fields: frozenset[str]) -> Mapping[str, Any] | None:
    if not isinstance(value, Mapping) or len(value) != len(fields):
        return None
    try:
        return value if set(value) == fields else None
    except Exception:
        return None


def _logical_evaluation_time(
    value: datetime | None,
    *,
    wall_time: datetime,
) -> tuple[datetime, set[str]]:
    if value is None:
        return wall_time, set()
    logical_time = _parse_utc_whole_second(value)
    if logical_time is None or type(value) is not datetime:
        return wall_time, {"invalid_logical_evaluation_time"}
    age_seconds = (wall_time - logical_time).total_seconds()
    if age_seconds < 0.0:
        return wall_time, {"future_logical_evaluation_time"}
    if age_seconds > _TQQQ_EVIDENCE_MAX_AGE_SECONDS:
        return wall_time, {"stale_logical_evaluation_time"}
    return logical_time, set()


def _sha256(value: Any) -> str | None:
    normalized, valid = _canonical_string(value)
    if not valid or normalized is None or len(normalized) != 64:
        return None
    return (
        normalized
        if all(character in "0123456789abcdef" for character in normalized)
        else None
    )


def _git_revision(value: Any) -> str | None:
    normalized, valid = _canonical_string(value)
    if not valid or normalized is None or len(normalized) != 40:
        return None
    return (
        normalized
        if all(character in "0123456789abcdef" for character in normalized)
        else None
    )


def _decision_metrics(
    decision: StrategyDecision,
    *,
    total_equity: float | None,
) -> tuple[dict[str, Any], list[tuple[str, float]], set[str]]:
    active: list[tuple[str, float]] = []
    reason_codes: set[str] = set()
    position_payloads: list[dict[str, Any]] = []
    raw_positions = decision.positions
    if type(raw_positions) is not tuple or len(raw_positions) > _MAX_MATERIAL_ITEMS:
        raw_positions = ()
        reason_codes.add("invalid_risk_metadata")
    for position in raw_positions:
        if type(position) is not PositionTarget:
            reason_codes.add("invalid_risk_metadata")
            continue
        symbol, valid_symbol = _canonical_string(position.symbol)
        role, valid_role = _canonical_string(position.role, optional=True)
        order_preference, valid_order = _canonical_string(
            position.order_preference,
            optional=True,
        )
        weight = _finite_number(position.target_weight)
        target_value = _finite_number(position.target_value)
        if (
            not valid_symbol
            or not valid_role
            or not valid_order
            or (position.target_weight is not None and weight is None)
            or (position.target_value is not None and target_value is None)
        ):
            reason_codes.add("invalid_risk_metadata")
        position_payloads.append(
            {
                "symbol": symbol,
                "target_weight": weight,
                "target_value": target_value,
                "role": role,
                "order_preference": order_preference,
            }
        )
        if (
            not valid_symbol
            or symbol is None
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
        if (
            normalized_weight is None
            or not math.isfinite(normalized_weight)
            or normalized_weight < 0.0
        ):
            reason_codes.add("invalid_decision_exposure")
            continue
        if normalized_weight > 0.0:
            active.append((symbol, normalized_weight))
    budget_payloads: list[dict[str, Any]] = []
    raw_budgets = decision.budgets
    if type(raw_budgets) is not tuple or len(raw_budgets) > _MAX_MATERIAL_ITEMS:
        raw_budgets = ()
        reason_codes.add("invalid_risk_metadata")
    for budget in raw_budgets:
        if type(budget) is not BudgetIntent:
            reason_codes.add("invalid_risk_metadata")
            continue
        name, valid_name = _canonical_string(budget.name)
        symbol, valid_symbol = _canonical_string(budget.symbol, optional=True)
        unit, valid_unit = _canonical_string(budget.unit)
        purpose, valid_purpose = _canonical_string(budget.purpose, optional=True)
        amount = _finite_number(budget.amount)
        if (
            not valid_name
            or not valid_symbol
            or not valid_unit
            or not valid_purpose
            or (budget.amount is not None and amount is None)
        ):
            reason_codes.add("invalid_risk_metadata")
        if amount is None or amount < 0.0:
            reason_codes.add("invalid_decision_budget")
        budget_payloads.append(
            {
                "name": name,
                "symbol": symbol,
                "amount": amount,
                "unit": unit,
                "purpose": purpose,
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
    require_utc_whole_second: bool = False,
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
    as_of = (
        _parse_utc_whole_second(as_of_value)
        if require_utc_whole_second
        else _parse_utc_timestamp(as_of_value)
    )
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


def _static_gate_total_equity(portfolio_snapshot: Any) -> float | None:
    """Return the equity needed to normalize value targets in the live gate.

    The non-evidence ``apply_risk_gate`` path accepts both weight and value
    targets.  A value target has no meaningful concentration without the same
    account equity used by the strategy invocation, so an absent or malformed
    snapshot must never turn it into a zero-weight target.
    """
    try:
        if isinstance(portfolio_snapshot, Mapping):
            raw_total_equity = portfolio_snapshot.get("total_equity")
        elif isinstance(portfolio_snapshot, PortfolioSnapshot):
            raw_total_equity = portfolio_snapshot.total_equity
        else:
            return None
    except Exception:
        return None
    total_equity = _finite_number(raw_total_equity)
    if total_equity is None or total_equity <= 0.0:
        return None
    return total_equity
