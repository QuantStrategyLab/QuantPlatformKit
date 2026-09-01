"""Safe, immutable bindings for strategy decision-data artifacts.

Decision data is deliberately distinct from execution-time quotes.  A binding
contains only stable identifiers and evidence hashes, never provider URLs,
credentials, account identifiers, or market-data payloads.  This lets a
runtime prove which frozen input it used without exposing private operational
details through a control plane or an execution report.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from hashlib import sha256
import json
import re
from typing import Any, Mapping


DECISION_DATA_BINDING_SCHEMA_VERSION = "qpk.decision_data_binding.v1"

DECISION_DATA_MODE_LEGACY_RUNTIME_FETCH = "legacy_runtime_fetch"
DECISION_DATA_MODE_ARTIFACT_OPTIONAL = "artifact_optional"
DECISION_DATA_MODE_ARTIFACT_REQUIRED = "artifact_required"

DECISION_DATA_ASSURANCE_LEGACY = "LEGACY"
DECISION_DATA_ASSURANCE_VERIFIED = "VERIFIED"
DECISION_DATA_ASSURANCE_DEGRADED = "DEGRADED"
DECISION_DATA_ASSURANCE_PARKED = "PARKED"

_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{1,127}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_MODES = frozenset(
    {
        DECISION_DATA_MODE_LEGACY_RUNTIME_FETCH,
        DECISION_DATA_MODE_ARTIFACT_OPTIONAL,
        DECISION_DATA_MODE_ARTIFACT_REQUIRED,
    }
)
_ASSURANCE_STATUSES = frozenset(
    {
        DECISION_DATA_ASSURANCE_LEGACY,
        DECISION_DATA_ASSURANCE_VERIFIED,
        DECISION_DATA_ASSURANCE_DEGRADED,
        DECISION_DATA_ASSURANCE_PARKED,
    }
)


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")


def _require_identifier(value: object, *, field_name: str) -> str:
    text = str(value or "").strip()
    if not _IDENTIFIER_RE.fullmatch(text):
        raise ValueError(f"{field_name} must be a stable identifier")
    return text


def _require_date(value: object, *, field_name: str) -> str:
    text = str(value or "").strip()
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError as exc:
        raise ValueError(f"{field_name} must be an ISO-8601 date") from exc


def _require_sha256(value: object, *, field_name: str) -> str:
    text = str(value or "").strip().lower().removeprefix("sha256:")
    if not _SHA256_RE.fullmatch(text):
        raise ValueError(f"{field_name} must be a SHA-256 digest")
    return text


@dataclass(frozen=True)
class DecisionDataBinding:
    """A redacted, versioned reference to one strategy decision-data input.

    ``legacy_runtime_fetch`` exists only for an explicit, observable migration
    period.  Artifact modes require a content hash, cutoff date, adjustment
    basis, and source identities.  A caller resolves the actual private
    artifact location through its own environment, not through this contract.
    """

    binding_id: str
    strategy_scope: str
    mode: str
    source_ids: tuple[str, ...] = ()
    as_of: str | None = None
    adjustment_basis: str | None = None
    artifact_sha256: str | None = None
    assurance_status: str = DECISION_DATA_ASSURANCE_LEGACY
    schema_version: str = DECISION_DATA_BINDING_SCHEMA_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "binding_id", _require_identifier(self.binding_id, field_name="binding_id"))
        object.__setattr__(self, "strategy_scope", _require_identifier(self.strategy_scope, field_name="strategy_scope"))

        mode = str(self.mode or "").strip()
        if mode not in _MODES:
            raise ValueError("mode is unsupported")
        object.__setattr__(self, "mode", mode)

        schema_version = str(self.schema_version or "").strip()
        if schema_version != DECISION_DATA_BINDING_SCHEMA_VERSION:
            raise ValueError("schema_version is unsupported")
        object.__setattr__(self, "schema_version", schema_version)

        source_ids = tuple(_require_identifier(value, field_name="source_ids[]") for value in self.source_ids)
        if len(set(source_ids)) != len(source_ids):
            raise ValueError("source_ids must not contain duplicates")
        object.__setattr__(self, "source_ids", source_ids)

        assurance_status = str(self.assurance_status or "").strip().upper()
        if assurance_status not in _ASSURANCE_STATUSES:
            raise ValueError("assurance_status is unsupported")
        object.__setattr__(self, "assurance_status", assurance_status)

        if mode == DECISION_DATA_MODE_LEGACY_RUNTIME_FETCH:
            if self.artifact_sha256 is not None or self.as_of is not None or self.adjustment_basis is not None:
                raise ValueError("legacy_runtime_fetch must not claim an immutable artifact")
            if assurance_status != DECISION_DATA_ASSURANCE_LEGACY:
                raise ValueError("legacy_runtime_fetch must use LEGACY assurance_status")
            return

        if not source_ids:
            raise ValueError("artifact decision-data modes require source_ids")
        object.__setattr__(self, "as_of", _require_date(self.as_of, field_name="as_of"))
        object.__setattr__(
            self,
            "adjustment_basis",
            _require_identifier(self.adjustment_basis, field_name="adjustment_basis"),
        )
        object.__setattr__(
            self,
            "artifact_sha256",
            _require_sha256(self.artifact_sha256, field_name="artifact_sha256"),
        )
        if assurance_status == DECISION_DATA_ASSURANCE_LEGACY:
            raise ValueError("artifact decision-data modes must declare an assurance status")

    def to_dict(self) -> dict[str, object]:
        """Return the public-safe contract payload without an artifact location."""

        payload: dict[str, object] = {
            "schema_version": self.schema_version,
            "binding_id": self.binding_id,
            "strategy_scope": self.strategy_scope,
            "mode": self.mode,
            "source_ids": list(self.source_ids),
            "assurance_status": self.assurance_status,
        }
        if self.mode != DECISION_DATA_MODE_LEGACY_RUNTIME_FETCH:
            payload.update(
                {
                    "as_of": self.as_of,
                    "adjustment_basis": self.adjustment_basis,
                    "artifact_sha256": self.artifact_sha256,
                }
            )
        return payload

    @property
    def binding_sha256(self) -> str:
        return sha256(_canonical_bytes(self.to_dict())).hexdigest()

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "DecisionDataBinding":
        """Parse a public-safe binding payload and reject unknown fields."""

        if not isinstance(payload, Mapping):
            raise ValueError("decision data binding must be an object")
        expected = {
            "schema_version",
            "binding_id",
            "strategy_scope",
            "mode",
            "source_ids",
            "as_of",
            "adjustment_basis",
            "artifact_sha256",
            "assurance_status",
        }
        unsupported = sorted(set(payload) - expected)
        if unsupported:
            raise ValueError("decision data binding contains unsupported fields: " + ", ".join(unsupported))
        return cls(
            schema_version=payload.get("schema_version", DECISION_DATA_BINDING_SCHEMA_VERSION),
            binding_id=payload.get("binding_id"),
            strategy_scope=payload.get("strategy_scope"),
            mode=payload.get("mode"),
            source_ids=tuple(payload.get("source_ids") or ()),
            as_of=payload.get("as_of"),
            adjustment_basis=payload.get("adjustment_basis"),
            artifact_sha256=payload.get("artifact_sha256"),
            assurance_status=payload.get("assurance_status", DECISION_DATA_ASSURANCE_LEGACY),
        )
