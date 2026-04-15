# Platform Strategy Matrix

_Verified snapshot: 2026-04-15_

This page is the short answer to one question:

> which platforms belong to which strategy domain today, which profiles are configurable, and what is only a future extension point?

For runtime projects, services, schedulers, runtime identities, and secret names, see [`platform_runtime_inventory.md`](./platform_runtime_inventory.md).

For repository responsibility boundaries, see [`platform_repo_boundaries.md`](./platform_repo_boundaries.md).

## Summary

- There are currently two strategy domains:
  - `us_equity`
  - `crypto`
- Runtime repositories already expose `STRATEGY_PROFILE`, but this is **not** a full multi-strategy marketplace yet.
- Today, each US equity platform can switch among the `runtime_enabled` `us_equity` profiles published by `UsEquityStrategies`.
- Platform runtime adapters are generated from strategy input/target-mode declarations plus platform capabilities, so new in-contract profiles should not need per-platform allowlist edits.
- The shared contract is in `QuantPlatformKit`; real `us_equity` strategy implementations now live in `UsEquityStrategies`, while platform repositories own runtime adapters and broker execution.

## Current platform matrix

| Platform | Repo | Strategy domain | Configurable profile scope | Runtime model | Real switching today? |
|---|---|---|---|---|---|
***REMOVED***
***REMOVED***
***REMOVED***
| Binance | `QuantStrategyLab/BinancePlatform` | `crypto` | `crypto_leader_rotation` | Oracle Cloud + self-hosted runner | No - only this profile is supported today |

## What this means right now

### `us_equity`

Platforms currently in this domain:

- `InteractiveBrokersPlatform`
- `CharlesSchwabPlatform`
- `LongBridgePlatform`

Important limitation:

- This does **not** mean any arbitrary future `us_equity` strategy can run by name alone.
- It means strategies that stay inside the shared input/target-mode contract can be admitted through `UsEquityStrategies` metadata and generated runtime adapters.
- If a strategy needs a new input type or broker capability, the shared contract and platform capability matrix must be extended first.

Currently enabled live profiles in `us_equity`:

- `dynamic_mega_leveraged_pullback`
- `global_etf_rotation`
- `mega_cap_leader_rotation_dynamic_top20`
- `russell_1000_multi_factor_defensive`
- `soxl_soxx_trend_income`
- `tqqq_growth_income`
- `tech_communication_pullback_enhancement`

### `crypto`

Platforms currently in this domain:

- `BinancePlatform`

Configurable profile scope in `crypto`:

- `crypto_leader_rotation`

Current practical rule:

- Binance is the only live `crypto` platform today.
- Binance should not be treated like the Cloud Run platforms; its runtime model remains Oracle Cloud + self-hosted runner.

## What is already in place

These pieces are already real and shared:

- common strategy domain and profile contract in `QuantPlatformKit`
- per-platform strategy registry in each runtime repository
- fail-fast validation when `STRATEGY_PROFILE` is unsupported for that platform

## What is not finished yet

These are **not** true yet:

- selecting a future `us_equity` strategy before it has a catalog entry, manifest, base runtime adapter spec, and supported input contract
- running strategies that require new platform capabilities before those capabilities are added to the shared matrix
- independent strategy repositories outside `UsEquityStrategies` that are already used in production

## Recommended interpretation

Use the current model like this:

- first choose the **platform repository**
- then choose the **supported strategy profile for that platform**
- do not assume a shared domain automatically means shared implementation

## Recommended next step

Before extracting real strategy implementations, keep doing this in order:

1. keep runtime naming and docs aligned
2. keep the platform/domain/profile matrix accurate
3. keep strategy-layer behavior and cadence in `UsEquityStrategies`
4. keep platform docs focused on runtime adapters, profile enablement, and broker execution
