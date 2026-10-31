"""Non-authoritative lineage for observed inputs and actual decision targets."""
from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import asdict
from datetime import date, datetime, timezone
from typing import Any

from .execution_receipts import (
    EXECUTION_RECEIPT_BROKER_CONFIRMATIONS, EXECUTION_RECEIPT_OUTCOMES,
    _validate_outcome_confirmation, calculate_execution_receipt_sha256, validate_execution_receipt,
)
from .strategy_contracts import StrategyDecision

_SCHEMA = "qsl_decision_consumption_receipt.v1"
_SHA = re.compile(r"[0-9a-f]{64}")
_REV = re.compile(r"[0-9a-f]{40}")


def _digest(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _optional_hash(value: object, pattern: re.Pattern, name: str) -> str | None:
    if value is None:
        return None
    if type(value) is not str or pattern.fullmatch(value) is None:
        raise ValueError(f"invalid {name}")
    return value


def _time(value: object) -> str:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("invalid timestamp") from exc
    else:
        raise ValueError("invalid timestamp")
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timestamp requires timezone")
    return parsed.astimezone(timezone.utc).isoformat()


def _target_hash(decision: StrategyDecision | None) -> str | None:
    if decision is None:
        return None
    if type(decision) is not StrategyDecision:
        raise ValueError("target must be an actual StrategyDecision")
    positions = [asdict(position) for position in decision.positions]
    budgets = [asdict(budget) for budget in decision.budgets]
    if any(type(item.get("symbol")) is not str or not item["symbol"] for item in positions):
        raise ValueError("invalid target symbol")
    if len({item["symbol"] for item in positions}) != len(positions):
        raise ValueError("duplicate target symbol")
    return _digest({"positions": positions, "budgets": budgets})


def _observations(value: object, decision_at: str) -> list[dict[str, Any]]:
    if not isinstance(value, (tuple, list)):
        raise ValueError("observations must be a list")
    result = []
    references = set()
    for item in value:
        required = {"reference", "status", "artifact_sha256", "digest_status", "availability_at", "authority"}
        optional = {"consumer", "observed_at", "consumer_payload_sha256"}
        if not isinstance(item, Mapping) or not required <= set(item) or set(item) - required - optional:
            raise ValueError("invalid observation fields")
        reference, status = item["reference"], item["status"]
        if type(reference) is not str or not reference or reference in references:
            raise ValueError("invalid or duplicate observation reference")
        references.add(reference)
        digest = _optional_hash(item["artifact_sha256"], _SHA, "artifact_sha256")
        consumer_digest = _optional_hash(item.get("consumer_payload_sha256"), _SHA, "consumer_payload_sha256")
        consumer = item.get("consumer")
        if consumer is not None and (type(consumer) is not str or not consumer.strip() or consumer != consumer.strip()):
            raise ValueError("invalid observation consumer")
        observed_at = _time(item["observed_at"]) if item.get("observed_at") is not None else None
        digest_status, authority = item["digest_status"], item["authority"]
        if status == "observed":
            if digest is None or digest_status not in {"verified", "unverified"}:
                raise ValueError("observed artifact requires digest status")
        elif status in {"missing", "unavailable"}:
            if (digest is not None or consumer_digest is not None or observed_at is not None or digest_status != "unknown"
                    or item["availability_at"] is not None or authority != "unknown"):
                raise ValueError("missing observation cannot assert facts")
        else:
            raise ValueError("invalid observation status")
        if authority not in {"authorized", "denied", "unknown"}:
            raise ValueError("invalid observation authority")
        available = _time(item["availability_at"]) if item["availability_at"] is not None else None
        availability_status = ("unknown" if available is None else
            "available_by_decision" if datetime.fromisoformat(available) <= datetime.fromisoformat(decision_at)
            else "after_decision")
        read_status = ("unknown" if observed_at is None else
            "read_by_decision" if datetime.fromisoformat(observed_at) <= datetime.fromisoformat(decision_at)
            else "after_decision")
        result.append({"reference": reference, "status": status, "artifact_sha256": digest,
            "digest_status": digest_status, "availability_at": available,
            "availability_status": availability_status, "authority": authority, "consumer": consumer,
            "observed_at": observed_at, "read_status": read_status, "consumer_payload_sha256": consumer_digest})
    return result


def build_decision_consumption_receipt(*, run_id: str, strategy_profile: str, strategy_revision: str | None,
    config_sha256: str | None, decision_at: datetime | str, pre_risk_decision: StrategyDecision | None,
    post_risk_decision: StrategyDecision | None, observations: Sequence[Mapping[str, Any]],
    signal_session: str | None = None, intent_sha256: str | None = None,
    execution_receipt: Mapping[str, Any] | None = None) -> dict[str, Any]:
    if any(type(x) is not str or not x.strip() or x != x.strip() for x in (run_id, strategy_profile)):
        raise ValueError("run_id and strategy_profile are required")
    revision = _optional_hash(strategy_revision, _REV, "strategy_revision")
    config = _optional_hash(config_sha256, _SHA, "config_sha256")
    instant = _time(decision_at)
    if signal_session is not None:
        try:
            if type(signal_session) is not str or date.fromisoformat(signal_session).isoformat() != signal_session:
                raise ValueError("invalid signal_session")
        except ValueError as exc:
            raise ValueError("invalid signal_session") from exc
    execution = validate_execution_receipt(execution_receipt) if execution_receipt is not None else None
    if execution and (execution["strategy_profile"] != strategy_profile
                      or (revision is not None and execution["strategy_revision"] != revision)):
        raise ValueError("execution receipt identity mismatch")
    payload = {"schema_version": _SCHEMA, "run_id": run_id, "strategy_profile": strategy_profile,
        "strategy_revision": revision, "config_sha256": config, "decision_at": instant, "signal_session": signal_session,
        "signal_session_status": ("unknown" if signal_session is None else "date_not_future"
            if date.fromisoformat(signal_session) <= datetime.fromisoformat(instant).date() else "after_decision"),
        "pre_risk_target_sha256": _target_hash(pre_risk_decision), "post_risk_target_sha256": _target_hash(post_risk_decision),
        "observations": _observations(observations, instant), "intent_sha256": _optional_hash(intent_sha256, _SHA, "intent_sha256"),
        "execution_receipt_sha256": calculate_execution_receipt_sha256(execution) if execution else None,
        "execution_outcome": execution["outcome"] if execution else None,
        "broker_confirmation": execution["broker_confirmation"] if execution else None}
    return {**payload, "receipt_sha256": _digest(payload)}


def validate_decision_consumption_receipt(value: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError("receipt must be an object")
    fields = {"schema_version", "run_id", "strategy_profile", "strategy_revision", "config_sha256", "decision_at", "signal_session", "signal_session_status",
        "pre_risk_target_sha256", "post_risk_target_sha256", "observations", "intent_sha256",
        "execution_receipt_sha256", "execution_outcome", "broker_confirmation", "receipt_sha256"}
    if set(value) != fields or value["schema_version"] != _SCHEMA:
        raise ValueError("invalid receipt fields")
    if any(type(value[key]) is not str or not value[key].strip() or value[key] != value[key].strip()
           for key in ("run_id", "strategy_profile")):
        raise ValueError("invalid receipt identity")
    if _time(value["decision_at"]) != value["decision_at"]:
        raise ValueError("noncanonical decision time")
    if value["signal_session"] is not None:
        try:
            if type(value["signal_session"]) is not str or date.fromisoformat(value["signal_session"]).isoformat() != value["signal_session"]:
                raise ValueError("invalid signal session")
        except ValueError as exc:
            raise ValueError("invalid signal session") from exc
    expected_session_status = ("unknown" if value["signal_session"] is None else "date_not_future"
        if date.fromisoformat(value["signal_session"]) <= datetime.fromisoformat(value["decision_at"]).date()
        else "after_decision")
    if value["signal_session_status"] != expected_session_status:
        raise ValueError("signal session status mismatch")
    payload = {key: value[key] for key in value if key != "receipt_sha256"}
    if _digest(payload) != value["receipt_sha256"]:
        raise ValueError("receipt digest mismatch")
    for key in ("pre_risk_target_sha256", "post_risk_target_sha256", "intent_sha256", "execution_receipt_sha256"):
        _optional_hash(value[key], _SHA, key)
    _optional_hash(value["strategy_revision"], _REV, "strategy_revision")
    _optional_hash(value["config_sha256"], _SHA, "config_sha256")
    if not isinstance(value["observations"], list) or any(not isinstance(row, Mapping) for row in value["observations"]):
        raise ValueError("invalid observations")
    observations = [{k: v for k, v in row.items() if k not in {"availability_status", "read_status"}}
                    for row in value["observations"]]
    if _observations(observations, _time(value["decision_at"])) != value["observations"]:
        raise ValueError("observation status mismatch")
    if (value["execution_receipt_sha256"] is None) != (value["execution_outcome"] is None and value["broker_confirmation"] is None):
        raise ValueError("incomplete execution binding")
    if value["execution_receipt_sha256"] is not None:
        if value["execution_outcome"] not in EXECUTION_RECEIPT_OUTCOMES or value["broker_confirmation"] not in EXECUTION_RECEIPT_BROKER_CONFIRMATIONS:
            raise ValueError("invalid execution outcome")
        _validate_outcome_confirmation(value["execution_outcome"], value["broker_confirmation"])
    return dict(value)


def attach_decision_consumption_receipt(report: dict[str, Any], receipt: Mapping[str, Any], *,
    post_risk_decision: StrategyDecision | None = None) -> dict[str, Any]:
    normalized = validate_decision_consumption_receipt(receipt)
    if report.get("run_id") != normalized["run_id"] or report.get("strategy_profile") != normalized["strategy_profile"]:
        raise ValueError("receipt run or strategy mismatch")
    if report.get("decision_at") is not None and _time(report["decision_at"]) != normalized["decision_at"]:
        raise ValueError("receipt decision clock mismatch")
    loaded = report.get("runtime_release_receipt") or {}
    release = loaded.get("strategy_release") or {} if isinstance(loaded, Mapping) else {}
    if normalized["strategy_revision"] is not None and release.get("strategy_revision") != normalized["strategy_revision"]:
        raise ValueError("receipt strategy revision mismatch")
    if (normalized["config_sha256"] is not None and release.get("config_sha256") is not None
            and release.get("config_sha256") != normalized["config_sha256"]):
        raise ValueError("receipt configuration mismatch")
    if post_risk_decision is not None and _target_hash(post_risk_decision) != normalized["post_risk_target_sha256"]:
        raise ValueError("receipt post-risk target mismatch")
    execution = report.get("execution_receipt")
    if normalized["execution_receipt_sha256"] is not None:
        if execution is None or calculate_execution_receipt_sha256(execution) != normalized["execution_receipt_sha256"]:
            raise ValueError("receipt execution binding mismatch")
    existing = report.get("decision_consumption_receipt")
    if existing is not None and existing != normalized:
        raise ValueError("report already has a different decision receipt")
    report["decision_consumption_receipt"] = normalized
    return report


def attach_decision_execution_link(report: dict[str, Any], receipt: Mapping[str, Any], *,
    order_records: Sequence[Mapping[str, Any]] | None = None,
    fill_records: Sequence[Mapping[str, Any]] | None = None) -> dict[str, Any]:
    """Link an immutable decision receipt to separately observed execution facts.

    Callers must supply actual report records; ``None`` means not observed and
    an empty sequence means an observed empty record set. The v1 execution
    receipt itself has no run identifier, so the link is partial provenance.
    """
    normalized = validate_decision_consumption_receipt(receipt)
    if report.get("decision_consumption_receipt") != normalized:
        raise ValueError("decision receipt must already be attached to report")
    attach_decision_consumption_receipt(report, normalized)
    execution = validate_execution_receipt(report.get("execution_receipt"))
    if (execution["strategy_profile"] != normalized["strategy_profile"]
            or (normalized["strategy_revision"] is not None
                and execution["strategy_revision"] != normalized["strategy_revision"])):
        raise ValueError("link execution identity mismatch")
    def records_digest(records):
        if records is None:
            return None
        if not isinstance(records, (list, tuple)) or any(not isinstance(row, Mapping) for row in records):
            raise ValueError("execution records must be mappings")
        return _digest([dict(row) for row in records])
    payload = {"schema_version": "qsl_decision_execution_link.v1", "run_id": normalized["run_id"],
        "strategy_profile": normalized["strategy_profile"], "decision_receipt_sha256": normalized["receipt_sha256"],
        "execution_receipt_sha256": calculate_execution_receipt_sha256(execution),
        "order_records_sha256": records_digest(order_records), "fill_records_sha256": records_digest(fill_records),
        "provenance_status": "partial"}
    link = {**payload, "link_sha256": _digest(payload)}
    existing = report.get("decision_execution_link")
    if existing is not None and existing != link:
        raise ValueError("report already has a different decision execution link")
    report["decision_execution_link"] = link
    return report
