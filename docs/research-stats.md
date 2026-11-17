# `research_stats` (RS-01, Research-Only)

[简体中文](research-stats.zh-CN.md)

`quant_platform_kit.research_stats` provides statistical primitives for backtest evidence. It **never** reads accounts, calls brokers, places orders, writes risk policy, or grants paper/shadow/live authority. Runtime, execution-kernel, and notification modules must not import it (enforced by `tests/test_research_stats_import_boundary.py`).

Install with `pip install 'quant-platform-kit[research]'`. `numpy` and `pandas` stay strictly in the optional `research` and `dev` extras while core `dependencies` remain empty. PSR/DSR, PBO, and cost stress use Python's standard library only; `stationary_bootstrap_ci` imports `numpy` lazily.

See [QSL Backtest Standard v1](backtest-standard-v1.md) for usage rules. This module and its tests use synthetic data only and contain no live backtest results.

## Components

| Component | Function | Failure semantics |
|---|---|---|
| Probabilistic Sharpe (PSR, Bailey & López de Prado 2012) | `probabilistic_sharpe_ratio(returns, sr_benchmark=0, min_observations=30)` | Too few samples, zero variance, non-finite, `<= -1`, `bool` -> `UNCOMPUTABLE`, `value=None` |
| Deflated Sharpe (DSR, 2014) | `deflated_sharpe_ratio(returns, trial_sharpes, n_effective_trials=None)` | `< 2` trials, effective trials > registered, zero trial Sharpe variance -> `UNCOMPUTABLE` |
| Expected max Sharpe | `expected_max_sharpe(variance, n_trials)` | Same as above |
| Probability of Backtest Overfitting (PBO, CSCV, Bailey et al. 2017) | `probability_of_backtest_overfitting(returns_by_trial, n_splits=16, metric="sharpe", min_rows_per_block=2)` | `< 2` trials, unequal lengths, odd or `> 16` splits, short blocks, undefined block metric -> `UNCOMPUTABLE` |
| Stationary block bootstrap (Politis & Romano 1994) | `stationary_bootstrap_ci(returns, *, seed, mean_block_length, n_resamples=1000, confidence=0.95)` | `seed` required; block > samples or `< 100` resamples -> `UNCOMPUTABLE`; per-stat undefined marks only that stat `UNCOMPUTABLE` |
| Cost stress | `cost_stress_recompute(gross, turnover, *, cost_bps_per_side, multipliers=(1,2,3))` | Length mismatch, negative turnover, non-finite, duplicate multipliers -> `PARKED` |
| Report template | `BacktestReportV1` + `schemas/backtest-report.v1.schema.json` | Fixes `live_ready=False`, `no_order=True`; non-`COMPUTED` requires `value=None` + `reason_code`; `development` cannot be `OOS_EVALUATED` |

## Conventions

- Sharpe is always **per-period, non-annualized** (`mean / sample_std(ddof=1)`), with `rf`/`MAR` subtracted beforehand by the caller. `performance_metrics.compute_window_metrics` defaults to `ddof=0` and annualizes, differing by `sqrt(n / (n - 1))`; pass `volatility_ddof=1` when parity is needed (see [Window Metrics Semantics](window-metrics-semantics.md)). `trial_sharpes` must include all trials (failed and rejected) at the same return frequency.
- Skewness and kurtosis use population moments with non-excess kurtosis (normal = `3`).
- `min_observations=30` matches Kelly Contract v2 as a structural floor only, not a quality threshold.
- Bootstrap statistics cover per-period log growth `mean(log1p r)`, per-period Sharpe, and max drawdown from initial NAV using percentile intervals; they correct only block autocorrelation and never guarantee future risk or replace multiple-testing adjustment.
- PBO partitions a `T x N` matrix of all trials (including failed/rejected) on aligned dates into `S` contiguous equal blocks, dropping earliest remainder rows recorded in `rows_dropped_leading`, enumerates `C(S, S/2)` IS/OOS splits, sets `lambda = logit(OOS_rank_of_IS_best / (N + 1))`, and computes the fraction with `lambda <= 0`. Pure noise yields high PBO; it measures overfitting risk rather than defining a cutoff.
- Costs use `turnover[t]` = total buy/sell notional / pre-trade NAV, paying `cost_bps_per_side * multiplier` per unit turnover (`net = (1 - tau * c)(1 + gross) - 1`). Convert half-L1 conventions beforehand.
- Report schemas enforce structure and honesty constraints only, setting no Sharpe or drawdown cutoffs; veto thresholds must be frozen before viewing holdout results (`gates.veto_items[].frozen_at`/`frozen_by`).

## Non-goals

- Never alters semantics of existing shared metric functions such as `strategy_lifecycle/performance_metrics.py`.
- Never wires consumers, bumps downstream QPK pins, or edits `QPK_PIN`.
- UES trial-journal integration lives on the UES side (RS-02); QPK remains strategy-agnostic.
