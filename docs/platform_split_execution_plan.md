# Platform Split Execution Plan

_Verified snapshot: 2026-03-30_

This document turns the current platform/strategy review into an execution plan.

## Final target

### Naming target

For deployable runtime units, use:

```text
{platform}-quant-{strategy}-{scope?}-service
```

Examples:

- `interactive-brokers-quant-global-etf-rotation-service`
- `charles-schwab-quant-hybrid-growth-income-service`
- `longbridge-quant-semiconductor-rotation-income-hk-service`
- `longbridge-quant-semiconductor-rotation-income-sg-service`
- `binance-quant-crypto-leader-rotation-service`

For runtime-facing prefixes such as logs / Telegram labels, keep:

```text
{platform}-quant-{strategy}-{scope?}
```

Do not force the `-service` suffix into every user-facing prefix if it hurts readability.

Scheduler names should follow:

```text
{service-name}-scheduler
```

Trigger names should follow:

```text
{platform-or-repo}-{strategy}-{scope?}-main-deploy
```

Examples:

- `interactive-brokers-quant-global-etf-rotation-service-scheduler`
- `charles-schwab-platform-hybrid-growth-income-main-deploy`
- `longbridge-platform-semiconductor-rotation-income-hk-main-deploy`

### Repository target

- one repository per platform runtime
- one shared `QuantPlatformKit`
- future strategy code split by domain first, not by broker

Recommended future strategy repositories:

- `UsEquityStrategies`
- `CryptoStrategies`

### Strategy-selection target

- crypto platforms may only select `crypto` strategies
- US-equity platforms may only select `us_equity` strategies
- platform repositories choose a strategy by configuration
- shared strategy implementations should eventually live outside the platform runtime repositories

## Current distance from target

### Near target

- Cloud Run service naming for IBKR / Schwab / LongBridge is already close to the final pattern
- strategy domains are already explicit: `us_equity` and `crypto`
- each platform already exposes `STRATEGY_PROFILE`
- common strategy contract already lives in `QuantPlatformKit`

### Midway

- platform repositories enforce domain/profile compatibility, but each still supports only one real profile today
- LongBridge and IBKR runtime-facing naming is now mostly aligned, but the final `-service` rule is not yet applied everywhere
- Binance has now been renamed to `BinancePlatform`; the remaining work is strategy/code split, not repo naming

### Still far

- there are no independent strategy repositories yet
- platform repositories still import local strategy implementations directly
- changing `STRATEGY_PROFILE` does not yet load an external strategy package
- US-equity platforms cannot yet share the same strategy implementation package in production

## Phase plan

### Phase 1: freeze naming rules

Goal:

- define one final naming rule for runtime units, runtime prefixes, schedulers, and triggers

Tasks:

1. keep Cloud Run / VPS service naming rule in docs
2. keep runtime prefix rule in docs
3. keep scheduler and trigger naming rule in docs
4. avoid changing GCP project ids in this phase

Exit criteria:

- docs clearly state the final naming rules
- no active disagreement remains about `-service` usage

### Phase 2: finish platform repository naming

Goal:

- make repository naming consistent across all platform runtimes

Tasks:

1. keep `BinancePlatform` as the runtime repo name
2. keep Oracle/VPS dispatch, runner, and local workspace paths aligned with the renamed repo
3. continue with strategy split work after runtime verification

Exit criteria:

- all runtime repos follow the platform naming style

### Phase 3: align runtime-unit names to the final pattern

Goal:

- move live runtime-unit names to the final `...-service` pattern

Tasks:

1. rename IBKR Cloud Run service
2. rename Schwab Cloud Run service
3. rename LongBridge HK / SG Cloud Run services
4. rename or define the Binance VPS runtime unit name
5. update matching scheduler / trigger names and URLs
6. update docs and runtime inventory

Exit criteria:

- every live runtime unit follows the final service naming rule
- schedulers and triggers match the same naming scheme

### Phase 4: create strategy-repository skeletons

Goal:

- create the future split boundary without moving all strategy code at once

Tasks:

1. create `UsEquityStrategies`
2. create `CryptoStrategies`
3. define packaging / versioning model
4. decide how platform repos consume released strategy packages

Exit criteria:

- empty but real strategy repositories exist
- package/version flow is chosen

### Phase 5: move the first real strategies out

Goal:

- prove the split with the safest first strategies

Recommended first extraction:

- `global_etf_rotation` -> `UsEquityStrategies`
- `crypto_leader_rotation` -> `CryptoStrategies`

Not recommended as the first extraction:

- SOXL/TQQQ-related strategies
- highly platform-shaped runtime logic

Exit criteria:

- at least one `us_equity` strategy and one `crypto` strategy are loaded from outside the platform repo

### Phase 6: let platform repos load external strategies

Goal:

- make `STRATEGY_PROFILE` choose a real external implementation

Tasks:

1. extend the shared strategy contract if needed
2. load implementations from the domain strategy packages
3. keep platform/domain compatibility checks
4. keep platform-specific runtime config in the platform repos

Exit criteria:

- changing `STRATEGY_PROFILE` can select a supported external strategy implementation
- unsupported domain/profile combinations still fail fast

### Phase 7: migrate additional strategies gradually

Goal:

- move the remaining platform-local strategies only after the first split works

Recommended order:

1. `hybrid_growth_income`
2. `semiconductor_rotation_income`
3. SOXL/TQQQ-related strategies later

Exit criteria:

- remaining extracted strategies justify their own shared package placement
- platform repos no longer keep reusable strategy math locally unless it is still platform-specific

## Working rule during execution

Always prefer this order:

1. inspect current code and runtime state
2. do the smallest safe change
3. verify locally or against live config
4. push only after the verification matches the intended phase goal
