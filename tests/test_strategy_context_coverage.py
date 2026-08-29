from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from quant_platform_kit.strategy_lifecycle.strategy_context_coverage import (
    STRATEGY_CONTEXT_COVERAGE_CATALOG_SCHEMA,
    StrategyContextCoverage,
    StrategyContextCoverageError,
    build_strategy_context_coverage_catalog,
    load_strategy_context_coverage_catalog,
)


def _coverage(strategy_profile: str = "explicit_profile") -> StrategyContextCoverage:
    return StrategyContextCoverage(
        strategy_profile=strategy_profile,
        domain="us_equity",
        strategy_kind="sector_etf_trend",
        instrument_classes=("leveraged_etf", "etf"),
        exposure_buckets=("sector_semiconductors", "us_equity_growth"),
        capital_role="satellite",
        benchmark_ids=("buy_hold_SOXX",),
        allowed_m0_research_subject_types=(
            "strategy_hypothesis",
            "theme_context",
            "risk_context",
        ),
    )


class StrategyContextCoverageTests(unittest.TestCase):
    def test_catalog_is_research_only_and_keeps_explicit_metadata(self) -> None:
        catalog = build_strategy_context_coverage_catalog((_coverage(),))

        self.assertEqual(catalog["schema_version"], STRATEGY_CONTEXT_COVERAGE_CATALOG_SCHEMA)
        self.assertEqual(catalog["authority"], {"research_only": True, "no_order": True})
        binding = catalog["bindings"][0]
        self.assertEqual(binding["strategy_profile"], "explicit_profile")
        self.assertEqual(binding["instrument_classes"], ["etf", "leveraged_etf"])
        self.assertEqual(binding["benchmark_ids"], ["buy_hold_SOXX"])
        self.assertNotIn("target_weight", binding)
        self.assertNotIn("platform_id", binding)

    def test_catalog_rejects_duplicate_profile_declarations(self) -> None:
        binding = _coverage("profile_declared_once")
        with self.assertRaisesRegex(StrategyContextCoverageError, "profiles must be unique"):
            build_strategy_context_coverage_catalog((binding, binding))

    def test_unknown_taxonomy_value_is_rejected_instead_of_inferred(self) -> None:
        with self.assertRaisesRegex(StrategyContextCoverageError, "strategy kind is not supported"):
            StrategyContextCoverage(
                strategy_profile="looks_like_a_strategy_but_is_not_metadata",
                domain="us_equity",
                strategy_kind="guess_from_name",
                instrument_classes=("etf",),
                exposure_buckets=("explicit_exposure",),
                capital_role="core",
                benchmark_ids=("buy_hold_SPY",),
                allowed_m0_research_subject_types=("risk_context",),
            )

    def test_load_requires_research_only_no_order_authority(self) -> None:
        catalog = build_strategy_context_coverage_catalog((_coverage(),))
        catalog["authority"] = {"research_only": True, "no_order": False}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "coverage.json"
            path.write_text(json.dumps(catalog), encoding="utf-8")
            with self.assertRaisesRegex(StrategyContextCoverageError, "research-only"):
                load_strategy_context_coverage_catalog(path)

    def test_load_rejects_runtime_or_allocation_fields(self) -> None:
        catalog = build_strategy_context_coverage_catalog((_coverage(),))
        catalog["bindings"][0]["target_weight"] = 0.25
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "coverage.json"
            path.write_text(json.dumps(catalog), encoding="utf-8")
            with self.assertRaisesRegex(StrategyContextCoverageError, "unsupported fields"):
                load_strategy_context_coverage_catalog(path)

    def test_load_returns_explicit_profile_mapping(self) -> None:
        catalog = build_strategy_context_coverage_catalog((_coverage("declared_profile"),))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "coverage.json"
            path.write_text(json.dumps(catalog), encoding="utf-8")
            loaded = load_strategy_context_coverage_catalog(path)

        self.assertEqual(set(loaded), {"declared_profile"})
        self.assertEqual(loaded["declared_profile"].capital_role, "satellite")
        self.assertEqual(
            loaded["declared_profile"].allowed_m0_research_subject_types,
            ("risk_context", "strategy_hypothesis", "theme_context"),
        )


if __name__ == "__main__":
    unittest.main()
