"""Backtest runner protocol and result types.

BacktestRunner is the single protocol that every strategy domain
(UsEquity, HkEquity, CnEquity, Crypto) implements to plug into the
backtest orchestration system.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol, runtime_checkable

from quant_platform_kit.backtest.config import BacktestConfig
from quant_platform_kit.strategy_lifecycle.contracts import StrategyPerformanceSnapshot


@dataclass(frozen=True)
class WindowPerformance:
    """Performance metrics for a single evaluation window."""

    window: int  # trading days
    cagr: float
    sharpe: float
    max_drawdown: float
    volatility: float
    win_rate: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "window": self.window,
            "cagr": self.cagr,
            "sharpe": self.sharpe,
            "max_drawdown": self.max_drawdown,
            "volatility": self.volatility,
            "win_rate": self.win_rate,
        }


@dataclass(frozen=True)
class BacktestResult:
    """Complete result of a backtest run including performance and metadata."""

    strategy_profile: str
    config: BacktestConfig
    windows: tuple[WindowPerformance, ...] = ()
    final_equity: float = 0.0
    total_return: float = 0.0
    annualised_return: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    metadata: Mapping[str, Any] = field(default_factory=dict)
    snapshot: StrategyPerformanceSnapshot | None = None

    def summary(self) -> dict[str, Any]:
        return {
            "strategy_profile": self.strategy_profile,
            "total_return": self.total_return,
            "annualised_return": self.annualised_return,
            "sharpe_ratio": self.sharpe_ratio,
            "max_drawdown": self.max_drawdown,
            "windows": [w.to_dict() for w in self.windows],
        }


@runtime_checkable
class BacktestRunner(Protocol):
    """Protocol that every strategy domain must implement.

    Pipeline repos (UsEquitySnapshotPipelines, HkEquitySnapshotPipelines, etc.)
    implement this protocol via their ``strategy_lifecycle/backtest_wrapper.py``
    modules.
    """

    def run(self, config: BacktestConfig) -> BacktestResult:
        ...


def build_backtest_runner(
    strategy_profile: str,
    *,
    runner_class: type[BacktestRunner] | None = None,
) -> BacktestRunner:
    """Factory to instantiate a domain-specific backtest runner.

    Parameters
    ----------
    strategy_profile :
        Strategy profile string (e.g. 'russell_top50_leader_rotation').
    runner_class :
        Concrete implementation class. When omitted, the caller must
        supply a domain-specific factory.
    """
    if runner_class is None:
        raise ValueError(
            "No runner_class provided; use a domain-specific factory like "
            "UsEquityBacktestRunner from UsEquitySnapshotPipelines"
        )
    return runner_class()
