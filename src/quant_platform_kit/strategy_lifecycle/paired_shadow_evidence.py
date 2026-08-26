"""Immutable evidence for a baseline/candidate paired-shadow observation.

This module is deliberately a contract, not a simulator.  An observation
adapter supplies the baseline and candidate outputs it obtained from the same
timestamped input snapshot; this module only makes that claim explicit,
candidate-bound, append-only, and independently verifiable.  It never
calculates signals, positions, costs, or returns, and cannot create an order
or grant live authority.

``forward_observation_receipt.v1`` remains the source of truth for the P4
window.  A paired-shadow artifact is its companion: it binds one receipt to
one same-input baseline/candidate comparison without changing the established
receipt schema.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from typing import Any

from .forward_observation import ForwardObservationPolicy
from .forward_observation_receipt import (
    forward_observation_receipt_sha256,
    validate_forward_observation_receipt,
)


PAIRED_SHADOW_EVIDENCE_SCHEMA_VERSION = "paired_shadow_evidence.v1"
PAIRED_SHADOW_EVIDENCE_KIND = "paired_shadow"
PAIRED_SHADOW_LEG_FIELDS = frozenset(
    {"signal", "hypothetical_order", "position", "cost", "return"}
)

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_TOP_LEVEL_FIELDS = frozenset(
    {
        "schema_version",
        "evidence_kind",
        "candidate_id",
        "baseline_id",
        "observation_session",
        "observation_index",
        "observed_at",
        "input_snapshot_sha256",
        "forward_observation_receipt_sha256",
        "previous_paired_shadow_evidence_sha256",
        "candidate",
        "baseline",
        "no_order",
        "live_authority_granted",
        "paired_shadow_evidence_sha256",
    }
)


class InvalidPairedShadowEvidence(ValueError):
    """Raised when a paired-shadow evidence artifact cannot be trusted."""


def _invalid(message: str) -> None:
    raise InvalidPairedShadowEvidence(message)


def _canonical_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise InvalidPairedShadowEvidence(
            "evidence must contain only canonical JSON values"
        ) from exc


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        _invalid(f"{field} must be a non-empty string")
    if any(ord(character) < 0x20 or ord(character) == 0x7F for character in value):
        _invalid(f"{field} contains a control character")
    return value.strip()


def _digest(value: object, field: str) -> str:
    text = _text(value, field)
    if _SHA256.fullmatch(text) is None:
        _invalid(f"{field} must be a lowercase SHA-256 digest")
    return text


def _session(value: object, field: str) -> str:
    text = _text(value, field)
    try:
        return datetime.fromisoformat(f"{text}T00:00:00+00:00").date().isoformat()
    except ValueError as exc:
        raise InvalidPairedShadowEvidence(
            f"{field} must be an ISO-8601 date"
        ) from exc


def _index(value: object, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        _invalid(f"{field} must be a positive integer")
    return value


def _observed_at(value: object) -> str:
    text = _text(value, "observed_at")
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise InvalidPairedShadowEvidence(
            "observed_at must be an ISO-8601 timestamp with a timezone"
        ) from exc
    if parsed.tzinfo is None:
        _invalid("observed_at must be an ISO-8601 timestamp with a timezone")
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _json_object(value: object, field: str) -> dict[str, Any]:
    """Normalize one leg field without interpreting its strategy-specific values."""

    if not isinstance(value, Mapping):
        _invalid(f"{field} must be a JSON object")
    try:
        normalized = json.loads(_canonical_bytes(value))
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive only
        raise InvalidPairedShadowEvidence(
            f"{field} must be a JSON object"
        ) from exc
    if not isinstance(normalized, dict):  # pragma: no cover - guarded by Mapping
        _invalid(f"{field} must be a JSON object")
    return normalized


def _leg(value: object, field: str) -> dict[str, dict[str, Any]]:
    if not isinstance(value, Mapping) or set(value) != PAIRED_SHADOW_LEG_FIELDS:
        _invalid(
            f"{field} must contain signal, hypothetical_order, position, cost, and return"
        )
    return {
        key: _json_object(value[key], f"{field}.{key}")
        for key in sorted(PAIRED_SHADOW_LEG_FIELDS)
    }


def _core(value: Mapping[str, object]) -> dict[str, object]:
    return {
        key: value[key]
        for key in sorted(_TOP_LEVEL_FIELDS - {"paired_shadow_evidence_sha256"})
    }


def build_paired_shadow_evidence(
    *,
    policy: ForwardObservationPolicy,
    forward_observation_receipt: Mapping[str, object],
    baseline_id: str,
    observed_at: str,
    input_snapshot_sha256: str,
    candidate: Mapping[str, object],
    baseline: Mapping[str, object],
    previous_evidence: Mapping[str, object] | None = None,
    previous_forward_observation_receipt: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Build one no-order paired-shadow companion artifact.

    Both legs receive one ``observed_at`` and one
    ``input_snapshot_sha256``.  The adapter, rather than this pure module,
    owns the market-data snapshot and strategy calculations.  Supplying a
    prior artifact requires the matching prior forward-observation receipt so
    the two append-only chains advance together.
    """

    if previous_evidence is None and previous_forward_observation_receipt is not None:
        _invalid("previous forward-observation receipt requires previous evidence")
    if previous_evidence is not None and previous_forward_observation_receipt is None:
        _invalid("previous evidence requires previous forward-observation receipt")

    forward = validate_forward_observation_receipt(
        forward_observation_receipt,
        policy=policy,
        previous_receipt=previous_forward_observation_receipt,
    )
    normalized_baseline_id = _text(baseline_id, "baseline_id")
    if normalized_baseline_id == policy.candidate_id:
        _invalid("baseline_id must differ from candidate_id")

    evidence: dict[str, object] = {
        "schema_version": PAIRED_SHADOW_EVIDENCE_SCHEMA_VERSION,
        "evidence_kind": PAIRED_SHADOW_EVIDENCE_KIND,
        "candidate_id": policy.candidate_id,
        "baseline_id": normalized_baseline_id,
        "observation_session": forward["observation_session"],
        "observation_index": forward["observation_index"],
        "observed_at": _observed_at(observed_at),
        "input_snapshot_sha256": _digest(
            input_snapshot_sha256, "input_snapshot_sha256"
        ),
        "forward_observation_receipt_sha256": forward["receipt_sha256"],
        "previous_paired_shadow_evidence_sha256": (
            None
            if previous_evidence is None
            else _digest(
                previous_evidence.get("paired_shadow_evidence_sha256"),
                "previous_evidence.paired_shadow_evidence_sha256",
            )
        ),
        "candidate": _leg(candidate, "candidate"),
        "baseline": _leg(baseline, "baseline"),
        "no_order": True,
        "live_authority_granted": False,
        "paired_shadow_evidence_sha256": "",
    }
    evidence["paired_shadow_evidence_sha256"] = sha256(
        _canonical_bytes(_core(evidence))
    ).hexdigest()
    return validate_paired_shadow_evidence(
        evidence,
        policy=policy,
        forward_observation_receipt=forward_observation_receipt,
        previous_evidence=previous_evidence,
        previous_forward_observation_receipt=previous_forward_observation_receipt,
    )


def validate_paired_shadow_evidence(
    value: Mapping[str, object],
    *,
    policy: ForwardObservationPolicy | None = None,
    forward_observation_receipt: Mapping[str, object] | None = None,
    previous_evidence: Mapping[str, object] | None = None,
    previous_forward_observation_receipt: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Validate integrity and, when supplied, bind the evidence to P4 receipts.

    A standalone validation establishes only the artifact's closed schema and
    digest.  A trusting consumer must provide its frozen policy and matching
    forward-observation receipt; a continuous consumer also provides both
    predecessors.  This prevents a recent production performance snapshot
    from being re-labelled as paired shadow evidence.
    """

    if not isinstance(value, Mapping) or set(value) != _TOP_LEVEL_FIELDS:
        _invalid("evidence must be a closed paired-shadow object")
    if value.get("schema_version") != PAIRED_SHADOW_EVIDENCE_SCHEMA_VERSION:
        _invalid(
            f"schema_version must equal {PAIRED_SHADOW_EVIDENCE_SCHEMA_VERSION}"
        )
    if value.get("evidence_kind") != PAIRED_SHADOW_EVIDENCE_KIND:
        _invalid(f"evidence_kind must equal {PAIRED_SHADOW_EVIDENCE_KIND}")

    candidate_id = _text(value.get("candidate_id"), "candidate_id")
    baseline_id = _text(value.get("baseline_id"), "baseline_id")
    if baseline_id == candidate_id:
        _invalid("baseline_id must differ from candidate_id")
    session = _session(value.get("observation_session"), "observation_session")
    index = _index(value.get("observation_index"), "observation_index")
    timestamp = _observed_at(value.get("observed_at"))
    input_digest = _digest(value.get("input_snapshot_sha256"), "input_snapshot_sha256")
    forward_digest = _digest(
        value.get("forward_observation_receipt_sha256"),
        "forward_observation_receipt_sha256",
    )
    previous_digest = value.get("previous_paired_shadow_evidence_sha256")
    if previous_digest is not None:
        previous_digest = _digest(
            previous_digest, "previous_paired_shadow_evidence_sha256"
        )
    elif index != 1:
        _invalid("evidence after the first must include previous_paired_shadow_evidence_sha256")
    candidate = _leg(value.get("candidate"), "candidate")
    baseline = _leg(value.get("baseline"), "baseline")
    if value.get("no_order") is not True:
        _invalid("no_order must be true")
    if value.get("live_authority_granted") is not False:
        _invalid("live_authority_granted must be false")
    claimed_digest = _digest(
        value.get("paired_shadow_evidence_sha256"), "paired_shadow_evidence_sha256"
    )
    if claimed_digest != sha256(_canonical_bytes(_core(value))).hexdigest():
        _invalid("paired_shadow_evidence_sha256 does not match canonical evidence content")

    if policy is not None and candidate_id != policy.candidate_id:
        _invalid("candidate_id does not match policy")
    if forward_observation_receipt is not None:
        forward = validate_forward_observation_receipt(
            forward_observation_receipt,
            policy=policy,
            previous_receipt=previous_forward_observation_receipt,
        )
        if forward_observation_receipt_sha256(forward) != forward_digest:
            _invalid("forward_observation_receipt_sha256 does not match receipt")
        if candidate_id != forward["candidate_id"]:
            _invalid("candidate_id does not match forward-observation receipt")
        if session != forward["observation_session"] or index != forward["observation_index"]:
            _invalid("observation session/index does not match forward-observation receipt")
    elif previous_forward_observation_receipt is not None:
        _invalid("previous forward-observation receipt requires current receipt")

    if previous_evidence is not None:
        if forward_observation_receipt is None or previous_forward_observation_receipt is None:
            _invalid("continuous evidence validation requires both forward-observation receipts")
        previous = validate_paired_shadow_evidence(
            previous_evidence,
            policy=policy,
            forward_observation_receipt=previous_forward_observation_receipt,
        )
        if previous_digest != previous["paired_shadow_evidence_sha256"]:
            _invalid("previous_paired_shadow_evidence_sha256 does not match predecessor")
        if index != int(previous["observation_index"]) + 1:
            _invalid("observation_index does not increment from the predecessor")
        if session <= str(previous["observation_session"]):
            _invalid("observation_session does not advance from the predecessor")
        if timestamp <= str(previous["observed_at"]):
            _invalid("observed_at does not advance from the predecessor")
        if candidate_id != previous["candidate_id"] or baseline_id != previous["baseline_id"]:
            _invalid("candidate or baseline identity changed within the evidence chain")
        previous_forward_digest = previous["forward_observation_receipt_sha256"]
        forward_previous_digest = previous_forward_observation_receipt.get(
            "receipt_sha256"
        )
        if previous_forward_digest != forward_previous_digest:
            _invalid("previous evidence is not bound to its forward-observation receipt")
        current_forward_previous_digest = forward_observation_receipt.get(
            "previous_receipt_sha256"
        )
        if current_forward_previous_digest != previous_forward_digest:
            _invalid("forward-observation receipt chain does not match evidence chain")
    elif previous_digest is not None:
        _invalid("previous paired-shadow digest requires predecessor evidence")

    return {
        "schema_version": PAIRED_SHADOW_EVIDENCE_SCHEMA_VERSION,
        "evidence_kind": PAIRED_SHADOW_EVIDENCE_KIND,
        "candidate_id": candidate_id,
        "baseline_id": baseline_id,
        "observation_session": session,
        "observation_index": index,
        "observed_at": timestamp,
        "input_snapshot_sha256": input_digest,
        "forward_observation_receipt_sha256": forward_digest,
        "previous_paired_shadow_evidence_sha256": previous_digest,
        "candidate": candidate,
        "baseline": baseline,
        "no_order": True,
        "live_authority_granted": False,
        "paired_shadow_evidence_sha256": claimed_digest,
    }


def canonical_paired_shadow_evidence_bytes(value: Mapping[str, object]) -> bytes:
    """Return canonical bytes for a schema-valid paired-shadow artifact."""

    return _canonical_bytes(validate_paired_shadow_evidence(value))


def paired_shadow_evidence_sha256(value: Mapping[str, object]) -> str:
    """Return the deterministic SHA-256 identity of a valid artifact."""

    return str(
        validate_paired_shadow_evidence(value)["paired_shadow_evidence_sha256"]
    )


__all__ = [
    "PAIRED_SHADOW_EVIDENCE_KIND",
    "PAIRED_SHADOW_EVIDENCE_SCHEMA_VERSION",
    "PAIRED_SHADOW_LEG_FIELDS",
    "InvalidPairedShadowEvidence",
    "build_paired_shadow_evidence",
    "canonical_paired_shadow_evidence_bytes",
    "paired_shadow_evidence_sha256",
    "validate_paired_shadow_evidence",
]
