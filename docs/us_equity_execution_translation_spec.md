# US equity execution translation spec

## Goal

This document defines the P3 rule set for translating a unified US equity
`AllocationIntent` into broker-native execution targets.

It sits between:

- strategy-side `target_mode`
- platform-side broker execution payloads

It does **not** define strategy formulas, platform input builders, or broker
order sequencing.

## Native execution modes by platform

Current native preferences are:

- `ibkr`: `weight`
- `schwab`: `value`
- `longbridge`: `value`

That means platform runtimes must support these translation paths:

- `weight -> value`
  - needed for `schwab`
  - needed for `longbridge`
- `value -> weight`
  - needed for `ibkr`

If a platform and strategy already share the same mode, no translation is
needed beyond validation and normalization.

## Translation boundary

Strategy code owns:

- semantic target intent
- risk flags
- diagnostics
- canonical `target_mode`

Platform code owns:

- conversion into broker-native target units
- lot-size rounding
- min-trade filtering
- executable cash checks
- broker-specific order sequencing
- fail-closed behavior when required live pricing is missing

Strategies must never implement broker translation directly.

## Required inputs to translation

The translation layer may depend on:

- `AllocationIntent`
- `PortfolioSnapshot`
- latest executable price map
- platform execution config

It must **not** depend on raw broker env vars from strategy code.

## `weight -> value` rules

When a `weight` strategy runs on a value-native platform:

1. choose a translation base
   - default: `portfolio_snapshot.total_equity`
   - if the platform later needs a narrower deployable base, that override must
     be explicit in platform config
2. compute target gross dollar value per symbol
   - `target_value = target_weight * translation_base`
3. preserve explicit zero targets
   - `target_weight=0` must map to `target_value=0`
4. do not silently renormalize strategy weights unless the strategy contract
   explicitly allows it
5. keep cash residue handling in the platform layer
   - rounding leftovers
   - min-trade leftovers
   - broker-specific buying-power limits

## `value -> weight` rules

When a `value` strategy runs on a weight-native platform:

1. choose a translation base
   - default: `portfolio_snapshot.total_equity`
2. require a live price for every non-zero target symbol
3. compute target weight from target dollar value
   - `target_weight = target_value / translation_base`
4. preserve explicit zero targets
5. do not let missing prices silently turn into partial execution
   - the platform should fail closed or no-op with an explicit reason

## Cash and residual handling

Residual cash is a platform execution concern, not a strategy concern.

Translation may leave residual cash because of:

- round lots
- minimum notional rules
- broker precision limits
- unavailable prices

Platforms may surface these diagnostics, but must not push them back into the
strategy contract.

## Safe-haven and parking symbols

If a strategy explicitly outputs a parking symbol such as `BIL` or `BOXX`,
translation must preserve that symbol as part of the target set.

Platforms must not replace the safe-haven symbol with broker-local cash logic
unless the strategy contract explicitly allows that substitution.

## Rounding and thresholds

These rules belong to the platform execution layer:

- share rounding
- fractional-share support checks
- minimum trade threshold
- order type selection
- time-in-force

They must happen **after** target-mode translation.

## Failure policy

If translation cannot produce a safe executable target set, the platform must
emit an explicit blocked/no-op outcome.

Typical fail-closed reasons include:

- missing live price for required symbols
- zero or invalid translation base
- unsupported broker precision for required target set

The blocked reason should appear in platform diagnostics or runtime reports.

## Current live-profile implications

- `global_etf_rotation`
  - strategy contract is now `market_history` + `target_mode=weight`
  - `schwab` / `longbridge` need `weight -> value`
- `tqqq_growth_income`
  - strategy contract is now canonical `value`
  - `ibkr` needs `value -> weight`
- `soxl_soxx_trend_income`
  - strategy contract is now canonical `value`
  - `ibkr` needs `value -> weight`
- `russell_1000_multi_factor_defensive`
  - still artifact-driven, but cross-platform rollout later also depends on
    translation support
- `qqq_tech_enhancement`
  - same as Russell: artifact path first, translation path next

## Review rule for P3 PRs

A P3 execution-translation PR should state clearly:

- which translation path changed
- what translation base it uses
- where live prices come from
- what happens on missing prices
- which rounding/min-trade rules stay platform-local
