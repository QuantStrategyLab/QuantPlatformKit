"""Shared snapshot and pipeline contracts used across QuantStrategyLab pipelines.

This module consolidates common data types that were previously duplicated
across UsEquitySnapshotPipelines, HkEquitySnapshotPipelines, and
CnEquitySnapshotPipelines.  New pipeline implementations should import
from here rather than redefining these types.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping


@dataclass(frozen=True)
class SnapshotProfileContract:
    """Contract binding a strategy profile to its feature-snapshot artifact names.

    Every feature-snapshot pipeline (US, HK, CN) registers one contract per
    profile so consumers can discover the canonical artifact file names without
    hard-coding them.
    """

    profile: str
    display_name: str
    contract_version: str
    snapshot_filename: str
    manifest_filename: str
    ranking_filename: str
    release_summary_filename: str = "release_status_summary.json"
    legacy_aliases: tuple[str, ...] = ()
    current_gcs_prefix_hint: str | None = None
    neutral_gcs_prefix_hint: str | None = None
    manifest_required_by_runtime: bool = False

    def artifact_paths(self, output_dir: str | Path) -> dict[str, Path]:
        root = Path(output_dir)
        return {
            "snapshot": root / self.snapshot_filename,
            "manifest": root / self.manifest_filename,
            "ranking": root / self.ranking_filename,
            "release_summary": root / self.release_summary_filename,
        }


@dataclass(frozen=True)
class SnapshotBuildResult:
    """Result of a single snapshot build cycle.

    Bundles the snapshot DataFrame, ranking DataFrame, artifact paths, and
    a human-readable description for downstream consumers.
    """

    snapshot: Any  # pandas.DataFrame at runtime
    ranking: Any  # pandas.DataFrame at runtime
    artifact_paths: dict[str, Path]
    description: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)


def resolve_snapshot_profile(
    profile: str,
    *,
    contracts: Mapping[str, SnapshotProfileContract],
    aliases: Mapping[str, str] | None = None,
) -> SnapshotProfileContract:
    """Resolve a profile string to its contract, supporting aliases.

    Parameters
    ----------
    profile :
        Profile name or alias to resolve.
    contracts :
        Canonical profile → contract mapping.
    aliases :
        Optional alias → canonical profile mapping.  When provided, an
        unknown profile is looked up in this map before raising.

    Returns
    -------
    SnapshotProfileContract

    Raises
    ------
    ValueError
        If the profile cannot be resolved.
    """
    normalized = str(profile or "").strip().lower().replace("-", "_")
    if not normalized:
        raise ValueError("Profile name must not be empty")

    # Direct hit
    contract = contracts.get(normalized)
    if contract is not None:
        return contract

    # Try legacy alias
    if aliases is not None:
        canonical = aliases.get(normalized)
        if canonical is not None:
            candidate = contracts.get(canonical)
            if candidate is not None:
                return candidate

    known = ", ".join(sorted(contracts))
    raise ValueError(f"Unknown snapshot profile {profile!r}; known profiles: {known}")
