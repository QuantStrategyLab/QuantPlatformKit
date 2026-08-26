"""Validated, read-only benchmark bindings for lifecycle monitoring.

The catalog deliberately maps a *strategy profile* to the passive or
unleveraged instrument used to judge it. It supplies monitoring context only:
it cannot change a strategy, rebalance an account, or grant execution rights.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path


STRATEGY_BENCHMARK_CATALOG_SCHEMA = "qsl.strategy-benchmark-catalog.v1"
_BENCHMARK_KINDS = frozenset({"passive", "unleveraged_underlying"})


class StrategyBenchmarkCatalogError(ValueError):
    """Raised when a benchmark catalog cannot be safely used for monitoring."""


def _nonblank(value: object, label: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise StrategyBenchmarkCatalogError(f"{label} must be a non-empty canonical string")
    return value


@dataclass(frozen=True)
class StrategyBenchmarkBinding:
    """One explicit, no-authority performance benchmark binding."""

    strategy_profile: str
    benchmark_symbol: str
    benchmark_kind: str = "passive"
    relative_drawdown_required: bool = True

    def __post_init__(self) -> None:
        _nonblank(self.strategy_profile, "strategy profile")
        _nonblank(self.benchmark_symbol, "benchmark symbol")
        if self.benchmark_kind not in _BENCHMARK_KINDS:
            raise StrategyBenchmarkCatalogError("benchmark kind is not supported")
        if type(self.relative_drawdown_required) is not bool:
            raise StrategyBenchmarkCatalogError("relative drawdown requirement must be boolean")


def build_strategy_benchmark_catalog(
    bindings: Sequence[StrategyBenchmarkBinding],
) -> dict[str, object]:
    """Return a validated, JSON-ready catalog without execution authority."""
    entries = tuple(bindings)
    if not entries or any(type(entry) is not StrategyBenchmarkBinding for entry in entries):
        raise StrategyBenchmarkCatalogError("catalog must contain immutable benchmark bindings")
    profiles = [entry.strategy_profile for entry in entries]
    if len(set(profiles)) != len(profiles):
        raise StrategyBenchmarkCatalogError("strategy profiles must be unique")
    return {
        "schema_version": STRATEGY_BENCHMARK_CATALOG_SCHEMA,
        "authority": {"monitoring_only": True, "no_order": True},
        "bindings": [
            {
                "strategy_profile": entry.strategy_profile,
                "benchmark_symbol": entry.benchmark_symbol,
                "benchmark_kind": entry.benchmark_kind,
                "relative_drawdown_required": entry.relative_drawdown_required,
            }
            for entry in entries
        ],
    }


def load_strategy_benchmark_catalog(path: str | Path) -> dict[str, str]:
    """Load explicit profile-to-benchmark bindings from a validated JSON catalog."""
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise StrategyBenchmarkCatalogError("benchmark catalog could not be read as JSON") from exc
    if not isinstance(payload, Mapping):
        raise StrategyBenchmarkCatalogError("benchmark catalog must be an object")
    if payload.get("schema_version") != STRATEGY_BENCHMARK_CATALOG_SCHEMA:
        raise StrategyBenchmarkCatalogError("benchmark catalog schema version is not supported")
    authority = payload.get("authority")
    if authority != {"monitoring_only": True, "no_order": True}:
        raise StrategyBenchmarkCatalogError("benchmark catalog must declare monitoring-only no-order authority")
    raw_bindings = payload.get("bindings")
    if not isinstance(raw_bindings, list):
        raise StrategyBenchmarkCatalogError("benchmark catalog bindings must be a list")
    bindings: list[StrategyBenchmarkBinding] = []
    for raw in raw_bindings:
        if not isinstance(raw, Mapping):
            raise StrategyBenchmarkCatalogError("benchmark catalog binding must be an object")
        bindings.append(
            StrategyBenchmarkBinding(
                strategy_profile=raw.get("strategy_profile"),
                benchmark_symbol=raw.get("benchmark_symbol"),
                benchmark_kind=raw.get("benchmark_kind", "passive"),
                relative_drawdown_required=raw.get("relative_drawdown_required", True),
            )
        )
    catalog = build_strategy_benchmark_catalog(bindings)
    return {
        str(item["strategy_profile"]): str(item["benchmark_symbol"])
        for item in catalog["bindings"]
        if isinstance(item, Mapping)
    }


__all__ = [
    "STRATEGY_BENCHMARK_CATALOG_SCHEMA",
    "StrategyBenchmarkBinding",
    "StrategyBenchmarkCatalogError",
    "build_strategy_benchmark_catalog",
    "load_strategy_benchmark_catalog",
]
