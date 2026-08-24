"""Fail-closed assurance for independently acquired daily market data.

The contract in this module deliberately has no HTTP, broker, storage, or
strategy dependency.  A market-data adapter produces one immutable source
snapshot per provider; this module only decides whether those snapshots agree
well enough to be used as evidence.  It never selects one provider silently.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from hashlib import sha256
import json
from math import isfinite
import re
from typing import Any, Iterable


MULTISOURCE_DAILY_BAR_ASSURANCE_SCHEMA_VERSION = "qpk.multisource_daily_bar_assurance.v1"

DATA_ASSURANCE_STATUS_VERIFIED = "VERIFIED"
DATA_ASSURANCE_STATUS_DEGRADED = "DEGRADED"
DATA_ASSURANCE_STATUS_PARKED = "PARKED"

SOURCE_OBSERVATION_READY = "READY"
SOURCE_OBSERVATION_UNAVAILABLE = "UNAVAILABLE"
SOURCE_OBSERVATION_INVALID = "INVALID"
SOURCE_OBSERVATION_MISSING = "MISSING"

_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{1,127}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_SOURCE_OBSERVATION_STATUSES = frozenset(
    {SOURCE_OBSERVATION_READY, SOURCE_OBSERVATION_UNAVAILABLE, SOURCE_OBSERVATION_INVALID}
)


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")


def _digest(value: object) -> str:
    return sha256(_canonical_bytes(value)).hexdigest()


def _require_identifier(value: object, *, field_name: str, upper: bool = False) -> str:
    text = str(value or "").strip()
    if upper:
        text = text.upper()
    if not _IDENTIFIER_RE.fullmatch(text):
        raise ValueError(f"{field_name} must be a stable identifier")
    return text


def _require_date(value: object, *, field_name: str) -> str:
    text = str(value or "").strip()
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError as exc:
        raise ValueError(f"{field_name} must be an ISO-8601 date") from exc


def _require_sha256(value: object, *, field_name: str) -> str:
    text = str(value or "").strip().lower().removeprefix("sha256:")
    if not _SHA256_RE.fullmatch(text):
        raise ValueError(f"{field_name} must be a SHA-256 digest")
    return text


def _require_nonnegative_float(value: object, *, field_name: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be a finite number") from exc
    if not isfinite(number) or number < 0:
        raise ValueError(f"{field_name} must be a non-negative finite number")
    return number


def _relative_delta(left: float, right: float) -> float:
    denominator = max(abs(left), abs(right), 1e-12)
    return abs(left - right) / denominator


@dataclass(frozen=True)
class DailyBar:
    """One normalized regular-session daily OHLCV bar."""

    session_date: str
    open: float
    high: float
    low: float
    close: float
    volume: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "session_date", _require_date(self.session_date, field_name="session_date"))
        for field_name in ("open", "high", "low", "close", "volume"):
            object.__setattr__(
                self,
                field_name,
                _require_nonnegative_float(getattr(self, field_name), field_name=field_name),
            )
        if self.low > min(self.open, self.close) or self.high < max(self.open, self.close):
            raise ValueError("daily bar OHLC relationship is invalid")

    def to_dict(self) -> dict[str, object]:
        return {
            "session_date": self.session_date,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
        }


@dataclass(frozen=True)
class DailyBarSourceSnapshot:
    """One source-specific, immutable daily-bar observation.

    ``source_artifact_sha256`` must identify the source root produced by the
    adapter.  It keeps the assurance report auditable without embedding raw
    market data or filesystem paths in control-plane diagnostics.
    """

    source_id: str
    symbol: str
    date_cutoff: str
    adjustment_basis: str
    source_artifact_sha256: str
    bars: tuple[DailyBar, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_id", _require_identifier(self.source_id, field_name="source_id"))
        object.__setattr__(self, "symbol", _require_identifier(self.symbol, field_name="symbol", upper=True))
        object.__setattr__(self, "date_cutoff", _require_date(self.date_cutoff, field_name="date_cutoff"))
        object.__setattr__(
            self,
            "adjustment_basis",
            _require_identifier(self.adjustment_basis, field_name="adjustment_basis"),
        )
        object.__setattr__(
            self,
            "source_artifact_sha256",
            _require_sha256(self.source_artifact_sha256, field_name="source_artifact_sha256"),
        )
        bars = tuple(self.bars)
        if not bars or any(not isinstance(bar, DailyBar) for bar in bars):
            raise ValueError("bars must contain at least one DailyBar")
        sorted_bars = tuple(sorted(bars, key=lambda bar: bar.session_date))
        dates = tuple(bar.session_date for bar in sorted_bars)
        if len(set(dates)) != len(dates):
            raise ValueError("bars must not contain duplicate sessions")
        if dates[-1] > self.date_cutoff:
            raise ValueError("bars must not extend beyond date_cutoff")
        object.__setattr__(self, "bars", sorted_bars)

    def to_dict(self) -> dict[str, object]:
        return {
            "source_id": self.source_id,
            "symbol": self.symbol,
            "date_cutoff": self.date_cutoff,
            "adjustment_basis": self.adjustment_basis,
            "source_artifact_sha256": self.source_artifact_sha256,
            "bars": [bar.to_dict() for bar in self.bars],
        }

    @property
    def snapshot_sha256(self) -> str:
        return _digest(self.to_dict())


@dataclass(frozen=True)
class DailyBarSourceObservation:
    """Terminal result from one provider, including a safe unavailable state."""

    source_id: str
    status: str
    snapshot: DailyBarSourceSnapshot | None = None
    reason_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        source_id = _require_identifier(self.source_id, field_name="source_id")
        status = str(self.status or "").strip().upper()
        if status not in _SOURCE_OBSERVATION_STATUSES:
            raise ValueError("source observation status is unsupported")
        if status == SOURCE_OBSERVATION_READY:
            if not isinstance(self.snapshot, DailyBarSourceSnapshot) or self.snapshot.source_id != source_id:
                raise ValueError("ready source observation must carry its matching snapshot")
        elif self.snapshot is not None:
            raise ValueError("non-ready source observation must not carry a snapshot")
        reasons = tuple(
            _require_identifier(reason, field_name="reason_codes[]")
            for reason in self.reason_codes
        )
        if len(set(reasons)) != len(reasons):
            raise ValueError("reason_codes must not contain duplicates")
        object.__setattr__(self, "source_id", source_id)
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "reason_codes", reasons)


@dataclass(frozen=True)
class MultiSourceDailyBarPolicy:
    """Explicit agreement requirements for one daily-bar research input."""

    scope_id: str
    symbol: str
    date_cutoff: str
    adjustment_basis: str
    required_source_ids: tuple[str, ...]
    minimum_ready_sources: int = 2
    price_relative_tolerance: float = 0.0001
    volume_relative_tolerance: float = 0.05

    def __post_init__(self) -> None:
        object.__setattr__(self, "scope_id", _require_identifier(self.scope_id, field_name="scope_id"))
        object.__setattr__(self, "symbol", _require_identifier(self.symbol, field_name="symbol", upper=True))
        object.__setattr__(self, "date_cutoff", _require_date(self.date_cutoff, field_name="date_cutoff"))
        object.__setattr__(
            self,
            "adjustment_basis",
            _require_identifier(self.adjustment_basis, field_name="adjustment_basis"),
        )
        source_ids = tuple(
            _require_identifier(source_id, field_name="required_source_ids[]")
            for source_id in self.required_source_ids
        )
        if len(source_ids) < 2 or len(set(source_ids)) != len(source_ids):
            raise ValueError("required_source_ids must contain at least two unique sources")
        try:
            minimum_ready_sources = int(self.minimum_ready_sources)
        except (TypeError, ValueError) as exc:
            raise ValueError("minimum_ready_sources must be an integer") from exc
        if not 2 <= minimum_ready_sources <= len(source_ids):
            raise ValueError("minimum_ready_sources must be between two and required source count")
        object.__setattr__(self, "required_source_ids", source_ids)
        object.__setattr__(self, "minimum_ready_sources", minimum_ready_sources)
        object.__setattr__(
            self,
            "price_relative_tolerance",
            _require_nonnegative_float(self.price_relative_tolerance, field_name="price_relative_tolerance"),
        )
        object.__setattr__(
            self,
            "volume_relative_tolerance",
            _require_nonnegative_float(self.volume_relative_tolerance, field_name="volume_relative_tolerance"),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "scope_id": self.scope_id,
            "symbol": self.symbol,
            "date_cutoff": self.date_cutoff,
            "adjustment_basis": self.adjustment_basis,
            "required_source_ids": list(self.required_source_ids),
            "minimum_ready_sources": self.minimum_ready_sources,
            "price_relative_tolerance": self.price_relative_tolerance,
            "volume_relative_tolerance": self.volume_relative_tolerance,
        }

    @property
    def policy_sha256(self) -> str:
        return _digest(self.to_dict())


@dataclass(frozen=True)
class MultiSourceDailyBarAssurance:
    """Redacted, immutable conclusion from a multi-source daily-bar check."""

    policy: MultiSourceDailyBarPolicy
    status: str
    source_statuses: tuple[tuple[str, str], ...]
    source_reason_codes: tuple[tuple[str, tuple[str, ...]], ...]
    source_snapshot_sha256: tuple[tuple[str, str], ...]
    findings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.policy, MultiSourceDailyBarPolicy):
            raise ValueError("policy must be a MultiSourceDailyBarPolicy")
        if self.status not in {
            DATA_ASSURANCE_STATUS_VERIFIED,
            DATA_ASSURANCE_STATUS_DEGRADED,
            DATA_ASSURANCE_STATUS_PARKED,
        }:
            raise ValueError("data assurance status is unsupported")
        statuses = tuple(self.source_statuses)
        if tuple(source_id for source_id, _ in statuses) != self.policy.required_source_ids:
            raise ValueError("source_statuses must cover the policy sources in policy order")
        for source_id, status in statuses:
            _require_identifier(source_id, field_name="source_statuses[].source_id")
            if status not in {
                SOURCE_OBSERVATION_READY,
                SOURCE_OBSERVATION_UNAVAILABLE,
                SOURCE_OBSERVATION_INVALID,
                SOURCE_OBSERVATION_MISSING,
            }:
                raise ValueError("source_statuses contains an unsupported status")
        for source_id, reasons in self.source_reason_codes:
            if source_id not in self.policy.required_source_ids:
                raise ValueError("source reason is not configured by policy")
            for reason in reasons:
                _require_identifier(reason, field_name="source_reason_codes[].reason")
        for source_id, digest in self.source_snapshot_sha256:
            if source_id not in self.policy.required_source_ids:
                raise ValueError("source snapshot is not configured by policy")
            _require_sha256(digest, field_name="source_snapshot_sha256[].sha256")
        finding_values = tuple(_require_identifier(finding, field_name="findings[]") for finding in self.findings)
        if len(set(finding_values)) != len(finding_values):
            raise ValueError("findings must not contain duplicates")
        object.__setattr__(self, "source_statuses", statuses)
        object.__setattr__(self, "source_reason_codes", tuple(sorted(self.source_reason_codes)))
        object.__setattr__(self, "source_snapshot_sha256", tuple(sorted(self.source_snapshot_sha256)))
        object.__setattr__(self, "findings", finding_values)

    @property
    def is_verified(self) -> bool:
        return self.status == DATA_ASSURANCE_STATUS_VERIFIED and not self.findings

    @property
    def can_publish_research_input(self) -> bool:
        """Only independent agreement may become a canonical research input."""

        return self.is_verified

    def to_diagnostic(self) -> dict[str, object]:
        """Return stable identifiers and digests only; never raw market data."""

        return {
            "schema_version": MULTISOURCE_DAILY_BAR_ASSURANCE_SCHEMA_VERSION,
            "policy_sha256": self.policy.policy_sha256,
            "scope_id": self.policy.scope_id,
            "symbol": self.policy.symbol,
            "date_cutoff": self.policy.date_cutoff,
            "status": self.status,
            "can_publish_research_input": self.can_publish_research_input,
            "source_statuses": dict(self.source_statuses),
            "source_reason_codes": {
                source_id: list(reasons) for source_id, reasons in self.source_reason_codes
            },
            "source_snapshot_sha256": dict(self.source_snapshot_sha256),
            "findings": list(self.findings),
        }

    @property
    def report_sha256(self) -> str:
        return _digest(self.to_diagnostic())


def assess_multisource_daily_bars(
    policy: MultiSourceDailyBarPolicy,
    observations: Iterable[DailyBarSourceObservation],
) -> MultiSourceDailyBarAssurance:
    """Assess provider agreement without selecting, merging, or repairing data.

    A healthy source is never enough by itself.  If a configured source is
    unavailable, malformed, on a different adjustment basis, or disagrees on
    sessions/OHLCV, the result is non-publishable.  Callers may still retain a
    source-specific artifact for diagnostics or shadow research.
    """

    if not isinstance(policy, MultiSourceDailyBarPolicy):
        raise ValueError("policy must be a MultiSourceDailyBarPolicy")

    findings: list[str] = []
    observation_by_source: dict[str, DailyBarSourceObservation] = {}
    for observation in observations:
        if not isinstance(observation, DailyBarSourceObservation):
            raise ValueError("observations must contain DailyBarSourceObservation values")
        if observation.source_id not in policy.required_source_ids:
            _append_finding(findings, "unconfigured_source_observed")
            continue
        if observation.source_id in observation_by_source:
            _append_finding(findings, "duplicate_source_observation")
            continue
        observation_by_source[observation.source_id] = observation

    source_statuses: list[tuple[str, str]] = []
    source_reason_codes: list[tuple[str, tuple[str, ...]]] = []
    ready_snapshots: list[DailyBarSourceSnapshot] = []
    snapshot_digests: list[tuple[str, str]] = []
    for source_id in policy.required_source_ids:
        observation = observation_by_source.get(source_id)
        if observation is None:
            source_statuses.append((source_id, SOURCE_OBSERVATION_MISSING))
            _append_finding(findings, "required_source_missing")
            continue
        if observation.status != SOURCE_OBSERVATION_READY:
            source_statuses.append((source_id, observation.status))
            if observation.reason_codes:
                source_reason_codes.append((source_id, observation.reason_codes))
            _append_finding(findings, "required_source_unavailable")
            continue
        snapshot = observation.snapshot
        assert snapshot is not None  # enforced by DailyBarSourceObservation
        if not _snapshot_matches_policy(snapshot, policy):
            source_statuses.append((source_id, SOURCE_OBSERVATION_INVALID))
            _append_finding(findings, "source_snapshot_policy_mismatch")
            continue
        source_statuses.append((source_id, SOURCE_OBSERVATION_READY))
        ready_snapshots.append(snapshot)
        snapshot_digests.append((source_id, snapshot.snapshot_sha256))

    if len(ready_snapshots) < policy.minimum_ready_sources:
        _append_finding(findings, "minimum_ready_sources_not_met")
    elif len(ready_snapshots) >= 2:
        baseline = ready_snapshots[0]
        for candidate in ready_snapshots[1:]:
            _compare_snapshots(baseline, candidate, policy, findings)

    if not ready_snapshots:
        status = DATA_ASSURANCE_STATUS_PARKED
    elif findings:
        status = DATA_ASSURANCE_STATUS_DEGRADED
    else:
        status = DATA_ASSURANCE_STATUS_VERIFIED
    return MultiSourceDailyBarAssurance(
        policy=policy,
        status=status,
        source_statuses=tuple(source_statuses),
        source_reason_codes=tuple(source_reason_codes),
        source_snapshot_sha256=tuple(snapshot_digests),
        findings=tuple(findings),
    )


def _snapshot_matches_policy(snapshot: DailyBarSourceSnapshot, policy: MultiSourceDailyBarPolicy) -> bool:
    return (
        snapshot.symbol == policy.symbol
        and snapshot.date_cutoff == policy.date_cutoff
        and snapshot.adjustment_basis == policy.adjustment_basis
    )


def _compare_snapshots(
    baseline: DailyBarSourceSnapshot,
    candidate: DailyBarSourceSnapshot,
    policy: MultiSourceDailyBarPolicy,
    findings: list[str],
) -> None:
    baseline_sessions = tuple(bar.session_date for bar in baseline.bars)
    candidate_sessions = tuple(bar.session_date for bar in candidate.bars)
    if baseline_sessions != candidate_sessions:
        _append_finding(findings, "daily_bar_session_coverage_mismatch")
        return
    for left, right in zip(baseline.bars, candidate.bars):
        if any(
            _relative_delta(getattr(left, field_name), getattr(right, field_name))
            > policy.price_relative_tolerance
            for field_name in ("open", "high", "low", "close")
        ):
            _append_finding(findings, "daily_bar_price_divergence")
            break
    for left, right in zip(baseline.bars, candidate.bars):
        if _relative_delta(left.volume, right.volume) > policy.volume_relative_tolerance:
            _append_finding(findings, "daily_bar_volume_divergence")
            break


def _append_finding(findings: list[str], finding: str) -> None:
    if finding not in findings:
        findings.append(finding)


__all__ = [
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
]
