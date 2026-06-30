"""Backtest configuration and shared constants.

Standardised across all QuantStrategyLab pipelines and platforms.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

# Standard evaluation windows in trading days
DEFAULT_WINDOWS = (21, 63, 126, 252, 756)
DEFAULT_RISK_FREE_RATE = 0.0
DEFAULT_TRADING_DAYS_PER_YEAR = 252


@dataclass(frozen=True)
class BacktestConfig:
    """Shared configuration for all backtest runs.

    This replaces ad-hoc dict configs previously passed between
    strategy_lifecycle modules and pipeline wrappers.
    """

    strategy_profile: str
    domain: str = "us_equity"
    windows: tuple[int, ...] = DEFAULT_WINDOWS
    risk_free_rate: float = DEFAULT_RISK_FREE_RATE
    trading_days_per_year: int = DEFAULT_TRADING_DAYS_PER_YEAR
    benchmark_symbol: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    initial_capital: float = 1_000_000.0
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @property
    def annualisation_factor(self) -> float:
        return float(self.trading_days_per_year)
