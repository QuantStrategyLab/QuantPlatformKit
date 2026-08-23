"""Cross-asset, research-only P1-P3 terminal driver contract.

The driver is deliberately a pure evidence-envelope builder.  It does not
fetch data, run a backtest, inspect a catalog, call a broker, or grant a
lifecycle permission.  Producers validate their P1/P2/P3 artifacts first and
pass only their immutable identities into this boundary.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from hashlib import sha256
import json
import re
from typing import Any


RESEARCH_DRIVER_SCHEMA_VERSION = "research_driver_terminal.v1"
RESEARCH_DRIVER_DOMAINS = frozenset(
    {"us_equity", "cn_equity", "hk_equity", "crypto"}
)
RESEARCH_DRIVER_TERMINAL_STATUSES = frozenset(
    {"READY", "DEFERRED", "PARKED"}
)

_STAGE_SPECS = {
    "p1_input": ("P1", "research_input_manifest.v1"),
    "p2_freeze": ("P2", "strategy_config_freeze.v1"),
    "p3_evidence": ("P3", "strategy_evidence_package.v2"),
}
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_REASON_CODE_RE = re.compile(r"^[a-z][a-z0-9_]{0,127}$")
_ARTIFACT_FIELDS = frozenset({"artifact_id", "schema_version", "sha256"})
_STAGE_FIELDS = frozenset({"stage", "status", "artifact", "reason_codes"})
_TOP_LEVEL_FIELDS = frozenset(
    {
        "schema_version",
        "terminal",
        "terminal_status",
        "generated_at",
        "run_id",
        "strategy_id",
        "candidate_id",
        "domain",
        "no_order",
        "permission_effect",
        "catalog_status_used_as_evidence",
        "stages",
    }
)


class InvalidResearchDriverArtifact(ValueError):
    """Raised when a terminal research-driver artifact is not trustworthy."""


def _invalid(message: str) -> None:
    raise InvalidResearchDriverArtifact(message)


def _nonblank_string(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        _invalid(f"{field} must be a non-empty string")
    if any(ord(character) < 0x20 or ord(character) == 0x7F for character in value):
        _invalid(f"{field} contains a control character")
    return value.strip()


def _timezone_timestamp(value: object, field: str) -> str:
    text = _nonblank_string(value, field)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        _invalid(f"{field} must be an ISO-8601 timestamp")
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        _invalid(f"{field} must include a timezone")
    return text


def _reason_codes(values: object, field: str, *, required: bool) -> list[str]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        _invalid(f"{field} must be an array")
    normalized: list[str] = []
    for value in values:
        code = _nonblank_string(value, field)
        if not _REASON_CODE_RE.fullmatch(code):
            _invalid(f"{field} contains an invalid reason code")
        normalized.append(code)
    if normalized != sorted(set(normalized)):
        _invalid(f"{field} must be sorted and unique")
    if required and not normalized:
        _invalid(f"{field} must explain a non-ready stage")
    if not required and normalized:
        _invalid(f"{field} must be empty for READY")
    return normalized


def _artifact_identity(
    value: object, *, field: str, expected_schema_version: str
) -> dict[str, str]:
    if not isinstance(value, Mapping) or set(value) != _ARTIFACT_FIELDS:
        _invalid(f"{field} must be a closed artifact identity")
    artifact_id = _nonblank_string(value.get("artifact_id"), f"{field}.artifact_id")
    schema_version = _nonblank_string(
        value.get("schema_version"), f"{field}.schema_version"
    )
    if schema_version != expected_schema_version:
        _invalid(
            f"{field}.schema_version must equal {expected_schema_version}"
        )
    digest = _nonblank_string(value.get("sha256"), f"{field}.sha256")
    if not _SHA256_RE.fullmatch(digest):
        _invalid(f"{field}.sha256 must be a lowercase SHA-256 digest")
    return {
        "artifact_id": artifact_id,
        "schema_version": schema_version,
        "sha256": digest,
    }


def build_ready_research_stage(
    stage_name: str, *, artifact_id: str, artifact_sha256: str
) -> dict[str, Any]:
    """Build a READY stage from an already validated immutable artifact."""

    if stage_name not in _STAGE_SPECS:
        _invalid(f"unsupported research stage: {stage_name!r}")
    stage, schema_version = _STAGE_SPECS[stage_name]
    record = {
        "stage": stage,
        "status": "READY",
        "artifact": {
            "artifact_id": artifact_id,
            "schema_version": schema_version,
            "sha256": artifact_sha256,
        },
        "reason_codes": [],
    }
    return _validate_stage_record(stage_name, record)


def build_nonready_research_stage(
    stage_name: str, *, status: str, reason_codes: Sequence[str]
) -> dict[str, Any]:
    """Build a truthful DEFERRED or PARKED stage without claiming evidence."""

    if stage_name not in _STAGE_SPECS:
        _invalid(f"unsupported research stage: {stage_name!r}")
    normalized_status = _nonblank_string(status, "status").upper()
    if normalized_status not in {"DEFERRED", "PARKED"}:
        _invalid("non-ready stage status must be DEFERRED or PARKED")
    stage, _ = _STAGE_SPECS[stage_name]
    record = {
        "stage": stage,
        "status": normalized_status,
        "artifact": None,
        "reason_codes": list(reason_codes),
    }
    return _validate_stage_record(stage_name, record)


def _validate_stage_record(stage_name: str, value: object) -> dict[str, Any]:
    expected_stage, expected_schema_version = _STAGE_SPECS[stage_name]
    if not isinstance(value, Mapping) or set(value) != _STAGE_FIELDS:
        _invalid(f"{stage_name} must be a closed stage record")
    stage = _nonblank_string(value.get("stage"), f"{stage_name}.stage")
    if stage != expected_stage:
        _invalid(f"{stage_name}.stage must equal {expected_stage}")
    status = _nonblank_string(value.get("status"), f"{stage_name}.status").upper()
    if status not in RESEARCH_DRIVER_TERMINAL_STATUSES:
        _invalid(f"{stage_name}.status is unsupported")
    if status == "READY":
        artifact = _artifact_identity(
            value.get("artifact"),
            field=f"{stage_name}.artifact",
            expected_schema_version=expected_schema_version,
        )
        reasons = _reason_codes(
            value.get("reason_codes"), f"{stage_name}.reason_codes", required=False
        )
    else:
        if value.get("artifact") is not None:
            _invalid(f"{stage_name}.artifact must be null unless status is READY")
        artifact = None
        reasons = _reason_codes(
            value.get("reason_codes"), f"{stage_name}.reason_codes", required=True
        )
    return {
        "stage": expected_stage,
        "status": status,
        "artifact": artifact,
        "reason_codes": reasons,
    }


def _normalize_stage(stage_name: str, value: object) -> dict[str, Any]:
    if value is None:
        return build_nonready_research_stage(
            stage_name,
            status="DEFERRED",
            reason_codes=(f"{stage_name}_not_produced",),
        )
    try:
        return _validate_stage_record(stage_name, value)
    except InvalidResearchDriverArtifact:
        return build_nonready_research_stage(
            stage_name,
            status="PARKED",
            reason_codes=(f"{stage_name}_invalid",),
        )


def _enforce_dependencies(stages: dict[str, dict[str, Any]]) -> None:
    dependencies = {
        "p2_freeze": "p1_input",
        "p3_evidence": "p2_freeze",
    }
    for stage_name, dependency in dependencies.items():
        if (
            stages[stage_name]["status"] == "READY"
            and stages[dependency]["status"] != "READY"
        ):
            stages[stage_name] = build_nonready_research_stage(
                stage_name,
                status="PARKED",
                reason_codes=(f"{dependency}_not_ready",),
            )


def _terminal_status(stages: Mapping[str, Mapping[str, Any]]) -> str:
    statuses = {str(stage["status"]) for stage in stages.values()}
    if "PARKED" in statuses:
        return "PARKED"
    if statuses == {"READY"}:
        return "READY"
    return "DEFERRED"


def build_research_driver_terminal_artifact(
    *,
    run_id: str,
    generated_at: str,
    strategy_id: str,
    candidate_id: str,
    domain: str,
    p1_input: Mapping[str, Any] | None = None,
    p2_freeze: Mapping[str, Any] | None = None,
    p3_evidence: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return one terminal, no-order P1-P3 artifact for every valid run identity.

    Missing stages become ``DEFERRED``.  Malformed evidence or an impossible
    dependency chain becomes ``PARKED``.  Catalog state is intentionally not an
    input and cannot contribute to readiness.
    """

    normalized_domain = _nonblank_string(domain, "domain").lower()
    if normalized_domain not in RESEARCH_DRIVER_DOMAINS:
        _invalid(f"unsupported research domain: {domain!r}")
    stages = {
        "p1_input": _normalize_stage("p1_input", p1_input),
        "p2_freeze": _normalize_stage("p2_freeze", p2_freeze),
        "p3_evidence": _normalize_stage("p3_evidence", p3_evidence),
    }
    _enforce_dependencies(stages)
    artifact = {
        "schema_version": RESEARCH_DRIVER_SCHEMA_VERSION,
        "terminal": True,
        "terminal_status": _terminal_status(stages),
        "generated_at": _timezone_timestamp(generated_at, "generated_at"),
        "run_id": _nonblank_string(run_id, "run_id"),
        "strategy_id": _nonblank_string(strategy_id, "strategy_id"),
        "candidate_id": _nonblank_string(candidate_id, "candidate_id"),
        "domain": normalized_domain,
        "no_order": True,
        "permission_effect": "none",
        "catalog_status_used_as_evidence": False,
        "stages": stages,
    }
    return validate_research_driver_terminal_artifact(artifact)


def validate_research_driver_terminal_artifact(
    artifact: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate a closed terminal artifact and return a detached JSON value."""

    if not isinstance(artifact, Mapping) or set(artifact) != _TOP_LEVEL_FIELDS:
        _invalid("terminal artifact must be a closed object")
    if artifact.get("schema_version") != RESEARCH_DRIVER_SCHEMA_VERSION:
        _invalid(f"schema_version must equal {RESEARCH_DRIVER_SCHEMA_VERSION}")
    if artifact.get("terminal") is not True:
        _invalid("terminal must remain true")
    if artifact.get("no_order") is not True:
        _invalid("no_order must remain true")
    if artifact.get("permission_effect") != "none":
        _invalid("permission_effect must remain none")
    if artifact.get("catalog_status_used_as_evidence") is not False:
        _invalid("catalog status cannot be used as evidence")
    domain = _nonblank_string(artifact.get("domain"), "domain").lower()
    if domain not in RESEARCH_DRIVER_DOMAINS:
        _invalid("domain is unsupported")
    stages_value = artifact.get("stages")
    if not isinstance(stages_value, Mapping) or set(stages_value) != set(_STAGE_SPECS):
        _invalid("stages must contain exactly P1, P2, and P3")
    stages = {
        stage_name: _validate_stage_record(stage_name, stages_value[stage_name])
        for stage_name in _STAGE_SPECS
    }
    dependency_copy = json.loads(json.dumps(stages))
    _enforce_dependencies(dependency_copy)
    if dependency_copy != stages:
        _invalid("a READY stage cannot bypass a non-ready dependency")
    terminal_status = _nonblank_string(
        artifact.get("terminal_status"), "terminal_status"
    ).upper()
    if terminal_status != _terminal_status(stages):
        _invalid("terminal_status does not match stage results")
    result = {
        "schema_version": RESEARCH_DRIVER_SCHEMA_VERSION,
        "terminal": True,
        "terminal_status": terminal_status,
        "generated_at": _timezone_timestamp(artifact.get("generated_at"), "generated_at"),
        "run_id": _nonblank_string(artifact.get("run_id"), "run_id"),
        "strategy_id": _nonblank_string(
            artifact.get("strategy_id"), "strategy_id"
        ),
        "candidate_id": _nonblank_string(
            artifact.get("candidate_id"), "candidate_id"
        ),
        "domain": domain,
        "no_order": True,
        "permission_effect": "none",
        "catalog_status_used_as_evidence": False,
        "stages": stages,
    }
    return json.loads(
        json.dumps(result, sort_keys=True, separators=(",", ":"), allow_nan=False)
    )


def canonical_research_driver_terminal_bytes(artifact: Mapping[str, Any]) -> bytes:
    """Return deterministic UTF-8 JSON bytes for a validated artifact."""

    validated = validate_research_driver_terminal_artifact(artifact)
    return json.dumps(
        validated,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def research_driver_terminal_sha256(artifact: Mapping[str, Any]) -> str:
    """Return the digest of the canonical terminal artifact bytes."""

    return sha256(canonical_research_driver_terminal_bytes(artifact)).hexdigest()


__all__ = [
    "InvalidResearchDriverArtifact",
    "RESEARCH_DRIVER_DOMAINS",
    "RESEARCH_DRIVER_SCHEMA_VERSION",
    "RESEARCH_DRIVER_TERMINAL_STATUSES",
    "build_nonready_research_stage",
    "build_ready_research_stage",
    "build_research_driver_terminal_artifact",
    "canonical_research_driver_terminal_bytes",
    "research_driver_terminal_sha256",
    "validate_research_driver_terminal_artifact",
]
