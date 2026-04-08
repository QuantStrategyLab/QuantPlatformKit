# Platform Strategy Matrix

_Verified snapshot: 2026-03-30_

This page is the short answer to one question:

> which platforms belong to which strategy domain today, which profiles are configurable, and what is only a future extension point?

For runtime projects, services, schedulers, runtime identities, and secret names, see [`platform_runtime_inventory.md`](./platform_runtime_inventory.md).

For repository responsibility boundaries, see [`platform_repo_boundaries.md`](./platform_repo_boundaries.md).

## Summary

- There are currently two strategy domains:
  - `us_equity`
  - `crypto`
- Runtime repositories already expose `STRATEGY_PROFILE`, but this is **not** a full multi-strategy marketplace yet.
- Today, each platform repository still supports only its configurable profile scope.
- The shared contract is in `QuantPlatformKit`; real strategy implementations still live in the platform runtime repositories.

## Current platform matrix

| Platform | Repo | Strategy domain | Configurable profile scope | Runtime model | Real switching today? |
|---|---|---|---|---|---|
***REMOVED***
***REMOVED***
| LongBridge | `QuantStrategyLab/LongBridgePlatform` | `us_equity` | `STRATEGY_PROFILE=<runtime_enabled us_equity profile>` | Cloud Run | configurable |
| Binance | `QuantStrategyLab/BinancePlatform` | `crypto` | `crypto_leader_rotation` | Oracle Cloud + self-hosted runner | No - only this profile is supported today |

## What this means right now

### `us_equity`

Platforms currently in this domain:

- `InteractiveBrokersPlatform`
- `CharlesSchwabPlatform`
- `LongBridgePlatform`

Important limitation:

- This does **not** mean every `us_equity` strategy can already run on every `us_equity` platform.
- It only means these platforms now share the same top-level domain and compatibility model.
- Each concrete strategy still needs its own platform-compatibility declaration and runtime fit.

Configurable profile scopes in `us_equity`:

- `soxl_soxx_trend_income`
- `tqqq_growth_income`
- `qqq_tech_enhancement`

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

- selecting any `us_equity` strategy on any `us_equity` platform by one env change
- shared cross-platform strategy implementation packages
- independent strategy repositories that are already used in production

## Recommended interpretation

Use the current model like this:

- first choose the **platform repository**
- then choose the **supported strategy profile for that platform**
- do not assume a shared domain automatically means shared implementation

## Recommended next step

Before extracting real strategy implementations, keep doing this in order:

1. keep runtime naming and docs aligned
2. keep the platform/domain/profile matrix accurate
3. wait until at least one `us_equity` strategy is truly ready to be reused across IBKR / Schwab / LongBridge
4. then extract by **strategy domain**, not by broker
