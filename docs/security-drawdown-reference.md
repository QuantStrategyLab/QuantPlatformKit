# Frozen security drawdown references

`strategy_lifecycle.security_drawdown_reference.describe_security_drawdown_reference`
describes an explicitly selected, frozen historical security proxy. It is broker
independent and accepts no account identifier, capital amount, risk budget,
candidate allocation or execution instruction. Platforms bind their own account
choice and policy separately.

The `qsl.security_drawdown_reference.v1` packet contains `benchmark_symbol`,
`reference_id`, `available_at_utc`, `frozen_at_utc`, `dates`, `returns`, and `context`.
Context declares currency, calendar, window, security series, source SHA-256,
daily frequency, `DAILY_CLOSE` sampling, `SECURITY_BENCHMARK_REFERENCE` wealth
scope, `PROVIDER_ADJUSTED_CLOSE_RATIO`, `PROVIDER_SPLIT_DIVIDEND_ADJUSTED`,
`ACCOUNT_TRADING_COSTS_EXCLUDED`, and `NOT_AN_ACCOUNT` for external flows and
cash income. It must not contain `account_scope`.

The function validates selection, denomination, calendar, sampling, causal
availability/freeze/current-cutoff ordering and finite compoundable daily returns.
It reuses `compute_window_metrics` for maximum drawdown including initial wealth
1; annualization and volatility conventions do not affect this statistic.
Provider pages, data rights, exact calendar coverage and adjustment methodology
are qualified by the source producer, not by these declarations or hashes.
Do not label this price proxy as an account's net total return or an intraday
worst-loss limit. An account path separately needs applicable costs and external
flow adjustments. Current use of a fixed historical reference does not fabricate
historical point-in-time evidence.

The output contains the observed loss fraction, source identity and basis, with
qualification, calibration, enforcement and execution flags false. It returns no
policy limit, account decision, raw path or configuration. Unknown inputs raise
fixed diagnostics rather than defaulting to a zero-loss history. There are no
default securities, historical years, personal percentages or broker settings.
Numerical dependencies are loaded only by this research call; no new core
dependency, storage, scheduler or policy framework is introduced.

[Alpaca's bar documentation](https://docs.alpaca.markets/us/reference/stockbars)
documents price adjustment categories. This supports the provider-adjusted label,
not certification of an account net-return or reinvestment path.
