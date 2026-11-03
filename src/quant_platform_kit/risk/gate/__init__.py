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

from quant_platform_kit.common.capital_base import (
    CapitalBaseBinding,
    CapitalBaseSnapshot,
    CapitalBaseValidation,
    validate_capital_base,
)
from quant_platform_kit.common.models import PortfolioSnapshot
from quant_platform_kit.position_sizing import validate_reduce_only_normalization
from quant_platform_kit.risk.contracts import (
    CandidateRiskIdentity,
    DEFAULT_SMALL_ACCOUNT_HOLD_POLICY,
    RiskGateAssessment,
    RiskGateResult,
    RuntimeRiskLimits,
    SmallAccountRiskHoldPolicy,
)
from quant_platform_kit.risk.engine import build_risk_engine
from quant_platform_kit.common.risk_mandates import (
    _APPROVED_BOOTSTRAP_MANDATE,
    _BOOTSTRAP_EFFECTIVE_EXPOSURE_CAP,
    _BOOTSTRAP_NOMINAL_CAPS,
    _TQQQ_ETF_ONLY_EFFECTIVE_CAPS,
    _TQQQ_ETF_ONLY_FACTORS,
    _TQQQ_ETF_ONLY_NOMINAL_CAPS,
    _TQQQ_ETF_ONLY_RESEARCH_MANDATE,
    _TQQQ_ETF_ONLY_STRATEGY_PROFILE,
)
from quant_platform_kit.common.strategy_contracts import (
    BudgetIntent,
    PositionTarget,
    StrategyDecision,
)


logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


from .support import (
    _TQQQ_EVIDENCE_MAX_AGE_SECONDS,
    _MAX_JSON_SAFE_INTEGER,
    _MAX_MATERIAL_ITEMS,
    _utc_timestamp,
    _canonical_digest,
    _capital_base_snapshot_commitment,
    _finite_number,
    _bounded_nonnegative_int,
    _canonical_string,
    _canonical_string_list,
    _canonical_numeric_mapping,
    _normalized_weight_map,
    _portfolio_current_weights,
    _resolve_small_account_hold_policy,
    _small_account_hold_allows_overrun,
    _observe,
    _runtime_risk_limits_rejection,
    _canonical_cap_material,
    _safe_diagnostics,
    _parse_utc_timestamp,
    _parse_utc_whole_second,
    _exact_mapping,
    _logical_evaluation_time,
    _sha256,
    _git_revision,
    _decision_metrics,
    _snapshot_metrics,
    _static_gate_total_equity,
)


from .mandates import (
    _DEFAULT_MAX_SINGLE_WEIGHT,
    _TQQQ_EVIDENCE_MANDATE_SCHEMA,
    _TQQQ_EVIDENCE_PORTFOLIO_SCHEMA,
    _TQQQ_EVIDENCE_RISK_STATE_SCHEMA,
    _TQQQ_EVIDENCE_MANDATE_ID,
    _TQQQ_EVIDENCE_PURPOSE,
    _TQQQ_EVIDENCE_FACTORS,
    _TQQQ_EVIDENCE_NOMINAL_CAPS,
    _TQQQ_EVIDENCE_EFFECTIVE_CAPS,
    _TQQQ_EVIDENCE_DRAWDOWN_SCALARS,
    _TQQQ_EVIDENCE_STRESS_LOSS_DISTANCE,
    _RETIRED_GLOBAL_ETF_RESEARCH_MANDATE,
    _FALLBACK_MAX_SNAPSHOT_AGE_SECONDS_V1,
    _ALLOWED_MANDATE_SCOPES,
    _value_target_exposure_audit,
    _exact_numeric_mapping,
    _exact_tqqq_mandate_errors,
    _tqqq_evidence_mandate_fields,
    _mandate_fields,
    _candidate_binding_errors,
    _position_cap,
    _budget_authority_errors,
    _tqqq_evidence_capital_errors,
    _tqqq_evidence_portfolio_fields,
    _tqqq_evidence_risk_control_fields,
    _risk_control_fields,
)


from .static import (
    _STOP_LOSS_THRESHOLD,
    _MAX_CONSECUTIVE_LOSSES,
    _apply_risk_gate_static,
    apply_risk_gate,
    _reject,
)


from .assessment import (
    _ASSESSMENT_CONTRACT_VERSION,
    _ASSESSMENT_POLICY_ID,
    _ASSESSMENT_POLICY_VERSION,
    _ALLOWED_SCOPES,
    _assess_with_evidence_static,
    _invalid_assessment_result,
    assess_with_evidence,
    enrich_decision_risk_diagnostics,
)
