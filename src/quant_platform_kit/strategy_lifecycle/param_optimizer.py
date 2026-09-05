"""Parameter optimizer — grid search with seen-development robustness checks."""

from __future__ import annotations

import itertools
from dataclasses import replace
from datetime import date, datetime, timezone
from typing import Any, Mapping

import numpy as np

from quant_platform_kit.strategy_lifecycle.backtest_orchestrator import BacktestOrchestrator
from quant_platform_kit.strategy_lifecycle.contracts import (
    BacktestResult,
    OptimizationProposal,
    ParamSearchSpace,
)
from quant_platform_kit.strategy_lifecycle.param_search_space import get_search_space
from quant_platform_kit.strategy_lifecycle.performance_store import PerformanceStore


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Grid Search ─────────────────────────────────────────────────────


def _generate_grid_combinations(
    space: ParamSearchSpace,
    *,
    max_combinations: int = 500,
) -> list[dict[str, Any]]:
    """Generate parameter combinations from a search space using grid sampling."""
    values_per_dim: dict[str, list[Any]] = {}
    for name, dim in space.dimensions.items():
        if dim.param_type == "choice" and dim.choices:
            values_per_dim[name] = list(dim.choices)
        elif dim.bounds:
            low, high = dim.bounds
            step = dim.step or (1 if dim.param_type == "int" else (high - low) / 5)
            num_vals = min(int((high - low) / step) + 1, 10)
            values = [low + i * (high - low) / max(num_vals - 1, 1) for i in range(num_vals)]
            if dim.param_type == "int":
                values_per_dim[name] = [int(round(v)) for v in values]
            else:
                values_per_dim[name] = [round(v, 4) for v in values]
        else:
            values_per_dim[name] = [dim.current_value]

    keys = list(values_per_dim)
    value_lists = [values_per_dim[k] for k in keys]
    total = 1
    for vl in value_lists:
        total *= len(vl)

    if total <= max_combinations:
        combinations = list(itertools.product(*value_lists))
        return [dict(zip(keys, combo)) for combo in combinations]

    step_ratio = max(1, total // max_combinations)
    result: list[dict[str, Any]] = []
    for idx, combo in enumerate(itertools.product(*value_lists)):
        if idx % step_ratio == 0:
            result.append(dict(zip(keys, combo)))
        if len(result) >= max_combinations:
            break
    return result


def _score_backtest_result(result: BacktestResult) -> float:
    """Compute a composite score for a backtest result (higher is better)."""
    score = 0.0
    if result.sharpe_ratio is not None and not np.isnan(result.sharpe_ratio):
        score += result.sharpe_ratio * 0.35
    if result.calmar_ratio is not None and not np.isnan(result.calmar_ratio):
        score += result.calmar_ratio * 0.25
    if result.cagr is not None and not np.isnan(result.cagr):
        score += max(0, result.cagr) * 1.0 * 0.15
    if result.max_drawdown is not None and not np.isnan(result.max_drawdown):
        score += (1.0 + result.max_drawdown) * 0.15
    if result.sortino_ratio is not None and not np.isnan(result.sortino_ratio):
        score += result.sortino_ratio * 0.10
    return score


# ── Development Validation ──────────────────────────────────────────


def _run_development_validation(
    strategy_profile: str,
    *,
    domain: str,
    params: Mapping[str, Any],
    orchestrator: BacktestOrchestrator,
    start_date: date | None = None,
    end_date: date | None = None,
    folds: int = 3,
) -> tuple[float | None, float | None, float | None, float | None]:
    """Check fixed-parameter robustness over required seen-development segments.

    Parameters were selected on the full window; these segments do not train
    or select independently and are not untouched OOS or promotion evidence.
    The initial segment is omitted to preserve the existing slicing convention.

    Returns:
        (stability, mean_sharpe, mean_calmar, worst_max_dd)
        stability: 0-1 dispersion diagnostic, not a generalization probability.
        All values are None if any required segment/window/metric is incomplete.
    """
    if start_date is None or end_date is None or folds < 2:
        return None, None, None, None

    total_days = (end_date - start_date).days
    if total_days < 252:
        return None, None, None, None

    fold_days = total_days // (folds + 1)  # +1 for the initial development segment
    if fold_days < 60:
        return None, None, None, None

    segment_sharpes: list[float] = []
    segment_calmars: list[float] = []
    segment_max_dds: list[float] = []

    from datetime import timedelta

    for fold in range(1, folds + 1):
        segment_boundary = start_date + timedelta(days=fold * fold_days)
        test_start = segment_boundary + timedelta(days=1)
        test_end = min(test_start + timedelta(days=fold_days), end_date)

        if (test_end - test_start).days < 20:
            return None, None, None, None

        try:
            fold_result = orchestrator.run(
                strategy_profile,
                domain=domain,
                params=params,
                param_set_id=f"{strategy_profile}_development_segment{fold}",
                param_version=1,
                start_date=test_start,
                end_date=test_end,
            )

            if (
                isinstance(fold_result.observation_count, bool)
                or not isinstance(fold_result.observation_count, (int, np.integer))
                or fold_result.observation_count <= 0
                or fold_result.start_date is None
                or fold_result.end_date is None
                or not test_start <= fold_result.start_date <= fold_result.end_date <= test_end
            ):
                return None, None, None, None
            metrics = (fold_result.sharpe_ratio, fold_result.calmar_ratio, fold_result.max_drawdown)
            if any(value is None or not np.isfinite(value) for value in metrics):
                return None, None, None, None
            segment_sharpes.append(fold_result.sharpe_ratio)
            segment_calmars.append(fold_result.calmar_ratio)
            segment_max_dds.append(fold_result.max_drawdown)
        except Exception:
            return None, None, None, None

    if not segment_sharpes:
        return None, None, None, None

    # Stability: 1 - (CV of development-segment Sharpes), clamped to [0, 1]
    mean_sharpe = float(np.mean(segment_sharpes))
    std_sharpe = float(np.std(segment_sharpes, ddof=0)) if len(segment_sharpes) > 1 else 0.0
    mean_segment_calmar = float(np.mean(segment_calmars))
    worst_segment_max_dd = float(np.min(segment_max_dds))  # worst across all required folds
    if not all(np.isfinite(value) for value in (mean_sharpe, std_sharpe, mean_segment_calmar, worst_segment_max_dd)):
        return None, None, None, None
    cv = std_sharpe / max(abs(mean_sharpe), 0.01)
    stability = max(0.0, min(1.0, 1.0 - cv))

    mean_segment_sharpe = mean_sharpe
    return stability, mean_segment_sharpe, mean_segment_calmar, worst_segment_max_dd


# ── Pipeline helpers ──────────────────────────────────────────────────


def _run_baseline(
    strategy_profile: str, domain: str, params: Mapping[str, Any],
    orchestrator: BacktestOrchestrator, start_date: date | None, end_date: date | None,
) -> tuple[BacktestResult, float]:
    """Run baseline (current params) and return (result, score)."""
    r = orchestrator.run(strategy_profile, domain=domain, params=params,
        param_set_id=f"{strategy_profile}_current", param_version=0,
        start_date=start_date, end_date=end_date)
    return r, _score_backtest_result(r)


def _run_best_grid(
    strategy_profile: str, domain: str, space: ParamSearchSpace,
    orchestrator: BacktestOrchestrator, baseline_score: float,
    start_date: date | None, end_date: date | None,
    max_combinations: int = 500,
) -> tuple[BacktestResult | None, dict[str, Any], int]:
    """Run grid combinations, return (best_result, best_params, iteration_count)."""
    combos = _generate_grid_combinations(space, max_combinations=max_combinations)
    best_result: BacktestResult | None = None
    best_params: dict[str, Any] = {}
    best_score = baseline_score

    for idx, params in enumerate(combos):
        try:
            r = orchestrator.run(strategy_profile, domain=domain, params=params,
                param_set_id=f"{strategy_profile}_grid_{idx}", param_version=1,
                start_date=start_date, end_date=end_date)
            s = _score_backtest_result(r)
            if s > best_score:
                best_score, best_result, best_params = s, r, dict(params)
        except Exception:
            continue
    return best_result, best_params, len(combos)


def _build_optimization_proposal(
    strategy_profile: str, domain: str,
    current_params: Mapping[str, Any], proposed_params: Mapping[str, Any],
    baseline: BacktestResult, best_result: BacktestResult,
    improvement: float, search_count: int,
    *, development_stability: float | None = None,
) -> OptimizationProposal:
    """Build a research proposal; confidence is seen-development stability only.

    Display copies clear independent-validation labels without mutating any
    input result or evidence already stored by the orchestrator.
    """
    baseline = replace(baseline, oos_sharpe=None, oos_calmar=None,
                       oos_max_drawdown=None, walk_forward_stability=None)
    best_result = replace(best_result, oos_sharpe=None, oos_calmar=None,
                          oos_max_drawdown=None, walk_forward_stability=None)
    winning, regressing = _compare_dimensions(baseline, best_result)
    stability = development_stability
    if stability is not None and (not np.isfinite(stability) or not 0.0 <= stability <= 1.0):
        stability = None
    confidence = stability if stability is not None and np.isfinite(improvement) else 0.0

    development_stable = bool(stability is not None and np.isfinite(improvement) and stability >= 0.5)
    if improvement > 0.05 and development_stable and len(regressing) <= 1:
        rec = "research_candidate"
    elif improvement > 0.02 and (stability is None or stability >= 0.4):
        rec = "needs_review"
    else:
        rec = "reject"

    return OptimizationProposal(
        strategy_profile=strategy_profile, domain=domain,
        current_params=dict(current_params), proposed_params=dict(proposed_params),
        current_metrics=baseline, proposed_metrics=best_result,
        improvement_score=round(improvement, 4), confidence=round(confidence, 4),
        winning_dimensions=tuple(winning), regressing_dimensions=tuple(regressing),
        recommendation=rec, walk_forward_passed=False,
        optimization_method="grid_search_seen_development", search_iterations=search_count,
        computed_at=_now_iso(),
    )


# ── Main Grid Search ─────────────────────────────────────────────────


def run_grid_search(
    strategy_profile: str,
    *,
    domain: str,
    orchestrator: BacktestOrchestrator,
    search_space: ParamSearchSpace | None = None,
    current_params: Mapping[str, Any] | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    max_combinations: int = 500,
) -> OptimizationProposal:
    """Run grid search with seen-development segment diagnostics, not OOS.

    Pipeline: resolve space → baseline → grid search → development checks → propose.
    """
    space = search_space or get_search_space(strategy_profile)
    if space is None:
        raise ValueError(f"No search space defined for strategy={strategy_profile!r}")

    current_params = dict(current_params or {})
    if not current_params:
        current_params = {name: dim.current_value for name, dim in space.dimensions.items()}

    baseline, baseline_score = _run_baseline(strategy_profile, domain, current_params, orchestrator, start_date, end_date)

    best_result, best_params, search_count = _run_best_grid(
        strategy_profile, domain, space, orchestrator, baseline_score,
        start_date, end_date, max_combinations,
    )

    if best_result is None or _score_backtest_result(best_result) <= baseline_score:
        return _build_optimization_proposal(
            strategy_profile, domain, current_params, current_params,
            baseline, baseline, 0.0, search_count,
        )

    development = _run_development_validation(
        strategy_profile, domain=domain, params=best_params, orchestrator=orchestrator,
        start_date=start_date or best_result.start_date,
        end_date=end_date or best_result.end_date, folds=3,
    )
    improvement = _score_backtest_result(best_result) - baseline_score

    return _build_optimization_proposal(
        strategy_profile, domain, current_params, best_params,
        baseline, best_result, improvement, search_count,
        development_stability=development[0],
    )


def run_optimization(
    strategy_profile: str,
    *,
    method: str = "grid_search",
    domain: str = "",
    store: PerformanceStore | None = None,
) -> OptimizationProposal:
    """Entry point for running parameter optimization from the CLI/service layer."""
    store = store or PerformanceStore.from_env()

    space = get_search_space(strategy_profile)
    if space is None:
        raise ValueError(f"No search space defined for strategy={strategy_profile!r}")

    resolved_domain = domain or space.domain

    orchestrator = BacktestOrchestrator(store=store)
    _auto_register_runner(orchestrator, resolved_domain)

    if method == "grid_search":
        proposal = run_grid_search(
            strategy_profile,
            domain=resolved_domain,
            orchestrator=orchestrator,
            search_space=space,
        )
    else:
        raise ValueError(f"Unknown optimization method: {method!r}")

    store.save_proposal(proposal)
    return proposal


def _compare_dimensions(
    baseline: BacktestResult,
    candidate: BacktestResult,
) -> tuple[list[str], list[str]]:
    """Compare individual metric dimensions between two backtest results."""
    winning: list[str] = []
    regressing: list[str] = []
    comparisons = [
        ("sharpe_ratio", 1, False),
        ("calmar_ratio", 1, False),
        ("cagr", 1, False),
        ("max_drawdown", -1, True),
    ]
    for metric, direction, _lower in comparisons:
        base_val = getattr(baseline, metric, None)
        cand_val = getattr(candidate, metric, None)
        if base_val is None or cand_val is None:
            continue
        if np.isnan(base_val) or np.isnan(cand_val):
            continue
        diff = (cand_val - base_val) * direction
        threshold = abs(base_val) * 0.02
        if diff > threshold:
            winning.append(metric)
        elif diff < -threshold:
            regressing.append(metric)
    return winning, regressing


def _auto_register_runner(orchestrator: BacktestOrchestrator, domain: str) -> None:
    import importlib

    adapter_map = {
        "us_equity": (
            "us_equity_snapshot_pipelines.strategy_lifecycle.backtest_wrapper",
            "us_equity_snapshot_pipelines.lifecycle.backtest_wrapper",
            "strategy_lifecycle.backtest_wrapper",
        ),
        "crypto": (
            "crypto_live_pool_pipelines.strategy_lifecycle.backtest_wrapper",
            "strategy_lifecycle.backtest_wrapper",
        ),
        "hk_equity": (
            "hk_equity_snapshot_pipelines.strategy_lifecycle.backtest_wrapper",
            "strategy_lifecycle.backtest_wrapper",
        ),
        "cn_equity": (
            "cn_equity_snapshot_pipelines.strategy_lifecycle.backtest_wrapper",
            "strategy_lifecycle.backtest_wrapper",
        ),
    }

    module_paths = adapter_map.get(domain)
    if module_paths is None:
        return

    errors: list[str] = []
    for module_path in module_paths:
        try:
            module = importlib.import_module(module_path)
        except ImportError as exc:
            errors.append(f"{module_path}: {exc}")
            continue

        runner_factory = getattr(module, "build_backtest_runner", None)
        if runner_factory is None:
            errors.append(f"{module_path}: missing build_backtest_runner()")
            continue

        runner = runner_factory()
        runner_kind = getattr(runner, "runner_kind", None)
        if runner_kind != "real":
            raise RuntimeError(
                f"BacktestRunner for domain={domain!r} requires explicit runner_kind='real'; "
                f"received {runner_kind!r}."
            )

        orchestrator.register_runner(domain, runner)
        return

    raise RuntimeError(
        f"Unable to register BacktestRunner for domain={domain!r}. "
        f"Tried: {', '.join(module_paths)}. Errors: {' | '.join(errors) or 'none'}"
    )
