"""Explicit, read-only links between strategies and M0 research context.

This module intentionally does not inspect a strategy name, market data, a
broker, or a runtime target.  A repository owner must declare the taxonomy
for every admitted profile.  The resulting catalog is research-only context
for later P1--P3 work; it cannot select a strategy, alter a weight, or grant
execution authority.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path


STRATEGY_CONTEXT_COVERAGE_CATALOG_SCHEMA = "qsl.strategy-context-coverage-catalog.v1"

_STRATEGY_KINDS = frozenset(
    {
        "single_instrument_trend",
        "sector_etf_trend",
        "diversified_etf_rotation",
        "equity_selection",
        "dca",
        "crypto_pool_rotation",
        "multi_strategy_combo",
        "risk_overlay",
        "research_sidecar",
    }
)
_INSTRUMENT_CLASSES = frozenset(
    {
        "single_equity",
        "etf",
        "leveraged_etf",
        "index",
        "crypto_asset",
        "cash_equivalent",
        "multi_asset",
        "derivative",
        "plugin",
    }
)
_CAPITAL_ROLES = frozenset({"core", "satellite", "defensive", "reserve", "overlay"})
_M0_RESEARCH_SUBJECT_TYPES = frozenset(
    {"asset_idea", "theme_context", "strategy_hypothesis", "risk_context"}
)
_RESEARCH_ONLY_AUTHORITY = {"research_only": True, "no_order": True}
_CATALOG_FIELDS = frozenset({"schema_version", "authority", "bindings"})
_COVERAGE_FIELDS = frozenset(
    {
        "strategy_profile",
        "domain",
        "strategy_kind",
        "instrument_classes",
        "exposure_buckets",
        "capital_role",
        "benchmark_ids",
        "allowed_m0_research_subject_types",
    }
)


class StrategyContextCoverageError(ValueError):
    """Raised when a coverage catalog is incomplete or has unsafe authority."""


def _canonical_string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise StrategyContextCoverageError(f"{label} must be a non-empty canonical string")
    return value


def _canonical_enum(value: object, label: str, allowed: frozenset[str]) -> str:
    normalized = _canonical_string(value, label)
    if normalized not in allowed:
        raise StrategyContextCoverageError(f"{label} is not supported")
    return normalized


def _canonical_string_tuple(
    values: Sequence[object],
    label: str,
    *,
    allowed: frozenset[str] | None = None,
) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence) or not values:
        raise StrategyContextCoverageError(f"{label} must be a non-empty list")
    normalized = tuple(_canonical_string(value, f"{label} item") for value in values)
    if len(set(normalized)) != len(normalized):
        raise StrategyContextCoverageError(f"{label} must not contain duplicates")
    if allowed is not None and any(value not in allowed for value in normalized):
        raise StrategyContextCoverageError(f"{label} contains an unsupported value")
    return tuple(sorted(normalized))


@dataclass(frozen=True)
class StrategyContextCoverage:
    """Declared M0 research coverage for one strategy profile.

    ``benchmark_ids`` are opaque, versioned identifiers.  They must be bound
    to actual passive/unleveraged benchmarks by the separate benchmark catalog
    before performance monitoring.  Keeping the two catalogs separate avoids
    this research-only descriptor becoming a runtime configuration path.
    """

    strategy_profile: str
    domain: str
    strategy_kind: str
    instrument_classes: tuple[str, ...]
    exposure_buckets: tuple[str, ...]
    capital_role: str
    benchmark_ids: tuple[str, ...]
    allowed_m0_research_subject_types: tuple[str, ...]

    def __post_init__(self) -> None:
        _canonical_string(self.strategy_profile, "strategy profile")
        _canonical_string(self.domain, "domain")
        _canonical_enum(self.strategy_kind, "strategy kind", _STRATEGY_KINDS)
        object.__setattr__(
            self,
            "instrument_classes",
            _canonical_string_tuple(
                self.instrument_classes,
                "instrument classes",
                allowed=_INSTRUMENT_CLASSES,
            ),
        )
        object.__setattr__(
            self,
            "exposure_buckets",
            _canonical_string_tuple(self.exposure_buckets, "exposure buckets"),
        )
        _canonical_enum(self.capital_role, "capital role", _CAPITAL_ROLES)
        object.__setattr__(
            self,
            "benchmark_ids",
            _canonical_string_tuple(self.benchmark_ids, "benchmark ids"),
        )
        object.__setattr__(
            self,
            "allowed_m0_research_subject_types",
            _canonical_string_tuple(
                self.allowed_m0_research_subject_types,
                "allowed M0 research subject types",
                allowed=_M0_RESEARCH_SUBJECT_TYPES,
            ),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "strategy_profile": self.strategy_profile,
            "domain": self.domain,
            "strategy_kind": self.strategy_kind,
            "instrument_classes": list(self.instrument_classes),
            "exposure_buckets": list(self.exposure_buckets),
            "capital_role": self.capital_role,
            "benchmark_ids": list(self.benchmark_ids),
            "allowed_m0_research_subject_types": list(
                self.allowed_m0_research_subject_types
            ),
        }


def build_strategy_context_coverage_catalog(
    bindings: Sequence[StrategyContextCoverage],
) -> dict[str, object]:
    """Build a JSON-ready, no-authority coverage catalog.

    The function accepts only immutable coverage records and rejects duplicate
    profile declarations.  It intentionally returns no route, order, weight,
    account, or platform fields.
    """

    entries = tuple(bindings)
    if not entries or any(type(entry) is not StrategyContextCoverage for entry in entries):
        raise StrategyContextCoverageError(
            "catalog must contain immutable strategy context coverage bindings"
        )
    profiles = [entry.strategy_profile for entry in entries]
    if len(set(profiles)) != len(profiles):
        raise StrategyContextCoverageError("strategy profiles must be unique")
    return {
        "schema_version": STRATEGY_CONTEXT_COVERAGE_CATALOG_SCHEMA,
        "authority": dict(_RESEARCH_ONLY_AUTHORITY),
        "bindings": [
            entry.to_dict()
            for entry in sorted(entries, key=lambda item: item.strategy_profile)
        ],
    }


def load_strategy_context_coverage_catalog(
    path: str | Path,
) -> dict[str, StrategyContextCoverage]:
    """Load explicit profile coverage without inferring metadata from names."""

    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise StrategyContextCoverageError("coverage catalog could not be read as JSON") from exc
    if not isinstance(payload, Mapping):
        raise StrategyContextCoverageError("coverage catalog must be an object")
    if set(payload) != _CATALOG_FIELDS:
        raise StrategyContextCoverageError("coverage catalog contains unsupported fields")
    if payload.get("schema_version") != STRATEGY_CONTEXT_COVERAGE_CATALOG_SCHEMA:
        raise StrategyContextCoverageError("coverage catalog schema version is not supported")
    if payload.get("authority") != _RESEARCH_ONLY_AUTHORITY:
        raise StrategyContextCoverageError(
            "coverage catalog must declare research-only no-order authority"
        )
    raw_bindings = payload.get("bindings")
    if not isinstance(raw_bindings, list):
        raise StrategyContextCoverageError("coverage catalog bindings must be a list")
    bindings: list[StrategyContextCoverage] = []
    for raw in raw_bindings:
        if not isinstance(raw, Mapping):
            raise StrategyContextCoverageError("coverage catalog binding must be an object")
        if set(raw) != _COVERAGE_FIELDS:
            raise StrategyContextCoverageError(
                "coverage catalog binding contains unsupported fields"
            )
        bindings.append(
            StrategyContextCoverage(
                strategy_profile=raw.get("strategy_profile"),
                domain=raw.get("domain"),
                strategy_kind=raw.get("strategy_kind"),
                instrument_classes=raw.get("instrument_classes"),
                exposure_buckets=raw.get("exposure_buckets"),
                capital_role=raw.get("capital_role"),
                benchmark_ids=raw.get("benchmark_ids"),
                allowed_m0_research_subject_types=raw.get(
                    "allowed_m0_research_subject_types"
                ),
            )
        )
    build_strategy_context_coverage_catalog(bindings)
    return {
        binding.strategy_profile: binding
        for binding in sorted(bindings, key=lambda item: item.strategy_profile)
    }


__all__ = [
    "STRATEGY_CONTEXT_COVERAGE_CATALOG_SCHEMA",
    "StrategyContextCoverage",
    "StrategyContextCoverageError",
    "build_strategy_context_coverage_catalog",
    "load_strategy_context_coverage_catalog",
]
