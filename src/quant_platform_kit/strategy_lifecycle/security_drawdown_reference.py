"""Describe a frozen security-price proxy, independently of any broker/account.

No acquisition, persistence, account policy, configuration or execution API.
Numerical dependencies are imported only when this research function is used.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping
from datetime import date, datetime, timezone


class SecurityDrawdownReferenceError(ValueError):
    """Fixed diagnostics without source values or private paths."""


def _require(condition, code):
    if not condition:
        raise SecurityDrawdownReferenceError(code)


def _stamp(raw):
    try:
        value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        _require(value.tzinfo is not None and value.utcoffset() is not None,
                 "SECURITY_REFERENCE_TIME_INVALID")
        return value.astimezone(timezone.utc)
    except (TypeError, ValueError, AttributeError, OverflowError):
        raise SecurityDrawdownReferenceError("SECURITY_REFERENCE_TIME_INVALID") from None


def describe_security_drawdown_reference(reference, *, selected_benchmark, currency,
        calendar_id, valuation_sampling, decision_cutoff_utc):
    """Validate declared source semantics and compute a daily-close proxy DD.

    This is a current frozen historical reference, not a reconstruction of
    past knowledge. Callers separately establish calendar coverage, provider
    adjustments, licensing and the policy that selects this reference.
    Initial wealth is 1, before the first supplied return. Annualization and
    volatility conventions do not enter maximum drawdown. No account path,
    budget, proposed allocation or risk allowance is accepted or inferred.
    """
    fields = {"schema_version", "benchmark_symbol", "reference_id", "available_at_utc",
              "frozen_at_utc", "dates", "returns", "context"}
    _require(isinstance(reference, Mapping) and set(reference) == fields,
             "SECURITY_REFERENCE_INCOMPLETE")
    _require(reference["schema_version"] == "qsl.security_drawdown_reference.v1",
             "SECURITY_REFERENCE_SCHEMA_UNSUPPORTED")
    _require(all(isinstance(v, str) and bool(v.strip()) for v in
                 (selected_benchmark, currency, calendar_id, reference["benchmark_symbol"], reference["reference_id"])),
             "SECURITY_REFERENCE_IDENTITY_REQUIRED")
    source = reference["context"]
    _require(isinstance(source, Mapping), "SECURITY_REFERENCE_CONTEXT_REQUIRED")
    _require(all(isinstance(source.get(k), str) and bool(source[k].strip())
                 for k in ("currency", "calendar_id", "window_id", "series_id")),
             "SECURITY_REFERENCE_CONTEXT_REQUIRED")
    _require(source.get("wealth_scope") == "SECURITY_BENCHMARK_REFERENCE"
        and "account_scope" not in source
        and source.get("return_basis") == "PROVIDER_ADJUSTED_CLOSE_RATIO"
        and source.get("distribution_treatment") == "PROVIDER_SPLIT_DIVIDEND_ADJUSTED"
        and source.get("cost_treatment") == "ACCOUNT_TRADING_COSTS_EXCLUDED"
        and source.get("cash_flow_basis") == "NOT_AN_ACCOUNT"
        and source.get("cash_income_treatment") == "NOT_AN_ACCOUNT",
        "SECURITY_REFERENCE_BASIS_REQUIRED")
    _require(source.get("frequency") == "daily"
        and source.get("valuation_sampling") == valuation_sampling == "DAILY_CLOSE",
        "SECURITY_REFERENCE_DAILY_CLOSE_REQUIRED")
    _require(source["currency"] == currency and source["calendar_id"] == calendar_id,
             "SECURITY_REFERENCE_COMPARISON_BASIS_MISMATCH")
    _require(source["series_id"] == reference["benchmark_symbol"] == selected_benchmark,
             "SECURITY_REFERENCE_SELECTION_MISMATCH")
    _require(isinstance(source.get("source_sha256"), str)
        and re.fullmatch(r"[0-9a-f]{64}", source["source_sha256"]), "SECURITY_REFERENCE_SOURCE_REQUIRED")
    available, frozen, cutoff = (_stamp(reference["available_at_utc"]),
        _stamp(reference["frozen_at_utc"]), _stamp(decision_cutoff_utc))
    _require(available <= frozen <= cutoff, "SECURITY_REFERENCE_NOT_AVAILABLE_AT_FREEZE")
    dates, returns = reference["dates"], reference["returns"]
    _require(type(dates) is list and type(returns) is list and len(dates) == len(returns)
             and len(dates) >= 2, "SECURITY_REFERENCE_DAILY_PATH_REQUIRED")
    try:
        _require(all(isinstance(day, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", day)
                     for day in dates), "SECURITY_REFERENCE_DATES_INVALID")
        sessions = [date.fromisoformat(day) for day in dates]
    except ValueError:
        raise SecurityDrawdownReferenceError("SECURITY_REFERENCE_DATES_INVALID") from None
    _require(sessions == sorted(set(sessions)) and all(day < available.date() for day in sessions),
             "SECURITY_REFERENCE_DATES_INVALID")
    try:
        valid = all(type(v) in (int, float) and math.isfinite(v) and v > -1 for v in returns)
    except OverflowError:
        valid = False
    _require(valid, "SECURITY_REFERENCE_RETURNS_INVALID")
    wealth = 1.0
    for value in returns:
        wealth *= 1.0 + value
        _require(math.isfinite(wealth) and wealth > 0, "SECURITY_REFERENCE_WEALTH_UNCOMPUTABLE")
    try:
        encoded = json.dumps(dict(reference=dict(reference), selected_benchmark=selected_benchmark,
            currency=currency, calendar_id=calendar_id, valuation_sampling=valuation_sampling,
            decision_cutoff_utc=decision_cutoff_utc), sort_keys=True,
            separators=(",", ":"), allow_nan=False).encode()
    except (TypeError, ValueError):
        raise SecurityDrawdownReferenceError("SECURITY_REFERENCE_JSON_INVALID") from None
    try:
        import pandas as pd
        from quant_platform_kit.strategy_lifecycle.performance_metrics import compute_window_metrics

        # Only drawdown is consumed: do not make it depend on annualization or
        # std ddof, or replicate the library's initial-wealth calculation.
        loss = -compute_window_metrics(pd.Series(returns, index=pd.to_datetime(dates))).max_drawdown
    except ImportError:
        raise SecurityDrawdownReferenceError("SECURITY_REFERENCE_NUMERICS_UNAVAILABLE") from None
    except (ArithmeticError, ValueError, TypeError):
        raise SecurityDrawdownReferenceError("SECURITY_REFERENCE_METRIC_UNCOMPUTABLE") from None
    _require(math.isfinite(loss) and 0 <= loss < 1, "SECURITY_REFERENCE_METRIC_UNCOMPUTABLE")
    return dict(schema_version="qsl.security_drawdown_reference_diagnostic.v1", preview_only=True,
        input_sha256=hashlib.sha256(encoded).hexdigest(), max_drawdown_loss_fraction=loss,
        benchmark_symbol=reference["benchmark_symbol"], reference_id=reference["reference_id"],
        reference_source_sha256=source["source_sha256"], available_at_utc=reference["available_at_utc"],
        frozen_at_utc=reference["frozen_at_utc"],
        reference_window=dict(start_date=dates[0], end_date=dates[-1], observations=len(dates), window_id=source["window_id"]),
        reference_return_basis=source["return_basis"], reference_wealth_scope=source["wealth_scope"],
        valuation_sampling=source["valuation_sampling"], distribution_treatment=source["distribution_treatment"],
        account_costs_included=False, reference_qualified=False, calendar_coverage_verified=False,
        model_calibrated=False, enforcement_eligible=False, policy_selected=False,
        settings_applied=False, execution_authorized=False)
