"""Backtest orchestrator — standardized interface for running backtests across markets.

Uses a Protocol-based design so each market provides its own BacktestRunner adapter.
"""

from __future__ import annotations

import itertools
import uuid
from dataclasses import replace
from datetime import date, datetime, timezone
from typing import Any, Mapping, Protocol, Sequence, runtime_checkable

from quant_platform_kit.strategy_lifecycle.contracts import BacktestResult, SensitivityReport
from quant_platform_kit.strategy_lifecycle.performance_store import PerformanceStore


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_id() -> str:
    return uuid.uuid4().hex[:12]


@runtime_checkable
class BacktestRunner(Protocol):
    """Protocol that each market adapter must implement.

    Each market (US equity, crypto, HK, CN) provides its own implementation
    that wraps the existing backtest scripts.
    """

    def run(
        self,
        strategy_profile: str,
        params: Mapping[str, Any],
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> BacktestResult:
        """Execute a backtest for the given strategy with the given parameters.

        Args:
            strategy_profile: Canonical strategy profile name.
            params: Strategy parameters to pass to the backtest.
            start_date: Optional override for backtest start.
            end_date: Optional override for backtest end.

        Returns:
            Standardized BacktestResult with computed metrics.
        """
        ...


class BacktestOrchestrator:
    """Orchestrates backtest runs across strategies and markets.

    Usage::

        orchestrator = BacktestOrchestrator(store=store)
        orchestrator.register_runner("us_equity", us_equity_runner)
        result = orchestrator.run("global_etf_rotation", params={...})
    """

    def __init__(self, *, store: PerformanceStore | None = None):
        self._runners: dict[str, BacktestRunner] = {}
        self._store = store or PerformanceStore.from_env()

    def register_runner(self, domain: str, runner: BacktestRunner) -> None:
        """Register a BacktestRunner adapter for a market domain."""
        self._runners[domain] = runner

    def get_runner(self, domain: str) -> BacktestRunner | None:
        return self._runners.get(domain)

    def persist_result(
        self,
        result: BacktestResult,
        *,
        strategy_profile: str,
        domain: str,
        params: Mapping[str, Any],
        param_set_id: str = "",
        param_version: int = 1,
    ) -> BacktestResult:
        enriched = BacktestResult(
            strategy_profile=strategy_profile,
            domain=domain,
            param_set_id=param_set_id or result.param_set_id or _run_id(),
            params=dict(params),
            param_version=max(param_version, 1),
            sharpe_ratio=result.sharpe_ratio,
            calmar_ratio=result.calmar_ratio,
            sortino_ratio=result.sortino_ratio,
            max_drawdown=result.max_drawdown,
            cagr=result.cagr,
            volatility=result.volatility,
            win_rate=result.win_rate,
            total_return=result.total_return,
            start_date=result.start_date,
            end_date=result.end_date,
            observation_count=result.observation_count,
            benchmark_symbol=result.benchmark_symbol,
            benchmark_cagr=result.benchmark_cagr,
            benchmark_max_drawdown=result.benchmark_max_drawdown,
            excess_cagr=result.excess_cagr,
            oos_sharpe=result.oos_sharpe,
            oos_calmar=result.oos_calmar,
            oos_max_drawdown=result.oos_max_drawdown,
            walk_forward_stability=result.walk_forward_stability,
            run_id=result.run_id or _run_id(),
            run_duration_seconds=result.run_duration_seconds,
            source_script=result.source_script or "backtest_orchestrator",
            computed_at=result.computed_at or _now_iso(),
        )
        self._store.save_backtest_result(enriched)
        return enriched

    def run(
        self,
        strategy_profile: str,
        *,
        domain: str,
        params: Mapping[str, Any],
        param_set_id: str = "",
        param_version: int = 1,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> BacktestResult:
        """Run a backtest for a strategy.

        Args:
            strategy_profile: Canonical strategy profile.
            domain: Market domain.
            params: Strategy parameters.
            param_set_id: Identifier for this parameter set.
            param_version: Version number for this parameter set.
            start_date: Backtest start date.
            end_date: Backtest end date.

        Returns:
            Standardized BacktestResult.

        Raises:
            ValueError: If no runner is registered for the domain.
        """
        runner = self._runners.get(domain)
        if runner is None:
            raise ValueError(f"No BacktestRunner registered for domain={domain!r}. Available: {sorted(self._runners)}")

        result = runner.run(strategy_profile, params, start_date=start_date, end_date=end_date)
        if result.start_date is None or result.end_date is None:
            result = replace(
                result,
                start_date=result.start_date or start_date,
                end_date=result.end_date or end_date,
            )
        return self.persist_result(
            result,
            strategy_profile=strategy_profile,
            domain=domain,
            params=params,
            param_set_id=param_set_id,
            param_version=param_version,
        )

    def run_latest(self, strategy_profile: str, *, domain: str) -> BacktestResult | None:
        """Load the latest persisted backtest result for a strategy."""
        return self._store.load_latest_backtest(domain, strategy_profile)

    def walk_forward(
        self,
        strategy_profile: str,
        *,
        domain: str,
        params: Mapping[str, Any],
        windows: Sequence[tuple[date | None, date | None]],
        param_set_id: str = "",
        param_version: int = 1,
    ) -> list[BacktestResult]:
        """Run backtests across multiple time windows.

        Args:
            strategy_profile: Canonical strategy profile.
            domain: Market domain.
            params: Strategy parameters shared across windows.
            windows: Sequence of (start_date, end_date) pairs, one per fold.
            param_set_id: Base identifier for parameter set metadata.
            param_version: Version number for this parameter set.

        Returns:
            One BacktestResult per window, in order.

        Raises:
            ValueError: If windows is empty or no runner is registered.
        """
        if not windows:
            raise ValueError("windows must contain at least one (start_date, end_date) pair")

        base_id = param_set_id or _run_id()
        results: list[BacktestResult] = []
        for idx, (start_date, end_date) in enumerate(windows):
            results.append(
                self.run(
                    strategy_profile,
                    domain=domain,
                    params=params,
                    param_set_id=f"{base_id}_wf{idx}",
                    param_version=param_version,
                    start_date=start_date,
                    end_date=end_date,
                )
            )
        return results

    def sensitivity(
        self,
        strategy_profile: str,
        *,
        domain: str,
        base_params: Mapping[str, Any],
        param_ranges: Mapping[str, Sequence[Any]],
        start_date: date | None = None,
        end_date: date | None = None,
        max_combinations: int = 500,
    ) -> SensitivityReport:
        """Run a basic parameter-grid sensitivity sweep.

        Expands ``param_ranges`` via Cartesian product, merging each combination
        onto ``base_params``, and runs one backtest per combination.

        Args:
            strategy_profile: Canonical strategy profile.
            domain: Market domain.
            base_params: Fixed parameters applied to every combination.
            param_ranges: Per-parameter value lists to sweep.
            start_date: Backtest start date.
            end_date: Backtest end date.
            max_combinations: Upper bound on grid size (subsamples if exceeded).

        Returns:
            SensitivityReport with one BacktestResult per combination tried.

        Raises:
            ValueError: If param_ranges is empty or no runner is registered.
        """
        if not param_ranges:
            raise ValueError("param_ranges must contain at least one parameter dimension")

        keys = sorted(param_ranges.keys())
        value_lists = [list(param_ranges[k]) for k in keys]
        total = 1
        for values in value_lists:
            total *= len(values)

        combos: list[dict[str, Any]] = []
        for idx, combo in enumerate(itertools.product(*value_lists)):
            if total > max_combinations and idx % max(1, total // max_combinations) != 0:
                continue
            merged = dict(base_params)
            merged.update(dict(zip(keys, combo)))
            combos.append(merged)
            if len(combos) >= max_combinations:
                break

        results: list[BacktestResult] = []
        for idx, combo_params in enumerate(combos):
            results.append(
                self.run(
                    strategy_profile,
                    domain=domain,
                    params=combo_params,
                    param_set_id=f"{strategy_profile}_sens_{idx}",
                    param_version=1,
                    start_date=start_date,
                    end_date=end_date,
                )
            )

        return SensitivityReport(
            strategy_profile=strategy_profile,
            domain=domain,
            base_params=dict(base_params),
            results=tuple(results),
            combination_count=len(results),
        )
