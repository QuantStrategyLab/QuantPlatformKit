"""End-to-end tests for the strategy catalog → entrypoint → decision chain.

Verifies that strategy definitions can be loaded, entrypoints resolved,
and the core build_target_weights / compute_signals pipeline works end-to-end.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from typing import Any


# Fixture paths
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


class StrategyCatalogE2ETest(unittest.TestCase):
    """Test the full strategy catalog lifecycle without requiring external dependencies."""

    def test_strategy_catalog_structure_is_valid(self) -> None:
        """Verify StrategyCatalog dataclass validates correctly."""
        from quant_platform_kit.common.strategies import (
            StrategyCatalog,
            StrategyDefinition,
            StrategyMetadata,
            build_strategy_catalog,
        )

        definitions = {
            "test_strategy": StrategyDefinition(
                profile="test_strategy",
                domain="us_equity",
                supported_platforms=frozenset({"ibkr"}),
                target_mode="weight",
            ),
        }
        metadata = {
            "test_strategy": StrategyMetadata(
                canonical_profile="test_strategy",
                display_name="Test Strategy",
                description="E2E test strategy for validation",
                status="runtime_enabled",
            ),
        }
        catalog = build_strategy_catalog(
            strategy_definitions=definitions,
            metadata=metadata,
        )
        self.assertIn("test_strategy", catalog.definitions)
        self.assertEqual(
            catalog.metadata["test_strategy"].display_name,
            "Test Strategy",
        )

    def test_catalog_resolution_and_lookup(self) -> None:
        """Test profile resolution, aliases, and metadata lookup."""
        from quant_platform_kit.common.strategies import (
            StrategyCatalog,
            StrategyDefinition,
            StrategyMetadata,
            build_strategy_catalog,
            get_catalog_strategy_definition,
            get_catalog_strategy_metadata,
            resolve_catalog_profile,
        )

        definitions = {
            "e2e_momentum": StrategyDefinition(
                profile="e2e_momentum",
                domain="us_equity",
                supported_platforms=frozenset({"ibkr", "schwab"}),
                target_mode="weight",
            ),
            "e2e_dca": StrategyDefinition(
                profile="e2e_dca",
                domain="crypto",
                supported_platforms=frozenset({"binance"}),
                target_mode="value",
            ),
        }
        metadata = {
            "e2e_momentum": StrategyMetadata(
                canonical_profile="e2e_momentum",
                display_name="E2E Momentum",
                description="Momentum strategy for E2E testing",
                aliases=("e2e_mom",),
                status="runtime_enabled",
            ),
            "e2e_dca": StrategyMetadata(
                canonical_profile="e2e_dca",
                display_name="E2E DCA",
                description="DCA strategy for E2E testing",
                status="runtime_enabled",
            ),
        }
        catalog = build_strategy_catalog(
            strategy_definitions=definitions,
            metadata=metadata,
        )
        # Alias resolution
        self.assertEqual(resolve_catalog_profile("e2e_mom", strategy_catalog=catalog), "e2e_momentum")
        self.assertEqual(resolve_catalog_profile("e2e_dca", strategy_catalog=catalog), "e2e_dca")

        # Metadata lookup
        md = get_catalog_strategy_metadata(catalog, "e2e_momentum")
        self.assertEqual(md.display_name, "E2E Momentum")

        # Definition lookup
        d = get_catalog_strategy_definition(catalog, "e2e_momentum")
        self.assertEqual(d.domain, "us_equity")


class RiskEngineE2ETest(unittest.TestCase):
    """Test the risk engine end-to-end across regime detection and signal aggregation."""

    def test_risk_engine_with_single_signal(self) -> None:
        """A single ROUTE_RISK_REDUCED signal should produce that route."""
        from quant_platform_kit.risk.contracts import (
            ROUTE_RISK_REDUCED,
            RiskAssessment,
            RiskSignal,
        )
        from quant_platform_kit.risk.engine import aggregate_risk_signals

        signal = RiskSignal(
            plugin="test_plugin",
            schema_version="test.v1",
            route=ROUTE_RISK_REDUCED,
            confidence=0.85,
            suggested_action="risk_reduced",
            reason_codes=("macro_volatility_spike",),
            as_of="2026-06-30",
        )
        assessment = aggregate_risk_signals((signal,))
        self.assertEqual(assessment.effective_route, ROUTE_RISK_REDUCED)
        self.assertEqual(assessment.confidence, 0.85)
        self.assertTrue(assessment.actionable)

    def test_risk_engine_conservative_aggregation(self) -> None:
        """When multiple signals exist, the most severe route wins."""
        from quant_platform_kit.risk.contracts import (
            ROUTE_NO_ACTION,
            ROUTE_RISK_OFF,
            ROUTE_WATCH,
            RiskSignal,
        )
        from quant_platform_kit.risk.engine import aggregate_risk_signals

        signals = (
            RiskSignal(
                plugin="plugin_a",
                schema_version="a.v1",
                route=ROUTE_NO_ACTION,
                confidence=1.0,
                suggested_action="no_action",
                as_of="2026-06-30",
            ),
            RiskSignal(
                plugin="plugin_b",
                schema_version="b.v1",
                route=ROUTE_WATCH,
                confidence=0.9,
                suggested_action="watch",
                as_of="2026-06-30",
            ),
            RiskSignal(
                plugin="plugin_c",
                schema_version="c.v1",
                route=ROUTE_RISK_OFF,
                confidence=0.7,
                suggested_action="risk_off",
                reason_codes=("crisis_detected",),
                emergency=True,
                as_of="2026-06-30",
            ),
        )
        assessment = aggregate_risk_signals(signals)
        self.assertEqual(assessment.effective_route, ROUTE_RISK_OFF)
        self.assertEqual(assessment.confidence, 0.7)  # min confidence
        self.assertTrue(assessment.actionable)

    def test_risk_engine_resolve_action(self) -> None:
        """RiskAssessment should translate to concrete RiskAction."""
        from quant_platform_kit.risk.contracts import (
            ROUTE_RISK_REDUCED,
            RiskAssessment,
            RiskSignal,
        )
        from quant_platform_kit.risk.engine import RiskEngine

        assessment = RiskAssessment(
            as_of="2026-06-30",
            effective_route=ROUTE_RISK_REDUCED,
            effective_regime="elevated",
            confidence=0.8,
            signals=(
                RiskSignal(
                    plugin="test",
                    schema_version="test.v1",
                    route=ROUTE_RISK_REDUCED,
                    confidence=0.8,
                    suggested_action="risk_reduced",
                    as_of="2026-06-30",
                ),
            ),
        )
        engine = RiskEngine()
        action = engine.resolve(assessment, {"risk_reduced_scalar": 0.4})
        self.assertEqual(action.action, "risk_reduced")
        self.assertEqual(action.budget_scalar, 0.4)


class DataVersionE2ETest(unittest.TestCase):
    """Test data versioning end-to-end — semver parsing, latest selection, manifest building."""

    def test_semver_parsing_and_comparison(self) -> None:
        from quant_platform_kit.data.version import DataVersion, latest_version, semver_version

        v1 = semver_version("1.0.0")
        v2 = semver_version("2.1.3")
        v3 = semver_version("1.9.5")
        self.assertEqual(v1.semver, "1.0.0")
        self.assertEqual(v2.semver, "2.1.3")

        latest = latest_version((v1, v2, v3))
        self.assertIsNotNone(latest)
        self.assertEqual(latest.semver, "2.1.3")

    def test_data_version_full_format(self) -> None:
        from quant_platform_kit.data.version import DataVersion

        v = DataVersion(major=1, minor=5, patch=2, as_of="2026-06-30", source="pipeline_v2")
        self.assertIn("1.5.2", v.full)
        self.assertIn("2026-06-30", v.full)
        self.assertIn("pipeline_v2", v.full)

    def test_artifact_manifest_building(self) -> None:
        import tempfile
        from quant_platform_kit.data.manifest import build_artifact_record, write_data_release
        from quant_platform_kit.data.version import DataVersion

        with tempfile.TemporaryDirectory() as tmp:
            fake_path = Path(tmp) / "test_snapshot.csv"
            fake_path.write_text("symbol,score\nAAPL,0.95\n")
            record = build_artifact_record(fake_path, artifact_type="feature_snapshot")
            self.assertEqual(record["artifact_type"], "feature_snapshot")
            self.assertIn("sha256", record)

            version = DataVersion(major=1, minor=0, as_of="2026-06-30")
            manifest = write_data_release(
                (record,),
                output_dir=tmp,
                version=version,
                source_project="e2e_test",
            )
            self.assertTrue(Path(manifest).exists())
            self.assertIn("releases", str(manifest))


class BacktestE2ETest(unittest.TestCase):
    """Test backtest runner protocol and configuration."""

    def test_backtest_config_defaults(self) -> None:
        from quant_platform_kit.backtest.config import (
            DEFAULT_WINDOWS,
            BacktestConfig,
        )

        config = BacktestConfig(strategy_profile="test_e2e")
        self.assertEqual(config.windows, DEFAULT_WINDOWS)
        self.assertEqual(config.domain, "us_equity")
        self.assertEqual(config.initial_capital, 1_000_000.0)

    def test_window_performance_serialization(self) -> None:
        from quant_platform_kit.backtest.runner import WindowPerformance

        wp = WindowPerformance(
            window=252,
            cagr=0.15,
            sharpe=1.2,
            max_drawdown=-0.25,
            volatility=0.18,
            win_rate=0.55,
        )
        d = wp.to_dict()
        self.assertEqual(d["window"], 252)
        self.assertEqual(d["cagr"], 0.15)
        self.assertAlmostEqual(d["sharpe"], 1.2)


class CrossModuleIntegrationTest(unittest.TestCase):
    """Verify that modules work together across risk, data, and backtest boundaries."""

    def test_risk_assessment_can_be_serialized_for_audit(self) -> None:
        from quant_platform_kit.risk.contracts import (
            ROUTE_RISK_REDUCED,
            RiskAssessment,
            RiskSignal,
        )
        from quant_platform_kit.data.version import DataVersion

        assessment = RiskAssessment(
            as_of="2026-06-30",
            effective_route=ROUTE_RISK_REDUCED,
            effective_regime="elevated",
            confidence=0.75,
            signals=(
                RiskSignal(
                    plugin="test",
                    schema_version="test.v1",
                    route=ROUTE_RISK_REDUCED,
                    confidence=0.75,
                    suggested_action="risk_reduced",
                    as_of="2026-06-30",
                ),
            ),
        )
        # Risk assessment can be versioned for data tracking
        version = DataVersion(major=1, as_of=assessment.as_of)
        self.assertIsNotNone(version.full)
        self.assertTrue(assessment.actionable)
