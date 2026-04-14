# Platform Strategy Matrix

_Verified snapshot: 2026-04-14_

This page is the short answer to one question:

> which platforms belong to which strategy domain today, what is live right now, and what is only a future extension point?

For live runtime projects, services, schedulers, runtime identities, and secret names, see [`platform_runtime_inventory.md`](./platform_runtime_inventory.md).

For repository responsibility boundaries, see [`platform_repo_boundaries.md`](./platform_repo_boundaries.md).

## Summary

- There are currently two strategy domains:
  - `us_equity`
  - `crypto`
- Runtime repositories already expose `STRATEGY_PROFILE`, but this is **not** a full multi-strategy marketplace yet.
- Today, each US equity platform can switch among its enabled live `us_equity` profiles through its rollout allowlist.
- The shared contract is in `QuantPlatformKit`; real `us_equity` strategy implementations now live in `UsEquityStrategies`, while platform repositories own runtime adapters and broker execution.

## Current platform matrix

| Platform | Repo | Strategy domain | Current live profile | Runtime model | Real switching today? |
|---|---|---|---|---|---|
| IBKR | `QuantStrategyLab/InteractiveBrokersPlatform` | `us_equity` | `soxl_soxx_trend_income` | Cloud Run | Yes - rollout allowlist can switch among supported profiles |
| Charles Schwab | `QuantStrategyLab/CharlesSchwabPlatform` | `us_equity` | `tqqq_growth_income` | Cloud Run | Yes - rollout allowlist can switch among supported profiles |
| LongBridge | `QuantStrategyLab/LongBridgePlatform` | `us_equity` | `tech_communication_pullback_enhancement` on HK / `tqqq_growth_income` on SG | Cloud Run | Yes - rollout allowlist can switch among supported profiles |
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

Current live profiles in `us_equity`:

- `soxl_soxx_trend_income`
- `tqqq_growth_income`
- `tech_communication_pullback_enhancement`

### `crypto`

Platforms currently in this domain:

- `BinancePlatform`

Current live profile in `crypto`:

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

- selecting any future `us_equity` strategy on any `us_equity` platform by one env change
- every strategy having complete adapter coverage on every broker
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
