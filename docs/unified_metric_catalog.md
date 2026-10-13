# QSL unified quantitative metrics: semantics, capabilities and gaps

This catalog explains the existing [backtest standard](backtest_standard_v1.zh-CN.md), [window metrics](window_metrics_semantics.zh-CN.md) and research-only B3 `build_unified_net_report`. It adds no promotion thresholds, candidates, trading permission or risk budget. See the [Chinese version](unified_metric_catalog.zh-CN.md).

## Outcome metrics

|Metric|Definition|Capability and boundary|
|---|---|---|
|Positive-day share `win_rate`|Positive days / all valid days, including zeros|Existing window metric; not closed-trade win rate|
|Win rate excluding zeros|Positive / (positive + negative) observations|Existing `daily_win_rate_ex_zero`; optional B3 `net_win_rate_ex_zero_per_period`; undefined for all-zero samples|
|Payoff ratio|Mean gain / absolute mean loss|Kelly has mean inputs; optional B3 `net_payoff_ratio_per_period`; both sides required|
|Profit Factor|Total gains / absolute total losses|Existing daily `profit_factor`; optional B3 `net_profit_factor_per_period`; undefined without losses, genuinely zero with losses and no gains|
|Sample mean net return|Arithmetic mean of same-period net returns, including zeros|Optional B3 `mean_net_return_per_period`; neither future profit nor compound growth|
|Closed-trade outcomes|Win rate, payoff, Profit Factor and expectancy on net realized P&L|The standard requires trade win rate/expectancy, but return-series tools do not implement trade pairing/accounting|

Enable the four B3 diagnostics with `include_outcome_diagnostics=True`. Default output retains its original eight metrics. Each new result records positive/negative/zero counts, `aggregation_level=return_observations_not_trades`, `input_basis=same_period_net_returns` and `descriptive_only=true`. Undefined, overflowing or nonzero-underflowing results are `UNCOMPUTABLE` with null value and reason, never infinity or fabricated zero. A complete sample with exactly zero net sum, including all-zero observations or exact positive/negative cancellation, has a known zero mean.

For a consistent sample, `Profit Factor = payoff ratio × positive count / negative count`. The mean including zeros is `p_positive × mean_gain − p_negative × absolute_mean_loss`, with both probabilities using all observations. Do not substitute the excluding-zero probability into this formula. A high win rate can have negative expectancy; positive arithmetic mean does not guarantee positive log growth.

## Core groups for a mature system

|Purpose|Important metrics|Current unified capability|
|---|---|---|
|Return and benchmark|Net log growth, cumulative return, CAGR, aligned excess return, alpha/beta and tracking error|B3 net per-period growth; existing window returns/CAGR/benchmark comparisons, alpha/IR and alignment counts; other attribution/tracking-error projections need explicit conventions|
|Risk-adjusted return|Sharpe, Sortino, Calmar, Information Ratio|Window implementation; B3 unannualized ddof=1 Sharpe; frequency and risk-free conventions must align|
|Loss and tails|Drawdown, monetary loss/duration/recovery, CVaR/ES, VaR, stress loss|B3 initial-NAV drawdown and exact worst-5% probability-mass CVaR95; monetary/duration/VaR/stress projections still need separate inputs|
|Outcome distribution|Win rate, payoff, Profit Factor, mean net return, loss streaks, counts and uncertainty|Four research diagnostics implemented; trade/streak definitions require accounting; bootstrap is separate, not automatic confidence intervals for new outcomes|
|Statistical reliability|PSR, DSR, MinTRL, PBO, walk-forward/OOS, parameter stability|Primitives/B3 available; PBO/bootstrap separate; actual cumulative trials and frozen assumptions must be verified|
|Execution and cost|Turnover, commissions/spread/impact/financing, cost drag, slippage/fill/rejection rates and latency|A2 models and B3 cost drag available; actual quality and denominators require timestamped order/quote/fill evidence|
|Portfolio and capacity|Correlation, concentration, risk contribution, cash/exposure, liquidity and capacity|Separate risk/portfolio tools; no claim of a completed B3 capacity or live-portfolio projection|
|Operations and data|Source/PIT, freshness, funds/position reconciliation, duplicate/unknown orders, report delivery/recovery|Actual runtime/source/receipts required; source CI is insufficient|

Select metrics for the research/trade/portfolio/operations purpose, rather than requiring every strategy to use every metric. Disclose missing preregistered items. Reporting, ranking, veto roles and thresholds remain subject to the existing frozen contract.

## Common evidence requirements

1. Declare observation unit, zero handling, count denominator, window and holdings coverage. `per_period` does not imply daily or annualized.
2. Align costs, cash flows, corporate actions, currencies, cash/financing and signal/fill timing. A `net_returns` argument does not attest underlying accounting; bind A2 reconciliation and source evidence.
3. Declare calendars/annualization for equity sessions versus 24/7 crypto. Window Sharpe defaults to ddof=0; research inference uses ddof=1.
4. Freeze FIFO/other pairing, partial fills/closes, multi-leg grouping, strategy attribution, fees/FX, holding periods and open positions before trade statistics. Orders, fills and positive days are not automatically winning trades.
5. Preserve sample size, data identity and computability. No observed losses does not mean no risk. Missing trade records/prices/NAV are not zeros. Some legacy window ratios retain NaN for compatibility; consumers must handle undefined values explicitly.
6. Bind DSR to the actual cumulative trials under the frozen failed/rejected/interrupted counting rules; preserve PBO/WFA/OOS timing and isolation. Declared ledger counts, implemented formulas and synthetic regression passes do not establish an edge or live adoption.

This batch adds only optional B3 period-return diagnostics and the catalog. Closed-trade statistics remain a separate accounting-dependent implementation; drawdown recovery, capacity and live execution quality follow their own evidence. It does not change existing window semantics, original B3 results, gates, sizing or production pins, or replace B1/B2/B4 freezing and E1 review.
