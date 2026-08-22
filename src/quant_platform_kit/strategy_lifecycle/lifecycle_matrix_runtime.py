"""Read-only aggregation of lifecycle terminal artifacts.

This module deliberately only reads explicit local JSON files.  It does not
run a strategy, fetch data, retry a job, publish an alert, or authorize
promotion.  Producers may emit one artifact per observed lifecycle stage
using the small envelope documented in :func:`build_lifecycle_matrix`.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any, Iterable

_STAGES = tuple(f"p{i}" for i in range(7))
_STATUSES = {
    "not_started",
    "in_progress",
    "verified",
    "parked",
    "deferred",
    "inconclusive",
}
_OBSERVED_STAGES = {"p1", "p3", "p4", "p5"}


class LifecycleMatrixInputError(ValueError):
    """Raised when an artifact cannot be safely attributed to a matrix entry."""


def _required_string(value: Any, field: str, path: Path) -> str:
    if not isinstance(value, str) or not value.strip():
        raise LifecycleMatrixInputError(f"{path}: {field} must be a non-empty string")
    return value.strip()


def _read_artifact(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LifecycleMatrixInputError(f"{path}: invalid JSON artifact") from exc
    if not isinstance(payload, dict):
        raise LifecycleMatrixInputError(f"{path}: artifact must be a JSON object")
    return payload


def _stage_record(payload: dict[str, Any], path: Path) -> tuple[str, dict[str, Any]]:
    stage = payload.get("stage", payload.get("lifecycle_stage"))
    stage = _required_string(stage, "stage", path).lower()
    if stage not in _OBSERVED_STAGES:
        raise LifecycleMatrixInputError(
            f"{path}: stage must be one of {sorted(_OBSERVED_STAGES)}"
        )
    status = _required_string(payload.get("status"), "status", path).lower()
    if status not in _STATUSES:
        raise LifecycleMatrixInputError(f"{path}: unsupported status {status!r}")
    ref = payload.get("evidence_ref", payload.get("evidence_refs"))
    if isinstance(ref, str):
        refs = [ref.strip()] if ref.strip() else []
    elif isinstance(ref, list) and all(isinstance(item, str) and item.strip() for item in ref):
        refs = [item.strip() for item in ref]
    else:
        raise LifecycleMatrixInputError(f"{path}: evidence_ref(s) must be non-empty")
    if not refs:
        raise LifecycleMatrixInputError(f"{path}: evidence_ref(s) must be non-empty")
    record: dict[str, Any] = {"status": status, "evidence_refs": refs}
    digest = payload.get("digest", payload.get("evidence_digest"))
    if digest is not None:
        record["digest"] = _required_string(digest, "digest", path)
    note = payload.get("note")
    if note is not None:
        record["note"] = _required_string(note, "note", path)
    return stage, record


def build_lifecycle_matrix(
    artifact_paths: Iterable[str | Path], *, generated_at: str | None = None
) -> dict[str, Any]:
    """Aggregate terminal P1/P3/P4/P5 artifacts into the shared matrix schema.

    Every input must explicitly identify ``strategy_id`` (or ``id``),
    ``kind``, ``lineage``, ``stage``, ``status`` and an evidence reference.
    Duplicate strategy/stage inputs are rejected rather than silently choosing
    one.  The returned object is detached from the inputs and safe to serialize.
    """

    paths = [Path(item) for item in artifact_paths]
    if not paths:
        raise LifecycleMatrixInputError("at least one lifecycle artifact is required")
    entries: dict[str, dict[str, Any]] = {}
    for path in paths:
        payload = _read_artifact(path)
        strategy_id = _required_string(payload.get("strategy_id", payload.get("id")), "strategy_id", path)
        kind = _required_string(payload.get("kind"), "kind", path).lower()
        if kind not in {"strategy", "plugin", "portfolio"}:
            raise LifecycleMatrixInputError(f"{path}: unsupported kind {kind!r}")
        lineage = _required_string(payload.get("lineage"), "lineage", path)
        stage, record = _stage_record(payload, path)
        entry = entries.setdefault(
            strategy_id,
            {
                "id": strategy_id,
                "display_name": payload.get("display_name", strategy_id),
                "kind": kind,
                "lineage": lineage,
                "stages": {
                    name: {"status": "not_started", "evidence_refs": []}
                    for name in _STAGES
                },
                "blocking_reasons": [],
                "next_action": "等待生命周期证据。",
            },
        )
        if entry["kind"] != kind or entry["lineage"] != lineage:
            raise LifecycleMatrixInputError(f"{path}: identity conflicts for {strategy_id}")
        if entry["stages"][stage]["evidence_refs"]:
            raise LifecycleMatrixInputError(f"{path}: duplicate artifact for {strategy_id}/{stage}")
        entry["stages"][stage] = record
        reason = payload.get("blocking_reason")
        if reason is not None:
            entry["blocking_reasons"].append(_required_string(reason, "blocking_reason", path))
        next_action = payload.get("next_action")
        if next_action is not None:
            entry["next_action"] = _required_string(next_action, "next_action", path)

    for entry in entries.values():
        if not any(entry["stages"][stage]["status"] in {"parked", "deferred", "inconclusive"} for stage in _STAGES):
            entry["next_action"] = entry["next_action"] or "继续读取后续生命周期证据。"
    return {
        "schema_version": "strategy_lifecycle_matrix.v1",
        "generated_at": generated_at or date.today().isoformat(),
        "source_policy": "Read-only aggregation of terminal artifacts; never authorizes promotion or trading.",
        "entries": list(entries.values()),
    }

