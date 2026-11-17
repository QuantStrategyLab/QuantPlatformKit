# Window Metrics Semantics (`compute_window_metrics`, `qpk.window_metrics.v2`)

[简体中文](window-metrics-semantics.zh-CN.md)

Applies to `WindowPerformance` outputs from `quant_platform_kit.strategy_lifecycle.performance_metrics.compute_window_metrics` and `compute_windows` (context: [#659](https://github.com/QuantStrategyLab/QuantPlatformKit/issues/659)).

`v2` **only adds new fields**. Under identical inputs and default arguments, all `v1` fields (`volatility`, `sharpe_ratio`, `win_rate`, `profit_factor`, benchmark fields, etc.) preserve bit-exact values (`tests/test_lifecycle_metrics_semantics_v2.py::LegacyFieldRegressionTest`). Generated records set `metric_semantics_version="qpk.window_metrics.v2"`; manually constructed or deserialized legacy records carry an empty version string with `None` for new fields (`volatility_ddof=0`), meaning "undeclared" rather than zero.

## 1. `ddof` for volatility and Sharpe

| Location | Standard deviation | Annualization |
|---|---|---|
| `compute_window_metrics` (default) | Population std (`ddof=0`) | `* sqrt(periods_per_year)` |
| `compute_window_metrics(volatility_ddof=1)` | Sample std (`ddof=1`) | `* sqrt(periods_per_year)` |
| `research_stats.sharpe_inference` (PSR/DSR) | Sample std (`ddof=1`) | Unannualized (per-period) |

- They differ solely by Bessel's correction: `Sharpe_ddof0 = Sharpe_ddof1 * sqrt(n / (n - 1))` (+2.5% at `n=21`, +0.4% at `n=126`, +0.2% at `n=252`).
- Default remains `0` because stored snapshots, `compare_with_backtest` drift thresholds (`sharpe_deviation`, `volatility_deviation_pct`), and backtest baselines assume `ddof=0`; changing the default silently would create false drift.
- `volatility_ddof` records the value used and accepts only `0` or `1`, raising `ValueError` otherwise.
- Sortino (full-sample downside RMS), beta (population covariance), and information ratio (population std) stay unchanged.
- Align `ddof` explicitly via `volatility_ddof=1` or the scaling formula before comparing Sharpe across conventions.

## 2. Win rate and profit factor (daily, not per-trade)

`profit_factor` equals total gains divided by total losses rather than average win divided by average loss. Window objects do not expose per-trade payoff ratios; see the [Unified Metric Catalog](unified-metric-catalog.md) for B3 per-period diagnostics and capability coverage.

| Field | Definition | Zero-return days |
|---|---|---|
| `win_rate` (`v1`, unchanged) | Positive-return days / total trading days | Included in denominator (counted as non-win) |
| `daily_win_rate_ex_zero` (`v2` addition) | Positive-return days / `(positive + negative)` days | Excluded; `None` if all days are zero |
| `zero_return_days` (`v2` addition) | Count of trading days with exact `0` return | — |
| `profit_factor` (`v1`, unchanged) | Sum of positive daily returns / `abs(sum of negative daily returns)` | Ignored; `None` if no loss days |

- `daily_win_rate_ex_zero` matches `position_sizing.estimate_kelly` (`test_ex_zero_rate_matches_estimate_kelly_definition`).
- Strategies frequently holding cash accumulate zero-return days that depress `win_rate`; use `daily_win_rate_ex_zero` alongside `zero_return_days` when comparing strategies with different exposure rates.
- `compare_with_backtest` continues comparing `v1` `win_rate`; backtest baselines must match that daily convention.
- **Per-trade win rate and payoff ratio** require paired entry/exit trade logs and cannot be computed or inferred from daily returns; implement separate trade-log functions if needed.

## 3. Benchmark alignment reporting

Benchmark comparisons still inner-join shared dates between strategy window and benchmark. `v2` adds three count fields (all `None` when no benchmark is supplied):

| Field | Meaning |
|---|---|
| `benchmark_aligned_days` | Shared dates included in benchmark comparisons |
| `benchmark_dropped_strategy_days` | Dates within the window having strategy return but missing benchmark return |
| `benchmark_dropped_benchmark_days` | Dates within `[start_date, end_date]` having benchmark return but missing strategy return (out-of-window history excluded) |

Always report `benchmark_aligned_days` with benchmark metrics; any dropped count > 0 means benchmark CAGR/alpha/IR covered fewer days than `observation_count`. Callers preregister whether drops invalidate comparability; this module sets no threshold.

## 4. Unified net metrics for offline compounding research (`qpk.net_compounding.v1`)

Passing an explicit `periods_per_year=P` to `research_stats.unified_report.build_unified_net_report(..., periods_per_year=P)` appends `net_cagr` and `net_calmar_ratio` without modifying lifecycle monitors or default reports. `max_drawdown` retains non-positive signed values. The helper accepts caller-supplied complete, same-frequency, same-window net simple returns only, reading no quotes, accounts, or files.

- `n` is the true observation count including real zero-return periods; initial `NAV=1` is not an extra day. Strip initial placeholder zeros beforehand while keeping genuine flat/cash days.
- Let `L = sum(log1p(r_t))`; per-observation net log growth is `L / n`, and geometric CAGR is `expm1(P * L / n)`—never arithmetic mean times `P` or arithmetic averages of yearly CAGRs. Daily equities fix `P = 252`; never mix frequencies. Net returns must reflect actual path costs, cash yield, and cash-flow adjustments rather than treating raw external flows as return.
- `W_0 = 1, W_t = product(1 + r_i)`; peak tracks `W_0`, signed `MDD = min(W_t / max(W_0..W_t) - 1)`, and loss magnitude is `abs(MDD)` over the exact same path and window as CAGR.
- `Calmar = net_cagr / abs(MDD)`, preserving negative ratios when CAGR is negative. `MDD = 0` yields `null` / `UNCOMPUTABLE` / `zero_drawdown` rather than infinity or automatic pass. Empty, missing, non-finite, or `r <= -1` inputs fail, and numerical overflow marks uncomputable rather than returning `0`.
- Compounding comparisons require identical strategy and benchmark sessions with no silent inner joins (existing `v2` lifecycle drop diagnostics remain unchanged). Period outcomes are not per-trade results; fee/FX/closed-trade attribution in Q06 remains separate.

These are `REPORT_ONLY` definitions adding no unified promotion thresholds. Candidates must freeze reporting, ranking, and veto roles, comparators, thresholds, cost scenarios, and uncomputable rules before viewing holdouts; missing frozen packages forbid `PASS`, and CI green status never proves research edge or trading authority.
