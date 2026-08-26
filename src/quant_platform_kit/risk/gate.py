"""Unified risk gate — hard checks before any StrategyDecision is returned.

Consolidates the lightweight gate from CnEquityStrategies entrypoints with
optional RiskEngine integration and circuit-breaker diagnostics (task 8 prep).
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import unicodedata
from datetime import datetime, timezone
from typing import Any, Mapping

from quant_platform_kit.common.models import PortfolioSnapshot
from quant_platform_kit.position_sizing import validate_reduce_only_normalization
from quant_platform_kit.risk.contracts import (
    CandidateRiskIdentity,
    RiskGateAssessment,
    RiskGateResult,
)
from quant_platform_kit.risk.engine import build_risk_engine
from quant_platform_kit.strategy_contracts import (
    BudgetIntent,
    PositionTarget,
    StrategyDecision,
)

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
_RETIRED_GLOBAL_ETF_RESEARCH_MANDATE = (
    "global_etf_rotation_etf_only_research_v1"
)
_BOOTSTRAP_EFFECTIVE_EXPOSURE_CAP = 0.50
_BOOTSTRAP_NOMINAL_CAPS = {1: 0.50, 2: 0.25, 3: 0.15}
_ASSESSMENT_CONTRACT_VERSION = "qsl.risk_gate_assessment.v2"
_ASSESSMENT_POLICY_ID = "qpk.risk_gate"
_ASSESSMENT_POLICY_VERSION = "v2"
_FALLBACK_MAX_SNAPSHOT_AGE_SECONDS_V1 = 300.0
_ALLOWED_SCOPES = frozenset({"MEMBER", "ACCOUNT"})
_ALLOWED_MANDATE_SCOPES = frozenset({"RESEARCH_ONLY", "PAPER", "LIVE"})
_MAX_JSON_SAFE_INTEGER = (1 << 53) - 1
_MAX_MATERIAL_ITEMS = 1_000


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


def _exact_numeric_mapping(value: Any, expected: Mapping[str, float]) -> bool:
    normalized = _canonical_numeric_mapping(value, maximum=1.0)
    if normalized is None or set(normalized) != set(expected):
        return False
    return all(
        (number := _finite_number(normalized[key])) is not None
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
    allowed_assets = _canonical_string_list(
        mandate_provenance.get("allowed_nonzero_assets")
    )
    factors = _canonical_numeric_mapping(
        mandate_provenance.get("product_leverage_factors"),
        integer=True,
        minimum=1.0,
    )
    exact_factors = factors == _TQQQ_ETF_ONLY_FACTORS
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
        or allowed_assets is None
        or len(allowed_assets) != 2
        or set(allowed_assets) != set(_TQQQ_ETF_ONLY_FACTORS)
        or _bounded_nonnegative_int(mandate_provenance.get("max_nonzero_assets"))
        != 1
        or _bounded_nonnegative_int(mandate_provenance.get("broker_margin_factor"))
        != 1
        or mandate_provenance.get("margin_stacking") is not False
        or mandate_provenance.get("borrowing") is not False
        or mandate_provenance.get("shorting") is not False
        or mandate_provenance.get("income_sleeve_enabled") is not False
        or mandate_provenance.get("option_overlay_enabled") is not False
        or _finite_number(
            mandate_provenance.get("precommitted_executable_stop_distance")
        )
        != 0.05
        or _bounded_nonnegative_int(
            mandate_provenance.get("max_consecutive_completed_losing_exits")
        )
        != 5
        or (expires_at - effective_at).total_seconds() > 90 * 24 * 60 * 60
    )
    return {"invalid_tqqq_research_mandate"} if invalid else set()


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
    if mandate_provenance.get("mandate_id") == _RETIRED_GLOBAL_ETF_RESEARCH_MANDATE:
        return {}, {"retired_global_etf_research_mandate"}

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
    if any(field not in mandate_provenance for field in required):
        return {}, {"invalid_mandate"}

    mandate_id, valid_mandate_id = _canonical_string(
        mandate_provenance["mandate_id"]
    )
    mandate_version, valid_mandate_version = _canonical_string(
        mandate_provenance["mandate_version"]
    )
    authority_scope, valid_authority_scope = _canonical_string(
        mandate_provenance["authority_scope"]
    )
    strategy_profile, valid_strategy_profile = _canonical_string(
        mandate_provenance["strategy_profile"]
    )
    account_mode, valid_account_mode = _canonical_string(
        mandate_provenance["account_mode"]
    )
    receipt_sha256 = _sha256(mandate_provenance["authority_receipt_sha256"])
    strategy_revision = _git_revision(mandate_provenance["strategy_revision"])
    runner_revision = _git_revision(mandate_provenance["runner_revision"])
    source_revision = _git_revision(mandate_provenance["source_revision"])
    config_sha256 = _sha256(mandate_provenance["config_sha256"])
    input_manifest_sha256 = _sha256(mandate_provenance["input_manifest_sha256"])
    candidate_identity_sha256 = _sha256(
        mandate_provenance["candidate_identity_sha256"]
    )
    effective_at = _parse_utc_timestamp(mandate_provenance["effective_at"])
    expires_at = _parse_utc_timestamp(mandate_provenance["expires_at"])
    max_snapshot_age_seconds = _finite_number(
        mandate_provenance["max_snapshot_age_seconds"]
    )
    cap = _finite_number(mandate_provenance["effective_exposure_cap"])
    loss_budget = _finite_number(mandate_provenance["loss_budget"])
    product_caps = _canonical_cap_material(mandate_provenance["product_caps"])
    nominal_caps = _canonical_cap_material(mandate_provenance["nominal_caps"])
    product_effective_caps = _canonical_cap_material(
        mandate_provenance.get("product_effective_caps", 1.0)
    )
    factors = _canonical_numeric_mapping(
        mandate_provenance["product_leverage_factors"],
        integer=True,
        minimum=1.0,
    )
    allowed_assets = _canonical_string_list(
        mandate_provenance["allowed_nonzero_assets"]
    )
    max_nonzero_assets_value = mandate_provenance.get("max_nonzero_assets")
    max_nonzero_assets = (
        None
        if max_nonzero_assets_value is None
        else _bounded_nonnegative_int(max_nonzero_assets_value)
    )
    if (
        not valid_mandate_id
        or not valid_mandate_version
        or not valid_authority_scope
        or not valid_strategy_profile
        or not valid_account_mode
        or authority_scope not in _ALLOWED_MANDATE_SCOPES
        or receipt_sha256 is None
        or strategy_revision is None
        or runner_revision is None
        or source_revision is None
        or config_sha256 is None
        or input_manifest_sha256 is None
        or candidate_identity_sha256 is None
        or effective_at is None
        or expires_at is None
        or max_snapshot_age_seconds is None
        or max_snapshot_age_seconds <= 0.0
        or cap is None
        or not 0.0 <= cap <= 1.0
        or loss_budget is None
        or loss_budget < 0.0
        or product_caps is None
        or nominal_caps is None
        or product_effective_caps is None
        or factors is None
        or not factors
        or allowed_assets is None
        or (max_nonzero_assets_value is not None and max_nonzero_assets is None)
    ):
        return {}, {"invalid_mandate"}
    if effective_at > now or expires_at < now or expires_at <= effective_at:
        return {}, {"expired_mandate"}

    exact_mandate_errors = _exact_tqqq_mandate_errors(
        mandate_provenance,
        effective_at=effective_at,
        expires_at=expires_at,
    )
    if exact_mandate_errors:
        return {}, exact_mandate_errors
    return {
        "mandate_id": mandate_id,
        "mandate_version": mandate_version,
        "authority_receipt_sha256": receipt_sha256,
        "authority_scope": authority_scope,
        "source_revision": source_revision,
        "strategy_profile": strategy_profile,
        "account_mode": account_mode,
        "strategy_revision": strategy_revision,
        "runner_revision": runner_revision,
        "config_sha256": config_sha256,
        "input_manifest_sha256": input_manifest_sha256,
        "candidate_identity_sha256": candidate_identity_sha256,
        "effective_exposure_cap": cap,
        "max_snapshot_age_seconds": max_snapshot_age_seconds,
        "loss_budget": loss_budget,
        "product_leverage_factors": factors,
        "product_caps": product_caps,
        "nominal_caps": nominal_caps,
        "product_effective_caps": product_effective_caps,
        "allowed_nonzero_assets": set(allowed_assets),
        "max_nonzero_assets": max_nonzero_assets,
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
    if type(candidate_identity) is not CandidateRiskIdentity:
        return {"invalid_candidate_identity"}
    strategy_profile, valid_strategy_profile = _canonical_string(
        candidate_identity.strategy_profile
    )
    account_mode, valid_account_mode = _canonical_string(
        candidate_identity.account_mode
    )
    if (
        not valid_strategy_profile
        or not valid_account_mode
        or strategy_profile is None
        or account_mode is None
        or _git_revision(candidate_identity.strategy_revision) is None
        or _git_revision(candidate_identity.runner_revision) is None
        or _sha256(candidate_identity.config_sha256) is None
        or _sha256(candidate_identity.input_manifest_sha256) is None
        or _sha256(candidate_identity.authority_receipt_sha256) is None
        or _sha256(candidate_identity.candidate_sha256) is None
    ):
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
    if mandate.get("mandate_id") != _TQQQ_ETF_ONLY_RESEARCH_MANDATE:
        return empty, set()
    if (
        not isinstance(risk_control_state, Mapping)
        or len(risk_control_state) > _MAX_MATERIAL_ITEMS
    ):
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
    mandate_id, valid_mandate_id = _canonical_string(
        risk_control_state.get("mandate_id")
    )
    candidate_identity_sha256 = _sha256(
        risk_control_state.get("candidate_identity_sha256")
    )
    stop_loss_distance = _finite_number(risk_control_state.get("stop_loss_distance"))
    account_drawdown = _finite_number(
        risk_control_state.get("account_drawdown_fraction")
    )
    drawdown_scalar = _finite_number(risk_control_state.get("drawdown_scalar"))
    losses = _bounded_nonnegative_int(
        risk_control_state.get("consecutive_completed_losing_exits")
    )
    stop_intent_value = risk_control_state.get("stop_intent_ready")
    stop_intent_ready = stop_intent_value if type(stop_intent_value) is bool else None
    entry_fill_identity = _sha256(
        risk_control_state.get("tqqq_entry_fill_identity_sha256")
    )
    stop_entry_fill_identity = _sha256(
        risk_control_state.get("stop_entry_fill_identity_sha256")
    )
    max_age = _finite_number(mandate.get("max_snapshot_age_seconds"))

    if not valid_mandate_id:
        errors.add("invalid_risk_metadata")
    if as_of is None or max_age is None:
        errors.add("invalid_risk_control_state")
    elif (age := (now - as_of).total_seconds()) < 0.0 or age > max_age:
        errors.add("stale_risk_control_state")
    if mandate_id != mandate.get("mandate_id"):
        errors.add("risk_control_mandate_mismatch")
    if candidate_identity_sha256 != mandate.get("candidate_identity_sha256"):
        errors.add("risk_control_candidate_mismatch")
    if stop_loss_distance != 0.05:
        errors.add("invalid_stop_loss_distance")
    if stop_intent_ready is None:
        errors.add("invalid_stop_state")
    if account_drawdown is None or not 0.0 <= account_drawdown <= 1.0:
        errors.add("invalid_account_drawdown")
    if losses is None:
        errors.add("invalid_strategy_breaker_state")
    if entry_fill_identity is None or stop_entry_fill_identity is None:
        errors.add("invalid_stop_identity")

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
    if tqqq_active and stop_intent_ready is not True:
        errors.add("stop_intent_not_ready")
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
        "mandate_id": mandate_id,
        "candidate_identity_sha256": candidate_identity_sha256,
        "stop_loss_distance": stop_loss_distance,
        "stop_intent_ready": stop_intent_ready,
        "tqqq_entry_fill_identity_sha256": entry_fill_identity,
        "stop_entry_fill_identity_sha256": stop_entry_fill_identity,
        "consecutive_completed_losing_exits": losses,
        "account_drawdown_fraction": account_drawdown,
        "drawdown_scalar": drawdown_scalar,
    }
    return {
        "stop_loss_distance": stop_loss_distance,
        "stop_intent_ready": stop_intent_ready,
        "strategy_breaker_triggered": strategy_breaker,
        "account_breaker_triggered": account_breaker,
        "account_drawdown_fraction": account_drawdown,
        "drawdown_scalar": drawdown_scalar,
        "risk_control_state_digest_sha256": _canonical_digest(payload),
    }, errors

def _assess_with_evidence_static(
    decision: StrategyDecision,
    portfolio_snapshot: Any,
    *,
    scope: Any,
    mandate_provenance: Mapping[str, Any] | None,
    candidate_identity: CandidateRiskIdentity | None,
    normalization_origin_weights: Mapping[str, float] | None,
    risk_control_state: Mapping[str, Any] | None,
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
        weighted_exposure = 0.0
        if mandate_provenance is None and len(active_positions) > 1:
            reason_codes.add("fallback_position_count")
        if (
            mandate.get("mandate_id") == _TQQQ_ETF_ONLY_RESEARCH_MANDATE
            and len(active_positions) > mandate["max_nonzero_assets"]
        ):
            reason_codes.add("single_strategy_position_count")
        for symbol, weight in active_positions:
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

        target_weights: dict[str, float] = {}
        for symbol, weight in active_positions:
            combined_weight = target_weights.get(symbol, 0.0) + weight
            if not math.isfinite(combined_weight):
                reason_codes.add("invalid_risk_metadata")
                continue
            target_weights[symbol] = combined_weight
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
) -> RiskGateResult:
    reason_codes = {"invalid_risk_metadata"}
    try:
        if (
            isinstance(mandate_provenance, Mapping)
            and mandate_provenance.get("mandate_id")
            == _RETIRED_GLOBAL_ETF_RESEARCH_MANDATE
        ):
            reason_codes.add("retired_global_etf_research_mandate")
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
        reason_codes=tuple(sorted(reason_codes)),
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
) -> RiskGateResult:
    """Assess exactly once and fail closed with a redacted canonical receipt."""
    try:
        risk_action = build_risk_engine().assess(
            decision,
            portfolio_snapshot,
            market_data=market_data,
        )
    except Exception:
        risk_action = None
        risk_engine_failed = True
    else:
        risk_engine_failed = False
    now = _utc_now()
    try:
        return _assess_with_evidence_static(
            decision,
            portfolio_snapshot,
            scope=scope,
            mandate_provenance=mandate_provenance,
            candidate_identity=candidate_identity,
            normalization_origin_weights=normalization_origin_weights,
            risk_control_state=risk_control_state,
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
    engine_action: Any,
    engine_failed: bool,
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
            else:
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
            if weight > 0.0:
                weights.append((position, weight))

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
    elif static_rejection is None and positions:
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
) -> StrategyDecision:
    """Apply hard checks and call RiskEngine.assess exactly once."""
    try:
        engine_action = build_risk_engine().assess(
            decision,
            portfolio_snapshot,
            market_data=market_data,
        )
    except Exception:
        engine_action = None
        engine_failed = True
    else:
        engine_failed = False
    try:
        return _apply_risk_gate_static(
            decision,
            risk_mandate_id=risk_mandate_id,
            product_leverage_factors=product_leverage_factors,
            available_account_exposure=available_account_exposure,
            max_single_weight=max_single_weight,
            max_positions=max_positions,
            max_total_exposure=max_total_exposure,
            portfolio_snapshot=portfolio_snapshot,
            engine_action=engine_action,
            engine_failed=engine_failed,
        )
    except Exception:
        return _reject(
            decision,
            flag="rejected:invalid_risk_metadata",
            reason="invalid_risk_metadata",
            diagnostics={},
        )

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
