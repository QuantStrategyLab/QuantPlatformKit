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
from quant_platform_kit.data.multisource_assurance import (
    DATA_ASSURANCE_STATUS_DEGRADED,
    DATA_ASSURANCE_STATUS_PARKED,
    DATA_ASSURANCE_STATUS_VERIFIED,
    MULTISOURCE_DAILY_BAR_ASSURANCE_SCHEMA_VERSION,
    SOURCE_OBSERVATION_INVALID,
    SOURCE_OBSERVATION_MISSING,
    SOURCE_OBSERVATION_READY,
    SOURCE_OBSERVATION_UNAVAILABLE,
    DailyBar,
    DailyBarSourceObservation,
    DailyBarSourceSnapshot,
    MultiSourceDailyBarAssurance,
    MultiSourceDailyBarPolicy,
    assess_multisource_daily_bars,
)

__all__ = [
    "DataVersion",
    "DATA_ASSURANCE_STATUS_DEGRADED",
    "DATA_ASSURANCE_STATUS_PARKED",
    "DATA_ASSURANCE_STATUS_VERIFIED",
    "MULTISOURCE_DAILY_BAR_ASSURANCE_SCHEMA_VERSION",
    "SOURCE_OBSERVATION_INVALID",
    "SOURCE_OBSERVATION_MISSING",
    "SOURCE_OBSERVATION_READY",
    "SOURCE_OBSERVATION_UNAVAILABLE",
    "DailyBar",
    "DailyBarSourceObservation",
    "DailyBarSourceSnapshot",
    "MultiSourceDailyBarAssurance",
    "MultiSourceDailyBarPolicy",
    "assess_multisource_daily_bars",
    "build_artifact_record",
    "latest_version",
    "resolve_version",
    "semver_version",
    "write_artifact_manifest",
    "write_data_release",
]
