"""Explicit runtime-continuity contract for an already authorised live baseline.

This contract deliberately does *not* promote a research candidate.  It is a
separate, fail-closed record for the version that was already authorised to
run.  Candidate promotion remains an external control-plane responsibility.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import date
from typing import Any, Mapping


LIVE_CONTINUITY_STATES = frozenset(
    {
        "ACTIVE_LKG",
        "ACTIVE_REDUCED",
        "RECONCILE_ONLY",
        "RISK_REDUCTION_ONLY",
        "PAUSED",
        "ROLLBACK_LKG",
    }
)
BASELINE_KINDS = frozenset({"legacy_authorized", "release_attested"})
_BASELINE_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{2,127}$")
_SHA256_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")


def runtime_target_fingerprint(payload: Mapping[str, Any]) -> str:
    """Return the stable fingerprint of a target excluding continuity state.

    The state itself must be able to move from ``ACTIVE_LKG`` to a safe state
    without changing the frozen baseline it refers to.  All other target
    fields, including strategy release when present, are bound by the digest.
    """

    baseline = dict(payload)
    baseline.pop("live_continuity", None)
    serialized = json.dumps(
        baseline,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class LiveContinuity:
    """A frozen incumbent baseline and its current safe operating state."""

    state: str
    baseline_kind: str
    baseline_id: str
    baseline_target_sha256: str
    captured_at: str

    def __post_init__(self) -> None:
        state = str(self.state or "").strip().upper()
        if state not in LIVE_CONTINUITY_STATES:
            raise ValueError(
                "live_continuity.state must be one of "
                + ", ".join(sorted(LIVE_CONTINUITY_STATES))
            )
        object.__setattr__(self, "state", state)

        baseline_kind = str(self.baseline_kind or "").strip()
        if baseline_kind not in BASELINE_KINDS:
            raise ValueError(
                "live_continuity.baseline_kind must be one of "
                + ", ".join(sorted(BASELINE_KINDS))
            )
        object.__setattr__(self, "baseline_kind", baseline_kind)

        baseline_id = str(self.baseline_id or "").strip()
        if not _BASELINE_ID_PATTERN.fullmatch(baseline_id):
            raise ValueError("live_continuity.baseline_id has invalid characters")
        object.__setattr__(self, "baseline_id", baseline_id)

        digest = str(self.baseline_target_sha256 or "").strip().lower()
        if digest.startswith("sha256:"):
            digest = digest.removeprefix("sha256:")
        if not _SHA256_PATTERN.fullmatch(digest):
            raise ValueError("live_continuity.baseline_target_sha256 must be a SHA-256 digest")
        object.__setattr__(self, "baseline_target_sha256", digest)

        captured_at = str(self.captured_at or "").strip()
        try:
            captured_at = date.fromisoformat(captured_at).isoformat()
        except ValueError as exc:
            raise ValueError("live_continuity.captured_at must be an ISO-8601 date") from exc
        object.__setattr__(self, "captured_at", captured_at)

    @property
    def permits_standard_execution(self) -> bool:
        """Whether normal strategy orders are allowed for this state.

        Reduced-risk and risk-reduction modes require an explicitly wired,
        strategy-specific executor.  A generic runtime must fail closed rather
        than accidentally treat them as ordinary live operation.
        """

        return self.state in {"ACTIVE_LKG", "ROLLBACK_LKG"}

    def to_dict(self) -> dict[str, str]:
        return asdict(self)

    def assert_matches_target(self, payload: Mapping[str, Any]) -> None:
        actual = runtime_target_fingerprint(payload)
        if actual != self.baseline_target_sha256:
            raise ValueError(
                "live_continuity.baseline_target_sha256 does not match the runtime target"
            )


def build_live_continuity(value: LiveContinuity | Mapping[str, object]) -> LiveContinuity:
    if isinstance(value, LiveContinuity):
        return value
    if not isinstance(value, Mapping):
        raise ValueError("live_continuity must be an object")
    required_fields = (
        "state",
        "baseline_kind",
        "baseline_id",
        "baseline_target_sha256",
        "captured_at",
    )
    missing = tuple(field for field in required_fields if field not in value)
    if missing:
        raise ValueError("live_continuity is missing required fields: " + ", ".join(missing))
    unexpected = sorted(set(value) - set(required_fields))
    if unexpected:
        raise ValueError("live_continuity has unsupported fields: " + ", ".join(unexpected))
    return LiveContinuity(**{field: value[field] for field in required_fields})


__all__ = [
    "BASELINE_KINDS",
    "LIVE_CONTINUITY_STATES",
    "LiveContinuity",
    "build_live_continuity",
    "runtime_target_fingerprint",
]
