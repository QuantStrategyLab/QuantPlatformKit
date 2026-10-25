"""TQQQ mandate, evidence, candidate, budget, and risk-control field validation."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping

from quant_platform_kit.common.capital_base import CapitalBaseValidation
from quant_platform_kit.common.risk_mandates import (
    _TQQQ_ETF_ONLY_EFFECTIVE_CAPS,
    _TQQQ_ETF_ONLY_FACTORS,
    _TQQQ_ETF_ONLY_NOMINAL_CAPS,
    _TQQQ_ETF_ONLY_RESEARCH_MANDATE,
    _TQQQ_ETF_ONLY_STRATEGY_PROFILE,
)
from quant_platform_kit.common.strategy_contracts import PositionTarget, StrategyDecision
from quant_platform_kit.risk.contracts import CandidateRiskIdentity

from .support import (
    _MAX_MATERIAL_ITEMS,
    _TQQQ_EVIDENCE_MAX_AGE_SECONDS,
    _bounded_nonnegative_int,
    _canonical_cap_material,
    _canonical_digest,
    _canonical_numeric_mapping,
    _canonical_string,
    _canonical_string_list,
    _capital_base_snapshot_commitment,
    _exact_mapping,
    _finite_number,
    _git_revision,
    _parse_utc_timestamp,
    _parse_utc_whole_second,
    _sha256,
    _utc_timestamp,
)


_DEFAULT_MAX_SINGLE_WEIGHT = 0.10


_TQQQ_EVIDENCE_MANDATE_SCHEMA = "qsl.tqqq-evidence-risk-mandate.v1"


_TQQQ_EVIDENCE_PORTFOLIO_SCHEMA = "qsl.tqqq-evidence-portfolio-snapshot.v1"


_TQQQ_EVIDENCE_RISK_STATE_SCHEMA = "qsl.tqqq-evidence-risk-state.v1"


_TQQQ_EVIDENCE_MANDATE_ID = "tqqq_core_parity_v1"


_TQQQ_EVIDENCE_PURPOSE = "TQQQ_CANDIDATE_RESEARCH_EVIDENCE_ONLY"


_TQQQ_EVIDENCE_FACTORS = {"TQQQ": 3, "QQQM": 1, "BOXX": 1}


_TQQQ_EVIDENCE_NOMINAL_CAPS = {"TQQQ": 0.15, "QQQM": 0.50, "BOXX": 0.50}


_TQQQ_EVIDENCE_EFFECTIVE_CAPS = {"TQQQ": 0.45, "QQQM": 0.50, "BOXX": 0.50}


_TQQQ_EVIDENCE_DRAWDOWN_SCALARS = {
    "at_or_below_0_05": 1.0,
    "above_0_05_to_0_10": 0.5,
    "above_0_10": 0.0,
}


_TQQQ_EVIDENCE_STRESS_LOSS_DISTANCE = 0.05


_RETIRED_GLOBAL_ETF_RESEARCH_MANDATE = (
    "global_etf_rotation_etf_only_research_v1"
)


_FALLBACK_MAX_SNAPSHOT_AGE_SECONDS_V1 = 300.0


_ALLOWED_MANDATE_SCOPES = frozenset({"RESEARCH_ONLY", "PAPER", "LIVE"})


def _value_target_exposure_audit(
    positions: tuple[PositionTarget, ...],
    *,
    total_equity: float | None,
    enforced: bool,
    capital_base_validation: CapitalBaseValidation | None = None,
) -> dict[str, Any] | None:
    """Summarize value-target exposure without changing legacy execution.

    This is deliberately diagnostic-only while a legacy strategy is being
    migrated. It gives the runtime monitor a normalized exposure signal and
    makes an unreviewed amount-target contract observable, without silently
    treating missing account equity as a zero-weight target or abruptly
    stopping every legacy strategy in one release.
    """
    target_values: list[float] = []
    invalid_target_value = False
    has_value_target = False
    for position in positions:
        if position.target_value is None:
            continue
        has_value_target = True
        target_value = _finite_number(position.target_value)
        if target_value is None or target_value < 0.0:
            invalid_target_value = True
            continue
        if target_value > 0.0:
            target_values.append(target_value)
    if not has_value_target:
        return None

    active_target_count = len(target_values)
    audit: dict[str, Any] = {
        "version": "qpk.value_target_exposure_audit.v1",
        "enforcement": "enforced" if enforced else "legacy_compatibility",
        "migration_required": not enforced and active_target_count > 0,
        "equity_available": total_equity is not None,
        "active_target_count": active_target_count,
        "invalid_target_value": invalid_target_value,
        "max_target_weight": None,
        "total_target_weight": None,
    }
    if total_equity is not None and target_values:
        audit["max_target_weight"] = max(target_values) / total_equity
        audit["total_target_weight"] = sum(target_values) / total_equity
    if enforced and capital_base_validation is not None:
        audit["capital_base"] = capital_base_validation.to_safe_dict()
    return audit


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


def _tqqq_evidence_mandate_fields(
    mandate_provenance: Mapping[str, Any],
    *,
    now: datetime,
) -> tuple[dict[str, Any], set[str]]:
    invalid = {"invalid_tqqq_evidence_risk_mandate"}
    top_level = _exact_mapping(
        mandate_provenance,
        frozenset(
            {
                "schema_version",
                "mandate_id",
                "mandate_version",
                "purpose",
                "candidate_binding",
                "validity",
                "portfolio_policy",
                "capital_binding",
                "portfolio_binding",
                "risk_state_binding",
                "authority",
            }
        ),
    )
    if top_level is None:
        return {}, invalid
    candidate = _exact_mapping(
        top_level.get("candidate_binding"),
        frozenset(
            {
                "strategy_profile",
                "account_mode",
                "strategy_revision",
                "runner_revision",
                "config_sha256",
                "input_manifest_sha256",
                "candidate_identity_sha256",
            }
        ),
    )
    validity = _exact_mapping(
        top_level.get("validity"),
        frozenset(
            {
                "effective_at",
                "expires_at",
                "snapshot_max_age_seconds",
                "single_consumption",
            }
        ),
    )
    portfolio_policy = _exact_mapping(
        top_level.get("portfolio_policy"),
        frozenset(
            {
                "allowed_nonzero_assets",
                "benchmark_only_assets",
                "product_leverage_factors",
                "max_nonzero_assets",
                "effective_exposure_cap",
                "nominal_caps",
                "product_effective_caps",
                "loss_budget",
                "loss_budget_equity_reference",
                "modeled_stress_loss_distance",
                "stress_loss_is_model_assumption",
                "drawdown_scalars",
                "broker_margin_factor",
                "margin_stacking",
                "borrowing",
                "shorting",
            }
        ),
    )
    capital_binding = _exact_mapping(
        top_level.get("capital_binding"),
        frozenset(
            {
                "schema_version",
                "snapshot_digest_sha256",
                "as_of",
                "account_mode",
                "capital_scope",
                "valuation_basis",
                "target_currency",
                "max_age_seconds",
                "fx_conversion_allowed",
            }
        ),
    )
    portfolio_binding = _exact_mapping(
        top_level.get("portfolio_binding"),
        frozenset(
            {
                "schema_version",
                "snapshot_digest_sha256",
                "as_of",
                "source_identity_sha256",
                "max_age_seconds",
            }
        ),
    )
    risk_state_binding = _exact_mapping(
        top_level.get("risk_state_binding"),
        frozenset(
            {
                "schema_version",
                "snapshot_digest_sha256",
                "as_of",
                "max_age_seconds",
            }
        ),
    )
    authority = _exact_mapping(
        top_level.get("authority"),
        frozenset(
            {
                "authority_scope",
                "authority_receipt_sha256",
                "source_revision",
                "runner_is_authority",
                "no_order",
                "no_paper",
                "no_shadow",
                "no_live",
                "no_promotion_authority",
            }
        ),
    )
    if any(
        section is None
        for section in (
            candidate,
            validity,
            portfolio_policy,
            capital_binding,
            portfolio_binding,
            risk_state_binding,
            authority,
        )
    ):
        return {}, invalid
    assert candidate is not None
    assert validity is not None
    assert portfolio_policy is not None
    assert capital_binding is not None
    assert portfolio_binding is not None
    assert risk_state_binding is not None
    assert authority is not None

    strategy_profile, valid_strategy_profile = _canonical_string(
        candidate.get("strategy_profile")
    )
    account_mode, valid_account_mode = _canonical_string(
        candidate.get("account_mode")
    )
    strategy_revision = _git_revision(candidate.get("strategy_revision"))
    runner_revision = _git_revision(candidate.get("runner_revision"))
    config_sha256 = _sha256(candidate.get("config_sha256"))
    input_manifest_sha256 = _sha256(candidate.get("input_manifest_sha256"))
    candidate_identity_sha256 = _sha256(
        candidate.get("candidate_identity_sha256")
    )
    receipt_sha256 = _sha256(authority.get("authority_receipt_sha256"))
    source_revision = _git_revision(authority.get("source_revision"))
    effective_at = _parse_utc_whole_second(validity.get("effective_at"))
    expires_at = _parse_utc_whole_second(validity.get("expires_at"))
    capital_as_of = _parse_utc_whole_second(capital_binding.get("as_of"))
    portfolio_as_of = _parse_utc_whole_second(portfolio_binding.get("as_of"))
    risk_state_as_of = _parse_utc_whole_second(risk_state_binding.get("as_of"))
    capital_digest = _sha256(capital_binding.get("snapshot_digest_sha256"))
    portfolio_digest = _sha256(portfolio_binding.get("snapshot_digest_sha256"))
    portfolio_source_identity = _sha256(
        portfolio_binding.get("source_identity_sha256")
    )
    risk_state_digest = _sha256(
        risk_state_binding.get("snapshot_digest_sha256")
    )
    snapshot_max_age = _finite_number(
        validity.get("snapshot_max_age_seconds")
    )
    capital_max_age = _finite_number(capital_binding.get("max_age_seconds"))
    portfolio_max_age = _finite_number(portfolio_binding.get("max_age_seconds"))
    risk_state_max_age = _finite_number(
        risk_state_binding.get("max_age_seconds")
    )
    allowed_assets = _canonical_string_list(
        portfolio_policy.get("allowed_nonzero_assets")
    )
    benchmark_assets = _canonical_string_list(
        portfolio_policy.get("benchmark_only_assets")
    )
    factors = _canonical_numeric_mapping(
        portfolio_policy.get("product_leverage_factors"),
        integer=True,
        minimum=1.0,
    )
    max_nonzero_assets = _bounded_nonnegative_int(
        portfolio_policy.get("max_nonzero_assets")
    )
    effective_exposure_cap = _finite_number(
        portfolio_policy.get("effective_exposure_cap")
    )
    loss_budget = _finite_number(portfolio_policy.get("loss_budget"))

    fixed_values_valid = (
        top_level.get("schema_version") == _TQQQ_EVIDENCE_MANDATE_SCHEMA
        and top_level.get("mandate_id") == _TQQQ_EVIDENCE_MANDATE_ID
        and top_level.get("mandate_version") == "v1"
        and top_level.get("purpose") == _TQQQ_EVIDENCE_PURPOSE
        and valid_strategy_profile
        and strategy_profile == _TQQQ_EVIDENCE_MANDATE_ID
        and valid_account_mode
        and account_mode == "single_strategy_account_v1"
        and strategy_revision is not None
        and runner_revision is not None
        and config_sha256 is not None
        and input_manifest_sha256 is not None
        and candidate_identity_sha256 is not None
        and receipt_sha256 is not None
        and source_revision is not None
        and effective_at is not None
        and expires_at is not None
        and capital_as_of is not None
        and portfolio_as_of is not None
        and risk_state_as_of is not None
        and capital_digest is not None
        and portfolio_digest is not None
        and portfolio_source_identity is not None
        and risk_state_digest is not None
        and snapshot_max_age == _TQQQ_EVIDENCE_MAX_AGE_SECONDS
        and capital_max_age == _TQQQ_EVIDENCE_MAX_AGE_SECONDS
        and portfolio_max_age == _TQQQ_EVIDENCE_MAX_AGE_SECONDS
        and risk_state_max_age == _TQQQ_EVIDENCE_MAX_AGE_SECONDS
        and validity.get("single_consumption") is True
        and type(portfolio_policy.get("allowed_nonzero_assets")) is list
        and allowed_assets == ["TQQQ", "QQQM", "BOXX"]
        and type(portfolio_policy.get("benchmark_only_assets")) is list
        and benchmark_assets == ["QQQ"]
        and factors == _TQQQ_EVIDENCE_FACTORS
        and max_nonzero_assets == 3
        and effective_exposure_cap == 0.50
        and _exact_numeric_mapping(
            portfolio_policy.get("nominal_caps"),
            _TQQQ_EVIDENCE_NOMINAL_CAPS,
        )
        and _exact_numeric_mapping(
            portfolio_policy.get("product_effective_caps"),
            _TQQQ_EVIDENCE_EFFECTIVE_CAPS,
        )
        and loss_budget == 0.01
        and portfolio_policy.get("loss_budget_equity_reference")
        == "completed_session_equity"
        and _finite_number(
            portfolio_policy.get("modeled_stress_loss_distance")
        )
        == _TQQQ_EVIDENCE_STRESS_LOSS_DISTANCE
        and portfolio_policy.get("stress_loss_is_model_assumption") is True
        and _exact_numeric_mapping(
            portfolio_policy.get("drawdown_scalars"),
            _TQQQ_EVIDENCE_DRAWDOWN_SCALARS,
        )
        and _bounded_nonnegative_int(
            portfolio_policy.get("broker_margin_factor")
        )
        == 1
        and portfolio_policy.get("margin_stacking") is False
        and portfolio_policy.get("borrowing") is False
        and portfolio_policy.get("shorting") is False
        and capital_binding.get("schema_version") == "qpk.capital_base.v2"
        and capital_binding.get("account_mode") == account_mode
        and capital_binding.get("capital_scope") == "allocated_sleeve"
        and capital_binding.get("valuation_basis") == "allocated_sleeve_ledger"
        and capital_binding.get("target_currency") == "USD"
        and capital_binding.get("fx_conversion_allowed") is False
        and portfolio_binding.get("schema_version")
        == _TQQQ_EVIDENCE_PORTFOLIO_SCHEMA
        and risk_state_binding.get("schema_version")
        == _TQQQ_EVIDENCE_RISK_STATE_SCHEMA
        and authority.get("authority_scope") == "RESEARCH_ONLY"
        and authority.get("runner_is_authority") is False
        and authority.get("no_order") is True
        and authority.get("no_paper") is True
        and authority.get("no_shadow") is True
        and authority.get("no_live") is True
        and authority.get("no_promotion_authority") is True
    )
    if (
        not fixed_values_valid
        or expires_at <= effective_at
        or (expires_at - effective_at).total_seconds()
        > _TQQQ_EVIDENCE_MAX_AGE_SECONDS
    ):
        return {}, invalid
    if effective_at > now or expires_at < now:
        return {}, {"expired_mandate"}

    return {
        "schema_version": _TQQQ_EVIDENCE_MANDATE_SCHEMA,
        "mandate_id": _TQQQ_EVIDENCE_MANDATE_ID,
        "mandate_version": "v1",
        "authority_receipt_sha256": receipt_sha256,
        "authority_scope": "RESEARCH_ONLY",
        "source_revision": source_revision,
        "strategy_profile": strategy_profile,
        "account_mode": account_mode,
        "strategy_revision": strategy_revision,
        "runner_revision": runner_revision,
        "config_sha256": config_sha256,
        "input_manifest_sha256": input_manifest_sha256,
        "candidate_identity_sha256": candidate_identity_sha256,
        "effective_exposure_cap": effective_exposure_cap,
        "max_snapshot_age_seconds": snapshot_max_age,
        "loss_budget": loss_budget,
        "product_leverage_factors": factors,
        "product_caps": dict(_TQQQ_EVIDENCE_NOMINAL_CAPS),
        "nominal_caps": dict(_TQQQ_EVIDENCE_NOMINAL_CAPS),
        "product_effective_caps": dict(_TQQQ_EVIDENCE_EFFECTIVE_CAPS),
        "allowed_nonzero_assets": set(allowed_assets or ()),
        "benchmark_only_assets": set(benchmark_assets or ()),
        "max_nonzero_assets": max_nonzero_assets,
        "modeled_stress_loss_distance": _TQQQ_EVIDENCE_STRESS_LOSS_DISTANCE,
        "capital_binding": {
            "schema_version": "qpk.capital_base.v2",
            "snapshot_digest_sha256": capital_digest,
            "as_of": _utc_timestamp(capital_as_of),
            "account_mode": account_mode,
            "capital_scope": "allocated_sleeve",
            "valuation_basis": "allocated_sleeve_ledger",
            "target_currency": "USD",
            "max_age_seconds": capital_max_age,
            "fx_conversion_allowed": False,
        },
        "portfolio_binding": {
            "schema_version": _TQQQ_EVIDENCE_PORTFOLIO_SCHEMA,
            "snapshot_digest_sha256": portfolio_digest,
            "as_of": _utc_timestamp(portfolio_as_of),
            "source_identity_sha256": portfolio_source_identity,
            "max_age_seconds": portfolio_max_age,
        },
        "risk_state_binding": {
            "schema_version": _TQQQ_EVIDENCE_RISK_STATE_SCHEMA,
            "snapshot_digest_sha256": risk_state_digest,
            "as_of": _utc_timestamp(risk_state_as_of),
            "max_age_seconds": risk_state_max_age,
        },
    }, set()


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
        }, {"missing_mandate"}
    if not isinstance(mandate_provenance, Mapping):
        return {}, {"invalid_mandate"}
    schema_version = mandate_provenance.get("schema_version")
    if schema_version is not None:
        if schema_version != _TQQQ_EVIDENCE_MANDATE_SCHEMA:
            return {}, {"unsupported_mandate_schema"}
        return _tqqq_evidence_mandate_fields(
            mandate_provenance,
            now=now,
        )
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
    if (
        mandate.get("schema_version") == _TQQQ_EVIDENCE_MANDATE_SCHEMA
        and decision.budgets
    ):
        return {"unsupported_evidence_budget"}
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


def _tqqq_evidence_capital_errors(
    validation: CapitalBaseValidation,
    *,
    mandate: Mapping[str, Any],
) -> set[str]:
    if not validation.is_valid:
        return set()
    snapshot = validation.snapshot
    binding = validation.binding
    expected = mandate.get("capital_binding")
    if snapshot is None or binding is None or not isinstance(expected, Mapping):
        return {"capital_base_mandate_mismatch"}
    errors: set[str] = set()
    if _capital_base_snapshot_commitment(snapshot) != expected.get(
        "snapshot_digest_sha256"
    ):
        errors.add("capital_base_digest_mismatch")
    if _parse_utc_whole_second(snapshot.as_of) is None:
        errors.add("invalid_capital_base_timestamp")
    elif _utc_timestamp(snapshot.as_of) != expected.get("as_of"):
        errors.add("capital_base_as_of_mismatch")
    capital_scope = (
        None if snapshot.capital_scope is None else snapshot.capital_scope.value
    )
    valuation_basis = (
        None if snapshot.valuation_basis is None else snapshot.valuation_basis.value
    )
    binding_capital_scope = (
        None if binding.capital_scope is None else binding.capital_scope.value
    )
    binding_valuation_basis = (
        None if binding.valuation_basis is None else binding.valuation_basis.value
    )
    if (
        snapshot.contract_version != expected.get("schema_version")
        or capital_scope != expected.get("capital_scope")
        or valuation_basis != expected.get("valuation_basis")
        or binding_capital_scope != expected.get("capital_scope")
        or binding_valuation_basis != expected.get("valuation_basis")
        or snapshot.target_currency != expected.get("target_currency")
        or snapshot.reported_currency != expected.get("target_currency")
        or binding.target_currency != expected.get("target_currency")
        or snapshot.fx_rate_to_target != 1.0
        or snapshot.fx_source_digest_sha256 is not None
        or binding.max_age_seconds != expected.get("max_age_seconds")
        or binding.strategy_scope != mandate.get("strategy_profile")
    ):
        errors.add("capital_base_mandate_mismatch")
    return errors


def _tqqq_evidence_portfolio_fields(
    portfolio_snapshot: Any,
    *,
    mandate: Mapping[str, Any],
) -> tuple[dict[str, Any], set[str]]:
    snapshot = _exact_mapping(
        portfolio_snapshot,
        frozenset(
            {
                "schema_version",
                "as_of",
                "observed_effective_exposure",
                "total_equity",
                "source_identity_sha256",
            }
        ),
    )
    binding = mandate.get("portfolio_binding")
    if snapshot is None or not isinstance(binding, Mapping):
        return {}, {"invalid_portfolio_snapshot"}
    schema_version, valid_schema = _canonical_string(snapshot.get("schema_version"))
    as_of = _parse_utc_whole_second(snapshot.get("as_of"))
    observed = _finite_number(snapshot.get("observed_effective_exposure"))
    total_equity = _finite_number(snapshot.get("total_equity"))
    source_identity = _sha256(snapshot.get("source_identity_sha256"))
    if (
        not valid_schema
        or schema_version != _TQQQ_EVIDENCE_PORTFOLIO_SCHEMA
        or as_of is None
        or observed is None
        or observed < 0.0
        or total_equity is None
        or total_equity <= 0.0
        or source_identity is None
    ):
        return {}, {"invalid_portfolio_snapshot"}
    payload = {
        "schema_version": schema_version,
        "as_of": _utc_timestamp(as_of),
        "observed_effective_exposure": observed,
        "total_equity": total_equity,
        "source_identity_sha256": source_identity,
    }
    errors: set[str] = set()
    if binding.get("schema_version") != schema_version:
        errors.add("portfolio_snapshot_schema_mismatch")
    if binding.get("as_of") != payload["as_of"]:
        errors.add("portfolio_snapshot_as_of_mismatch")
    if binding.get("source_identity_sha256") != source_identity:
        errors.add("portfolio_snapshot_source_mismatch")
    if binding.get("snapshot_digest_sha256") != _canonical_digest(payload):
        errors.add("portfolio_snapshot_digest_mismatch")
    return payload, errors


def _tqqq_evidence_risk_control_fields(
    risk_control_state: Mapping[str, Any] | None,
    *,
    mandate: Mapping[str, Any],
    now: datetime,
) -> tuple[dict[str, Any], set[str]]:
    empty = {
        "stop_loss_distance": None,
        "stop_intent_ready": None,
        "strategy_breaker_triggered": False,
        "account_breaker_triggered": False,
        "account_drawdown_fraction": None,
        "drawdown_scalar": None,
        "modeled_stress_loss_distance": None,
        "risk_control_state_digest_sha256": None,
    }
    state = _exact_mapping(
        risk_control_state,
        frozenset(
            {
                "schema_version",
                "as_of",
                "mandate_id",
                "candidate_identity_sha256",
                "modeled_stress_loss_distance",
                "account_drawdown_fraction",
                "drawdown_scalar",
            }
        ),
    )
    binding = mandate.get("risk_state_binding")
    if state is None or not isinstance(binding, Mapping):
        return empty, {"invalid_risk_control_state"}

    errors: set[str] = set()
    schema_version, valid_schema = _canonical_string(state.get("schema_version"))
    as_of = _parse_utc_whole_second(state.get("as_of"))
    mandate_id, valid_mandate_id = _canonical_string(state.get("mandate_id"))
    candidate_digest = _sha256(state.get("candidate_identity_sha256"))
    stress_distance = _finite_number(state.get("modeled_stress_loss_distance"))
    account_drawdown = _finite_number(state.get("account_drawdown_fraction"))
    drawdown_scalar = _finite_number(state.get("drawdown_scalar"))
    payload = {
        "schema_version": schema_version,
        "as_of": _utc_timestamp(as_of) if as_of is not None else None,
        "mandate_id": mandate_id,
        "candidate_identity_sha256": candidate_digest,
        "modeled_stress_loss_distance": stress_distance,
        "account_drawdown_fraction": account_drawdown,
        "drawdown_scalar": drawdown_scalar,
    }
    digest = _canonical_digest(payload)

    if not valid_schema or schema_version != _TQQQ_EVIDENCE_RISK_STATE_SCHEMA:
        errors.add("invalid_risk_control_state")
    if as_of is None:
        errors.add("invalid_risk_control_state")
    else:
        max_age = _finite_number(binding.get("max_age_seconds"))
        age_seconds = (now - as_of).total_seconds()
        if max_age is None or age_seconds < 0.0 or age_seconds > max_age:
            errors.add("stale_risk_control_state")
    if mandate_id != mandate.get("mandate_id"):
        errors.add("risk_control_mandate_mismatch")
    if candidate_digest != mandate.get("candidate_identity_sha256"):
        errors.add("risk_control_candidate_mismatch")
    if stress_distance != mandate.get("modeled_stress_loss_distance"):
        errors.add("invalid_modeled_stress_loss_distance")
    if binding.get("schema_version") != schema_version:
        errors.add("risk_control_state_schema_mismatch")
    if binding.get("as_of") != payload["as_of"]:
        errors.add("risk_control_state_as_of_mismatch")
    if binding.get("snapshot_digest_sha256") != digest:
        errors.add("risk_control_state_digest_mismatch")

    expected_scalar: float | None = None
    if account_drawdown is None or not 0.0 <= account_drawdown <= 1.0:
        errors.add("invalid_account_drawdown")
    elif account_drawdown <= 0.05:
        expected_scalar = 1.0
    elif account_drawdown <= 0.10:
        expected_scalar = 0.50
    else:
        expected_scalar = 0.0
    if expected_scalar is None or drawdown_scalar != expected_scalar:
        errors.add("drawdown_scalar_mismatch")
    account_breaker = account_drawdown is not None and account_drawdown > 0.10
    if account_breaker:
        errors.add("account_breaker_triggered")

    return {
        **empty,
        "account_breaker_triggered": account_breaker,
        "account_drawdown_fraction": account_drawdown,
        "drawdown_scalar": drawdown_scalar,
        "modeled_stress_loss_distance": stress_distance,
        "risk_control_state_digest_sha256": digest,
    }, errors


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
        "modeled_stress_loss_distance": None,
        "risk_control_state_digest_sha256": None,
    }
    if mandate.get("schema_version") == _TQQQ_EVIDENCE_MANDATE_SCHEMA:
        return _tqqq_evidence_risk_control_fields(
            risk_control_state,
            mandate=mandate,
            now=now,
        )
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
