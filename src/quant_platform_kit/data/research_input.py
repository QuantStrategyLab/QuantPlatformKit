"""Pure validation for immutable research-input manifest metadata.

This S0 contract deliberately does not acquire, read, materialize, replay, or
otherwise act on the referenced inputs.  It only validates the metadata that
binds a research consumer to already-produced immutable artifacts.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import datetime
from typing import Any


RESEARCH_INPUT_MANIFEST_SCHEMA_VERSION = "research_input_manifest.v1"

_INPUT_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_KIND = re.compile(r"^[a-z][a-z0-9_]*$")
_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_RFC3339_DATETIME = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$"
)
_REQUIRED_TOP_LEVEL = frozenset({"schema_version", "manifest_id", "created_at", "as_of", "inputs"})
_REQUIRED_INPUT = frozenset({"input_id", "kind", "artifact_uri", "sha256", "as_of"})


class ResearchInputManifestValidationError(ValueError):
    """Raised when a research-input manifest violates the S0 contract."""

    def __init__(self) -> None:
        super().__init__("invalid research input manifest")


def validate_research_input_manifest(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and return immutable metadata without dereferencing input artifacts."""

    if not isinstance(payload, Mapping) or set(payload) != _REQUIRED_TOP_LEVEL:
        raise ResearchInputManifestValidationError()
    if payload.get("schema_version") != RESEARCH_INPUT_MANIFEST_SCHEMA_VERSION:
        raise ResearchInputManifestValidationError()

    _require_identifier(payload.get("manifest_id"))
    created_at = _parse_datetime(payload.get("created_at"))
    manifest_as_of = _parse_datetime(payload.get("as_of"))
    if created_at < manifest_as_of:
        raise ResearchInputManifestValidationError()

    inputs = payload.get("inputs")
    if not isinstance(inputs, list) or not inputs:
        raise ResearchInputManifestValidationError()

    input_ids: set[str] = set()
    for input_metadata in inputs:
        _validate_input(input_metadata, manifest_as_of, input_ids)

    return dict(payload)


def _validate_input(value: object, manifest_as_of: datetime, input_ids: set[str]) -> None:
    if not isinstance(value, Mapping) or set(value) != _REQUIRED_INPUT:
        raise ResearchInputManifestValidationError()

    input_id = value.get("input_id")
    _require_identifier(input_id)
    if input_id in input_ids:
        raise ResearchInputManifestValidationError()
    input_ids.add(input_id)

    kind = value.get("kind")
    if not isinstance(kind, str) or not _KIND.fullmatch(kind):
        raise ResearchInputManifestValidationError()

    artifact_uri = value.get("artifact_uri")
    if not isinstance(artifact_uri, str) or not artifact_uri or any(char.isspace() for char in artifact_uri):
        raise ResearchInputManifestValidationError()

    sha256 = value.get("sha256")
    if not isinstance(sha256, str) or not _SHA256.fullmatch(sha256):
        raise ResearchInputManifestValidationError()

    if _parse_datetime(value.get("as_of")) > manifest_as_of:
        raise ResearchInputManifestValidationError()


def _require_identifier(value: object) -> None:
    if not isinstance(value, str) or not _INPUT_ID.fullmatch(value):
        raise ResearchInputManifestValidationError()


def _parse_datetime(value: object) -> datetime:
    if not isinstance(value, str) or not _RFC3339_DATETIME.fullmatch(value):
        raise ResearchInputManifestValidationError()
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ResearchInputManifestValidationError() from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ResearchInputManifestValidationError()
    return parsed
