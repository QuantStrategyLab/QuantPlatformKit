"""Data manifest building — unified artifact metadata and release packaging.

Replaces duplicated logic in UsEquitySnapshotPipelines/artifacts.py,
HkEquitySnapshotPipelines/artifacts.py, and CnEquitySnapshotPipelines/artifacts.py.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from quant_platform_kit.common.artifacts import sha256_file, write_json
from quant_platform_kit.data.version import DataVersion


def build_artifact_record(
    path: str | Path,
    *,
    artifact_type: str = "data",
    version: DataVersion | None = None,
    extra_meta: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a single artifact record with provenance metadata.

    Parameters
    ----------
    path :
        Filesystem path to the artifact.
    artifact_type :
        Discriminator (e.g. 'feature_snapshot', 'ranking', 'signal_bundle').
    version :
        Optional structured version. If omitted, inferred from file timestamp.
    extra_meta :
        Additional key-value pairs merged into the record.
    """
    resolved = Path(path)
    record: dict[str, Any] = {
        "path": str(resolved),
        "artifact_type": artifact_type,
        "size_bytes": resolved.stat().st_size if resolved.exists() else 0,
    }
    if resolved.exists():
        record["sha256"] = sha256_file(resolved)
    if version is not None:
        record["version"] = version.full
        if version.sha256:
            record["sha256"] = version.sha256
    if extra_meta:
        record.update(extra_meta)
    return record


def write_artifact_manifest(
    artifacts: tuple[dict[str, Any], ...],
    *,
    output_path: str | Path,
    source_project: str = "",
    profile: str = "",
    manifest_type: str = "artifact_manifest",
) -> Path:
    """Write an artifact manifest file listing all artifacts with metadata.

    Parameters
    ----------
    artifacts :
        Tuple of artifact records from :func:`build_artifact_record`.
    output_path :
        Where to write the manifest JSON.
    source_project :
        Name of the producing repository/pipeline.
    profile :
        Strategy profile name if applicable.
    manifest_type :
        Discriminator for the manifest (default 'artifact_manifest').
    """
    payload: dict[str, Any] = {
        "manifest_type": manifest_type,
        "source_project": source_project or "QuantStrategyLab",
        "profile": profile,
        "artifact_count": len(artifacts),
        "artifacts": list(artifacts),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    return write_json(output_path, payload)


def write_data_release(
    artifacts: tuple[dict[str, Any], ...],
    *,
    output_dir: str | Path,
    version: DataVersion,
    source_project: str,
    profile: str = "",
) -> Path:
    """Package artifacts into a versioned release directory and write manifest.

    Parameters
    ----------
    artifacts :
        Artifact records (see :func:`build_artifact_record`).
    output_dir :
        Root output directory.
    version :
        Release version identifier.
    source_project :
        Source repository name.
    profile :
        Optional strategy profile.

    Returns
    -------
    Path
        Path to the written release manifest.
    """
    root = Path(output_dir)
    release_dir = root / "releases" / version.full
    release_dir.mkdir(parents=True, exist_ok=True)

    manifest = write_artifact_manifest(
        artifacts,
        output_path=release_dir / "manifest.json",
        source_project=source_project,
        profile=profile,
        manifest_type="data_release",
    )

    # Also write a current symlink-like pointer
    pointer_payload = {
        "current_version": version.full,
        "release_dir": str(release_dir),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    write_json(root / "current_release.json", pointer_payload)

    return manifest
