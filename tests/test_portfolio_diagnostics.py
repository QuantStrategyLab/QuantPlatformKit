from __future__ import annotations

import unittest
from datetime import datetime, timezone
from types import SimpleNamespace

from quant_platform_kit.common.models import PortfolioSnapshot, Position
from quant_platform_kit.risk.portfolio_diagnostics import (
    compute_unrealized_pnl_pct,
    extract_portfolio_risk_diagnostics,
)


class PortfolioDiagnosticsTests(unittest.TestCase):
    def test_compute_unrealized_pnl_pct_from_positions(self) -> None:
        snapshot = PortfolioSnapshot(
            as_of=datetime.now(timezone.utc),
            total_equity=10_000.0,
            positions=(
                Position(symbol="SPY", quantity=10.0, market_value=5_500.0, average_cost=500.0),
                Position(symbol="QQQ", quantity=5.0, market_value=2_000.0, average_cost=450.0),
            ),
        )

        # SPY: 5500 - 5000 = 500; QQQ: 2000 - 2250 = -250 => net 250 / 10000 = 0.025
        self.assertAlmostEqual(compute_unrealized_pnl_pct(snapshot), 0.025)

    def test_compute_unrealized_pnl_pct_prefers_metadata_override(self) -> None:
        snapshot = PortfolioSnapshot(
            as_of=datetime.now(timezone.utc),
            total_equity=10_000.0,
            positions=(),
            metadata={"unrealized_pnl_pct": -0.12},
        )

        self.assertAlmostEqual(compute_unrealized_pnl_pct(snapshot), -0.12)

    def test_compute_unrealized_pnl_pct_returns_none_without_cost_basis(self) -> None:
        snapshot = PortfolioSnapshot(
            as_of=datetime.now(timezone.utc),
            total_equity=10_000.0,
            positions=(Position(symbol="SPY", quantity=10.0, market_value=5_000.0),),
        )

        self.assertIsNone(compute_unrealized_pnl_pct(snapshot))

    def test_extract_portfolio_risk_diagnostics_includes_streak(self) -> None:
        snapshot = PortfolioSnapshot(
            as_of=datetime.now(timezone.utc),
            total_equity=10_000.0,
            positions=(
                Position(symbol="SPY", quantity=10.0, market_value=4_500.0, average_cost=500.0),
            ),
            metadata={"consecutive_losses": 3},
        )

        diagnostics = extract_portfolio_risk_diagnostics(snapshot)

        self.assertAlmostEqual(diagnostics["unrealized_pnl_pct"], -0.05)
        self.assertEqual(diagnostics["consecutive_losses"], 3)
        self.assertAlmostEqual(diagnostics["unrealized_pnl_coverage"], 1.0)

    def test_short_position_uses_signed_cost_basis(self) -> None:
        snapshot = PortfolioSnapshot(
            as_of=datetime.now(timezone.utc),
            total_equity=10_000.0,
            positions=(
                Position(
                    symbol="SH",
                    quantity=-10.0,
                    market_value=-800.0,
                    average_cost=100.0,
                ),
            ),
        )

        # Shorted at 100, mark 80: pnl = -800 - (-1000) = +200 → 0.02
        self.assertAlmostEqual(compute_unrealized_pnl_pct(snapshot), 0.02)

    def test_partial_cost_coverage_is_not_complete_pnl(self) -> None:
        snapshot = PortfolioSnapshot(
            as_of=datetime.now(timezone.utc),
            total_equity=10_000.0,
            positions=(
                Position(symbol="SPY", quantity=10.0, market_value=5_500.0, average_cost=500.0),
                Position(symbol="QQQ", quantity=5.0, market_value=2_000.0),
            ),
        )

        self.assertIsNone(compute_unrealized_pnl_pct(snapshot))
        diagnostics = extract_portfolio_risk_diagnostics(snapshot)
        self.assertNotIn("unrealized_pnl_pct", diagnostics)
        self.assertAlmostEqual(diagnostics["unrealized_pnl_coverage"], 0.5)

    def test_non_finite_price_or_cost_returns_unknown(self) -> None:
        for kwargs in (
            {"market_value": float("nan"), "average_cost": 100.0},
            {"market_value": 1_000.0, "average_cost": float("inf")},
        ):
            with self.subTest(kwargs=kwargs):
                snapshot = PortfolioSnapshot(
                    as_of=datetime.now(timezone.utc),
                    total_equity=10_000.0,
                    positions=(Position(symbol="SPY", quantity=10.0, **kwargs),),
                )
                self.assertIsNone(compute_unrealized_pnl_pct(snapshot))
                diagnostics = extract_portfolio_risk_diagnostics(snapshot)
                self.assertNotIn("unrealized_pnl_pct", diagnostics)
                self.assertEqual(diagnostics["unrealized_pnl_coverage"], 0.0)

    def test_missing_none_or_false_position_inputs_are_unknown_but_numeric_zero_is_valid(self) -> None:
        invalid_positions = (
            Position(symbol="MISSING_MARK", quantity=10.0, market_value=None, average_cost=100.0),
            Position(symbol="MISSING_QTY", quantity=None, market_value=1_000.0, average_cost=100.0),
            Position(symbol="FALSE_MARK", quantity=10.0, market_value=False, average_cost=100.0),
            Position(symbol="FALSE_QTY", quantity=False, market_value=0.0, average_cost=100.0),
            SimpleNamespace(quantity=10.0, average_cost=100.0),
        )
        for position in invalid_positions:
            with self.subTest(position=position):
                snapshot = PortfolioSnapshot(
                    as_of=datetime.now(timezone.utc),
                    total_equity=10_000.0,
                    positions=(position,),
                )
                self.assertIsNone(compute_unrealized_pnl_pct(snapshot))
                diagnostics = extract_portfolio_risk_diagnostics(snapshot)
                self.assertNotIn("unrealized_pnl_pct", diagnostics)
                self.assertEqual(diagnostics["unrealized_pnl_coverage"], 0.0)

        zero_position = PortfolioSnapshot(
            as_of=datetime.now(timezone.utc),
            total_equity=10_000.0,
            positions=(Position(symbol="ZERO", quantity=0.0, market_value=0.0),),
        )
        self.assertEqual(compute_unrealized_pnl_pct(zero_position), 0.0)
        zero_diagnostics = extract_portfolio_risk_diagnostics(zero_position)
        self.assertEqual(zero_diagnostics["unrealized_pnl_pct"], 0.0)
        self.assertEqual(zero_diagnostics["unrealized_pnl_coverage"], 1.0)

    def test_arithmetic_overflow_returns_unknown_pnl(self) -> None:
        product_overflow = PortfolioSnapshot(
            as_of=datetime.now(timezone.utc),
            total_equity=10_000.0,
            positions=(
                Position(
                    symbol="SPY",
                    quantity=1e308,
                    market_value=1.0,
                    average_cost=1e308,
                ),
            ),
        )
        aggregate_overflow = PortfolioSnapshot(
            as_of=datetime.now(timezone.utc),
            total_equity=10_000.0,
            positions=(
                Position(symbol="A", quantity=1.0, market_value=1e308, average_cost=0.0),
                Position(symbol="B", quantity=1.0, market_value=1e308, average_cost=0.0),
            ),
        )
        ratio_overflow = PortfolioSnapshot(
            as_of=datetime.now(timezone.utc),
            total_equity=1e-308,
            positions=(
                Position(symbol="A", quantity=1.0, market_value=1e308, average_cost=0.0),
            ),
        )

        for snapshot in (product_overflow, aggregate_overflow, ratio_overflow):
            with self.subTest(snapshot=snapshot):
                self.assertIsNone(compute_unrealized_pnl_pct(snapshot))
                self.assertNotIn(
                    "unrealized_pnl_pct",
                    extract_portfolio_risk_diagnostics(snapshot),
                )

    def test_metadata_override_still_preferred_with_full_coverage(self) -> None:
        snapshot = PortfolioSnapshot(
            as_of=datetime.now(timezone.utc),
            total_equity=10_000.0,
            positions=(
                Position(symbol="SPY", quantity=10.0, market_value=4_500.0, average_cost=500.0),
            ),
            metadata={"unrealized_pnl_pct": -0.12},
        )

        self.assertAlmostEqual(compute_unrealized_pnl_pct(snapshot), -0.12)
        diagnostics = extract_portfolio_risk_diagnostics(snapshot)
        self.assertAlmostEqual(diagnostics["unrealized_pnl_pct"], -0.12)
        self.assertAlmostEqual(diagnostics["unrealized_pnl_coverage"], 1.0)
        self.assertEqual(diagnostics["unrealized_pnl_source"], "metadata")

    def test_metadata_override_requires_valid_positive_equity_in_both_apis(self) -> None:
        for total_equity in (0.0, float("nan")):
            with self.subTest(total_equity=total_equity):
                snapshot = PortfolioSnapshot(
                    as_of=datetime.now(timezone.utc),
                    total_equity=total_equity,
                    positions=(),
                    metadata={"unrealized_pnl_pct": -0.12},
                )
                self.assertIsNone(compute_unrealized_pnl_pct(snapshot))
                diagnostics = extract_portfolio_risk_diagnostics(snapshot)
                self.assertNotIn("unrealized_pnl_pct", diagnostics)
                self.assertNotEqual(diagnostics.get("unrealized_pnl_source"), "metadata")


if __name__ == "__main__":
    unittest.main()
