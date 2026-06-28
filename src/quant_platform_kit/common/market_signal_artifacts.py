"""Materialization helpers for external market signal artifact trees."""

from __future__ import annotations

import hashlib
import json
import posixpath
import warnings
from pathlib import Path
from typing import Any, Iterable, Mapping

from .strategy_plugin_artifacts import download_remote_object, parse_cloud_uri


MARKET_SIGNAL_ARTIFACT_LINK_FIELDS = frozenset(
    {
        "bundle_path",
        "catalog_path",
        "consumer_contract_registry_manifest_path",
        "handoff_manifest_path",
        "quality_report_path",
        "registry_path",
        "signal_bundle_manifest_path",
        "source_family_catalog_manifest_path",
    }
)


def materialize_market_signal_artifact_tree(
    reference: str,
    *,
    cache_dir: Path,
    client_factory: Any = None,
    link_fields: Iterable[str] | None = None,
) -> tuple[Path, dict[str, Any]]:
    """Return a local path for a market signal artifact and its linked JSON tree."""

    raw_reference = _required_string(reference, field_name="reference")
    if not raw_reference.startswith("gs://"):
        local_path = Path(raw_reference).expanduser()
        return local_path, {
            "source_uri": None,
            "local_path": raw_reference,
            "cache_dir": None,
            "materialized_count": 0,
            "materialized_paths": (),
        }

    fields = frozenset(link_fields or MARKET_SIGNAL_ARTIFACT_LINK_FIELDS)
    cache_root = cache_root_for_market_signal_artifact_tree(
        raw_reference,
        cache_dir=cache_dir,
    )
    visited: dict[str, Path] = {}
    _materialize_cloud_json_tree(
        raw_reference,
        cache_root=cache_root,
        client_factory=client_factory,
        link_fields=fields,
        visited=visited,
    )
    _, object_name = parse_cloud_uri(raw_reference)
    local_path = local_path_for_cloud_object(cache_root, object_name)
    return local_path, {
        "source_uri": raw_reference,
        "local_path": str(local_path),
        "cache_dir": str(cache_root),
        "materialized_count": len(visited),
        "materialized_paths": tuple(str(path) for path in visited.values()),
    }


def cache_root_for_market_signal_artifact_tree(reference: str, *, cache_dir: Path) -> Path:
    raw_reference = _required_string(reference, field_name="reference")
    digest = hashlib.sha256(raw_reference.encode("utf-8")).hexdigest()[:16]
    return cache_dir / digest


def local_path_for_cloud_object(cache_root: Path, object_name: str) -> Path:
    """Resolve a cloud object key to a local cache path."""
    raw_object_name = _required_string(object_name, field_name="object_name")
    if raw_object_name.startswith("/"):
        raise ValueError(f"Cloud object name must be relative: {raw_object_name}")
    normalized = posixpath.normpath(raw_object_name)
    if normalized in {"", ".", ".."} or normalized.startswith("../"):
        raise ValueError(f"Cloud object name escapes the cache root: {raw_object_name}")
    return cache_root.joinpath(*normalized.split("/"))


def resolve_cloud_artifact_reference(base_uri: str, reference: str) -> str:
    """Resolve a relative artifact reference against a cloud base URI."""
    raw_reference = _required_string(reference, field_name="reference")
    if raw_reference.startswith("gs://") or raw_reference.startswith("s3://"):
        parse_cloud_uri(raw_reference)
        return raw_reference
    if "://" in raw_reference:
        raise ValueError(f"Unsupported market signal artifact reference: {raw_reference}")
    if raw_reference.startswith("/"):
        raise ValueError(
            "Cloud market signal artifacts must use relative linked paths or gs:///s3:// URIs: "
            f"{raw_reference}"
        )

    bucket_name, object_name = parse_cloud_uri(base_uri)
    base_dir = posixpath.dirname(object_name)
    resolved = posixpath.normpath(posixpath.join(base_dir, raw_reference))
    if resolved in {"", ".", ".."} or resolved.startswith("../"):
        raise ValueError(
            "Cloud market signal artifact reference escapes the bucket root: "
            f"{raw_reference}"
        )
    scheme = base_uri.split("://")[0]
    return f"{scheme}://{bucket_name}/{resolved}"


def _materialize_cloud_json_tree(
    uri: str,
    *,
    cache_root: Path,
    client_factory: Any,
    link_fields: frozenset[str],
    visited: dict[str, Path],
) -> None:
    if uri in visited:
        return

    _, object_name = parse_cloud_uri(uri)
    local_path = local_path_for_cloud_object(cache_root, object_name)
    download_remote_object(uri, local_path, client_factory=client_factory)
    visited[uri] = local_path

    payload = _read_json_object(local_path)
    if payload is None:
        return
    for linked_uri in _iter_linked_cloud_artifact_uris(
        payload,
        base_uri=uri,
        link_fields=link_fields,
    ):
        _materialize_cloud_json_tree(
            linked_uri,
            cache_root=cache_root,
            client_factory=client_factory,
            link_fields=link_fields,
            visited=visited,
        )


def _read_json_object(path: Path) -> Mapping[str, Any] | list[Any] | None:
    if path.suffix.lower() != ".json":
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON market signal artifact: {path}") from exc
    if not isinstance(payload, (dict, list)):
        return None
    return payload


def _iter_linked_cloud_artifact_uris(
    payload: Any,
    *,
    base_uri: str,
    link_fields: frozenset[str],
) -> Iterable[str]:
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            if key in link_fields and isinstance(value, str) and value.strip():
                yield resolve_cloud_artifact_reference(base_uri, value.strip())
            yield from _iter_linked_cloud_artifact_uris(
                value,
                base_uri=base_uri,
                link_fields=link_fields,
            )
    elif isinstance(payload, list):
        for item in payload:
            yield from _iter_linked_cloud_artifact_uris(
                item,
                base_uri=base_uri,
                link_fields=link_fields,
            )


def _required_string(value: Any, *, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field_name} must be a non-empty string")
    return text


# ──────────────────────────────────────────────────────────────────────
#  Deprecated aliases — kept for backward compatibility
# ──────────────────────────────────────────────────────────────────────


def local_path_for_gcs_object(cache_root: Path, object_name: str) -> Path:
    warnings.warn(
        "local_path_for_gcs_object is deprecated, use local_path_for_cloud_object",
        DeprecationWarning,
        stacklevel=2,
    )
    return local_path_for_cloud_object(cache_root, object_name)


def resolve_gcs_artifact_reference(base_uri: str, reference: str) -> str:
    warnings.warn(
        "resolve_gcs_artifact_reference is deprecated, use resolve_cloud_artifact_reference",
        DeprecationWarning,
        stacklevel=2,
    )
    return resolve_cloud_artifact_reference(base_uri, reference)
