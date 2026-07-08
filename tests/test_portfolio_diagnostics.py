from __future__ import annotations

import unittest
from datetime import datetime, timezone

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


if __name__ == "__main__":
    unittest.main()
