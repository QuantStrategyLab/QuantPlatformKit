"""Unified backtest framework — runner protocol, configuration, and window constants.

Consolidates the BacktestRunner protocol and BacktestConfig that were
previously defined in strategy_lifecycle/backtest_orchestrator.py and
scattered across pipeline repos.
"""

from quant_platform_kit.backtest.config import (
    DEFAULT_RISK_FREE_RATE,
    DEFAULT_TRADING_DAYS_PER_YEAR,
    DEFAULT_WINDOWS,
    BacktestConfig,
)
from quant_platform_kit.backtest.runner import (
    BacktestResult,
    BacktestRunner,
    WindowPerformance,
    build_backtest_runner,
)

__all__ = [
    "BacktestConfig",
    "BacktestResult",
    "BacktestRunner",
    "DEFAULT_RISK_FREE_RATE",
    "DEFAULT_TRADING_DAYS_PER_YEAR",
    "DEFAULT_WINDOWS",
    "WindowPerformance",
    "build_backtest_runner",
]
