"""Shared pure helpers for broker account_new_risk_gate support adapters."""

from __future__ import annotations

import json
import math
import os
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
from typing import Any

from quant_platform_kit.risk.contracts import RuntimeRiskLimits
from quant_platform_kit.risk.production_drift_new_risk import (
    resolve_production_drift_status_from_store,
)

DEFAULT_STRATEGY_PROFILE = "soxl_soxx_trend_income"
DEFAULT_DOMAIN = "us_equity"
DEFAULT_DAILY_LOSS_LIMIT_CARRIER_SYMBOL = "SPY"
DEFAULT_BROKER_DRAWDOWN_MAX_AGE_SECONDS = 300.0


def coerce_optional_float(value: object) -> float | None:
    """Coerce a non-bool value to a finite float, returning ``None`` otherwise."""
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(number):
        return None
    return number


def positive_limit_or_none(value: object) -> float | None:
    """Accept only finite positive limits; never invent a production default."""
    number = coerce_optional_float(value)
    if number is None or number <= 0.0:
        return None
    return number


def mapping_or_empty(value: object) -> Mapping[str, Any]:
    """Return ``value`` when it is a ``Mapping``, else an empty dict."""
    return value if isinstance(value, Mapping) else {}


def portfolio_metadata(portfolio: object) -> Mapping[str, Any]:
    """Return ``portfolio['metadata']`` when both are mappings, else an empty dict."""
    return mapping_or_empty(mapping_or_empty(portfolio).get("metadata"))


def resolve_equity_usd(
    portfolio: Mapping[str, Any],
    execution: Mapping[str, Any] | None = None,
    *,
    equity_keys: Sequence[str] = ("total_equity", "total_strategy_equity"),
    include_broker_capital: bool = True,
    stop_on_present_key: bool = False,
) -> float | None:
    """Resolve positive account equity across portfolio, broker capital, and execution surfaces."""
    portfolio_map = mapping_or_empty(portfolio)
    for key in equity_keys:
        if key not in portfolio_map:
            continue
        equity = coerce_optional_float(portfolio_map.get(key))
        if equity is not None and equity > 0.0:
            return equity
        if stop_on_present_key:
            return None
    if include_broker_capital:
        broker_capital = portfolio_map.get("broker_capital")
        if isinstance(broker_capital, Mapping):
            equity = coerce_optional_float(broker_capital.get("net_assets"))
            if equity is not None and equity > 0.0:
                return equity
    if execution is not None:
        equity = coerce_optional_float(mapping_or_empty(execution).get("portfolio_total_equity"))
        if equity is not None and equity > 0.0:
            return equity
    return None


def resolve_unknown_pending(
    portfolio: Mapping[str, Any],
    projection: Mapping[str, Any],
    *,
    execution: Mapping[str, Any] | None = None,
    fail_closed_any: bool = False,
    include_pending_reconciliation: bool = False,
) -> bool:
    """Resolve whether unknown pending orders or pending reconciliation block new risk."""
    portfolio_map = mapping_or_empty(portfolio)
    projection_map = mapping_or_empty(projection)
    metadata = portfolio_metadata(portfolio_map)

    if fail_closed_any:
        unknown_pending = any(
            source["unknown_pending_orders"] is not False
            for source in (portfolio_map, metadata, projection_map)
            if "unknown_pending_orders" in source
        )
    elif include_pending_reconciliation:
        unknown_pending = bool(
            portfolio_map.get("unknown_pending_orders")
            or metadata.get("unknown_pending_orders")
            or projection_map.get("unknown_pending_orders")
        )
    elif "unknown_pending_orders" in projection_map:
        unknown_pending = bool(projection_map.get("unknown_pending_orders"))
    elif portfolio_map.get("unknown_pending_orders") is not None:
        unknown_pending = bool(portfolio_map.get("unknown_pending_orders"))
    else:
        unknown_pending = bool(metadata.get("unknown_pending_orders"))

    if unknown_pending or not include_pending_reconciliation:
        return unknown_pending

    execution_map = mapping_or_empty(execution)
    execution_metadata = mapping_or_empty(execution_map.get("metadata"))
    return bool(
        portfolio_map.get("pending_reconciliation")
        or metadata.get("pending_reconciliation")
        or execution_map.get("pending_reconciliation")
        or execution_metadata.get("pending_reconciliation")
    )


def _is_explicit_open(value: object) -> bool:
    return str(value or "").strip().upper() == "OPEN"


def resolve_durable_breaker_open(
    portfolio: Mapping[str, Any],
    projection: Mapping[str, Any],
    *,
    strict_closed_only: bool = False,
    check_projection_circuit_breaker: bool = False,
) -> bool:
    """Resolve whether a durable circuit-breaker flag indicates ``OPEN``."""
    portfolio_map = mapping_or_empty(portfolio)
    projection_map = mapping_or_empty(projection)
    metadata = portfolio_metadata(portfolio_map)

    if strict_closed_only:
        for source in (projection_map, portfolio_map, metadata):
            if "durable_circuit_breaker_state" not in source:
                continue
            value = source["durable_circuit_breaker_state"]
            if not isinstance(value, str) or value.strip().upper() != "CLOSED":
                return True
        return False

    if check_projection_circuit_breaker:
        return (
            _is_explicit_open(portfolio_map.get("durable_circuit_breaker_state"))
            or _is_explicit_open(metadata.get("durable_circuit_breaker_state"))
            or _is_explicit_open(projection_map.get("circuit_breaker_state"))
        )

    for source in (projection_map, portfolio_map, metadata):
        value = source.get("durable_circuit_breaker_state")
        if value is not None:
            return _is_explicit_open(value)
    return False


def resolve_production_drift_status(
    portfolio: Mapping[str, Any],
    projection: Mapping[str, Any],
    *,
    default_strategy_profile: str = DEFAULT_STRATEGY_PROFILE,
    default_domain: str = DEFAULT_DOMAIN,
    portfolio_first: bool = False,
    environ: Mapping[str, str] | None = None,
    store_resolver: Callable[..., str | None] | None = None,
) -> str | None:
    """Prefer explicit injected drift status; else fall back to read-only store lookup."""
    portfolio_map = mapping_or_empty(portfolio)
    projection_map = mapping_or_empty(projection)
    metadata = portfolio_metadata(portfolio_map)

    drift_sources = (
        (portfolio_map, projection_map, metadata)
        if portfolio_first
        else (projection_map, portfolio_map, metadata)
    )
    for source in drift_sources:
        raw = source.get("production_drift_status")
        if raw is not None and raw != "":
            return str(raw).strip()

    profile = ""
    domain = ""
    for source in (projection_map, portfolio_map, metadata):
        if not profile:
            value = source.get("strategy_profile")
            if isinstance(value, str) and value.strip():
                profile = value.strip()
        if not domain:
            value = source.get("strategy_domain") or source.get("domain")
            if isinstance(value, str) and value.strip():
                domain = value.strip()

    env = os.environ if environ is None else environ
    profile = profile or str(env.get("STRATEGY_PROFILE") or "").strip() or default_strategy_profile
    domain = domain or str(env.get("STRATEGY_DOMAIN") or "").strip() or default_domain
    resolver = store_resolver or resolve_production_drift_status_from_store
    return resolver(strategy_profile=profile, domain=domain)


def resolve_drawdown_from_peak(
    *,
    equity_usd: float | None,
    peak_equity_usd: float | None,
    explicit: float | None = None,
    explicit_source: Mapping[str, Any] | None = None,
    observed_at: object = None,
    max_age_seconds: float = DEFAULT_BROKER_DRAWDOWN_MAX_AGE_SECONDS,
    now: datetime | None = None,
) -> float | None:
    """Resolve drawdown from peak, supporting explicit-first or derived-with-fresh-cache modes."""
    if explicit_source is None:
        if explicit is not None:
            return explicit
        if equity_usd is None or peak_equity_usd is None or peak_equity_usd <= 0.0:
            return None
        return max(0.0, 1.0 - (equity_usd / peak_equity_usd))

    if (
        equity_usd is not None
        and equity_usd > 0.0
        and peak_equity_usd is not None
        and peak_equity_usd > 0.0
    ):
        return max(0.0, (peak_equity_usd - equity_usd) / peak_equity_usd)
    if not isinstance(observed_at, str):
        return None
    try:
        measured_at = datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
        if measured_at.tzinfo is None:
            return None
        reference_now = now if now is not None else datetime.now(timezone.utc)
        age = (reference_now - measured_at).total_seconds()
    except (ValueError, TypeError, OverflowError):
        return None
    if not 0.0 <= age <= max_age_seconds:
        return None
    broker_drawdown = coerce_optional_float(mapping_or_empty(explicit_source).get("drawdown_from_peak"))
    return broker_drawdown if broker_drawdown is not None and broker_drawdown >= 0.0 else None


def resolve_explicit_daily_loss_usd(
    projection: Mapping[str, Any],
    portfolio: Mapping[str, Any],
    execution: Mapping[str, Any] | None = None,
    *,
    portfolio_first: bool = False,
) -> float | None:
    """Pass through an explicit ``daily_loss_usd`` observation only; never invent one."""
    projection_map = mapping_or_empty(projection)
    portfolio_map = mapping_or_empty(portfolio)
    execution_map = mapping_or_empty(execution)
    sources = (
        (portfolio_map, projection_map, execution_map)
        if portfolio_first
        else (projection_map, portfolio_map, execution_map)
    )
    for source in sources:
        if "daily_loss_usd" in source:
            return coerce_optional_float(source.get("daily_loss_usd"))
    return None


def max_daily_loss_from_runtime_target_json(
    raw_target: str | None = None,
    *,
    environ: Mapping[str, str] | None = None,
) -> float | None:
    """Read ``runtime_risk_limits.max_daily_loss_usd`` from ``RUNTIME_TARGET_JSON``; soft-omit on errors."""
    env = os.environ if environ is None else environ
    raw = env.get("RUNTIME_TARGET_JSON") if raw_target is None else raw_target
    if raw is None or not str(raw).strip():
        return None
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError):
        return None
    if not isinstance(payload, Mapping):
        return None
    policy = payload.get("runtime_risk_limits")
    if not isinstance(policy, Mapping) or "max_daily_loss_usd" not in policy:
        return None
    return positive_limit_or_none(policy.get("max_daily_loss_usd"))


def resolve_max_daily_loss_usd(
    portfolio: Mapping[str, Any] | None = None,
    *,
    env_keys: Sequence[str] = ("MAX_DAILY_LOSS_USD",),
    environ: Mapping[str, str] | None = None,
    limit_callback: Callable[[Mapping[str, Any] | None], object] | None = None,
) -> float | None:
    """Resolve an explicit ``max_daily_loss_usd`` with optional broker policy callback; omit when unset."""
    if portfolio is not None:
        portfolio_map = mapping_or_empty(portfolio)
        projection_map = mapping_or_empty(portfolio_map.get("account_new_risk_snapshot"))
        for source in (projection_map, portfolio_map):
            if "max_daily_loss_usd" in source:
                return positive_limit_or_none(source.get("max_daily_loss_usd"))

    env = os.environ if environ is None else environ
    runtime_target_limit = max_daily_loss_from_runtime_target_json(environ=env)
    if runtime_target_limit is not None:
        return runtime_target_limit

    if limit_callback is not None:
        callback_limit = positive_limit_or_none(limit_callback(portfolio))
        if callback_limit is not None:
            return callback_limit

    for key in env_keys:
        raw = env.get(key)
        if raw is None or not str(raw).strip():
            continue
        limit = positive_limit_or_none(raw)
        if limit is not None:
            return limit
    return None


def runtime_risk_limits_for_daily_loss_axis(
    max_daily_loss_usd: float | None,
    *,
    carrier_symbol: str = DEFAULT_DAILY_LOSS_LIMIT_CARRIER_SYMBOL,
) -> RuntimeRiskLimits | None:
    """Build admission-only ``RuntimeRiskLimits`` carrying ``max_daily_loss_usd``, or omit."""
    limit = positive_limit_or_none(max_daily_loss_usd)
    if limit is None:
        return None
    return RuntimeRiskLimits(
        allowed_symbols=(carrier_symbol,),
        product_leverage_factors={carrier_symbol: 1},
        nominal_caps={carrier_symbol: 1.0},
        total_nominal_exposure_cap=1.0,
        total_effective_exposure_cap=1.0,
        max_positions=1,
        max_daily_loss_usd=limit,
    )


def resolve_daily_loss_runtime_risk_limits(
    portfolio: Mapping[str, Any] | None = None,
    *,
    max_daily_loss_resolver: Callable[[Mapping[str, Any] | None], object] | None = None,
    env_keys: Sequence[str] = ("MAX_DAILY_LOSS_USD",),
    environ: Mapping[str, str] | None = None,
    carrier_symbol: str = DEFAULT_DAILY_LOSS_LIMIT_CARRIER_SYMBOL,
) -> RuntimeRiskLimits | None:
    """Resolve daily-loss limit via a pluggable callback or default chain and wrap as ``RuntimeRiskLimits``."""
    if max_daily_loss_resolver is not None:
        limit = positive_limit_or_none(max_daily_loss_resolver(portfolio))
    else:
        limit = resolve_max_daily_loss_usd(
            portfolio,
            env_keys=env_keys,
            environ=environ,
        )
    return runtime_risk_limits_for_daily_loss_axis(limit, carrier_symbol=carrier_symbol)


def _first_configured_setting(
    sources: tuple[Mapping[str, Any], ...],
    key: str,
    env: Mapping[str, str],
    env_key: str,
) -> tuple[bool, object]:
    for source in sources:
        if key in source and source[key] is not None:
            candidate = source[key]
            if isinstance(candidate, str) and not candidate.strip():
                continue
            return True, candidate.strip() if isinstance(candidate, str) else candidate
    env_val = env.get(env_key)
    if env_val is not None and (not isinstance(env_val, str) or env_val.strip()):
        return True, env_val.strip() if isinstance(env_val, str) else env_val
    return False, None


def resolve_fuse_readback_inputs(
    portfolio: Mapping[str, Any],
    projection: Mapping[str, Any],
    *,
    current_trade_date: str | None = None,
    default_mode: str = "enforce",
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Extract FUSE-2 readback payload and independent decision controls.

    Never reads ``trade_date`` from the candidate ``fuse_readback`` or ``projection`` as the
    reference decision date, so a stale snapshot cannot validate against itself. Explicit
    non-empty invalid values from higher-priority sources are preserved so downstream
    fail-closed validation rejects them instead of silently falling back.
    """
    portfolio_map = mapping_or_empty(portfolio)
    projection_map = mapping_or_empty(projection)
    sources = (projection_map, portfolio_map, portfolio_metadata(portfolio_map))
    env = os.environ if environ is None else environ

    fuse_readback = None
    has_readback_key = False
    for source in sources:
        if "fuse_readback" in source and source["fuse_readback"] is not None:
            fuse_readback = source["fuse_readback"]
            has_readback_key = True
            break

    fuse_trade_date: object = current_trade_date.strip() if isinstance(current_trade_date, str) else current_trade_date
    has_trade_date = fuse_trade_date is not None and (not isinstance(fuse_trade_date, str) or bool(fuse_trade_date))
    if not has_trade_date:
        has_trade_date, fuse_trade_date = _first_configured_setting(
            sources, "fuse_expected_trade_date", env, "FUSE_TRADE_DATE"
        )

    mode_configured, raw_mode = _first_configured_setting(sources, "fuse_mode", env, "FUSE_READBACK_MODE")
    if not mode_configured:
        raw_mode = default_mode

    observe_configured, observe_until = _first_configured_setting(
        sources, "fuse_observe_until", env, "FUSE_OBSERVE_UNTIL"
    )

    return {
        "fuse_enabled": bool(has_readback_key or mode_configured or observe_configured or has_trade_date),
        "fuse_readback": fuse_readback,
        "fuse_trade_date": fuse_trade_date,
        "fuse_mode": raw_mode,
        "fuse_observe_until": observe_until,
    }


__all__ = [
    "DEFAULT_BROKER_DRAWDOWN_MAX_AGE_SECONDS",
    "DEFAULT_DAILY_LOSS_LIMIT_CARRIER_SYMBOL",
    "DEFAULT_DOMAIN",
    "DEFAULT_STRATEGY_PROFILE",
    "coerce_optional_float",
    "mapping_or_empty",
    "max_daily_loss_from_runtime_target_json",
    "portfolio_metadata",
    "positive_limit_or_none",
    "resolve_daily_loss_runtime_risk_limits",
    "resolve_drawdown_from_peak",
    "resolve_durable_breaker_open",
    "resolve_equity_usd",
    "resolve_explicit_daily_loss_usd",
    "resolve_fuse_readback_inputs",
    "resolve_max_daily_loss_usd",
    "resolve_production_drift_status",
    "resolve_unknown_pending",
    "runtime_risk_limits_for_daily_loss_axis",
]
