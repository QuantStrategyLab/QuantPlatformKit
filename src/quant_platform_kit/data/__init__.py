"""Data version management — artifact versioning, manifest building, and release tracking.

Consolidates logic previously duplicated across UsEquitySnapshotPipelines,
HkEquitySnapshotPipelines, CnEquitySnapshotPipelines, and CryptoLivePoolPipelines.
"""

from quant_platform_kit.data.manifest import (
    build_artifact_record,
    write_artifact_manifest,
    write_data_release,
)
from quant_platform_kit.data.version import (
    DataVersion,
    latest_version,
    resolve_version,
    semver_version,
)

__all__ = [
    "DataVersion",
    "build_artifact_record",
    "latest_version",
    "resolve_version",
    "semver_version",
    "write_artifact_manifest",
    "write_data_release",
]
