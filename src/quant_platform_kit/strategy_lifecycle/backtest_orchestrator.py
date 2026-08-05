"""Backtest orchestrator — standardized interface for running backtests across markets.

Uses a Protocol-based design so each market provides its own BacktestRunner adapter.
"""

from __future__ import annotations

import calendar
import itertools
import math
import re
import uuid
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from typing import Any, Mapping, Protocol, Sequence, runtime_checkable

from quant_platform_kit.strategy_lifecycle.contracts import (
    BacktestResult,
    BacktestValidationIdentity,
    PromotionBacktestRun,
    PromotionCostModel,
    PurgedWalkForwardFold,
    SensitivityReport,
)
from quant_platform_kit.strategy_lifecycle.performance_store import PerformanceStore


_PROMOTION_PROTOCOL = "purged_walk_forward.v1"
_SOURCE_REVISION_PATTERN = re.compile(r"[0-9a-f]{40}")
_PROMOTION_REQUIRED_METRICS = ("sharpe_ratio", "max_drawdown", "cagr")
_PROMOTION_OPTIONAL_METRICS = (
    "calmar_ratio",
    "sortino_ratio",
    "volatility",
    "win_rate",
    "total_return",
    "benchmark_cagr",
    "benchmark_max_drawdown",
    "excess_cagr",
    "oos_sharpe",
    "oos_calmar",
    "oos_max_drawdown",
    "walk_forward_stability",
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_id() -> str:
    return uuid.uuid4().hex[:12]


def _is_finite_number(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _add_calendar_months(value: date, months: int) -> date:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _validate_promotion_plan(
    folds: Sequence[PurgedWalkForwardFold],
    *,
    locked_oos_start: date,
    locked_oos_end: date,
    purge_days: int,
    embargo_days: int,
    source_revision: str,
    cost_model: PromotionCostModel,
) -> tuple[PurgedWalkForwardFold, ...]:
    for index, fold in enumerate(folds):
        if not isinstance(fold, PurgedWalkForwardFold):
            raise TypeError(f"folds[{index}] must be a PurgedWalkForwardFold")
    if len(folds) < 3:
        raise ValueError(
            "promotion-grade orchestration requires at least three Purged Walk-Forward folds"
        )
    if (
        not isinstance(purge_days, int)
        or isinstance(purge_days, bool)
        or purge_days <= 0
    ):
        raise ValueError("purge_days must be an explicit positive integer")
    if (
        not isinstance(embargo_days, int)
        or isinstance(embargo_days, bool)
        or embargo_days <= 0
    ):
        raise ValueError("embargo_days must be an explicit positive integer")
    if type(locked_oos_start) is not date or type(locked_oos_end) is not date:
        raise TypeError("locked OOS boundaries must be calendar dates")
    if not _SOURCE_REVISION_PATTERN.fullmatch(source_revision):
        raise ValueError(
            "source_revision must be a lowercase 40-character Git revision"
        )
    if not isinstance(cost_model, PromotionCostModel):
        raise TypeError("cost_model must be a PromotionCostModel")
    if not cost_model.model_id.strip():
        raise ValueError("cost_model.model_id must be non-empty")
    for name in ("commission_bps", "slippage_bps", "market_impact_bps"):
        value = getattr(cost_model, name)
        if not _is_finite_number(value) or float(value) < 0:
            raise ValueError(f"cost_model.{name} must be finite and non-negative")

    validated_folds: list[PurgedWalkForwardFold] = []
    previous_test_end: date | None = None
    for index, fold in enumerate(folds):
        boundaries = (fold.train_start, fold.train_end, fold.test_start, fold.test_end)
        if any(type(boundary) is not date for boundary in boundaries):
            raise TypeError(f"folds[{index}] boundaries must be calendar dates")
        if fold.train_start > fold.train_end:
            raise ValueError(f"folds[{index}] train boundaries are reversed")
        if fold.test_start > fold.test_end:
            raise ValueError(f"folds[{index}] test boundaries are reversed")
        if fold.train_end + timedelta(days=purge_days) >= fold.test_start:
            raise ValueError(
                f"folds[{index}] does not contain the required purge interval"
            )
        if (
            previous_test_end is not None
            and previous_test_end + timedelta(days=embargo_days) >= fold.train_start
        ):
            raise ValueError(
                f"folds[{index}] overlaps or violates the ordered embargo boundary"
            )
        validated_folds.append(fold)
        previous_test_end = fold.test_end

    if (
        previous_test_end is None
        or previous_test_end + timedelta(days=embargo_days) >= locked_oos_start
    ):
        raise ValueError(
            "locked OOS overlaps the folds or violates the embargo boundary"
        )
    if locked_oos_end < _add_calendar_months(locked_oos_start, 12):
        raise ValueError("locked OOS must span at least 12 calendar months")
    return tuple(validated_folds)


def _validate_promotion_result(
    result: object, *, start_date: date, end_date: date
) -> BacktestResult:
    if not isinstance(result, BacktestResult):
        raise TypeError("promotion runner must return BacktestResult")
    if result.start_date != start_date or result.end_date != end_date:
        raise ValueError(
            "promotion result must retain the exact dated window requested by the orchestrator"
        )
    if not isinstance(result.observation_count, int) or isinstance(
        result.observation_count, bool
    ):
        raise ValueError(
            "promotion result observation_count must be a positive integer"
        )
    if result.observation_count <= 0:
        raise ValueError("promotion result observation_count must be positive")
    for name in _PROMOTION_REQUIRED_METRICS:
        if not _is_finite_number(getattr(result, name)):
            raise ValueError(f"promotion result {name} must be present and finite")
    for name in _PROMOTION_OPTIONAL_METRICS:
        value = getattr(result, name)
        if value is not None and not _is_finite_number(value):
            raise ValueError(f"promotion result {name} must be finite when provided")
    if (
        not _is_finite_number(result.run_duration_seconds)
        or result.run_duration_seconds < 0
    ):
        raise ValueError(
            "promotion result run_duration_seconds must be finite and non-negative"
        )
    return result


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


@runtime_checkable
class PromotionBacktestRunner(Protocol):
    """Explicit capability contract for promotion-grade backtest adapters."""

    def run_purged_fold(
        self,
        strategy_profile: str,
        params: Mapping[str, Any],
        *,
        fold: PurgedWalkForwardFold,
        purge_days: int,
        embargo_days: int,
        cost_model: PromotionCostModel,
    ) -> BacktestResult: ...

    def run_locked_oos(
        self,
        strategy_profile: str,
        params: Mapping[str, Any],
        *,
        start_date: date,
        end_date: date,
        cost_model: PromotionCostModel,
    ) -> BacktestResult: ...


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
        param_version: int | None = None,
    ) -> BacktestResult:
        return self._persist_result(
            result,
            strategy_profile=strategy_profile,
            domain=domain,
            params=params,
            param_set_id=param_set_id,
            param_version=param_version,
            validation_identity=None,
        )

    def _persist_result(
        self,
        result: BacktestResult,
        *,
        strategy_profile: str,
        domain: str,
        params: Mapping[str, Any],
        param_set_id: str,
        param_version: int | None,
        validation_identity: BacktestValidationIdentity | None,
    ) -> BacktestResult:
        enriched = replace(
            result,
            strategy_profile=strategy_profile,
            domain=domain,
            param_set_id=param_set_id or result.param_set_id or _run_id(),
            params=dict(params),
            param_version=max(
                int(
                    (result.param_version if param_version is None else param_version)
                    or 1
                ),
                1,
            ),
            run_id=result.run_id or _run_id(),
            source_script=result.source_script or "backtest_orchestrator",
            computed_at=result.computed_at or _now_iso(),
            validation_identity=validation_identity,
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
            raise ValueError(
                f"No BacktestRunner registered for domain={domain!r}. Available: {sorted(self._runners)}"
            )

        result = runner.run(
            strategy_profile, params, start_date=start_date, end_date=end_date
        )
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

    def run_latest(
        self, strategy_profile: str, *, domain: str
    ) -> BacktestResult | None:
        """Load the latest persisted backtest result for a strategy."""
        return self._store.load_latest_backtest(domain, strategy_profile)

    def run_promotion(
        self,
        strategy_profile: str,
        *,
        domain: str,
        params: Mapping[str, Any],
        folds: Sequence[PurgedWalkForwardFold],
        locked_oos_start: date,
        locked_oos_end: date,
        purge_days: int,
        embargo_days: int,
        source_revision: str,
        cost_model: PromotionCostModel,
        param_set_id: str = "",
        param_version: int = 1,
    ) -> PromotionBacktestRun:
        """Run the explicit promotion-grade Purged Walk-Forward protocol.

        Ordinary ``run`` and ``walk_forward`` calls remain non-promotion. A
        runner opts in only by implementing both explicit promotion methods;
        generic ``**kwargs`` support is not treated as a capability.
        """
        validated_folds = _validate_promotion_plan(
            folds,
            locked_oos_start=locked_oos_start,
            locked_oos_end=locked_oos_end,
            purge_days=purge_days,
            embargo_days=embargo_days,
            source_revision=source_revision,
            cost_model=cost_model,
        )
        runner = self._runners.get(domain)
        if runner is None:
            raise ValueError(
                f"No BacktestRunner registered for domain={domain!r}. Available: {sorted(self._runners)}"
            )
        runner_kind = getattr(runner, "runner_kind", None)
        if runner_kind != "real":
            raise RuntimeError(
                "promotion-grade execution requires explicit runner_kind='real'; "
                f"received {runner_kind!r}"
            )
        if not isinstance(runner, PromotionBacktestRunner):
            raise TypeError(
                "promotion-grade execution requires explicit run_purged_fold and run_locked_oos runner methods"
            )

        raw_fold_results: list[BacktestResult] = []
        for fold in validated_folds:
            raw_fold_results.append(
                _validate_promotion_result(
                    runner.run_purged_fold(
                        strategy_profile,
                        params,
                        fold=fold,
                        purge_days=purge_days,
                        embargo_days=embargo_days,
                        cost_model=cost_model,
                    ),
                    start_date=fold.test_start,
                    end_date=fold.test_end,
                )
            )
        raw_locked_oos_result = _validate_promotion_result(
            runner.run_locked_oos(
                strategy_profile,
                params,
                start_date=locked_oos_start,
                end_date=locked_oos_end,
                cost_model=cost_model,
            ),
            start_date=locked_oos_start,
            end_date=locked_oos_end,
        )

        base_id = param_set_id or _run_id()
        cost_inputs = {
            "commission_bps": float(cost_model.commission_bps),
            "slippage_bps": float(cost_model.slippage_bps),
            "market_impact_bps": float(cost_model.market_impact_bps),
        }
        fold_results: list[BacktestResult] = []
        for index, (fold, raw_result) in enumerate(
            zip(validated_folds, raw_fold_results)
        ):
            identity = BacktestValidationIdentity(
                protocol=_PROMOTION_PROTOCOL,
                fold_id=f"{base_id}_wf{index}",
                fold_role="test",
                train_start=fold.train_start,
                train_end=fold.train_end,
                test_start=fold.test_start,
                test_end=fold.test_end,
                locked_oos_start=locked_oos_start,
                locked_oos_end=locked_oos_end,
                purge_days=purge_days,
                embargo_days=embargo_days,
            )
            fold_results.append(
                self._persist_result(
                    replace(
                        raw_result,
                        source_revision=source_revision,
                        cost_model=cost_model.model_id,
                        cost_inputs=cost_inputs,
                    ),
                    strategy_profile=strategy_profile,
                    domain=domain,
                    params=params,
                    param_set_id=identity.fold_id,
                    param_version=param_version,
                    validation_identity=identity,
                )
            )

        locked_identity = BacktestValidationIdentity(
            protocol=_PROMOTION_PROTOCOL,
            fold_id=f"{base_id}_locked_oos",
            fold_role="locked_oos",
            train_start=None,
            train_end=None,
            test_start=locked_oos_start,
            test_end=locked_oos_end,
            locked_oos_start=locked_oos_start,
            locked_oos_end=locked_oos_end,
            purge_days=purge_days,
            embargo_days=embargo_days,
        )
        locked_oos_result = self._persist_result(
            replace(
                raw_locked_oos_result,
                source_revision=source_revision,
                cost_model=cost_model.model_id,
                cost_inputs=cost_inputs,
            ),
            strategy_profile=strategy_profile,
            domain=domain,
            params=params,
            param_set_id=locked_identity.fold_id,
            param_version=param_version,
            validation_identity=locked_identity,
        )
        return PromotionBacktestRun(
            strategy_profile=strategy_profile,
            domain=domain,
            fold_results=tuple(fold_results),
            locked_oos_result=locked_oos_result,
            folds=validated_folds,
            locked_oos_start=locked_oos_start,
            locked_oos_end=locked_oos_end,
            purge_days=purge_days,
            embargo_days=embargo_days,
            source_revision=source_revision,
            cost_model=cost_model,
        )

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
            raise ValueError(
                "windows must contain at least one (start_date, end_date) pair"
            )

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
            raise ValueError(
                "param_ranges must contain at least one parameter dimension"
            )

        keys = sorted(param_ranges.keys())
        value_lists = [list(param_ranges[k]) for k in keys]
        total = 1
        for values in value_lists:
            total *= len(values)

        combos: list[dict[str, Any]] = []
        for idx, combo in enumerate(itertools.product(*value_lists)):
            if (
                total > max_combinations
                and idx % max(1, total // max_combinations) != 0
            ):
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
