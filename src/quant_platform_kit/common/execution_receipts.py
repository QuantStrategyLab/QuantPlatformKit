"""Minimal, privacy-safe facts about one completed execution decision.

An execution receipt is intentionally not an order payload, broker response,
fill record, position snapshot, or source of trading authority.  It is a
bounded statement that lets a read-only control plane distinguish a schedule
that was not due from a run that made no order, submitted one, received a
broker acknowledgement, or needs reconciliation.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any


EXECUTION_RECEIPT_SCHEMA_VERSION = "qsl_execution_receipt.v1"

_PLATFORM_ALIASES = {
    "alpaca": "alpaca",
    "binance": "binance",
    "charles-schwab": "schwab",
    "charles_schwab": "schwab",
    "firstrade": "firstrade",
    "ibkr": "ibkr",
    "interactive-brokers": "ibkr",
    "interactive_brokers": "ibkr",
    "longbridge": "longbridge",
    "qmt": "qmt",
    "schwab": "schwab",
}
EXECUTION_RECEIPT_OUTCOMES = frozenset(
    {
        "not_due",
        "no_action",
        "risk_blocked",
        "submitted",
        "broker_acknowledged",
        "partially_filled",
        "filled",
        "reconciliation_required",
        "failed",
    }
)
EXECUTION_RECEIPT_BROKER_CONFIRMATIONS = frozenset(
    {
        "not_applicable",
        "not_observed",
        "acknowledged",
        "partially_filled",
        "filled",
        "reconciliation_required",
    }
)
_OUTCOME_CONFIRMATIONS = {
    "not_due": frozenset({"not_applicable"}),
    "no_action": frozenset({"not_applicable"}),
    "risk_blocked": frozenset({"not_applicable"}),
    "submitted": frozenset({"not_observed"}),
    "broker_acknowledged": frozenset({"acknowledged"}),
    "partially_filled": frozenset({"partially_filled"}),
    "filled": frozenset({"filled"}),
    "reconciliation_required": frozenset({"reconciliation_required"}),
    # A failed execution can occur before submission, after an unconfirmed
    # request, or after a state mismatch.  The producer must say which safe,
    # non-claiming confirmation state applies rather than guessing.
    "failed": frozenset({"not_applicable", "not_observed", "reconciliation_required"}),
}
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._=-]{0,127}$")
_REVISION = re.compile(r"^[0-9a-f]{40}$")
_RECEIPT_ID = re.compile(r"^execution-receipt\.[0-9a-f]{32}$")


def build_execution_receipt(
    *,
    platform: object,
    strategy_profile: object,
    strategy_revision: object,
    execution_mode: object,
    outcome: object,
    broker_confirmation: object | None = None,
    observed_at: datetime | str | None = None,
) -> dict[str, str]:
    """Build one deterministic receipt without broker/account/order details.

    ``failed`` deliberately requires an explicit ``broker_confirmation``.  A
    timeout alone cannot establish whether a broker received a request, so the
    caller must use ``not_observed`` or ``reconciliation_required`` when that
    distinction is unknown.
    """

    normalized_outcome = _choice(outcome, EXECUTION_RECEIPT_OUTCOMES, "outcome")
    if broker_confirmation is None:
        allowed = _OUTCOME_CONFIRMATIONS[normalized_outcome]
        if len(allowed) != 1:
            raise ValueError("broker_confirmation is required for this outcome")
        broker_confirmation = next(iter(allowed))
    payload = {
        "schema_version": EXECUTION_RECEIPT_SCHEMA_VERSION,
        "platform": _platform(platform),
        "strategy_profile": _identifier(strategy_profile, "strategy_profile"),
        "strategy_revision": _revision(strategy_revision),
        "execution_mode": _choice(execution_mode, frozenset({"paper", "live"}), "execution_mode"),
        "outcome": normalized_outcome,
        "broker_confirmation": _choice(
            broker_confirmation,
            EXECUTION_RECEIPT_BROKER_CONFIRMATIONS,
            "broker_confirmation",
        ),
        "observed_at": _timestamp(observed_at),
    }
    _validate_outcome_confirmation(payload["outcome"], payload["broker_confirmation"])
    payload["receipt_id"] = f"execution-receipt.{_receipt_digest(payload)[:32]}"
    return validate_execution_receipt(payload)


def validate_execution_receipt(value: Mapping[str, Any] | object) -> dict[str, str]:
    """Validate and normalize an untrusted receipt without reading a broker."""

    if not isinstance(value, Mapping):
        raise ValueError("execution receipt must be an object")
    expected_fields = {
        "schema_version",
        "receipt_id",
        "platform",
        "strategy_profile",
        "strategy_revision",
        "execution_mode",
        "outcome",
        "broker_confirmation",
        "observed_at",
    }
    if set(value) != expected_fields:
        raise ValueError("execution receipt has invalid fields")
    if value.get("schema_version") != EXECUTION_RECEIPT_SCHEMA_VERSION:
        raise ValueError("execution receipt schema is unsupported")
    payload = {
        "schema_version": EXECUTION_RECEIPT_SCHEMA_VERSION,
        "platform": _platform(value.get("platform")),
        "strategy_profile": _identifier(value.get("strategy_profile"), "strategy_profile"),
        "strategy_revision": _revision(value.get("strategy_revision")),
        "execution_mode": _choice(value.get("execution_mode"), frozenset({"paper", "live"}), "execution_mode"),
        "outcome": _choice(value.get("outcome"), EXECUTION_RECEIPT_OUTCOMES, "outcome"),
        "broker_confirmation": _choice(
            value.get("broker_confirmation"),
            EXECUTION_RECEIPT_BROKER_CONFIRMATIONS,
            "broker_confirmation",
        ),
        "observed_at": _timestamp(value.get("observed_at")),
    }
    _validate_outcome_confirmation(payload["outcome"], payload["broker_confirmation"])
    receipt_id = str(value.get("receipt_id") or "").strip()
    if not _RECEIPT_ID.fullmatch(receipt_id):
        raise ValueError("receipt_id must be a bounded receipt digest")
    expected_receipt_id = f"execution-receipt.{_receipt_digest(payload)[:32]}"
    if receipt_id != expected_receipt_id:
        raise ValueError("receipt_id does not match receipt content")
    return {"receipt_id": receipt_id, **payload}


def attach_execution_receipt(
    runtime_report: dict[str, Any],
    receipt: Mapping[str, Any] | object,
) -> dict[str, Any]:
    """Attach a receipt only when it matches an attested runtime report.

    The helper mutates and returns ``runtime_report`` for parity with
    :func:`finalize_runtime_report`.  It performs no storage, network or broker
    operation.  An existing different receipt is rejected to avoid accidental
    post-hoc replacement of a recorded execution fact.
    """

    if not isinstance(runtime_report, dict):
        raise ValueError("runtime_report must be a dictionary")
    normalized = validate_execution_receipt(receipt)
    _validate_runtime_report_binding(runtime_report, normalized)
    existing = runtime_report.get("execution_receipt")
    if existing is not None and existing != normalized:
        raise ValueError("runtime_report already has a different execution receipt")
    runtime_report["execution_receipt"] = normalized
    return runtime_report


def attach_runtime_execution_receipt(
    runtime_report: dict[str, Any],
    *,
    outcome: object,
    broker_confirmation: object | None = None,
    observed_at: datetime | str | None = None,
) -> dict[str, Any]:
    """Build and attach a receipt from an already-attested runtime report.

    This is deliberately only a binding helper: each platform remains
    responsible for deriving ``outcome`` from facts it has actually observed.
    It does not inspect an order payload, call a broker, or infer a fill from a
    submission. Reusing the report's attested identity prevents platform
    adapters from duplicating release-revision extraction inconsistently.
    """

    if not isinstance(runtime_report, dict):
        raise ValueError("runtime_report must be a dictionary")
    target = runtime_report.get("runtime_target")
    runtime_loaded = runtime_report.get("runtime_release_receipt")
    target_mapping = target if isinstance(target, Mapping) else {}
    strategy_release = runtime_loaded.get("strategy_release") if isinstance(runtime_loaded, Mapping) else None
    strategy_release_mapping = strategy_release if isinstance(strategy_release, Mapping) else {}
    receipt = build_execution_receipt(
        platform=runtime_report.get("platform"),
        strategy_profile=runtime_report.get("strategy_profile"),
        strategy_revision=strategy_release_mapping.get("strategy_revision"),
        execution_mode=target_mapping.get("execution_mode"),
        outcome=outcome,
        broker_confirmation=broker_confirmation,
        observed_at=observed_at,
    )
    return attach_execution_receipt(runtime_report, receipt)


def resolve_execution_receipt_fact(
    *,
    dry_run: bool,
    submission_attempted: bool = False,
    broker_acknowledged: bool = False,
    partially_filled: bool = False,
    filled: bool = False,
    reconciliation_required: bool = False,
    risk_blocked: bool = False,
    failed: bool = False,
) -> tuple[str, str]:
    """Translate explicit execution observations into one safe receipt fact.

    The caller must pass only facts it can evidence.  In particular, setting
    ``submission_attempted`` never produces an acknowledgement or fill.  A
    failed broker-facing operation stays ``not_observed`` until reconciliation
    establishes a more specific state.  The return values are accepted by
    :func:`attach_runtime_execution_receipt`.
    """

    if dry_run:
        return "no_action", "not_applicable"
    if reconciliation_required:
        return "reconciliation_required", "reconciliation_required"
    if filled:
        return "filled", "filled"
    if partially_filled:
        return "partially_filled", "partially_filled"
    if broker_acknowledged:
        return "broker_acknowledged", "acknowledged"
    if failed:
        return "failed", "not_observed" if submission_attempted else "not_applicable"
    if submission_attempted:
        return "submitted", "not_observed"
    if risk_blocked:
        return "risk_blocked", "not_applicable"
    return "no_action", "not_applicable"


def canonical_execution_receipt_json(value: Mapping[str, Any] | object) -> str:
    """Return the deterministic JSON form used to calculate a receipt digest."""

    normalized = validate_execution_receipt(value)
    return json.dumps(
        {key: value for key, value in normalized.items() if key != "receipt_id"},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )


def calculate_execution_receipt_sha256(value: Mapping[str, Any] | object) -> str:
    """Return a SHA-256 digest for a validated receipt's public fields."""

    return hashlib.sha256(canonical_execution_receipt_json(value).encode("utf-8")).hexdigest()


def _validate_runtime_report_binding(report: Mapping[str, Any], receipt: Mapping[str, str]) -> None:
    if _platform(report.get("platform")) != receipt["platform"]:
        raise ValueError("execution receipt platform does not match runtime_report")
    if _identifier(report.get("strategy_profile"), "runtime_report.strategy_profile") != receipt["strategy_profile"]:
        raise ValueError("execution receipt strategy_profile does not match runtime_report")
    target = report.get("runtime_target")
    if not isinstance(target, Mapping):
        raise ValueError("runtime_report.runtime_target is required for an execution receipt")
    if _choice(target.get("execution_mode"), frozenset({"paper", "live"}), "runtime_report.execution_mode") != receipt["execution_mode"]:
        raise ValueError("execution receipt execution_mode does not match runtime_report")
    runtime_loaded = report.get("runtime_release_receipt")
    if not isinstance(runtime_loaded, Mapping) or runtime_loaded.get("attestation_state") != "self_attested":
        raise ValueError("runtime_report must have a self-attested strategy release")
    strategy_release = runtime_loaded.get("strategy_release")
    if not isinstance(strategy_release, Mapping) or _revision(strategy_release.get("strategy_revision")) != receipt["strategy_revision"]:
        raise ValueError("execution receipt strategy_revision does not match runtime_report")


def _platform(value: object) -> str:
    normalized = _PLATFORM_ALIASES.get(str(value or "").strip().lower())
    if normalized is None:
        raise ValueError("platform is unsupported")
    return normalized


def _identifier(value: object, field: str) -> str:
    text = str(value or "").strip()
    if not _IDENTIFIER.fullmatch(text):
        raise ValueError(f"{field} must be a bounded identifier")
    return text


def _revision(value: object) -> str:
    text = str(value or "").strip()
    if not _REVISION.fullmatch(text):
        raise ValueError("strategy_revision must be a 40-character lowercase revision")
    return text


def _choice(value: object, allowed: frozenset[str], field: str) -> str:
    text = str(value or "").strip()
    if text not in allowed:
        raise ValueError(f"{field} is unsupported")
    return text


def _timestamp(value: datetime | str | None) -> str:
    if value is None:
        parsed = datetime.now(UTC)
    elif isinstance(value, datetime):
        parsed = value
    else:
        text = str(value).strip()
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("observed_at must be an RFC3339 UTC timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("observed_at must be timezone-aware")
    return parsed.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _validate_outcome_confirmation(outcome: str, confirmation: str) -> None:
    if confirmation not in _OUTCOME_CONFIRMATIONS[outcome]:
        raise ValueError("broker_confirmation does not match outcome")


def _receipt_digest(payload: Mapping[str, str]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()


__all__ = [
    "EXECUTION_RECEIPT_SCHEMA_VERSION",
    "EXECUTION_RECEIPT_OUTCOMES",
    "EXECUTION_RECEIPT_BROKER_CONFIRMATIONS",
    "attach_execution_receipt",
    "attach_runtime_execution_receipt",
    "build_execution_receipt",
    "calculate_execution_receipt_sha256",
    "canonical_execution_receipt_json",
    "resolve_execution_receipt_fact",
    "validate_execution_receipt",
]
