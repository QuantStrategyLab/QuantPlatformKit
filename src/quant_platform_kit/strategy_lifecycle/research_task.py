"""Build the bounded ``qsl.research_task.v1`` records emitted by the watcher.

The record is intentionally data-free: it binds a future offline experiment to
already-sanitized P1/P2/P3 digests, but carries neither a parameter body nor an
execution capability.  The control-console consumer independently revalidates
the same wire contract before displaying a task.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from datetime import datetime
from typing import Any, Mapping


SCHEMA = "qsl.research_task.v1"
_IDENTITY = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$")
_REPOSITORY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*/[A-Za-z0-9][A-Za-z0-9_.-]*$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_REVISION = re.compile(r"^[0-9a-f]{40}$")
_TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_CANDIDATE_KINDS = frozenset({"individual", "portfolio", "plugin"})
_DOMAINS = frozenset({"us_equity", "hk_equity", "cn_equity", "crypto"})
_EVIDENCE_FIELDS = frozenset({"p1_input_digest", "p2_config_digest", "p3_evidence_id", "strategy_revision", "producer_revision"})
class ResearchTaskError(ValueError):
    """Raised when the watcher cannot prove a task is bounded research."""


def canonical_json(value: object) -> str:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ResearchTaskError("research task must use finite JSON values") from exc


def calculate_task_sha256(payload: Mapping[str, Any]) -> str:
    material = copy.deepcopy(dict(payload))
    material.pop("task_sha256", None)
    return hashlib.sha256(canonical_json(material).encode("utf-8")).hexdigest()


def _identity(value: object, label: str) -> str:
    if not isinstance(value, str) or not _IDENTITY.fullmatch(value):
        raise ResearchTaskError(f"{label} must be a stable identity")
    return value


def _sha256(value: object, label: str) -> str:
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise ResearchTaskError(f"{label} must be a lowercase SHA-256")
    return value


def _revision(value: object, label: str) -> str:
    if not isinstance(value, str) or not _REVISION.fullmatch(value):
        raise ResearchTaskError(f"{label} must be a 40-character revision")
    return value


def _timestamp(value: object, label: str) -> str:
    if not isinstance(value, str) or not _TIMESTAMP.fullmatch(value):
        raise ResearchTaskError(f"{label} must be a UTC timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ResearchTaskError(f"{label} must be a UTC timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ResearchTaskError(f"{label} must be a UTC timestamp")
    return value


def _evidence(value: object) -> dict[str, str]:
    if not isinstance(value, Mapping) or set(value) != _EVIDENCE_FIELDS:
        raise ResearchTaskError("research task evidence is incomplete")
    return {
        "p1_input_digest": _sha256(value["p1_input_digest"], "evidence.p1_input_digest"),
        "p2_config_digest": _sha256(value["p2_config_digest"], "evidence.p2_config_digest"),
        "p3_evidence_id": _sha256(value["p3_evidence_id"], "evidence.p3_evidence_id"),
        "strategy_revision": _revision(value["strategy_revision"], "evidence.strategy_revision"),
        "producer_revision": _revision(value["producer_revision"], "evidence.producer_revision"),
    }


def build_strategy_diagnosis_task(
    *,
    event_key: object,
    created_at: object,
    candidate_id: object,
    candidate_kind: object,
    domain: object,
    strategy_repository: object,
    evidence: object,
    parameter_bounds_sha256: str | None = None,
) -> dict[str, Any]:
    """Make one deterministic, bounded diagnosis task for a verified finding."""
    if not isinstance(event_key, str) or not re.fullmatch(r"[0-9a-f]{12}", event_key):
        raise ResearchTaskError("event_key is invalid")
    candidate = _identity(candidate_id, "candidate_id")
    created = _timestamp(created_at, "created_at")
    if candidate_kind not in _CANDIDATE_KINDS:
        raise ResearchTaskError("candidate_kind is unsupported")
    if domain not in _DOMAINS:
        raise ResearchTaskError("domain is unsupported")
    if not isinstance(strategy_repository, str) or not _REPOSITORY.fullmatch(strategy_repository):
        raise ResearchTaskError("strategy repository is invalid")
    verified_evidence = _evidence(evidence)
    if parameter_bounds_sha256 is not None:
        _sha256(parameter_bounds_sha256, "parameter_bounds_sha256")
    task: dict[str, Any] = {
        "schema": SCHEMA,
        "task_id": f"watcher-{event_key}",
        "created_at": created,
        "digest_algorithm": "sha256",
        "task_type": "strategy_diagnosis",
        "target": {
            "candidate_id": candidate,
            "candidate_kind": candidate_kind,
            "domain": domain,
            "repository": strategy_repository,
            "strategy_revision": verified_evidence["strategy_revision"],
        },
        "evidence": {
            "p1_input_digest": verified_evidence["p1_input_digest"],
            "p2_config_digest": verified_evidence["p2_config_digest"],
            "p3_evidence_id": verified_evidence["p3_evidence_id"],
            "producer_revision": verified_evidence["producer_revision"],
        },
        "experiment": {
            "objective": "diagnose_degradation",
            "hypothesis": "A verified P3 observation crossed a degradation threshold; diagnose it with one bounded offline comparison without changing active parameters.",
            "parameter_bounds_sha256": parameter_bounds_sha256,
            "max_runs": 1,
            "max_wall_seconds": 3600,
        },
        "authority": {
            "research_only": True,
            "no_order": True,
            "size_zero_required": True,
            "p4_p5_p6_authorized": False,
        },
    }
    task["task_sha256"] = calculate_task_sha256(task)
    return task


def validate_strategy_diagnosis_task(
    value: Mapping[str, Any], *, allowed_parameter_bounds: frozenset[str | None] = frozenset({None}),
) -> dict[str, Any]:
    """Fail closed unless ``value`` is the exact bounded watcher task shape.

    Consumers that trigger any automatic follow-up must validate the complete
    task, rather than trusting a task ID or a digest copied from an Issue.
    """
    if not isinstance(value, Mapping):
        raise ResearchTaskError("research task must be an object")
    task = copy.deepcopy(dict(value))
    expected_fields = {
        "schema",
        "task_id",
        "created_at",
        "digest_algorithm",
        "task_type",
        "target",
        "evidence",
        "experiment",
        "authority",
        "task_sha256",
    }
    if set(task) != expected_fields:
        raise ResearchTaskError("research task has unexpected fields")
    if task.get("schema") != SCHEMA or task.get("digest_algorithm") != "sha256":
        raise ResearchTaskError("research task schema is unsupported")
    task_id = task.get("task_id")
    if not isinstance(task_id, str) or re.fullmatch(r"watcher-[0-9a-f]{12}", task_id) is None:
        raise ResearchTaskError("research task ID is invalid")
    created_at = _timestamp(task.get("created_at"), "created_at")
    if task.get("task_type") != "strategy_diagnosis":
        raise ResearchTaskError("research task type is unsupported")

    target = task.get("target")
    if not isinstance(target, Mapping) or set(target) != {
        "candidate_id",
        "candidate_kind",
        "domain",
        "repository",
        "strategy_revision",
    }:
        raise ResearchTaskError("research task target is incomplete")
    candidate_id = _identity(target.get("candidate_id"), "target.candidate_id")
    candidate_kind = target.get("candidate_kind")
    if candidate_kind not in _CANDIDATE_KINDS:
        raise ResearchTaskError("target.candidate_kind is unsupported")
    domain = target.get("domain")
    if domain not in _DOMAINS:
        raise ResearchTaskError("target.domain is unsupported")
    repository = target.get("repository")
    if not isinstance(repository, str) or _REPOSITORY.fullmatch(repository) is None:
        raise ResearchTaskError("target.repository is invalid")
    strategy_revision = _revision(target.get("strategy_revision"), "target.strategy_revision")

    raw_evidence = task.get("evidence")
    expected_evidence_fields = _EVIDENCE_FIELDS - {"strategy_revision"}
    if not isinstance(raw_evidence, Mapping) or set(raw_evidence) != expected_evidence_fields:
        raise ResearchTaskError("research task evidence is incomplete")
    evidence = _evidence({**dict(raw_evidence), "strategy_revision": strategy_revision})
    if evidence["strategy_revision"] != strategy_revision:
        raise ResearchTaskError("research task strategy revision is not bound to evidence")

    experiment = task.get("experiment")
    expected_experiment = {
        "objective",
        "hypothesis",
        "parameter_bounds_sha256",
        "max_runs",
        "max_wall_seconds",
    }
    if not isinstance(experiment, Mapping) or set(experiment) != expected_experiment:
        raise ResearchTaskError("research task experiment is incomplete")
    parameter_bounds_sha256 = experiment.get("parameter_bounds_sha256")
    if parameter_bounds_sha256 is not None:
        _sha256(parameter_bounds_sha256, "experiment.parameter_bounds_sha256")
    if (
        experiment.get("objective") != "diagnose_degradation"
        or experiment.get("hypothesis")
        != "A verified P3 observation crossed a degradation threshold; diagnose it with one bounded offline comparison without changing active parameters."
        or parameter_bounds_sha256 not in allowed_parameter_bounds
        or type(experiment.get("max_runs")) is not int
        or experiment.get("max_runs") != 1
        or type(experiment.get("max_wall_seconds")) is not int
        or experiment.get("max_wall_seconds") != 3600
    ):
        raise ResearchTaskError("research task experiment exceeds the bounded diagnosis contract")

    authority = task.get("authority")
    expected_authority = {
        "research_only": True,
        "no_order": True,
        "size_zero_required": True,
        "p4_p5_p6_authorized": False,
    }
    if authority != expected_authority or any(type(authority.get(key)) is not bool for key in expected_authority):
        raise ResearchTaskError("research task authority is not bounded")
    supplied_digest = _sha256(task.get("task_sha256"), "task_sha256")
    if supplied_digest != calculate_task_sha256(task):
        raise ResearchTaskError("research task digest does not match canonical content")

    return {
        "schema": SCHEMA,
        "task_id": task_id,
        "created_at": created_at,
        "digest_algorithm": "sha256",
        "task_type": "strategy_diagnosis",
        "target": {
            "candidate_id": candidate_id,
            "candidate_kind": candidate_kind,
            "domain": domain,
            "repository": repository,
            "strategy_revision": strategy_revision,
        },
        "evidence": {
            "p1_input_digest": evidence["p1_input_digest"],
            "p2_config_digest": evidence["p2_config_digest"],
            "p3_evidence_id": evidence["p3_evidence_id"],
            "producer_revision": evidence["producer_revision"],
        },
        "experiment": dict(experiment),
        "authority": dict(expected_authority),
        "task_sha256": supplied_digest,
    }


__all__ = ["ResearchTaskError", "SCHEMA", "build_strategy_diagnosis_task",
           "calculate_task_sha256", "canonical_json", "validate_strategy_diagnosis_task"]
