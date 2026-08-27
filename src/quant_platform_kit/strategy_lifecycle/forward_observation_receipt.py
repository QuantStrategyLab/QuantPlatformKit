"""Immutable, no-order receipts for candidate-bound forward observation.

The receipt binds one observed session to the exact frozen candidate policy
and the digests of its evidence dependencies.  It is intentionally local and
pure: persistence remains an adapter concern, and this module has no broker,
runtime-target, deployment, account, or market-data dependency.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
from hashlib import sha256
import json
import re
from typing import Any

from .forward_observation import ForwardObservationPolicy


FORWARD_OBSERVATION_RECEIPT_SCHEMA_VERSION = "forward_observation_receipt.v1"
FORWARD_OBSERVATION_DEPENDENCY_DIGESTS = frozenset(
    {
        "p1_manifest",
        "p2_config",
        "p3_evidence",
        "risk_policy",
        "strategy_release",
        "plugin_bundle",
    }
)
_FROZEN_CHAIN_DEPENDENCY_DIGESTS = frozenset(
    {"p2_config", "p3_evidence", "risk_policy", "strategy_release", "plugin_bundle"}
)
FORWARD_OBSERVATION_EVIDENCE_MODES = frozenset(
    {"shadow_decision", "simulated_replay", "broker_paper"}
)

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_TOP_LEVEL_FIELDS = frozenset(
    {
        "schema_version",
        "candidate_id",
        "policy_sha256",
        "observation_session",
        "observation_index",
        "previous_receipt_sha256",
        "dependency_digests",
        "evidence_modes",
        "receipt_sha256",
    }
)


class InvalidForwardObservationReceipt(ValueError):
    """Raised when a forward-observation receipt cannot be trusted."""


def _invalid(message: str) -> None:
    raise InvalidForwardObservationReceipt(message)


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
        raise InvalidForwardObservationReceipt(
            "receipt must contain only canonical JSON values"
        ) from exc


def canonical_forward_observation_receipt_bytes(value: Mapping[str, object]) -> bytes:
    """Return canonical bytes for a validated receipt, including its digest."""

    return _canonical_bytes(validate_forward_observation_receipt(value))


def forward_observation_receipt_sha256(value: Mapping[str, object]) -> str:
    """Return the deterministic SHA-256 identity of a validated receipt."""

    return str(validate_forward_observation_receipt(value)["receipt_sha256"])


def forward_observation_policy_sha256(policy: ForwardObservationPolicy) -> str:
    """Return the immutable identity of the full candidate observation policy."""

    return sha256(_canonical_bytes(policy.to_dict())).hexdigest()


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
        return date.fromisoformat(text).isoformat()
    except ValueError as exc:
        raise InvalidForwardObservationReceipt(
            f"{field} must be an ISO-8601 date"
        ) from exc


def _index(value: object, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        _invalid(f"{field} must be a positive integer")
    return value


def _dependency_digests(value: object) -> dict[str, str]:
    if not isinstance(value, Mapping) or set(value) != FORWARD_OBSERVATION_DEPENDENCY_DIGESTS:
        _invalid("dependency_digests must contain the complete closed digest set")
    return {
        key: _digest(value[key], f"dependency_digests.{key}")
        for key in sorted(FORWARD_OBSERVATION_DEPENDENCY_DIGESTS)
    }


def _evidence_modes(value: object) -> tuple[str, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _invalid("evidence_modes must be an array")
    modes = tuple(_text(item, "evidence_modes").lower() for item in value)
    paper_modes = {"simulated_replay", "broker_paper"} & set(modes)
    if (
        len(modes) not in {1, 2}
        or len(set(modes)) != len(modes)
        or set(modes) - FORWARD_OBSERVATION_EVIDENCE_MODES
        or "shadow_decision" not in modes
        or len(paper_modes) > 1
    ):
        _invalid(
            "evidence_modes must contain shadow_decision and at most one paper mode"
        )
    return modes


def _receipt_core(value: Mapping[str, object]) -> dict[str, object]:
    return {key: value[key] for key in sorted(_TOP_LEVEL_FIELDS - {"receipt_sha256"})}


def build_forward_observation_receipt(
    *,
    policy: ForwardObservationPolicy,
    observation_session: str,
    observation_index: int,
    dependency_digests: Mapping[str, str],
    evidence_modes: Sequence[str],
    previous_receipt: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Build one candidate-bound receipt and append it to a verified chain.

    The caller supplies digest identities only.  Raw prices, account IDs,
    orders, credentials, and execution instructions are intentionally absent.
    """

    session = _session(observation_session, "observation_session")
    index = _index(observation_index, "observation_index")
    policy_digest = forward_observation_policy_sha256(policy)
    normalized_dependencies = _dependency_digests(dependency_digests)
    normalized_modes = _evidence_modes(evidence_modes)
    if normalized_modes != tuple(policy.non_live_evidence_modes):
        _invalid("evidence_modes must exactly match policy.non_live_evidence_modes")
    _validate_policy_window(policy, session, index)

    if previous_receipt is None:
        if index != 1:
            _invalid("first receipt must have observation_index=1")
        previous_digest: str | None = None
    else:
        previous = validate_forward_observation_receipt(previous_receipt, policy=policy)
        previous_index = _index(previous["observation_index"], "previous.observation_index")
        if index != previous_index + 1:
            _invalid("observation_index must increment by one from the previous receipt")
        previous_session = _session(previous["observation_session"], "previous.observation_session")
        if session <= previous_session:
            _invalid("observation_session must advance from the previous receipt")
        previous_digest = _digest(previous["receipt_sha256"], "previous.receipt_sha256")

    receipt: dict[str, object] = {
        "schema_version": FORWARD_OBSERVATION_RECEIPT_SCHEMA_VERSION,
        "candidate_id": policy.candidate_id,
        "policy_sha256": policy_digest,
        "observation_session": session,
        "observation_index": index,
        "previous_receipt_sha256": previous_digest,
        "dependency_digests": normalized_dependencies,
        "evidence_modes": list(normalized_modes),
        "receipt_sha256": "",
    }
    receipt["receipt_sha256"] = sha256(_canonical_bytes(_receipt_core(receipt))).hexdigest()
    return validate_forward_observation_receipt(receipt, policy=policy, previous_receipt=previous_receipt)


def validate_forward_observation_receipt(
    value: Mapping[str, object],
    *,
    policy: ForwardObservationPolicy | None = None,
    previous_receipt: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Validate a receipt and, when provided, its exact policy and predecessor."""

    if not isinstance(value, Mapping) or set(value) != _TOP_LEVEL_FIELDS:
        _invalid("receipt must be a closed object")
    if value.get("schema_version") != FORWARD_OBSERVATION_RECEIPT_SCHEMA_VERSION:
        _invalid(
            f"schema_version must equal {FORWARD_OBSERVATION_RECEIPT_SCHEMA_VERSION}"
        )
    candidate_id = _text(value.get("candidate_id"), "candidate_id")
    policy_digest = _digest(value.get("policy_sha256"), "policy_sha256")
    session = _session(value.get("observation_session"), "observation_session")
    index = _index(value.get("observation_index"), "observation_index")
    previous_digest = value.get("previous_receipt_sha256")
    if previous_digest is not None:
        previous_digest = _digest(previous_digest, "previous_receipt_sha256")
    elif index != 1:
        _invalid("receipt after the first must include previous_receipt_sha256")
    dependencies = _dependency_digests(value.get("dependency_digests"))
    modes = _evidence_modes(value.get("evidence_modes"))
    claimed_digest = _digest(value.get("receipt_sha256"), "receipt_sha256")
    if claimed_digest != sha256(_canonical_bytes(_receipt_core(value))).hexdigest():
        _invalid("receipt_sha256 does not match canonical receipt content")

    if policy is not None:
        if candidate_id != policy.candidate_id:
            _invalid("candidate_id does not match policy")
        if policy_digest != forward_observation_policy_sha256(policy):
            _invalid("policy_sha256 does not match policy")
        if modes != tuple(policy.non_live_evidence_modes):
            _invalid("evidence_modes do not match policy")
        _validate_policy_window(policy, session, index)

    if previous_receipt is not None:
        previous = validate_forward_observation_receipt(previous_receipt, policy=policy)
        if previous_digest != previous["receipt_sha256"]:
            _invalid("previous_receipt_sha256 does not match the predecessor")
        if index != int(previous["observation_index"]) + 1:
            _invalid("observation_index does not increment from the predecessor")
        if session <= str(previous["observation_session"]):
            _invalid("observation_session does not advance from the predecessor")
        if candidate_id != previous["candidate_id"] or policy_digest != previous["policy_sha256"]:
            _invalid("candidate or policy identity changed within the receipt chain")
        previous_dependencies = _dependency_digests(previous["dependency_digests"])
        if any(
            dependencies[field] != previous_dependencies[field]
            for field in _FROZEN_CHAIN_DEPENDENCY_DIGESTS
        ):
            _invalid("frozen dependency digest changed within the receipt chain")

    return {
        "schema_version": FORWARD_OBSERVATION_RECEIPT_SCHEMA_VERSION,
        "candidate_id": candidate_id,
        "policy_sha256": policy_digest,
        "observation_session": session,
        "observation_index": index,
        "previous_receipt_sha256": previous_digest,
        "dependency_digests": dependencies,
        "evidence_modes": list(modes),
        "receipt_sha256": claimed_digest,
    }


def _validate_policy_window(
    policy: ForwardObservationPolicy, session: str, index: int
) -> None:
    if index > policy.required_trading_sessions:
        _invalid("observation_index exceeds the frozen policy window")
    if policy.observation_window_type == "fixed":
        start = policy.observation_start_session
        assert start is not None
        if session < start:
            _invalid("observation_session precedes the fixed policy window")


__all__ = [
    "FORWARD_OBSERVATION_DEPENDENCY_DIGESTS",
    "FORWARD_OBSERVATION_EVIDENCE_MODES",
    "FORWARD_OBSERVATION_RECEIPT_SCHEMA_VERSION",
    "InvalidForwardObservationReceipt",
    "build_forward_observation_receipt",
    "canonical_forward_observation_receipt_bytes",
    "forward_observation_policy_sha256",
    "forward_observation_receipt_sha256",
    "validate_forward_observation_receipt",
]
