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
from quant_platform_kit.position_sizing import validate_reduce_only_normalization
from quant_platform_kit.risk.contracts import (
    CandidateRiskIdentity,
    RiskGateAssessment,
    RiskGateResult,
)
from quant_platform_kit.risk.engine import build_risk_engine
from quant_platform_kit.strategy_contracts import StrategyDecision

logger = logging.getLogger(__name__)

_STOP_LOSS_THRESHOLD = -0.20
_MAX_CONSECUTIVE_LOSSES = 5
_DEFAULT_MAX_SINGLE_WEIGHT = 0.10
_APPROVED_BOOTSTRAP_MANDATE = "bootstrap_small_account_v2"
_TQQQ_ETF_ONLY_RESEARCH_MANDATE = "tqqq_etf_only_research_v1"
_TQQQ_ETF_ONLY_STRATEGY_PROFILE = "tqqq_etf_only_single_strategy_research_v1"
_TQQQ_ETF_ONLY_FACTORS = {"TQQQ": 3, "BOXX": 1}
_TQQQ_ETF_ONLY_NOMINAL_CAPS = {"TQQQ": 0.15, "BOXX": 0.50}
_TQQQ_ETF_ONLY_EFFECTIVE_CAPS = {"TQQQ": 0.45, "BOXX": 0.50}
_GLOBAL_ETF_RESEARCH_MANDATE = "global_etf_rotation_etf_only_research_v1"
_GLOBAL_ETF_STRATEGY_PROFILE = (
    "global_etf_rotation_etf_only_single_strategy_research_v1"
)
_GLOBAL_ETF_ACCOUNT_MODE = "single_strategy_research_v1"
_GLOBAL_ETF_ALLOWED_ASSETS = (
    "EWY",
    "EWT",
    "INDA",
    "FXI",
    "EWJ",
    "VGK",
    "VOO",
    "XLK",
    "SMH",
    "GLD",
    "SLV",
    "USO",
    "DBA",
    "XLE",
    "XLF",
    "ITA",
    "XLP",
    "XLU",
    "XLV",
    "IHI",
    "VNQ",
    "KRE",
    "BIL",
)
_GLOBAL_ETF_FACTORS = {symbol: 1 for symbol in _GLOBAL_ETF_ALLOWED_ASSETS}
_GLOBAL_ETF_CAPS = {symbol: 0.50 for symbol in _GLOBAL_ETF_ALLOWED_ASSETS}
_GLOBAL_ETF_STOP_FILL_POLICY = "gap_aware_min_open_or_stop_v1"
_BOOTSTRAP_EFFECTIVE_EXPOSURE_CAP = 0.50
_BOOTSTRAP_NOMINAL_CAPS = {1: 0.50, 2: 0.25, 3: 0.15}
_ASSESSMENT_CONTRACT_VERSION = "qsl.risk_gate_assessment.v2"
_ASSESSMENT_POLICY_ID = "qpk.risk_gate"
_ASSESSMENT_POLICY_VERSION = "v2"
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


def _git_revision(value: Any) -> str | None:
    if not isinstance(value, str) or len(value) != 40:
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


def _completed_session_equity(portfolio_snapshot: Any) -> float | None:
    if isinstance(portfolio_snapshot, Mapping):
        value = portfolio_snapshot.get("completed_session_equity")
    elif isinstance(portfolio_snapshot, PortfolioSnapshot):
        value = portfolio_snapshot.metadata.get("completed_session_equity")
    else:
        return None
    completed_equity = _finite_number(value)
    return completed_equity if completed_equity is not None and completed_equity > 0.0 else None


def _exact_numeric_mapping(value: Any, expected: Mapping[str, float]) -> bool:
    if not isinstance(value, Mapping) or set(value) != set(expected):
        return False
    return all(
        (number := _finite_number(value[key])) is not None
        and number == expected_value
        for key, expected_value in expected.items()
    )


def _exact_tqqq_mandate_errors(
    mandate_provenance: Mapping[str, Any],
    *,
    effective_at: datetime,
    expires_at: datetime,
) -> set[str]:
    if mandate_provenance.get("mandate_id") != _TQQQ_ETF_ONLY_RESEARCH_MANDATE:
        return set()
    required = (
        "loss_budget_equity_reference",
        "product_effective_caps",
        "max_nonzero_assets",
        "broker_margin_factor",
        "margin_stacking",
        "borrowing",
        "shorting",
        "income_sleeve_enabled",
        "option_overlay_enabled",
        "precommitted_executable_stop_distance",
        "max_consecutive_completed_losing_exits",
    )
    allowed_assets = mandate_provenance.get("allowed_nonzero_assets")
    factors = mandate_provenance.get("product_leverage_factors")
    exact_factors = (
        isinstance(factors, Mapping)
        and set(factors) == set(_TQQQ_ETF_ONLY_FACTORS)
        and all(
            not isinstance(factors[symbol], bool)
            and isinstance(factors[symbol], int)
            and factors[symbol] == expected
            for symbol, expected in _TQQQ_ETF_ONLY_FACTORS.items()
        )
    )
    invalid = (
        any(field not in mandate_provenance for field in required)
        or mandate_provenance.get("mandate_version") != "v1"
        or mandate_provenance.get("authority_scope") != "RESEARCH_ONLY"
        or mandate_provenance.get("strategy_profile")
        != _TQQQ_ETF_ONLY_STRATEGY_PROFILE
        or mandate_provenance.get("account_mode") != "single_strategy_account_v1"
        or _finite_number(mandate_provenance.get("max_snapshot_age_seconds"))
        != 300.0
        or _finite_number(mandate_provenance.get("effective_exposure_cap")) != 0.50
        or _finite_number(mandate_provenance.get("loss_budget")) != 0.01
        or mandate_provenance.get("loss_budget_equity_reference")
        != "completed_session_equity"
        or not _exact_numeric_mapping(
            mandate_provenance.get("product_caps"),
            _TQQQ_ETF_ONLY_NOMINAL_CAPS,
        )
        or not _exact_numeric_mapping(
            mandate_provenance.get("nominal_caps"),
            _TQQQ_ETF_ONLY_NOMINAL_CAPS,
        )
        or not _exact_numeric_mapping(
            mandate_provenance.get("product_effective_caps"),
            _TQQQ_ETF_ONLY_EFFECTIVE_CAPS,
        )
        or not exact_factors
        or not isinstance(allowed_assets, (list, tuple))
        or len(allowed_assets) != 2
        or set(allowed_assets) != set(_TQQQ_ETF_ONLY_FACTORS)
        or isinstance(mandate_provenance.get("max_nonzero_assets"), bool)
        or mandate_provenance.get("max_nonzero_assets") != 1
        or isinstance(mandate_provenance.get("broker_margin_factor"), bool)
        or mandate_provenance.get("broker_margin_factor") != 1
        or mandate_provenance.get("margin_stacking") is not False
        or mandate_provenance.get("borrowing") is not False
        or mandate_provenance.get("shorting") is not False
        or mandate_provenance.get("income_sleeve_enabled") is not False
        or mandate_provenance.get("option_overlay_enabled") is not False
        or _finite_number(
            mandate_provenance.get("precommitted_executable_stop_distance")
        )
        != 0.05
        or isinstance(
            mandate_provenance.get("max_consecutive_completed_losing_exits"),
            bool,
        )
        or mandate_provenance.get("max_consecutive_completed_losing_exits") != 5
        or (expires_at - effective_at).total_seconds() > 90 * 24 * 60 * 60
    )
    return {"invalid_tqqq_research_mandate"} if invalid else set()


def _exact_global_etf_mandate_errors(
    mandate_provenance: Mapping[str, Any],
    *,
    effective_at: datetime,
    expires_at: datetime,
) -> set[str]:
    if mandate_provenance.get("mandate_id") != _GLOBAL_ETF_RESEARCH_MANDATE:
        return set()
    required = (
        "loss_budget_equity_reference",
        "product_effective_caps",
        "max_nonzero_assets",
        "broker_margin_factor",
        "margin_stacking",
        "borrowing",
        "shorting",
        "income_sleeve_enabled",
        "option_overlay_enabled",
        "ai_overlay_enabled",
        "market_regime_overlay_enabled",
        "precommitted_executable_stop_distance",
        "stop_fill_policy",
        "max_consecutive_completed_losing_exits",
    )
    allowed_assets = mandate_provenance.get("allowed_nonzero_assets")
    factors = mandate_provenance.get("product_leverage_factors")
    exact_factors = (
        isinstance(factors, Mapping)
        and set(factors) == set(_GLOBAL_ETF_FACTORS)
        and all(
            not isinstance(factors[symbol], bool)
            and isinstance(factors[symbol], int)
            and factors[symbol] == expected
            for symbol, expected in _GLOBAL_ETF_FACTORS.items()
        )
    )
    invalid = (
        any(field not in mandate_provenance for field in required)
        or mandate_provenance.get("mandate_version") != "v1"
        or mandate_provenance.get("authority_scope") != "RESEARCH_ONLY"
        or mandate_provenance.get("strategy_profile")
        != _GLOBAL_ETF_STRATEGY_PROFILE
        or mandate_provenance.get("account_mode") != _GLOBAL_ETF_ACCOUNT_MODE
        or _finite_number(mandate_provenance.get("max_snapshot_age_seconds"))
        != 300.0
        or _finite_number(mandate_provenance.get("effective_exposure_cap")) != 0.50
        or _finite_number(mandate_provenance.get("loss_budget")) != 0.01
        or mandate_provenance.get("loss_budget_equity_reference")
        != "completed_session_equity"
        or not _exact_numeric_mapping(
            mandate_provenance.get("product_caps"),
            _GLOBAL_ETF_CAPS,
        )
        or not _exact_numeric_mapping(
            mandate_provenance.get("nominal_caps"),
            _GLOBAL_ETF_CAPS,
        )
        or not _exact_numeric_mapping(
            mandate_provenance.get("product_effective_caps"),
            _GLOBAL_ETF_CAPS,
        )
        or not exact_factors
        or not isinstance(allowed_assets, (list, tuple))
        or tuple(allowed_assets) != _GLOBAL_ETF_ALLOWED_ASSETS
        or isinstance(mandate_provenance.get("max_nonzero_assets"), bool)
        or mandate_provenance.get("max_nonzero_assets") != 2
        or isinstance(mandate_provenance.get("broker_margin_factor"), bool)
        or mandate_provenance.get("broker_margin_factor") != 1
        or mandate_provenance.get("margin_stacking") is not False
        or mandate_provenance.get("borrowing") is not False
        or mandate_provenance.get("shorting") is not False
        or mandate_provenance.get("income_sleeve_enabled") is not False
        or mandate_provenance.get("option_overlay_enabled") is not False
        or mandate_provenance.get("ai_overlay_enabled") is not False
        or mandate_provenance.get("market_regime_overlay_enabled") is not False
        or _finite_number(
            mandate_provenance.get("precommitted_executable_stop_distance")
        )
        != 0.05
        or mandate_provenance.get("stop_fill_policy")
        != _GLOBAL_ETF_STOP_FILL_POLICY
        or isinstance(
            mandate_provenance.get("max_consecutive_completed_losing_exits"),
            bool,
        )
        or mandate_provenance.get("max_consecutive_completed_losing_exits") != 5
        or (expires_at - effective_at).total_seconds() > 90 * 24 * 60 * 60
    )
    return {"invalid_global_etf_research_mandate"} if invalid else set()


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
        "strategy_revision",
        "runner_revision",
        "config_sha256",
        "input_manifest_sha256",
        "candidate_identity_sha256",
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
    strategy_revision = _git_revision(mandate_provenance["strategy_revision"])
    runner_revision = _git_revision(mandate_provenance["runner_revision"])
    config_sha256 = _sha256(mandate_provenance["config_sha256"])
    input_manifest_sha256 = _sha256(mandate_provenance["input_manifest_sha256"])
    candidate_identity_sha256 = _sha256(
        mandate_provenance["candidate_identity_sha256"]
    )
    effective_at = _parse_utc_timestamp(mandate_provenance["effective_at"])
    expires_at = _parse_utc_timestamp(mandate_provenance["expires_at"])
    max_snapshot_age_seconds = _finite_number(mandate_provenance["max_snapshot_age_seconds"])
    cap = _finite_number(mandate_provenance["effective_exposure_cap"])
    loss_budget = _finite_number(mandate_provenance["loss_budget"])
    if (
        not isinstance(mandate_provenance["mandate_id"], str)
        or not isinstance(mandate_provenance["mandate_version"], str)
        or _git_revision(mandate_provenance["source_revision"]) is None
        or not isinstance(mandate_provenance["strategy_profile"], str)
        or not mandate_provenance["strategy_profile"]
        or mandate_provenance["strategy_profile"]
        != mandate_provenance["strategy_profile"].strip()
        or not isinstance(mandate_provenance["account_mode"], str)
        or not mandate_provenance["account_mode"]
        or mandate_provenance["account_mode"]
        != mandate_provenance["account_mode"].strip()
        or strategy_revision is None
        or runner_revision is None
        or config_sha256 is None
        or input_manifest_sha256 is None
        or candidate_identity_sha256 is None
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
    exact_mandate_errors = set()
    for validator in (
        _exact_tqqq_mandate_errors,
        _exact_global_etf_mandate_errors,
    ):
        exact_mandate_errors.update(
            validator(
                mandate_provenance,
                effective_at=effective_at,
                expires_at=expires_at,
            )
        )
    if exact_mandate_errors:
        return {}, exact_mandate_errors
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
        "strategy_profile": mandate_provenance["strategy_profile"],
        "account_mode": mandate_provenance["account_mode"],
        "strategy_revision": strategy_revision,
        "runner_revision": runner_revision,
        "config_sha256": config_sha256,
        "input_manifest_sha256": input_manifest_sha256,
        "candidate_identity_sha256": candidate_identity_sha256,
        "effective_exposure_cap": cap,
        "max_snapshot_age_seconds": max_snapshot_age_seconds,
        "loss_budget": loss_budget,
        "product_leverage_factors": factors,
        "product_caps": mandate_provenance["product_caps"],
        "nominal_caps": mandate_provenance["nominal_caps"],
        "product_effective_caps": mandate_provenance.get(
            "product_effective_caps",
            1.0,
        ),
        "allowed_nonzero_assets": set(allowed_assets) if allowed_assets is not None else None,
        "max_nonzero_assets": mandate_provenance.get("max_nonzero_assets"),
    }, set()


def _candidate_binding_errors(
    mandate_provenance: Mapping[str, Any] | None,
    mandate: Mapping[str, Any],
    candidate_identity: CandidateRiskIdentity | None,
) -> set[str]:
    if mandate_provenance is None:
        return {"candidate_without_mandate"} if candidate_identity is not None else set()
    if candidate_identity is None:
        return {"missing_candidate_identity"}
    if not isinstance(candidate_identity, CandidateRiskIdentity):
        return {"invalid_candidate_identity"}
    if not mandate:
        return set()
    comparisons = (
        (
            candidate_identity.strategy_profile,
            mandate.get("strategy_profile"),
            "candidate_strategy_profile_mismatch",
        ),
        (
            candidate_identity.account_mode,
            mandate.get("account_mode"),
            "candidate_account_mode_mismatch",
        ),
        (
            candidate_identity.strategy_revision,
            mandate.get("strategy_revision"),
            "candidate_strategy_revision_mismatch",
        ),
        (
            candidate_identity.runner_revision,
            mandate.get("runner_revision"),
            "candidate_runner_revision_mismatch",
        ),
        (
            candidate_identity.config_sha256,
            mandate.get("config_sha256"),
            "candidate_config_digest_mismatch",
        ),
        (
            candidate_identity.input_manifest_sha256,
            mandate.get("input_manifest_sha256"),
            "candidate_input_manifest_digest_mismatch",
        ),
        (
            candidate_identity.authority_receipt_sha256,
            mandate.get("authority_receipt_sha256"),
            "candidate_authority_digest_mismatch",
        ),
        (
            candidate_identity.candidate_sha256,
            mandate.get("candidate_identity_sha256"),
            "candidate_identity_digest_mismatch",
        ),
    )
    return {
        reason_code
        for actual, expected, reason_code in comparisons
        if actual != expected
    }


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


def _risk_control_fields(
    risk_control_state: Mapping[str, Any] | None,
    *,
    mandate: Mapping[str, Any],
    now: datetime,
    active_positions: list[tuple[str, float]],
) -> tuple[dict[str, Any], set[str]]:
    empty = {
        "stop_loss_distance": None,
        "stop_intent_ready": None,
        "strategy_breaker_triggered": None,
        "account_breaker_triggered": None,
        "account_drawdown_fraction": None,
        "drawdown_scalar": None,
        "risk_control_state_digest_sha256": None,
    }
    if mandate.get("mandate_id") == _GLOBAL_ETF_RESEARCH_MANDATE:
        return _global_etf_risk_control_fields(
            risk_control_state,
            mandate=mandate,
            now=now,
            active_positions=active_positions,
        )
    if mandate.get("mandate_id") != _TQQQ_ETF_ONLY_RESEARCH_MANDATE:
        return empty, set()
    if not isinstance(risk_control_state, Mapping):
        return empty, {"missing_risk_control_state"}

    required = (
        "as_of",
        "mandate_id",
        "candidate_identity_sha256",
        "stop_loss_distance",
        "stop_intent_ready",
        "tqqq_entry_fill_identity_sha256",
        "stop_entry_fill_identity_sha256",
        "consecutive_completed_losing_exits",
        "account_drawdown_fraction",
        "drawdown_scalar",
    )
    errors: set[str] = set()
    if any(field not in risk_control_state for field in required):
        errors.add("invalid_risk_control_state")

    as_of = _parse_utc_timestamp(risk_control_state.get("as_of"))
    stop_loss_distance = _finite_number(risk_control_state.get("stop_loss_distance"))
    account_drawdown = _finite_number(
        risk_control_state.get("account_drawdown_fraction")
    )
    drawdown_scalar = _finite_number(risk_control_state.get("drawdown_scalar"))
    raw_losses = risk_control_state.get("consecutive_completed_losing_exits")
    losses = (
        raw_losses
        if not isinstance(raw_losses, bool)
        and isinstance(raw_losses, int)
        and raw_losses >= 0
        else None
    )
    max_age = _finite_number(mandate.get("max_snapshot_age_seconds"))
    if as_of is None or max_age is None:
        errors.add("invalid_risk_control_state")
    elif (age := (now - as_of).total_seconds()) < 0.0 or age > max_age:
        errors.add("stale_risk_control_state")
    if risk_control_state.get("mandate_id") != mandate.get("mandate_id"):
        errors.add("risk_control_mandate_mismatch")
    if _sha256(risk_control_state.get("candidate_identity_sha256")) != mandate.get(
        "candidate_identity_sha256"
    ):
        errors.add("risk_control_candidate_mismatch")
    if stop_loss_distance != 0.05:
        errors.add("invalid_stop_loss_distance")
    if not isinstance(risk_control_state.get("stop_intent_ready"), bool):
        errors.add("invalid_stop_state")
    if account_drawdown is None or not 0.0 <= account_drawdown <= 1.0:
        errors.add("invalid_account_drawdown")
    if losses is None:
        errors.add("invalid_strategy_breaker_state")

    expected_scalar: float | None = None
    if account_drawdown is not None and 0.0 <= account_drawdown <= 1.0:
        if account_drawdown <= 0.05:
            expected_scalar = 1.0
        elif account_drawdown <= 0.10:
            expected_scalar = 0.50
        else:
            expected_scalar = 0.0
        if drawdown_scalar != expected_scalar:
            errors.add("drawdown_scalar_mismatch")
    elif drawdown_scalar is None:
        errors.add("invalid_drawdown_scalar")

    tqqq_active = any(symbol == "TQQQ" for symbol, _ in active_positions)
    if tqqq_active and risk_control_state.get("stop_intent_ready") is not True:
        errors.add("stop_intent_not_ready")
    entry_fill_identity = _sha256(
        risk_control_state.get("tqqq_entry_fill_identity_sha256")
    )
    stop_entry_fill_identity = _sha256(
        risk_control_state.get("stop_entry_fill_identity_sha256")
    )
    if tqqq_active and (
        entry_fill_identity is None
        or stop_entry_fill_identity is None
        or entry_fill_identity != stop_entry_fill_identity
    ):
        errors.add("stop_entry_fill_identity_mismatch")
    strategy_breaker = losses is not None and losses >= 5
    account_breaker = account_drawdown is not None and account_drawdown > 0.10
    if strategy_breaker:
        errors.add("strategy_breaker_triggered")
    if account_breaker:
        errors.add("account_breaker_triggered")

    payload = {
        "as_of": _utc_timestamp(as_of) if as_of is not None else None,
        "mandate_id": risk_control_state.get("mandate_id"),
        "candidate_identity_sha256": _sha256(
            risk_control_state.get("candidate_identity_sha256")
        ),
        "stop_loss_distance": stop_loss_distance,
        "stop_intent_ready": (
            risk_control_state.get("stop_intent_ready")
            if isinstance(risk_control_state.get("stop_intent_ready"), bool)
            else None
        ),
        "tqqq_entry_fill_identity_sha256": entry_fill_identity,
        "stop_entry_fill_identity_sha256": stop_entry_fill_identity,
        "consecutive_completed_losing_exits": losses,
        "account_drawdown_fraction": account_drawdown,
        "drawdown_scalar": drawdown_scalar,
    }
    return {
        "stop_loss_distance": stop_loss_distance,
        "stop_intent_ready": (
            risk_control_state.get("stop_intent_ready")
            if isinstance(risk_control_state.get("stop_intent_ready"), bool)
            else None
        ),
        "strategy_breaker_triggered": strategy_breaker,
        "account_breaker_triggered": account_breaker,
        "account_drawdown_fraction": account_drawdown,
        "drawdown_scalar": drawdown_scalar,
        "risk_control_state_digest_sha256": _canonical_digest(payload),
    }, errors


def _global_etf_risk_control_fields(
    risk_control_state: Mapping[str, Any] | None,
    *,
    mandate: Mapping[str, Any],
    now: datetime,
    active_positions: list[tuple[str, float]],
) -> tuple[dict[str, Any], set[str]]:
    empty = {
        "stop_loss_distance": None,
        "stop_intent_ready": None,
        "strategy_breaker_triggered": None,
        "account_breaker_triggered": None,
        "account_drawdown_fraction": None,
        "drawdown_scalar": None,
        "risk_control_state_digest_sha256": None,
    }
    if not isinstance(risk_control_state, Mapping):
        return empty, {"missing_risk_control_state"}

    required = (
        "as_of",
        "mandate_id",
        "candidate_identity_sha256",
        "stop_loss_distance",
        "stop_fill_policy",
        "position_stop_states",
        "consecutive_completed_losing_exits",
        "account_drawdown_fraction",
        "drawdown_scalar",
    )
    errors: set[str] = set()
    if any(field not in risk_control_state for field in required):
        errors.add("invalid_risk_control_state")

    as_of = _parse_utc_timestamp(risk_control_state.get("as_of"))
    stop_loss_distance = _finite_number(risk_control_state.get("stop_loss_distance"))
    account_drawdown = _finite_number(
        risk_control_state.get("account_drawdown_fraction")
    )
    drawdown_scalar = _finite_number(risk_control_state.get("drawdown_scalar"))
    raw_losses = risk_control_state.get("consecutive_completed_losing_exits")
    losses = (
        raw_losses
        if not isinstance(raw_losses, bool)
        and isinstance(raw_losses, int)
        and raw_losses >= 0
        else None
    )
    max_age = _finite_number(mandate.get("max_snapshot_age_seconds"))
    if as_of is None or max_age is None:
        errors.add("invalid_risk_control_state")
    elif (age := (now - as_of).total_seconds()) < 0.0 or age > max_age:
        errors.add("stale_risk_control_state")
    raw_mandate_id = risk_control_state.get("mandate_id")
    mandate_id = raw_mandate_id if isinstance(raw_mandate_id, str) else None
    if mandate_id != mandate.get("mandate_id"):
        errors.add("risk_control_mandate_mismatch")
    if _sha256(risk_control_state.get("candidate_identity_sha256")) != mandate.get(
        "candidate_identity_sha256"
    ):
        errors.add("risk_control_candidate_mismatch")
    if stop_loss_distance != 0.05:
        errors.add("invalid_stop_loss_distance")
    raw_stop_fill_policy = risk_control_state.get("stop_fill_policy")
    stop_fill_policy = (
        raw_stop_fill_policy if isinstance(raw_stop_fill_policy, str) else None
    )
    if stop_fill_policy != _GLOBAL_ETF_STOP_FILL_POLICY:
        errors.add("invalid_stop_fill_policy")
    if account_drawdown is None or not 0.0 <= account_drawdown <= 1.0:
        errors.add("invalid_account_drawdown")
    if losses is None:
        errors.add("invalid_strategy_breaker_state")

    expected_scalar: float | None = None
    if account_drawdown is not None and 0.0 <= account_drawdown <= 1.0:
        if account_drawdown <= 0.05:
            expected_scalar = 1.0
        elif account_drawdown <= 0.10:
            expected_scalar = 0.50
        else:
            expected_scalar = 0.0
        if drawdown_scalar != expected_scalar:
            errors.add("drawdown_scalar_mismatch")
    elif drawdown_scalar is None:
        errors.add("invalid_drawdown_scalar")

    active_symbols = [symbol for symbol, _weight in active_positions]
    if len(active_symbols) != len(set(active_symbols)):
        errors.add("duplicate_active_symbol")
    raw_stop_states = risk_control_state.get("position_stop_states")
    normalized_stop_states: dict[str, dict[str, Any]] = {}
    all_stop_intents_ready = True
    if not isinstance(raw_stop_states, Mapping):
        errors.add("invalid_position_stop_states")
        all_stop_intents_ready = False
    elif set(raw_stop_states) != set(active_symbols):
        errors.add("stop_state_positions_mismatch")
        all_stop_intents_ready = False
    else:
        expected_stop_fields = {
            "stop_intent_ready",
            "entry_fill_identity_sha256",
            "stop_entry_fill_identity_sha256",
        }
        for symbol in sorted(set(active_symbols)):
            raw_stop = raw_stop_states.get(symbol)
            if not isinstance(raw_stop, Mapping) or set(raw_stop) != expected_stop_fields:
                errors.add("invalid_position_stop_state")
                all_stop_intents_ready = False
                continue
            ready = raw_stop.get("stop_intent_ready")
            entry_fill_identity = _sha256(
                raw_stop.get("entry_fill_identity_sha256")
            )
            stop_entry_fill_identity = _sha256(
                raw_stop.get("stop_entry_fill_identity_sha256")
            )
            if ready is not True:
                errors.add("stop_intent_not_ready")
                all_stop_intents_ready = False
            if (
                entry_fill_identity is None
                or stop_entry_fill_identity is None
                or entry_fill_identity != stop_entry_fill_identity
            ):
                errors.add("stop_entry_fill_identity_mismatch")
                all_stop_intents_ready = False
            normalized_stop_states[symbol] = {
                "stop_intent_ready": ready if isinstance(ready, bool) else None,
                "entry_fill_identity_sha256": entry_fill_identity,
                "stop_entry_fill_identity_sha256": stop_entry_fill_identity,
            }

    strategy_breaker = losses is not None and losses >= 5
    account_breaker = account_drawdown is not None and account_drawdown > 0.10
    if strategy_breaker:
        errors.add("strategy_breaker_triggered")
    if account_breaker:
        errors.add("account_breaker_triggered")

    payload = {
        "as_of": _utc_timestamp(as_of) if as_of is not None else None,
        "mandate_id": mandate_id,
        "candidate_identity_sha256": _sha256(
            risk_control_state.get("candidate_identity_sha256")
        ),
        "stop_loss_distance": stop_loss_distance,
        "stop_fill_policy": stop_fill_policy,
        "position_stop_states": normalized_stop_states,
        "consecutive_completed_losing_exits": losses,
        "account_drawdown_fraction": account_drawdown,
        "drawdown_scalar": drawdown_scalar,
    }
    return {
        "stop_loss_distance": stop_loss_distance,
        "stop_intent_ready": all_stop_intents_ready,
        "strategy_breaker_triggered": strategy_breaker,
        "account_breaker_triggered": account_breaker,
        "account_drawdown_fraction": account_drawdown,
        "drawdown_scalar": drawdown_scalar,
        "risk_control_state_digest_sha256": _canonical_digest(payload),
    }, errors


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
) -> RiskGateResult:
    """Assess exactly once and fail closed with a redacted canonical receipt."""
    now = _utc_now()
    evaluated_at = _utc_timestamp(now)
    assessment_scope = scope if scope in _ALLOWED_SCOPES else "MEMBER"
    mandate, mandate_errors = _mandate_fields(mandate_provenance, now=now)
    reason_codes = set(mandate_errors)
    reason_codes.update(
        _candidate_binding_errors(
            mandate_provenance,
            mandate,
            candidate_identity,
        )
    )
    cap = mandate.get("effective_exposure_cap")
    snapshot_payload, observed, total_equity, snapshot_errors = _snapshot_metrics(
        portfolio_snapshot,
        now=now,
        max_snapshot_age_seconds=mandate.get("max_snapshot_age_seconds"),
    )
    reason_codes.update(snapshot_errors)
    completed_session_equity: float | None = None
    if mandate.get("mandate_id") == _GLOBAL_ETF_RESEARCH_MANDATE:
        completed_session_equity = _completed_session_equity(portfolio_snapshot)
        snapshot_payload["completed_session_equity"] = completed_session_equity
        if completed_session_equity is None:
            reason_codes.add("invalid_completed_session_equity")
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
        weighted_exposure = 0.0
        if mandate_provenance is None and len(active_positions) > 1:
            reason_codes.add("fallback_position_count")
        mandate_id = mandate.get("mandate_id")
        exact_research_mandate = mandate_id in {
            _TQQQ_ETF_ONLY_RESEARCH_MANDATE,
            _GLOBAL_ETF_RESEARCH_MANDATE,
        }
        if (
            exact_research_mandate
            and len(active_positions) > mandate["max_nonzero_assets"]
        ):
            reason_codes.add("single_strategy_position_count")
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
                    and weight
                    > loss_budget * drawdown_scalar / stop_distance + 1e-9
                ):
                    reason_codes.add("risk_budget_exposure_cap")
            weighted_exposure += weight * factor
        if mandate_id == _GLOBAL_ETF_RESEARCH_MANDATE:
            stop_distance = control_fields["stop_loss_distance"]
            drawdown_scalar = control_fields["drawdown_scalar"]
            loss_budget = mandate.get("loss_budget")
            modeled_stop_loss = (
                sum(weight for _symbol, weight in active_positions)
                * total_equity
                * stop_distance
                if stop_distance is not None and total_equity is not None
                else None
            )
            loss_budget_amount = (
                loss_budget * completed_session_equity * drawdown_scalar
                if loss_budget is not None
                and completed_session_equity is not None
                and drawdown_scalar is not None
                else None
            )
            if (
                modeled_stop_loss is not None
                and loss_budget_amount is not None
                and modeled_stop_loss > loss_budget_amount + 1e-9
            ):
                reason_codes.add("risk_budget_exposure_cap")
        target_weights: dict[str, float] = {}
        for symbol, weight in active_positions:
            target_weights[symbol] = target_weights.get(symbol, 0.0) + weight
        valid_normalization = False
        if normalization_origin_weights is not None:
            valid_normalization = validate_reduce_only_normalization(
                origin_weights=normalization_origin_weights,
                target_weights=target_weights,
                product_leverage_factors=factors,
                effective_exposure_cap=cap,
                observed_effective_exposure=observed,
                cash_only=exact_research_mandate,
            )
            if not valid_normalization:
                reason_codes.add("invalid_reduce_only_normalization")
            else:
                normalized_origin = {
                    symbol: float(weight)
                    for symbol, weight in sorted(normalization_origin_weights.items())
                }
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
        candidate_identity_sha256=(
            candidate_identity.candidate_sha256
            if isinstance(candidate_identity, CandidateRiskIdentity)
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
