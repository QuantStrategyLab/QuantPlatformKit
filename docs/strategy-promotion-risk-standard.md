# Strategy Promotion and Risk Standard

[简体中文](strategy-promotion-risk-standard.zh-CN.md)

This standard defines unified gates for strategy promotion, plugin automation, AI optimization, and Kelly readiness.

Research backtest reporting items, cost models, timing, data identity, and minimum observation rules appear in [QSL Backtest Standard v1](backtest-standard-v1.md) (module `research_stats`, template `qsl.backtest_report.v1`); that standard sets no numeric pass thresholds.

## Core principles

- Satisfy `live_ready` before considering automated release or capital impact.
- `kelly_ready` only means risk-budget caps are computable, explainable, and bounded; it **never** justifies promotion.
- Every automated action must bind to a traceable evidence package.
- Every AI optimization run must preserve the full trial ledger rather than keeping only winning parameters.

## `live_ready` vs. `kelly_ready`

| State | Meaning | Valid as promotion basis |
|---|---|---|
| `live_ready` | Meets rollout, operational, monitoring, and risk requirements for controlled live admission | Yes |
| `kelly_ready` | Computes Kelly risk-budget caps while possibly still failing rollout gates | No |

Requirements:

- `kelly_ready` may only cap maximum risk budgets, position limits, and drawdown tolerance.
- `kelly_ready` never replaces backtest, OOS, cost, risk, data-integrity, or plugin gates.
- A strategy holding `kelly_ready` alone remains non-live.

Additionally, Kelly outputs research recommendations only and remains capped by portfolio risk budgets, position caps, and fractional Kelly limits without increasing existing budgets. Insufficient samples, missing positive/negative returns, missing drawdown observations, or breached drawdown limits force `PARKED` with zero suggested weight; never extrapolate from small samples.

## Paper-trading minimum observation period

The minimum paper-trading observation period counts **completed full trading days on the relevant exchange calendar**, never calendar days or elapsed hours. Observations must span the entire regular trading session; open sessions, partial coverage, half-days, and early closes do not count. Exchange weekends and holidays do not count, and days missing calendar, timezone, or full-session evidence cannot be assumed valid. Each completed trading day counts once.

Minimum observation length must be configured explicitly as an **integer from 3 to 5 inclusive**, with **5 completed trading days** recommended. Under strict fail-closed semantics, unset, missing, unreadable, mistyped, or out-of-range values fail the gate without falling back to fewer days or passing merely because 5 days elapsed. Booleans are rejected; `None`, `"5"`, `3.0`, `True`, `False`, `2`, `6`, `0`, and negatives are invalid—only integers `3`, `4`, and `5` are valid.

Meeting the minimum observation period is necessary only; it neither establishes `live_ready` nor grants promotion or capital authority. Unresolved reconciliation breaks, open alerts, unchanged passing risk checks, and an explicit owner decision remain mandatory. Short 3-5 day windows can miss operational faults or market regimes. Live, Kelly, and all stop-loss switches (including `PORTFOLIO_LOSS_STOPLOSS_ENABLED`) stay OFF.

This section sets a baseline Paper window only and never shortens candidate-specific research, shadow, or forward windows. Frozen policies in the [Forward Observation Runtime Contract](forward-observation-runtime-contract.md) (such as the 252-day SOXL example) continue applying and cannot be bypassed by satisfying 3-5 Paper days.

These rules remain documented policy without wiring a global Paper day counter or auto-release gate; existing validators, schemas, and promotion checks stay unchanged.

## Minimum required risk metrics

The `risk` section of an evidence package must include all of:

- `risk.metrics.sharpe_ratio`, `sortino_ratio`, `max_drawdown`, `annualized_return`, `annualized_volatility`, `calmar_ratio`, `information_ratio`
- `risk.metrics.var_95`, `cvar_95`, `turnover`, `trade_count`, `win_rate`, `profit_factor`
- `risk.benchmark.name`, `alpha`, `beta`
- `risk.cost_stress.slippage_bps`, `commission_bps`, `passed`
- `risk.oos.window_start`, `window_end`, `locked`

Requirements:

- Missing any item makes the risk evidence package non-auditable.
- `risk.metrics` may carry extra fields, not a loose unvalidated object.
- `full_kelly_allowed=false` constrains Kelly caps only and never substitutes for these metrics.

## Unified evaluation semantics and categorized acceptance

This section aligns existing research and risk evaluation standards without modifying metric implementations, evidence schemas, frozen candidates, thresholds, or runtime permissions. Machine gates still check v2/v3 fields as implemented; complete documentation does not prove producer adoption or empirical verification.

### Shared metric semantics

New candidates document these conventions alongside producer source revisions and pinned consumer dependencies, without extending closed schemas ad hoc or reusing pre-change acceptances across semantic changes:

| Check area | Shared declaration |
|---|---|
| Sample and expectation | Separate account/strategy daily NAV returns, asset returns, per-trade returns, and scenario terminal values; declare simple vs. log returns, sample counts, effective samples, warmup/zero handling, and trade pairing. Name daily mean, per-trade expectancy, and expected log growth separately rather than calling positive-return days trade win rate. |
| Time and valuation | Declare currency, valuation timestamp, calendar/timezone, signal causal cutoff, fill timing, windows, and benchmarks; compare identical dates and cash-flow treatment without zero-filling or silent inner joins on missing dates. |
| Costs and cash | Separate gross vs. net returns; record commission, slippage, impact, financing assumptions, cash yield, dividends, FX, and external flows without double-counting or assuming missing cost terms are covered. |
| Annualization and inference | Declare `rf`/`MAR`, frequency, annualization base, variance `ddof`, and benchmark alignment; `rf=0` is an explicit assumption rather than zero funding cost. Identical names never mask different formulas or units. |
| Tails and drawdown | Declare VaR/ES/CVaR tail fraction, sign, quantile/tie handling, and tail observation count; drawdowns include initial NAV, and recovery durations state session units and right-censoring. Empirical tails do not guarantee population risk. |
| Uncomputable and uncertainty | Distinguish true zeros, undefined values, insufficient samples, and not-applicable fields with reason codes; disclose NaN/`None`/sentinel conventions rather than replacing missing fields with passing placeholders. |

Verify comparability across all axes before comparing performance in one window; never swap asset covariance, strategy net returns, trade expectancy, and scenario growth scores. Where serial dependence exists, state uncertainty methods and limits; plain annualized Sharpe or block bootstrap alone provides neither autocorrelation adjustment nor multiple-testing control. Keep uncomputed `PBO`/`DSR` states explicit.

### Separate registration of reporting, ranking, and veto roles

- **Reporting items** document computed values, sample sizes, and limits without acting as pass gates.
- **Ranking items** fix primary objective, comparators, and tie-breaking before inspecting candidates; heuristic scores stay scoped to their original research purpose.
- **Veto items** freeze metric, comparator, threshold, window, cost stress, uncomputable handling, and failure action under the candidate revision and human acceptance before inspecting holdout data; missing required evidence cannot be offset by strong performance elsewhere.

One metric may serve multiple roles if each role is explicit. AI-generated or AI-optimized candidates follow identical semantics and gates without relaxed lanes; display layers consume producer outcomes without recomputing metrics or presenting structural PASS as economic validity.

### Categorized acceptance and independent portfolio risk

Data, calculation semantics, evidence, and freeze workflows are standardized without forcing every strategy into one Sharpe or MDD threshold. Trend, mean-reversion, cash-defense, and leveraged-ETF categories declare their own objectives, benchmarks, primary comparators, and risk gates upfront without borrowing thresholds from another category. Development, tuning, locked OOS, and forward observations retain distinct identities.

Markowitz, fractional Kelly, and empirical log-growth are separate portfolio allocation/risk analyses rather than additive single-strategy scores. Account-level constraints and net-cost comparisons follow the [UES Portfolio Risk Budget Contract](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/main/docs/research/portfolio-risk-budget-contract.md), while QPK Kelly units and caps follow [Kelly Contract v2](kelly-contract-v2.md). No research optimum or positive growth estimate may override leverage, concentration, liquidity, drawdown/breaker limits, or `RiskEngine` vetoes. (`STRAT-02`, `STRAT-04`, and `STRAT-05` track remaining empirical verification gaps.)

## Required evidence package files

Before promotion, an evidence package must contain all of:

- `returns`, `trades`, `positions`, `config`, `data_manifest`
- `candidate_registry`, `benchmark_registry`, `cost_model`, `risk_report`, `kelly_readiness_report`

Requirements:

- Missing any file invalidates promotion eligibility.
- All files must share one `evidence_package_id` and matching content revision.
- `kelly_readiness_report` documents risk budgets only and never replaces `risk_report`.

## AI auto-optimization requirements

1. Record every trial, including failed, rejected, short-window, and manually stopped trials—never retain winning parameters alone.
2. Link every trial record back to its inputs, objectives, evaluation window, and outputs.
3. Freeze parameters once OOS results are locked; never tune parameters afterward—changes require a new trial and evidence package.
4. AI optimization conclusions never bypass `live_ready` gates.

### Binding drift re-optimization to shadow

After budget checks pass and before recording shadow, `run_research_promotion_cycle` must invoke `enforce_promotion_backtest_gates`, accepting either:

- `PromotionBacktestRun` from `BacktestOrchestrator.run_promotion`; or
- An explicit summary with `status=PASS` matching evidence package `backtest` fields: `BacktestOrchestrator`, `purged_walk_forward.v1`, `>= 3` ordered folds, positive purge/embargo, and locked independent `>= 12` calendar-month OOS not used for parameter selection.

Missing callbacks, missing fields, non-`PASS` status, identity mismatch, or callback errors fail closed: the ticket moves to `PARKED` without calling shadow. This gate verifies strict backtest evidence only and grants no paper, shadow, or live authority.

## Plugin automation gates

When a plugin sets `position_control_allowed=true`, it must satisfy all of:

- Bind a valid `evidence_package_id`.
- Declare an explicit validity window (`start` / `end` or equivalent expiry fields).
- Emit an auditable, verifiable, rejectable `bounded budget`.

`position_control_allowed=true` remains active only within that package's valid window and expires upon invalidation, expiration, or replacement. `bounded budget` must never be unbounded, implicit, or informal.

## Promotion sequence

1. Research complete
2. Evidence package complete
3. `live_ready` passed
4. Plugin gate passed
5. Automation release checks passed
6. Optional separate `kelly_ready` evaluation for tighter risk-budget caps

## Minimal checklist

- [ ] `live_ready` passed
- [ ] `kelly_ready` used strictly as an upper bound, never as promotion justification
- [ ] All evidence package files present
- [ ] All AI trials recorded
- [ ] No post-OOS parameter tuning
- [ ] `position_control_allowed=true` bound to `evidence_package_id`
- [ ] Evidence package validity window explicit
- [ ] `bounded budget` emitted and auditable

## `strategy_evidence_package.v2` promotion evidence gate

Promotion reruns must emit explicit versioned packages (`v2` or `v3` below); `v1`/aliases remain for research/monitoring compatibility without automatic upgrade. `v2` binds:

- Strategy/source revision and input provenance (`license`, range, timestamp, manifest digest).
- `BacktestOrchestrator` `purged_walk_forward.v1` output with `>= 3` ordered folds, positive purge/embargo, and locked independent `>= 12` calendar-month OOS.
- Calendar, timezone, signal/execution timing, and config, data-manifest, backtest, risk, IC, and cost artifacts with actual byte sizes and SHA-256 digests.
- Every required risk metric plus `information_coefficient` (present, non-`bool`, finite) with cost and risk status `PASS`.
- Human acceptance (`decision`, `id`, `actor`, timestamp, `authority_receipt_sha256`) bound to `evidence_core_sha256`.

Machine checks validate structure, identity, finiteness, dates, digests, and `PASS` statuses only; numeric thresholds for Sharpe, return, MDD, or IC stay with bound human acceptance.

The `v2` gate yields research promotion eligibility only, keeping `live_ready=false`, `size_zero_required=true`, and `no_order=true` fixed; `requested_stage`, CI, PRs, reviews, health checks, or notifications cannot alter those flags, and live/runtime requests stay `HOLD` (preserving P3 `TERMINALLY_PARKED_NO_MEMBER` where applicable).

### `v3`: applicability expression for `information_coefficient` only

`strategy_evidence_package.v3` alters `metrics.information_coefficient` only:

- Computed: `{"status":"computed","value":-0.2}` where `value` is a finite non-`bool` number in `[-1, 1]` (negative values remain valid; no positive IC cutoff is added).
- Not applicable: `{"status":"not_applicable","reason_code":"no_prediction_target","reason":"<non-empty reason explaining fixed producer has no prediction target or future label>"}` without `value` (not even `null`) or extra fields.

Predictive IC measures correlation between decision-time forecast scores and subsequent realized labels, requiring declared prediction target, label horizon, alignment timing, and method; contemporaneous correlation with a benchmark cannot substitute for predictive IC.

Not-applicable declarations belong only to verified fixed producer designs rather than CLI switches or caller exemptions. Missing samples, missing labels, constant predictions, or calculation errors are never `no_prediction_target` and cannot be masked as N/A or zero. Existing IC artifact digests, evidence core hashing, and human acceptance apply unchanged; semantic shifts require fresh acceptance rather than reusing old acceptances. Offline consumers must register both packaged schemas locally without network lookups. Packages without human acceptance stay `HUMAN_REQUIRED`, keeping `live_ready=false`, `size_zero_required=true`, and `no_order=true`.
