"""Bind redacted reconciliation equity summaries to injected gate snapshots (W2).

Read-only, inject-only: no broker I/O, no network, no live authority.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, fields, is_dataclass
import math
from typing import Any

from quant_platform_kit.risk.account_new_risk_gate import (
    AccountNewRiskGateError,
    InjectedReconciliationSnapshot,
    validate_injected_snapshot,
)

_EQUITY_SUMMARY_KEYS = frozenset(
    {
        "equity_usd",
        "peak_equity_usd",
        "drawdown_from_peak",
        "realized_vol",
    }
)
_HEALTH_AXIS_KEYS = frozenset(
    {
        "observation_status",
        "reconciliation_status",
        "circuit_breaker_state",
    }
)
_ALLOWED_SOURCE_KEYS = _EQUITY_SUMMARY_KEYS | _HEALTH_AXIS_KEYS


@dataclass(frozen=True)
class ReconciliationEquitySummary:
    """Redacted equity summary slice of a reconciliation snapshot."""

    equity_usd: float
    peak_equity_usd: float | None = None
    drawdown_from_peak: float | None = None
    realized_vol: float | None = None


def _require_finite_non_bool_number(
    value: Any,
    *,
    field_name: str,
    allow_none: bool = False,
    min_value: float | None = None,
) -> float | None:
    if value is None:
        if allow_none:
            return None
        raise AccountNewRiskGateError(f"{field_name} is required")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise AccountNewRiskGateError(f"{field_name} must be a finite number")
    number = float(value)
    if not math.isfinite(number):
        raise AccountNewRiskGateError(f"{field_name} must be a finite number")
    if min_value is not None and number < min_value:
        raise AccountNewRiskGateError(f"{field_name} must be >= {min_value}")
    return number


def _normalize_mapping(source: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(source, Mapping):
        raise AccountNewRiskGateError("equity summary source must be a mapping or dataclass")
    unknown = set(source.keys()) - _ALLOWED_SOURCE_KEYS
    if unknown:
        unknown_list = ", ".join(sorted(unknown))
        raise AccountNewRiskGateError(f"unsupported equity summary keys: {unknown_list}")
    return dict(source)


def _normalize_dataclass(source: ReconciliationEquitySummary) -> dict[str, Any]:
    if not isinstance(source, ReconciliationEquitySummary):
        raise AccountNewRiskGateError("equity summary dataclass has unexpected type")
    return {field.name: getattr(source, field.name) for field in fields(source)}


def build_injected_snapshot_from_equity_summary(
    source: Mapping[str, Any] | ReconciliationEquitySummary,
    *,
    observation_status: str = "COMPLETE",
    reconciliation_status: str = "VERIFIED",
    circuit_breaker_state: str = "CLOSED",
) -> InjectedReconciliationSnapshot:
    """Map a redacted equity summary dict/dataclass to ``InjectedReconciliationSnapshot``.

    Health axes may be supplied via kwargs or included in ``source`` when it is a
    mapping. Bad / unknown input raises ``AccountNewRiskGateError`` (fail-closed).
    """
    if isinstance(source, Mapping):
        payload = _normalize_mapping(source)
        observation_status = str(payload.pop("observation_status", observation_status))
        reconciliation_status = str(payload.pop("reconciliation_status", reconciliation_status))
        circuit_breaker_state = str(payload.pop("circuit_breaker_state", circuit_breaker_state))
    elif is_dataclass(source) and isinstance(source, ReconciliationEquitySummary):
        payload = _normalize_dataclass(source)
    else:
        raise AccountNewRiskGateError(
            "equity summary source must be ReconciliationEquitySummary or a mapping"
        )

    equity_usd = _require_finite_non_bool_number(
        payload.get("equity_usd"),
        field_name="equity_usd",
        min_value=0.0,
    )
    peak_equity_usd = _require_finite_non_bool_number(
        payload.get("peak_equity_usd"),
        field_name="peak_equity_usd",
        allow_none=True,
        min_value=0.0,
    )
    drawdown_from_peak = _require_finite_non_bool_number(
        payload.get("drawdown_from_peak"),
        field_name="drawdown_from_peak",
        allow_none=True,
        min_value=0.0,
    )
    realized_vol = _require_finite_non_bool_number(
        payload.get("realized_vol"),
        field_name="realized_vol",
        allow_none=True,
        min_value=0.0,
    )

    snapshot = InjectedReconciliationSnapshot(
        observation_status=observation_status,
        reconciliation_status=reconciliation_status,
        circuit_breaker_state=circuit_breaker_state,
        equity_usd=equity_usd,
        peak_equity_usd=peak_equity_usd,
        drawdown_from_peak=drawdown_from_peak,
        realized_vol=realized_vol,
    )
    return validate_injected_snapshot(snapshot)


__all__ = [
    "ReconciliationEquitySummary",
    "build_injected_snapshot_from_equity_summary",
]
