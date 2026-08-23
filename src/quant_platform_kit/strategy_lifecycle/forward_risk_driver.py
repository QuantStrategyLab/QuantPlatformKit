"""Cross-asset, no-order P4/P5 terminal observation contract.

This adapter binds future/shadow observations and portfolio-risk snapshots to
an already terminal P1-P3 research run.  It only validates immutable artifact
identities.  It never starts a paper account, fetches market data, calls a
broker, changes a position, or grants lifecycle authority.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from typing import Any

from .research_driver import (
    RESEARCH_DRIVER_DOMAINS,
    research_driver_terminal_sha256,
    validate_research_driver_terminal_artifact,
)


FORWARD_RISK_SCHEMA_VERSION = "forward_risk_terminal.v1"
FORWARD_RISK_TERMINAL_STATUSES = frozenset({"READY", "DEFERRED", "PARKED"})
P4_OBSERVATION_MODES = frozenset({"shadow", "paper"})

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_REASON_CODE_RE = re.compile(r"^[a-z][a-z0-9_]{0,127}$")
_STAGE_FIELDS = frozenset({"stage", "status", "mode", "artifact", "reason_codes"})
_BASE_ARTIFACT_FIELDS = frozenset(
    {
        "artifact_id",
        "schema_version",
        "sha256",
        "candidate_id",
        "observed_at",
        "expires_at",
    }
)
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
        "research_terminal_status",
        "research_terminal_sha256",
        "no_order",
        "permission_effect",
        "broker_dependency",
        "stages",
    }
)


class InvalidForwardRiskArtifact(ValueError):
    """Raised when a P4/P5 observation artifact fails closed validation."""


def _invalid(message: str) -> None:
    raise InvalidForwardRiskArtifact(message)


def _nonblank_string(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        _invalid(f"{field} must be a non-empty string")
    if any(ord(character) < 0x20 or ord(character) == 0x7F for character in value):
        _invalid(f"{field} contains a control character")
    return value.strip()


def _timestamp(value: object, field: str) -> tuple[str, datetime]:
    text = _nonblank_string(value, field)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        _invalid(f"{field} must be an ISO-8601 timestamp")
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        _invalid(f"{field} must include a timezone")
    return text, parsed.astimezone(timezone.utc)


def _reason_codes(values: object, field: str, *, required: bool) -> list[str]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        _invalid(f"{field} must be an array")
    normalized = [_nonblank_string(value, field) for value in values]
    if any(not _REASON_CODE_RE.fullmatch(value) for value in normalized):
        _invalid(f"{field} contains an invalid reason code")
    if normalized != sorted(set(normalized)):
        _invalid(f"{field} must be sorted and unique")
    if required and not normalized:
        _invalid(f"{field} must explain a non-ready stage")
    if not required and normalized:
        _invalid(f"{field} must be empty for READY")
    return normalized


def _artifact_identity(
    value: object,
    *,
    field: str,
    expected_schema_version: str,
    expected_candidate_id: str | None = None,
    generated_at: datetime | None = None,
) -> dict[str, str]:
    if not isinstance(value, Mapping) or set(value) != _BASE_ARTIFACT_FIELDS:
        _invalid(f"{field} must be a closed artifact identity")
    digest = _nonblank_string(value.get("sha256"), f"{field}.sha256")
    if not _SHA256_RE.fullmatch(digest):
        _invalid(f"{field}.sha256 must be a lowercase SHA-256 digest")
    schema_version = _nonblank_string(
        value.get("schema_version"), f"{field}.schema_version"
    )
    if schema_version != expected_schema_version:
        _invalid(f"{field}.schema_version must equal {expected_schema_version}")
    candidate_id = _nonblank_string(
        value.get("candidate_id"), f"{field}.candidate_id"
    )
    if expected_candidate_id is not None and candidate_id != expected_candidate_id:
        _invalid(f"{field}.candidate_id does not match the research terminal")
    observed_at, observed_time = _timestamp(
        value.get("observed_at"), f"{field}.observed_at"
    )
    expires_at, expiry_time = _timestamp(
        value.get("expires_at"), f"{field}.expires_at"
    )
    if expiry_time <= observed_time:
        _invalid(f"{field}.expires_at must be later than observed_at")
    if generated_at is not None and expiry_time <= generated_at:
        _invalid(f"{field} is expired at generated_at")
    return {
        "artifact_id": _nonblank_string(
            value.get("artifact_id"), f"{field}.artifact_id"
        ),
        "schema_version": schema_version,
        "sha256": digest,
        "candidate_id": candidate_id,
        "observed_at": observed_at,
        "expires_at": expires_at,
    }


def _build_ready_stage(
    *,
    stage: str,
    mode: str,
    schema_version: str,
    artifact_id: str,
    artifact_sha256: str,
    candidate_id: str,
    observed_at: str,
    expires_at: str,
) -> dict[str, Any]:
    return {
        "stage": stage,
        "status": "READY",
        "mode": mode,
        "artifact": _artifact_identity(
            {
                "artifact_id": artifact_id,
                "schema_version": schema_version,
                "sha256": artifact_sha256,
                "candidate_id": candidate_id,
                "observed_at": observed_at,
                "expires_at": expires_at,
            },
            field=f"{stage.lower()}.artifact",
            expected_schema_version=schema_version,
        ),
        "reason_codes": [],
    }


def build_ready_forward_observation_stage(
    *,
    mode: str,
    artifact_id: str,
    artifact_sha256: str,
    candidate_id: str,
    observed_at: str,
    expires_at: str,
) -> dict[str, Any]:
    """Build a P4 identity for validated shadow or simulated-paper evidence."""

    normalized_mode = _nonblank_string(mode, "mode").lower()
    if normalized_mode not in P4_OBSERVATION_MODES:
        _invalid("P4 mode must be shadow or paper")
    return _build_ready_stage(
        stage="P4",
        mode=normalized_mode,
        schema_version="forward_observation.v1",
        artifact_id=artifact_id,
        artifact_sha256=artifact_sha256,
        candidate_id=candidate_id,
        observed_at=observed_at,
        expires_at=expires_at,
    )


def build_ready_portfolio_risk_stage(
    *,
    artifact_id: str,
    artifact_sha256: str,
    candidate_id: str,
    observed_at: str,
    expires_at: str,
) -> dict[str, Any]:
    """Build a P5 identity for an already validated portfolio RiskSnapshot."""

    return _build_ready_stage(
        stage="P5",
        mode="portfolio_risk",
        schema_version="portfolio_risk_snapshot.v1",
        artifact_id=artifact_id,
        artifact_sha256=artifact_sha256,
        candidate_id=candidate_id,
        observed_at=observed_at,
        expires_at=expires_at,
    )


def build_nonready_forward_risk_stage(
    stage: str, *, status: str, reason_codes: Sequence[str]
) -> dict[str, Any]:
    """Build a truthful P4/P5 DEFERRED or PARKED terminal stage."""

    normalized_stage = _nonblank_string(stage, "stage").upper()
    if normalized_stage not in {"P4", "P5"}:
        _invalid("stage must be P4 or P5")
    normalized_status = _nonblank_string(status, "status").upper()
    if normalized_status not in {"DEFERRED", "PARKED"}:
        _invalid("non-ready stage status must be DEFERRED or PARKED")
    return {
        "stage": normalized_stage,
        "status": normalized_status,
        "mode": "shadow" if normalized_stage == "P4" else "portfolio_risk",
        "artifact": None,
        "reason_codes": _reason_codes(
            list(reason_codes), "reason_codes", required=True
        ),
    }


def _validate_stage(
    value: object,
    *,
    stage: str,
    candidate_id: str,
    generated_at: datetime,
) -> dict[str, Any]:
    field = "p4_forward" if stage == "P4" else "p5_risk"
    if not isinstance(value, Mapping) or set(value) != _STAGE_FIELDS:
        _invalid(f"{field} must be a closed stage record")
    if value.get("stage") != stage:
        _invalid(f"{field}.stage must equal {stage}")
    status = _nonblank_string(value.get("status"), f"{field}.status").upper()
    if status not in FORWARD_RISK_TERMINAL_STATUSES:
        _invalid(f"{field}.status is unsupported")
    mode = _nonblank_string(value.get("mode"), f"{field}.mode").lower()
    allowed_modes = P4_OBSERVATION_MODES if stage == "P4" else {"portfolio_risk"}
    if mode not in allowed_modes:
        _invalid(f"{field}.mode is unsupported")
    if status == "READY":
        artifact = _artifact_identity(
            value.get("artifact"),
            field=f"{field}.artifact",
            expected_schema_version=(
                "forward_observation.v1"
                if stage == "P4"
                else "portfolio_risk_snapshot.v1"
            ),
            expected_candidate_id=candidate_id,
            generated_at=generated_at,
        )
        reasons = _reason_codes(
            value.get("reason_codes"), f"{field}.reason_codes", required=False
        )
    else:
        if value.get("artifact") is not None:
            _invalid(f"{field}.artifact must be null unless status is READY")
        artifact = None
        reasons = _reason_codes(
            value.get("reason_codes"), f"{field}.reason_codes", required=True
        )
    return {
        "stage": stage,
        "status": status,
        "mode": mode,
        "artifact": artifact,
        "reason_codes": reasons,
    }


def _normalize_stage(
    value: object | None,
    *,
    stage: str,
    candidate_id: str,
    generated_at: datetime,
) -> dict[str, Any]:
    if value is None:
        return build_nonready_forward_risk_stage(
            stage,
            status="DEFERRED",
            reason_codes=(("p4_observation_not_produced" if stage == "P4" else "p5_risk_not_produced"),),
        )
    try:
        return _validate_stage(
            value,
            stage=stage,
            candidate_id=candidate_id,
            generated_at=generated_at,
        )
    except InvalidForwardRiskArtifact:
        return build_nonready_forward_risk_stage(
            stage,
            status="PARKED",
            reason_codes=(("p4_observation_invalid" if stage == "P4" else "p5_risk_invalid"),),
        )


def _terminal_status(
    research_status: str, stages: Mapping[str, Mapping[str, Any]]
) -> str:
    statuses = {research_status, *(str(value["status"]) for value in stages.values())}
    if "PARKED" in statuses:
        return "PARKED"
    if statuses == {"READY"}:
        return "READY"
    return "DEFERRED"


def build_forward_risk_terminal_artifact(
    *,
    research_terminal: Mapping[str, Any],
    generated_at: str,
    p4_forward: Mapping[str, Any] | None = None,
    p5_risk: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Bind P4/P5 evidence to a validated P1-P3 terminal artifact."""

    research = validate_research_driver_terminal_artifact(research_terminal)
    generated_at_text, generated_time = _timestamp(generated_at, "generated_at")
    candidate_id = str(research["candidate_id"])
    stages = {
        "p4_forward": _normalize_stage(
            p4_forward,
            stage="P4",
            candidate_id=candidate_id,
            generated_at=generated_time,
        ),
        "p5_risk": _normalize_stage(
            p5_risk,
            stage="P5",
            candidate_id=candidate_id,
            generated_at=generated_time,
        ),
    }
    if stages["p5_risk"]["status"] == "READY" and stages["p4_forward"]["status"] != "READY":
        stages["p5_risk"] = build_nonready_forward_risk_stage(
            "P5", status="PARKED", reason_codes=("p4_forward_not_ready",)
        )
    if research["terminal_status"] != "READY":
        for key, stage_name in (("p4_forward", "P4"), ("p5_risk", "P5")):
            if stages[key]["status"] == "READY":
                stages[key] = build_nonready_forward_risk_stage(
                    stage_name,
                    status="PARKED",
                    reason_codes=("research_terminal_not_ready",),
                )
    artifact = {
        "schema_version": FORWARD_RISK_SCHEMA_VERSION,
        "terminal": True,
        "terminal_status": _terminal_status(str(research["terminal_status"]), stages),
        "generated_at": generated_at_text,
        "run_id": str(research["run_id"]),
        "strategy_id": str(research["strategy_id"]),
        "candidate_id": candidate_id,
        "domain": str(research["domain"]),
        "research_terminal_status": str(research["terminal_status"]),
        "research_terminal_sha256": research_driver_terminal_sha256(research),
        "no_order": True,
        "permission_effect": "none",
        "broker_dependency": False,
        "stages": stages,
    }
    return validate_forward_risk_terminal_artifact(artifact)


def validate_forward_risk_terminal_artifact(
    artifact: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate a closed P4/P5 terminal envelope without side effects."""

    if not isinstance(artifact, Mapping) or set(artifact) != _TOP_LEVEL_FIELDS:
        _invalid("terminal artifact must be a closed object")
    if artifact.get("schema_version") != FORWARD_RISK_SCHEMA_VERSION:
        _invalid(f"schema_version must equal {FORWARD_RISK_SCHEMA_VERSION}")
    if artifact.get("terminal") is not True:
        _invalid("terminal must remain true")
    if artifact.get("no_order") is not True:
        _invalid("no_order must remain true")
    if artifact.get("permission_effect") != "none":
        _invalid("permission_effect must remain none")
    if artifact.get("broker_dependency") is not False:
        _invalid("broker_dependency must remain false")
    generated_at, generated_time = _timestamp(artifact.get("generated_at"), "generated_at")
    domain = _nonblank_string(artifact.get("domain"), "domain").lower()
    if domain not in RESEARCH_DRIVER_DOMAINS:
        _invalid("domain is unsupported")
    candidate_id = _nonblank_string(artifact.get("candidate_id"), "candidate_id")
    digest = _nonblank_string(
        artifact.get("research_terminal_sha256"), "research_terminal_sha256"
    )
    if not _SHA256_RE.fullmatch(digest):
        _invalid("research_terminal_sha256 must be a lowercase SHA-256 digest")
    research_status = _nonblank_string(
        artifact.get("research_terminal_status"), "research_terminal_status"
    ).upper()
    if research_status not in FORWARD_RISK_TERMINAL_STATUSES:
        _invalid("research_terminal_status is unsupported")
    stages_value = artifact.get("stages")
    if not isinstance(stages_value, Mapping) or set(stages_value) != {"p4_forward", "p5_risk"}:
        _invalid("stages must contain exactly P4 and P5")
    stages = {
        "p4_forward": _validate_stage(
            stages_value["p4_forward"],
            stage="P4",
            candidate_id=candidate_id,
            generated_at=generated_time,
        ),
        "p5_risk": _validate_stage(
            stages_value["p5_risk"],
            stage="P5",
            candidate_id=candidate_id,
            generated_at=generated_time,
        ),
    }
    if stages["p5_risk"]["status"] == "READY" and stages["p4_forward"]["status"] != "READY":
        _invalid("P5 READY cannot bypass a non-ready P4")
    if research_status != "READY" and any(
        value["status"] == "READY" for value in stages.values()
    ):
        _invalid("P4/P5 READY cannot bypass a non-ready research terminal")
    terminal_status = _nonblank_string(
        artifact.get("terminal_status"), "terminal_status"
    ).upper()
    if terminal_status != _terminal_status(research_status, stages):
        _invalid("terminal_status does not match upstream and stage results")
    result = {
        "schema_version": FORWARD_RISK_SCHEMA_VERSION,
        "terminal": True,
        "terminal_status": terminal_status,
        "generated_at": generated_at,
        "run_id": _nonblank_string(artifact.get("run_id"), "run_id"),
        "strategy_id": _nonblank_string(
            artifact.get("strategy_id"), "strategy_id"
        ),
        "candidate_id": candidate_id,
        "domain": domain,
        "research_terminal_status": research_status,
        "research_terminal_sha256": digest,
        "no_order": True,
        "permission_effect": "none",
        "broker_dependency": False,
        "stages": stages,
    }
    return json.loads(
        json.dumps(result, sort_keys=True, separators=(",", ":"), allow_nan=False)
    )


def canonical_forward_risk_terminal_bytes(artifact: Mapping[str, Any]) -> bytes:
    """Return deterministic UTF-8 bytes for a validated P4/P5 artifact."""

    validated = validate_forward_risk_terminal_artifact(artifact)
    return json.dumps(
        validated,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def forward_risk_terminal_sha256(artifact: Mapping[str, Any]) -> str:
    """Return the SHA-256 digest of the canonical P4/P5 terminal bytes."""

    return sha256(canonical_forward_risk_terminal_bytes(artifact)).hexdigest()

