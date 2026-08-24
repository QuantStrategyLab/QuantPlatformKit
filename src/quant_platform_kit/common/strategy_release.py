"""Immutable strategy-release identity and runtime self-attestation helpers.

The release contract deliberately separates a research/evidence artifact from
the small immutable identity a trading runtime is allowed to load. A runtime
can self-report what it loaded; a future control-plane monitor is responsible
for comparing those receipts across platforms before it authorizes promotion.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from typing import Mapping


STRATEGY_RELEASE_MANIFEST_SCHEMA_VERSION = "strategy_release_manifest.v1"
RUNTIME_LOADED_RECEIPT_SCHEMA_VERSION = "runtime_loaded_receipt.v1"

_RELEASE_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{2,127}$")
_SHA256_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")


def _required_text(value: object, *, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field_name} is required")
    return text


def _normalize_sha256(value: object, *, field_name: str) -> str:
    text = _required_text(value, field_name=field_name).lower()
    if text.startswith("sha256:"):
        text = text.removeprefix("sha256:")
    if not _SHA256_PATTERN.fullmatch(text):
        raise ValueError(f"{field_name} must be a SHA-256 digest")
    return text


def _normalize_effective_session(value: object) -> str:
    text = _required_text(value, field_name="effective_session")
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError as exc:
        raise ValueError("effective_session must be an ISO-8601 date") from exc


def _normalize_targets(values: tuple[str, ...] | list[str] | object) -> tuple[str, ...]:
    if isinstance(values, str):
        values = (values,)
    if not isinstance(values, (tuple, list)):
        raise ValueError("targets must be a list or tuple")
    normalized = tuple(_required_text(value, field_name="targets[]") for value in values)
    if not normalized:
        raise ValueError("targets must not be empty")
    if len(set(normalized)) != len(normalized):
        raise ValueError("targets must not contain duplicates")
    return normalized


@dataclass(frozen=True)
class StrategyReleaseManifest:
    """The immutable, evidence-bound release record for one strategy version."""

    release_id: str
    strategy_profile: str
    strategy_revision: str
    config_sha256: str
    risk_policy_sha256: str
    evidence_sha256: str
    plugin_bundle_sha256: str
    effective_session: str
    target_set_id: str
    targets: tuple[str, ...]
    supersedes: str | None = None
    rollback_to: str | None = None

    def __post_init__(self) -> None:
        release_id = _required_text(self.release_id, field_name="release_id")
        if not _RELEASE_ID_PATTERN.fullmatch(release_id):
            raise ValueError("release_id must contain only letters, numbers, '.', '_' or '-'")
        object.__setattr__(self, "release_id", release_id)
        object.__setattr__(
            self,
            "strategy_profile",
            _required_text(self.strategy_profile, field_name="strategy_profile"),
        )
        object.__setattr__(
            self,
            "strategy_revision",
            _required_text(self.strategy_revision, field_name="strategy_revision"),
        )
        object.__setattr__(
            self,
            "config_sha256",
            _normalize_sha256(self.config_sha256, field_name="config_sha256"),
        )
        object.__setattr__(
            self,
            "risk_policy_sha256",
            _normalize_sha256(self.risk_policy_sha256, field_name="risk_policy_sha256"),
        )
        object.__setattr__(
            self,
            "evidence_sha256",
            _normalize_sha256(self.evidence_sha256, field_name="evidence_sha256"),
        )
        object.__setattr__(
            self,
            "plugin_bundle_sha256",
            _normalize_sha256(self.plugin_bundle_sha256, field_name="plugin_bundle_sha256"),
        )
        object.__setattr__(self, "effective_session", _normalize_effective_session(self.effective_session))
        object.__setattr__(self, "target_set_id", _required_text(self.target_set_id, field_name="target_set_id"))
        object.__setattr__(self, "targets", _normalize_targets(self.targets))
        object.__setattr__(self, "supersedes", _optional_text(self.supersedes))
        object.__setattr__(self, "rollback_to", _optional_text(self.rollback_to))

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        return {key: value for key, value in payload.items() if value is not None}

    @property
    def manifest_sha256(self) -> str:
        payload = json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def runtime_identity(self) -> "StrategyReleaseIdentity":
        return StrategyReleaseIdentity(
            release_id=self.release_id,
            manifest_sha256=self.manifest_sha256,
            strategy_revision=self.strategy_revision,
            config_sha256=self.config_sha256,
            risk_policy_sha256=self.risk_policy_sha256,
            evidence_sha256=self.evidence_sha256,
            plugin_bundle_sha256=self.plugin_bundle_sha256,
            effective_session=self.effective_session,
        )


@dataclass(frozen=True)
class StrategyReleaseIdentity:
    """The compact release identity placed in ``RUNTIME_TARGET_JSON``."""

    release_id: str
    manifest_sha256: str
    strategy_revision: str
    config_sha256: str
    risk_policy_sha256: str
    evidence_sha256: str
    plugin_bundle_sha256: str
    effective_session: str

    def __post_init__(self) -> None:
        release_id = _required_text(self.release_id, field_name="strategy_release.release_id")
        if not _RELEASE_ID_PATTERN.fullmatch(release_id):
            raise ValueError("strategy_release.release_id has invalid characters")
        object.__setattr__(self, "release_id", release_id)
        for field_name in (
            "manifest_sha256",
            "config_sha256",
            "risk_policy_sha256",
            "evidence_sha256",
            "plugin_bundle_sha256",
        ):
            object.__setattr__(
                self,
                field_name,
                _normalize_sha256(getattr(self, field_name), field_name=f"strategy_release.{field_name}"),
            )
        object.__setattr__(
            self,
            "strategy_revision",
            _required_text(self.strategy_revision, field_name="strategy_release.strategy_revision"),
        )
        object.__setattr__(self, "effective_session", _normalize_effective_session(self.effective_session))

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def build_strategy_release_identity(
    value: StrategyReleaseIdentity | Mapping[str, object],
) -> StrategyReleaseIdentity:
    if isinstance(value, StrategyReleaseIdentity):
        return value
    if not isinstance(value, Mapping):
        raise ValueError("strategy_release must be an object")
    required_fields = (
        "release_id",
        "manifest_sha256",
        "strategy_revision",
        "config_sha256",
        "risk_policy_sha256",
        "evidence_sha256",
        "plugin_bundle_sha256",
        "effective_session",
    )
    missing = tuple(field for field in required_fields if field not in value)
    if missing:
        raise ValueError(f"strategy_release is missing required fields: {', '.join(missing)}")
    return StrategyReleaseIdentity(**{field: value[field] for field in required_fields})


def build_runtime_loaded_receipt(
    *,
    strategy_release: StrategyReleaseIdentity | Mapping[str, object] | None,
    loaded_at: datetime | str | None = None,
    runtime_revision: str | None = None,
    runtime_image_digest: str | None = None,
) -> dict[str, object]:
    """Build an explicit self-attestation record for every runtime report.

    ``self_attested`` means only that this process loaded the displayed
    identity. It intentionally does *not* claim cross-platform release
    agreement; that comparison is a control-plane responsibility.
    """

    receipt: dict[str, object] = {
        "schema_version": RUNTIME_LOADED_RECEIPT_SCHEMA_VERSION,
        "loaded_at": _normalize_timestamp(loaded_at),
    }
    if strategy_release is None:
        receipt.update(
            {
                "attestation_state": "legacy_unattested",
                "release_id": None,
                "missing": ["strategy_release"],
            }
        )
        return receipt

    identity = build_strategy_release_identity(strategy_release)
    receipt.update(
        {
            "attestation_state": "self_attested",
            "release_id": identity.release_id,
            "strategy_release": identity.to_dict(),
        }
    )
    revision = _optional_text(runtime_revision)
    if revision is not None:
        receipt["runtime_revision"] = revision
    image_digest = _optional_text(runtime_image_digest)
    if image_digest is not None:
        receipt["runtime_image_digest"] = image_digest
    return receipt


def _optional_text(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def _normalize_timestamp(value: datetime | str | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    return _optional_text(value)


__all__ = [
    "RUNTIME_LOADED_RECEIPT_SCHEMA_VERSION",
    "STRATEGY_RELEASE_MANIFEST_SCHEMA_VERSION",
    "StrategyReleaseIdentity",
    "StrategyReleaseManifest",
    "build_runtime_loaded_receipt",
    "build_strategy_release_identity",
]
