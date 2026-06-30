"""Data version types and resolution utilities.

Provides a standard versioning scheme for data artifacts across all
QuantStrategyLab pipelines.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Mapping


@dataclass(frozen=True)
class DataVersion:
    """Structured version identifier for a data artifact.

    Supports semantic versioning and calendar versioning. The canonical
    form is ``major.minor.patch``, with an optional date-based qualifier.
    """

    major: int
    minor: int = 0
    patch: int = 0
    as_of: str | None = None  # ISO date
    source: str = ""
    sha256: str = ""

    @property
    def semver(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"

    @property
    def full(self) -> str:
        parts = [self.semver]
        if self.as_of:
            parts.append(self.as_of)
        if self.source:
            parts.append(self.source)
        return "+".join(parts)

    def __str__(self) -> str:
        return self.full


def semver_version(version_str: str) -> DataVersion:
    """Parse a semver string like '1.2.3' into a DataVersion."""
    parts = str(version_str).strip().split(".", 2)
    return DataVersion(
        major=int(parts[0]) if len(parts) > 0 else 0,
        minor=int(parts[1]) if len(parts) > 1 else 0,
        patch=int(parts[2]) if len(parts) > 2 else 0,
    )


def resolve_version(
    artifact_meta: Mapping[str, Any],
    *,
    fallback: DataVersion | None = None,
) -> DataVersion:
    """Extract version information from artifact metadata.

    Looks for keys in priority order: ``contract_version``, ``schema_version``,
    ``version``, ``data_version``.
    """
    for key in ("contract_version", "schema_version", "version", "data_version"):
        raw = artifact_meta.get(key)
        if raw is not None:
            return DataVersion(
                major=0, minor=0, patch=0,
                as_of=artifact_meta.get("as_of") or artifact_meta.get("generated_at"),
                source=str(raw),
                sha256=artifact_meta.get("sha256") or artifact_meta.get("snapshot_sha256") or "",
            )
    if fallback is not None:
        return fallback
    return DataVersion(major=0)


def latest_version(versions: tuple[DataVersion, ...]) -> DataVersion | None:
    """Select the latest version from a collection.

    Compares by semver, then by as_of date.
    """
    if not versions:
        return None
    best = versions[0]
    for v in versions[1:]:
        if (v.major, v.minor, v.patch) > (best.major, best.minor, best.patch):
            best = v
        elif (v.major, v.minor, v.patch) == (best.major, best.minor, best.patch):
            if v.as_of and best.as_of and v.as_of > best.as_of:
                best = v
    return best
