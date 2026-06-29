"""Unified artifact helpers: hashing, JSON I/O, manifest building.

Previously duplicated across UsEquitySnapshotPipelines, HkEquitySnapshotPipelines,
CnEquitySnapshotPipelines, and MarketSignalSources.  New code should import
from here.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


def sha256_file(path: str | Path) -> str:
    """Compute the SHA-256 hex digest of a file (1 MiB block size)."""
    hasher = hashlib.sha256()
    with Path(path).open("rb") as fh:
        while True:
            chunk = fh.read(1024 * 1024)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()


def write_json(path: str | Path, payload: Mapping[str, Any], *, indent: int = 2) -> Path:
    """Write a JSON object to *path*, creating parent directories as needed.

    Returns the resolved *path* for chaining.
    """
    resolved = Path(path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(
        json.dumps(payload, ensure_ascii=False, indent=indent, sort_keys=True),
        encoding="utf-8",
    )
    return resolved


def load_json(path: str | Path | None) -> dict[str, Any]:
    """Load a JSON file, returning an empty dict when *path* is None or missing."""
    if not path:
        return {}
    resolved = Path(path)
    if not resolved.exists():
        return {}
    payload = json.loads(resolved.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError(f"JSON object expected: {resolved}")
    return dict(payload)


def default_config_sha256(*, profile: str, contract_version: str, config_name: str | None = None) -> str:
    """Compute a deterministic SHA-256 for a default (strategy-manifest) config.

    Used when no explicit config file is provided — the hash proves which
    profile + version combination was used.
    """
    payload = {
        "config_source": "strategy_manifest_default",
        "config_name": config_name or profile,
        "strategy_profile": profile,
        "contract_version": contract_version,
    }
    content = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return hashlib.sha256(content).hexdigest()


def resolve_dataframe_as_of(df: Any, *, columns: tuple[str, ...] = ("as_of", "snapshot_date", "date")) -> str | None:
    """Extract the latest ``as_of`` date from a DataFrame.

    Parameters
    ----------
    df :
        pandas DataFrame expected at runtime.
    columns :
        Column names to check, in priority order.

    Returns
    -------
    str | None
        ISO-format date string, or None if no date column was found.
    """
    import pandas as pd  # noqa: F811 — lazy import for optional dependency

    for column in columns:
        if column not in df.columns:
            continue
        values = pd.to_datetime(df[column], errors="coerce")
        if values.notna().any():
            return pd.Timestamp(values.max()).date().isoformat()
    return None


def json_safe(value: Any) -> Any:
    """Recursively convert a Python value to JSON-safe types.

    Handles numpy/pandas scalars, Timestamps, tuples, and nested mappings.
    """
    if isinstance(value, Mapping):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, tuple):
        return [json_safe(v) for v in value]
    if isinstance(value, list):
        return [json_safe(v) for v in value]
    import pandas as pd  # lazy import

    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass
    return value


RELEASE_MANIFEST_TYPE = "release"
FEATURE_SNAPSHOT_MANIFEST_TYPE = "feature_snapshot"
STRATEGY_PLUGIN_MANIFEST_TYPE = "strategy_plugin_release"


def write_release_manifest(
    artifact_type: str,
    *,
    output_dir: str | Path,
    profile: str,
    contract_version: str,
    schema_version: str,
    as_of: str | None,
    source_project: str,
    repository: str | None = None,
    git_sha: str | None = None,
    run_id: str | None = None,
    run_attempt: str | None = None,
    extra_metadata: Mapping[str, Any] | None = None,
) -> Path:
    """Write a release manifest JSON file for a set of artifacts.

    Copies all files in *output_dir* to a versioned ``releases/`` subdirectory
    and records SHA-256 digests.

    Parameters
    ----------
    artifact_type :
        A discriminator like ``"feature_snapshot"``, ``"strategy_plugin_signal"``.
    output_dir :
        Directory containing the artifacts to release.
    profile :
        Strategy profile name.
    contract_version :
        Version string for the artifact contract.
    schema_version :
        Schema version embedded in the artifacts.
    as_of :
        Optional ``as_of`` date.
    source_project :
        Source project / repository name.
    repository, git_sha, run_id, run_attempt :
        CI provenance metadata.
    extra_metadata :
        Additional key-value pairs merged into the manifest root.

    Returns
    -------
    Path
        Path to the written ``release_manifest.json``.
    """
    resolved_output = Path(output_dir)
    version_parts = [
        _safe_version_part(as_of) if as_of else None,
        _safe_version_part(run_id or (str(git_sha)[:12] if git_sha else "local")),
        f"attempt-{_safe_version_part(run_attempt)}" if run_attempt else None,
    ]
    version = "-".join(part for part in version_parts if part)

    release_dir = resolved_output / "releases" / version
    release_dir.mkdir(parents=True, exist_ok=True)

    release_artifacts: dict[str, dict[str, str]] = {}
    for source_path in sorted(path for path in resolved_output.iterdir() if path.is_file()):
        destination = release_dir / source_path.name
        shutil.copy2(source_path, destination)
        release_artifacts[source_path.name] = {
            "path": str(destination),
            "sha256": sha256_file(destination),
        }

    payload: dict[str, Any] = {
        "manifest_type": RELEASE_MANIFEST_TYPE,
        "artifact_type": artifact_type,
        "contract_version": contract_version,
        "schema_version": schema_version,
        "version": version,
        "strategy_profile": profile,
        "as_of": as_of,
        "source_project": source_project,
        "producer": {
            "repository": repository or source_project,
            "git_sha": git_sha or "",
            "github_run_id": run_id or "",
            "github_run_attempt": run_attempt or "",
        },
        "current_artifacts": {
            path.name: {
                "path": str(path),
                "sha256": sha256_file(path),
            }
            for path in sorted(resolved_output.iterdir())
            if path.is_file()
        },
        "release_artifacts": release_artifacts,
        "release_dir": str(release_dir),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    if extra_metadata:
        payload.update(extra_metadata)

    write_json(release_dir / "release_manifest.json", payload)
    return write_json(resolved_output / "release_manifest.json", payload)


def _safe_version_part(value: Any) -> str:
    text = str(value or "").strip()
    safe = "".join(char if char.isalnum() or char in {"-", "_", "."} else "-" for char in text)
    return safe.strip("-_. ") or "unknown"
