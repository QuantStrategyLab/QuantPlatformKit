from __future__ import annotations

import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

import pandas as pd

from quant_platform_kit.strategy_lifecycle.benchmark_catalog import (
    STRATEGY_BENCHMARK_CATALOG_SCHEMA,
    StrategyBenchmarkBinding,
    StrategyBenchmarkCatalogError,
    build_strategy_benchmark_catalog,
    load_strategy_benchmark_catalog,
)
from quant_platform_kit.strategy_lifecycle.performance_monitor import run_monitor
from quant_platform_kit.strategy_lifecycle.performance_store import PerformanceStore
from quant_platform_kit.strategy_lifecycle.return_collector import MissingStrategyBenchmarkError


class _Collector:
    def __init__(self, *, include_benchmark: bool = True) -> None:
        index = pd.date_range("2026-01-01", periods=30, freq="D")
        self._returns = pd.Series([0.01] * 30, index=index)
        self._benchmark = pd.Series([0.005] * 30, index=index) if include_benchmark else None

    def collect(self, _domain: str) -> dict[str, pd.Series]:
        return {"soxl_soxx_trend_income": self._returns}

    def collect_benchmark(self, _domain: str, _symbol: str) -> pd.Series | None:
        return self._benchmark


class StrategyBenchmarkCatalogTests(unittest.TestCase):
    def test_catalog_is_monitoring_only_and_maps_explicit_profile(self) -> None:
        catalog = build_strategy_benchmark_catalog(
            (
                StrategyBenchmarkBinding(
                    strategy_profile="soxl_soxx_trend_income",
                    benchmark_symbol="buy_hold_SOXX",
                    benchmark_kind="unleveraged_underlying",
                ),
            )
        )
        self.assertEqual(catalog["schema_version"], STRATEGY_BENCHMARK_CATALOG_SCHEMA)
        self.assertEqual(catalog["authority"], {"monitoring_only": True, "no_order": True})
        self.assertEqual(catalog["bindings"][0]["benchmark_symbol"], "buy_hold_SOXX")

    def test_catalog_rejects_duplicate_profiles(self) -> None:
        binding = StrategyBenchmarkBinding("soxl_soxx_trend_income", "buy_hold_SOXX")
        with self.assertRaisesRegex(StrategyBenchmarkCatalogError, "profiles must be unique"):
            build_strategy_benchmark_catalog((binding, binding))

    def test_load_catalog_returns_profile_mapping(self) -> None:
        catalog = build_strategy_benchmark_catalog(
            (
                StrategyBenchmarkBinding(
                    "tqqq_growth_income",
                    "buy_hold_QQQ",
                    benchmark_kind="unleveraged_underlying",
                ),
            )
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "catalog.json"
            path.write_text(json.dumps(catalog), encoding="utf-8")
            self.assertEqual(
                load_strategy_benchmark_catalog(path),
                {"tqqq_growth_income": "buy_hold_QQQ"},
            )

    def test_load_catalog_requires_no_order_authority(self) -> None:
        payload = {
            "schema_version": STRATEGY_BENCHMARK_CATALOG_SCHEMA,
            "authority": {"monitoring_only": True, "no_order": False},
            "bindings": [],
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "catalog.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(StrategyBenchmarkCatalogError, "monitoring-only"):
                load_strategy_benchmark_catalog(path)

    def test_strict_monitoring_rejects_missing_profile_binding(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(MissingStrategyBenchmarkError, "no explicit benchmark binding"):
                run_monitor(
                    "us_equity",
                    collector=_Collector(),
                    store=PerformanceStore(local_root=Path(tmp)),
                    require_explicit_benchmark=True,
                )

    def test_strict_monitoring_requires_benchmark_data(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(RuntimeError, "benchmark data is unavailable"):
                run_monitor(
                    "us_equity",
                    collector=_Collector(include_benchmark=False),
                    store=PerformanceStore(local_root=Path(tmp)),
                    strategy_benchmarks={"soxl_soxx_trend_income": "buy_hold_SOXX"},
                    require_explicit_benchmark=True,
                )

    def test_strict_monitoring_persists_unleveraged_benchmark(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            snapshots = run_monitor(
                "us_equity",
                collector=_Collector(),
                store=PerformanceStore(local_root=Path(tmp)),
                strategy_benchmarks={"soxl_soxx_trend_income": "buy_hold_SOXX"},
                require_explicit_benchmark=True,
            )
        self.assertEqual(len(snapshots), 1)
        self.assertEqual(snapshots[0].benchmark_symbol, "buy_hold_SOXX")
        self.assertEqual(snapshots[0].as_of, date.today())
        self.assertIsNotNone(snapshots[0].windows[21].benchmark_max_drawdown)


if __name__ == "__main__":
    unittest.main()
