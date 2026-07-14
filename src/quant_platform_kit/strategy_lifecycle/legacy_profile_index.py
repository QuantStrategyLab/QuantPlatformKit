"""Offline schema and inventory transformation for legacy backtest prefixes.

This module is deliberately disconnected from ``PerformanceStore``.  Callers must
provide an explicit synthetic directory or exported key list; no production
storage, credentials, network client, or implicit filesystem scan is used.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from quant_platform_kit.strategy_lifecycle.capabilities import canonical_profile_id

SCHEMA_VERSION = "legacy_profile_prefix_index.v1"
_MAX_SEGMENT = 100


class IndexValidationError(ValueError):
    """Raised when an index or supplied inventory violates the safe schema."""

    def __init__(self) -> None:
        super().__init__("invalid legacy profile index")


def _safe_prefix(value: str) -> str:
    if not isinstance(value, str) or not value or len(value) > _MAX_SEGMENT:
        raise IndexValidationError()
    if value in {".", ".."} or "/" in value or "\\" in value or value.startswith("/"):
        raise IndexValidationError()
    if any(char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-" for char in value):
        raise IndexValidationError()
    if value.strip() != value or value != value.strip("-._"):
        raise IndexValidationError()
    return value


def _canonical(value: str) -> str:
    try:
        return canonical_profile_id(value)
    except Exception:
        return value


def _digest(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def build_index_from_keys(
    keys: Iterable[str], *, backend: str, complete: bool, source_label: str,
) -> dict[str, Any]:
    """Transform an explicitly supplied exported key list into a deterministic index."""
    if (
        isinstance(keys, (str, bytes))
        or not isinstance(backend, str)
        or not backend
        or type(complete) is not bool
        or not isinstance(source_label, str)
        or not source_label
    ):
        raise IndexValidationError()
    observations: dict[tuple[str, str], set[str]] = defaultdict(set)
    for key in keys:
        if not isinstance(key, str) or "\\" in key or key.startswith("/"):
            raise IndexValidationError()
        parts = key.split("/")
        if parts[0] != "backtest":
            continue
        if len(parts) < 4:
            raise IndexValidationError()
        domain = _safe_prefix(parts[1])
        prefix = _safe_prefix(parts[2])
        for artifact_segment in parts[3:]:
            _safe_prefix(artifact_segment)
        observations[(domain, _canonical(prefix))].add(prefix)

    entries: dict[str, dict[str, Any]] = {}
    collisions: list[dict[str, Any]] = []
    for (domain, canonical), prefixes in sorted(observations.items()):
        ordered = sorted(prefixes)
        domain_entries = entries.setdefault(domain, {})
        domain_entries[canonical] = {
            "prefixes": ordered,
            "backend_prefixes": {backend: ordered},
        }
        if len(ordered) > 1:
            collisions.append({"domain": domain, "canonical_profile": canonical, "prefixes": ordered})

    body: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "entries": entries,
        "collisions": collisions,
        "inventory": {
            "backend": backend,
            "backends": [backend],
            "source_label": source_label,
            "complete": bool(complete),
        },
    }
    body["inventory"]["digest"] = _digest(body)
    return body


def build_index_from_local_fixture(root: Path, *, source_label: str) -> dict[str, Any]:
    """Read an explicitly supplied synthetic fixture directory only."""
    if not isinstance(root, Path) or not root.exists() or not root.is_dir():
        raise IndexValidationError()
    keys = [path.relative_to(root).as_posix() for path in sorted(root.rglob("*.json"))]
    return build_index_from_keys(keys, backend="local_fixture", complete=True, source_label=source_label)


def index_from_dict(data: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and return a schema-shaped index without echoing invalid payloads."""
    try:
        if not isinstance(data, Mapping) or data.get("schema_version") != SCHEMA_VERSION:
            raise IndexValidationError()
        entries = data["entries"]
        collisions = data["collisions"]
        inventory = data["inventory"]
        if not isinstance(entries, Mapping) or not isinstance(collisions, list) or not isinstance(inventory, Mapping):
            raise IndexValidationError()
        declared_backend = inventory.get("backend")
        declared_backends = inventory.get("backends", [declared_backend])
        if not isinstance(declared_backends, list) or not declared_backends or any(
            not isinstance(backend, str) or not backend for backend in declared_backends
        ) or len(set(declared_backends)) != len(declared_backends):
            raise IndexValidationError()
        if declared_backend not in declared_backends:
            raise IndexValidationError()
        expected_collisions: list[dict[str, Any]] = []
        for domain, profiles in entries.items():
            _safe_prefix(domain)
            if not isinstance(profiles, Mapping):
                raise IndexValidationError()
            for canonical, entry in profiles.items():
                _safe_prefix(str(canonical))
                if not isinstance(entry, Mapping) or not isinstance(entry["prefixes"], list):
                    raise IndexValidationError()
                top_prefixes = entry["prefixes"]
                normalized_top = sorted({_safe_prefix(prefix) for prefix in top_prefixes})
                if top_prefixes != normalized_top:
                    raise IndexValidationError()
                if any(_canonical(prefix) != canonical for prefix in normalized_top):
                    raise IndexValidationError()
                backend_prefixes = entry.get("backend_prefixes")
                if not isinstance(backend_prefixes, Mapping):
                    raise IndexValidationError()
                if set(backend_prefixes) != set(declared_backends):
                    raise IndexValidationError()
                union: set[str] = set()
                for backend, backend_values in backend_prefixes.items():
                    if not isinstance(backend, str) or not backend or not isinstance(backend_values, list):
                        raise IndexValidationError()
                    normalized_backend = sorted({_safe_prefix(prefix) for prefix in backend_values})
                    if backend_values != normalized_backend:
                        raise IndexValidationError()
                    union.update(normalized_backend)
                if normalized_top != sorted(union):
                    raise IndexValidationError()
                if len(normalized_top) > 1:
                    expected_collisions.append(
                        {"domain": domain, "canonical_profile": canonical, "prefixes": normalized_top}
                    )
        if (
            not isinstance(declared_backend, str)
            or not declared_backend
            or not isinstance(inventory.get("source_label"), str)
            or not inventory.get("source_label")
            or not isinstance(inventory.get("complete"), bool)
            or not isinstance(inventory.get("digest"), str)
            or not inventory.get("digest")
        ):
            raise IndexValidationError()
        if collisions != sorted(expected_collisions, key=lambda item: (item["domain"], item["canonical_profile"])):
            raise IndexValidationError()
        expected = dict(data)
        expected_inventory = dict(inventory)
        expected_inventory.pop("digest", None)
        expected["inventory"] = expected_inventory
        if _digest(expected) != inventory["digest"]:
            raise IndexValidationError()
        return dict(data)
    except IndexValidationError:
        raise
    except Exception as exc:
        raise IndexValidationError() from exc
