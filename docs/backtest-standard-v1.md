# QSL Backtest Standard v1 (Research-Only)

[简体中文](backtest-standard-v1.zh-CN.md)

Version: v1. Status: research standard, **documentation only**.

This standard supplements the [Strategy Promotion and Risk Standard](strategy-promotion-risk-standard.md) by specifying what research backtests must report, how metrics are computed, how data identity is labeled, and minimum observation counts. It does not replace or alter promotion metric lists, `strategy_evidence_package.v2`/`v3` schemas, the `BacktestOrchestrator.run_promotion` structural gate, or the [Kelly Contract](kelly-contract-v2.md).

Metric definitions, implemented capabilities, and known input gaps live in the [Unified Metric Catalog](unified-metric-catalog.md). Per-trade expectancy is kept separate from Profit Factor, and daily return observations from closed trades; optional B3 diagnostics never substitute for trade-by-trade ledgers or add promotion thresholds.

## 0. Boundaries

- **No numeric pass thresholds here.** There is no organization-wide Sharpe, CAGR, drawdown, DSR, PBO, or cost cutoff. Every candidate's reporting, ranking, and veto items (metric, comparator, threshold, window, cost tier, and uncomputable handling) must be preregistered **before** viewing holdout results and bound by human acceptance. Unregistered thresholds cannot support a pass claim.
- Research backtests produce research evidence only: `live_ready=false`, `no_order=true`. They grant no paper, shadow, or live authority and never modify risk budgets, platform sizing, or `RiskEngine` vetoes.
- Synthetic data verifies implementation correctness only, never strategy performance. Numbers lacking documented source, window, and data identity per Section 6 must not appear in websites, daily digests, notifications, or PR descriptions.

## 1. Tools and templates

| Purpose | Implementation |
|---|---|
| Probabilistic / Deflated Sharpe (PSR / DSR) | `quant_platform_kit.research_stats.probabilistic_sharpe_ratio` / `deflated_sharpe_ratio` |
| Probability of Backtest Overfitting (PBO, CSCV) | `quant_platform_kit.research_stats.probability_of_backtest_overfitting` |
| Confidence intervals (stationary block bootstrap, fixed seed) | `quant_platform_kit.research_stats.stationary_bootstrap_ci` |
| Cost stress recomputation (default 1x/2x/3x) | `quant_platform_kit.research_stats.cost_stress_recompute` |
| Report template | `BacktestReportV1` + `schemas/backtest-report.v1.schema.json` (`qsl.backtest_report.v1`) |
| Shared window metrics (CAGR, vol, Sharpe, Sortino, Calmar, MDD) | `strategy_lifecycle.performance_metrics` (see [Window Metrics Semantics](window-metrics-semantics.md), [#659](https://github.com/QuantStrategyLab/QuantPlatformKit/issues/659)) |
| Promotion structural gate | `BacktestOrchestrator.run_promotion` (`purged_walk_forward.v1`) |

Function definitions and failure semantics are in the [`research_stats` reference](research-stats.md). All helpers return `UNCOMPUTABLE` or `PARKED` without numeric values when data is insufficient or undefined; **missing is never zero**.

## 2. Required reported metrics

Beyond the `risk.metrics.*` fields required for promotion, research backtest reports must include every item below, explicitly recording status and reason when uncomputable:

| Item | Definition | Default role |
|---|---|---|
| Expected log growth `g` | Per-period `mean(log(1+r))`, with annualization method and base stated | Report; primary comparator for compounding studies |
| CAGR, annualized volatility, MDD | Drawdown includes initial NAV; state `ddof` and annualization base | Report |
| MDD dollar amount, longest recovery | Recovery measured in trading days; note right-censoring if unrecovered | Report |
| CVaR95 (ES) | State tail fraction, sign, quantile/tie handling, and tail sample count | Report |
| PSR, DSR | DSR trial count must include **all** trials (including failed/rejected); insufficient trials yield `UNCOMPUTABLE` | Report |
| PBO | Return matrix across all trials on shared dates; record split count and dropped rows | Report |
| Confidence intervals | At least `g`, Sharpe, and MDD; state method, block length, resamples, seed, and level | Report |
| Costs | Turnover, cost share of gross return, and `g` across each cost tier | Report |
| Benchmark comparison | Same dates and cost basis for `g`, MDD, excess `g`, and beta | Report |
| Trade-level stats | Trade count, per-trade win rate, per-trade expectancy (distinct from positive-return-day ratio) | Report |
| Trial registry | Total, failed, and rejected counts, preregistered selection rules, trial ledger SHA-256 | Required |

Ranking and veto items may only be selected from registered report items and preregistered per Section 0. One metric may serve multiple roles when each role is stated explicitly.

## 3. Cost model

- Costs are **one-sided**: commission + half-spread + impact (bps) per unit traded notional. State whether cash legs incur fees; convert half-L1 conventions before cross-study comparison.
- Report at least three cost scenarios; default multipliers are 1x/2x/3x (`cost_stress_recompute` default). Candidates declare their base bps and source.
- Small-account studies must state integer-share rounding, minimum commissions, or ticket fees, plus settlement rules (e.g., T+N) for sale proceeds.
- Leveraged ETF expense ratios and volatility decay are already embedded in prices and must not be double-counted; list margin or borrow costs separately if applicable.
- Never deduct the same cost twice; gross return inputs must document which costs are included or excluded.
- Candidates preregister whether cost stress acts as a veto and at which multiplier.
- Backtests lacking a cost model (such as un-costed crypto studies) must be labeled uncosted and excluded from same-window comparisons.

## 4. Data hygiene and timing

1. Bind every result to a `data_manifest` recording source, license, date range, generation timestamp, and SHA-256.
2. **Signal causal cutoff**: signals may only use data known at or before `as_of`.
3. **Execution timing** must select one value in `timing.execution`:
   - `next_open`: signal after close, fill at next trading day's open.
   - `next_close`: fill at next completed trading day's close.
   - `same_close_research_only`: signal-day close fill, allowed as sensitivity reference only and **never** for promotion comparisons or mixing with other fill timings.
   Same-window comparisons must use identical execution timing.
4. Adjustments: price-based signals use split-adjusted prices; returns use total return (reinvested or cash-credited, explicitly stated). Never mix both.
5. Book corporate actions by effective date; disclose limitations when announcement timestamps cannot be verified.
6. Universe strategies must use point-in-time constituents including delistings; otherwise mark `SURVIVORSHIP_UNVERIFIED` and forbid promotion.
7. Never zero-fill missing prices or forward-fill returns; mark uncomputable rather than silently intersecting mismatched strategy and benchmark dates.
8. Explicitly state calendar (`XNYS`, `XHKG`, `24x7`) and annualization base.

## 5. Out-of-sample and walk-forward rules

- Promotion keeps the `purged_walk_forward.v1` structural gate: at least 3 ordered folds, positive purge/embargo, and at least 12 calendar months of locked independent OOS.
- Purge must cover at least the longest signal lookback plus holding/label horizon; embargo must cover at least the holding period, with exact days declared in the report.
- Select parameters using training segments only; each fold strictly follows estimate -> apply to next segment, declaring anchored or rolling windows upfront.
- Run locked OOS once only; never tune parameters afterward. Changes require a new trial and new evidence package.

### Data identity

`data.data_identity` must be one of three values:

| Identity | Meaning |
|---|---|
| `development` | Any interval inspected or used for tuning; repeatedly reused history stays `development` and may never be relabeled OOS |
| `locked_oos` | Holdout interval run once after freezing the candidate |
| `forward` | Real-time shadow/paper observations accumulated post-freeze |

`development` data cannot be labeled `OOS_EVALUATED` (enforced by template and schema).

## 6. Minimum observation gates

This standard adds no new numeric gates and summarizes existing conventions only; unlisted evaluation purposes must be declared and human-accepted per candidate.

| Purpose | Existing convention | Source |
|---|---|---|
| Kelly risk-share estimate | >= 30 return samples, both positive and negative returns, MDD observed | [Kelly Contract v2](kelly-contract-v2.md) |
| PSR / DSR structural floor | Default `min_observations=30` (structural floor only, not a quality bar); >= 2 trials for DSR | `research_stats` |
| PBO | >= 2 trials, >= `min_rows_per_block` rows per split block | `research_stats` |
| Promotion locked OOS | >= 12 calendar months, >= 3 purged folds | `run_promotion` |
| Forward observation | Declared in candidate's `ForwardObservationPolicy` (e.g., 252 XNYS trading days with paired shadow for SOXL V7) | [Forward Observation Contract](forward-observation-runtime-contract.md) |

Results below these thresholds stay `PARKED` or `UNCOMPUTABLE` with no extrapolation or position recommendation.

## 7. Report template and summary

Structured outputs use `qsl.backtest_report.v1` (`BacktestReportV1.to_dict()`, validated against the packaged JSON Schema), enforcing:

- `live_ready=false` and `no_order=true`
- Non-`COMPUTED` metrics carry `value=null` and `reason_code`
- Benchmark comparison sets `same_dates=true`
- Each metric's cost multiplier appears in `cost_model.scenario_multipliers`
- Veto items record `frozen_at` and `frozen_by`

Human-readable summaries must state data source and interval, data identity, execution timing, cost tiers, total trial count (including failures), whether DSR/PBO were computed, confidence-interval methodology, and limitations. Numbers lacking any item must not be cited externally.

## 8. Portfolio allocation methods

Max compounding (fractional Kelly / drawdown-constrained growth optimization) and Markowitz (mean-variance, min-variance, risk parity) studies follow the UES [Portfolio Risk Budget Contract](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/main/docs/research/portfolio-risk-budget-contract.md). Results must:

- Compare against `1/N`, fixed weights, and unlevered benchmarks over identical executable constraints, dates, and cost basis.
- Evaluate strictly walk-forward (estimate in train, apply to next segment) and report under this standard.
- Output advisory `APPROVE` / `REDUCE` / `PARKED` verdicts through `portfolio_risk_budget` without raising risk budgets or permitting full Kelly.

## 9. Known gaps (tracked, not resolved here)

- Shared metric semantics mismatch: silent benchmark date intersection, `win_rate` measuring positive return days, `profit_factor` based on daily returns ([#659](https://github.com/QuantStrategyLab/QuantPlatformKit/issues/659)). Explicit diagnostics (`qpk.window_metrics.v2`: alignment counts, `daily_win_rate_ex_zero`, `zero_return_days`, `volatility_ddof`) preserve legacy values (see [Window Metrics Semantics](window-metrics-semantics.md)); per-trade win rate remains absent.
- Simulator execution timing differences (`same_close` / `next_close` / `next_open`) — [UES #575](https://github.com/QuantStrategyLab/UsEquityStrategies/issues/575).
- Un-costed Binance research backtests — [BinancePlatform #366](https://github.com/QuantStrategyLab/BinancePlatform/issues/366).
