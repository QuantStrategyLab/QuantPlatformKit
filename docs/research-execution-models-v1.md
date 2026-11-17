# Research Execution and Cost Models v1 (A2)

[简体中文](research-execution-models-v1.zh-CN.md)

`quant_platform_kit.research_stats.execution_models` provides pure standard-library helpers that never read accounts, quotes, files, or configuration, and never call brokers. Existing backtest entry points do not migrate automatically.

`FillModel(timing).resolve(signal_index=..., available_index=..., bar_count=...)` returns `FillPoint(index, price_field, timing)`, or `None` when the final signal lacks a subsequent bar. Indices follow the caller's strictly ordered trading calendar, and `available_index` cannot be later than signal-day close.

| `timing` | Fill convention | First return of new position |
|---|---|---|
| `same_close` | Signal-day close price (explicit post-close research assumption) | Next trading day |
| `next_close` | Next trading day's close price | Trading day after next |
| `next_open` | Next trading day's open price | Fill-day open to close |

Missing bars are never interpolated or forward-filled. Callers must validate prices, trading calendars, and corporate actions; raw unadjusted OHLC cannot be mixed directly into total-return series.

`CostModel(commission_bps, slippage_bps, multiplier)` charges on traded security notional per side (cash legs are free). Commission and slippage are one-sided bps summed and multiplied by the stress multiplier; `fraction(turnover)` returns cost relative to pre-trade NAV.

`net_return(gross_return, turnover, charge_at="start")` computes `(1 - cost) * (1 + gross) - 1`, bit-compatible with `cost_stress_recompute`; `charge_at="end"` computes `gross - cost`. Callers must choose one charging convention, avoid double-deducting net returns, and never defer close-fill costs outside the window. The model omits capacity, market impact beyond bps, taxes, dividends, and borrow costs, and authorizes neither real-data runs nor live use.

Offline tests use fixed-seed synthetic data covering all three timings, unavailable signals, terminal unfilled signals, entry/exit costs, invalid inputs, and 100-sample bit-level parity against `cost_stress_recompute`.
