# Deployment Model

## Summary

- `QuantPlatformKit` remains the shared platform package and is **not deployed as a runtime service**.
- The current runtime repositories (`InteractiveBrokersPlatform`, `CharlesSchwabPlatform`, `LongBridgePlatform`, `BinanceQuant`) are the **transitional deployment units**.
- The **target state** is one deployment repository per broker platform, with strategy behavior selected by configuration such as `STRATEGY_PROFILE`.
- Strategy or platform repositories should always depend on a fixed `QuantPlatformKit` Git tag instead of `main`.

For the live runtime inventory across repositories, projects, services, schedulers, runtime identities, and current secret names, see [`platform_runtime_inventory.md`](./platform_runtime_inventory.md).

For a cleaner split between shared package code, platform runtime repositories, and future strategy repositories, see [`platform_repo_boundaries.md`](./platform_repo_boundaries.md).

For the current platform / strategy-domain / live-profile matrix, see [`platform_strategy_matrix.md`](./platform_strategy_matrix.md).

## Current state vs target state

### Current transitional state

- `InteractiveBrokersPlatform`
- `CharlesSchwabPlatform`
- `LongBridgePlatform`
- `BinanceQuant`

These runtime repositories still own:

- strategy rules
- orchestration
- runtime entrypoints
- deployment configuration

This state is acceptable while migration is ongoing, but it is not the final operating model.

### Target state

The long-term deployment model should be:

- one repository per broker platform
- one shared `QuantPlatformKit` dependency
- strategy selection by configuration
- service split by account or region where necessary

That means:

- one **IBKR platform repo**
- one **Charles Schwab platform repo**
- one **LongBridge platform repo**
- one **Binance platform repo**

The runtime and deployment boundaries should already follow the platform split.

## Repository responsibilities

### Shared platform package

- `QuantPlatformKit`
  - shared domain models
  - narrow ports for market data, portfolio snapshots, execution, notifications, and state
  - broker adapters
  - small reusable utilities

### Platform runtime repositories

Each platform runtime repository should eventually own:

- strategy registry / strategy profile selection
- orchestration
- runtime entrypoints
- deployment configuration
- account or region selection
- platform-specific strategy implementations until they are intentionally extracted

### Infrastructure repositories

- `IBKRGatewayManager`
- `SchwabTokenAutoRefresher`

They are neither strategy repositories nor part of the shared platform package.

### Future strategy repositories

When strategy extraction becomes worth doing, those repositories should own:

- reusable strategy math
- domain-specific parameters
- platform-independent allocation / signal logic where possible

They should **not** own:

- Cloud Run entrypoints
- broker authentication
- scheduler definitions
- platform runtime secrets

## Dependency model

All strategy or platform runtime repositories should pin a fixed tag, for example:

```text
quant-platform-kit @ git+https://github.com/QuantStrategyLab/QuantPlatformKit.git@v0.5.0
```

Avoid:

```text
quant-platform-kit @ git+https://github.com/QuantStrategyLab/QuantPlatformKit.git@main
```

Reasons:

- reproducible builds
- simple rollback
- Cloud Run and VPS deployment units do not need to understand two source repositories
- repository rename and trigger migration are easier when every runtime repo is already aligned to one known tag

## Release order

Recommended order for shared-platform changes:

1. finish the change in `QuantPlatformKit`
2. run tests
3. push to `main`
4. create a new tag
5. update every runtime repository to the same tag
6. let each runtime repository trigger its own build or deployment

Before repository rename or GCP trigger migration, first align all runtime repositories to the same released `QuantPlatformKit` tag.

## Target deployment units

### One broker platform per deployment repository

Do **not** merge unrelated broker platforms into one deployable repository.

Good:

- one IBKR deployment repository
- one Charles Schwab deployment repository
- one LongBridge deployment repository
- one Binance deployment repository

Bad:

- one mega repository switching between IBKR / Schwab / LongBridge / Binance with a single parameter

### Strategy selection

Within one broker platform repository, selecting a strategy by configuration is reasonable.

Recommended selector:

- `STRATEGY_PROFILE`

Good examples:

- `STRATEGY_PROFILE=rotation`
- `STRATEGY_PROFILE=income`
- `STRATEGY_PROFILE=hybrid`

Avoid using `STRATEGY_PROFILE` for:

- different brokers
- unrelated portfolio models with totally different runtime contracts
- fundamentally different scheduling patterns in one service

## Platform-specific account model

### IBKR

IBKR should support multiple accounts or account groups under one platform repository.

Recommended configuration boundary:

- `STRATEGY_PROFILE`
- `ACCOUNT_GROUP` or `IB_ACCOUNT_SET`
- `IB_CLIENT_ID` or a deterministic `IB_CLIENT_ID_BASE`
- `IB_GATEWAY_MODE`
- `IB_GATEWAY_IP_MODE`
- `IB_GATEWAY_INSTANCE_NAME`
- `SERVICE_NAME`

Recommended rule:

- one Cloud Run service or trigger per **account group**
- keep gateway and account selection outside strategy math
- load account membership from environment, Secret Manager, or another runtime config source

### LongBridge

LongBridge should keep:

- one platform repository
- two runtime services
- two triggers
- two GitHub Environments

The split should always be defined by runtime configuration:

- `ACCOUNT_REGION=HK|SG`
- `ACCOUNT_PREFIX`
- `SERVICE_NAME`
- `CLOUD_RUN_SERVICE`
- `CLOUD_RUN_REGION`

Current naming examples:

- `longbridge-quant-semiconductor-rotation-income-hk-service`
- `longbridge-quant-semiconductor-rotation-income-sg-service`

### Charles Schwab

Charles Schwab can stay simpler:

- one platform repository
- one or more services only when strategy profiles truly differ
- `STRATEGY_PROFILE` is already part of the current runtime shape

### Binance

Binance can keep the existing self-hosted runner model in the short term, but the target naming/config model should still match the platform approach:

- one Binance platform repository
- `STRATEGY_PROFILE`
- `SERVICE_NAME`

## Google Cloud trigger / Cloud Build rules

If you rename a repository or move it under a different owner, Cloud Build and Cloud Run GitHub sources usually need to be rebound.

Recommended migration order:

1. align every runtime repository to the same `QuantPlatformKit` tag
2. finish the platform runtime configuration shape (`STRATEGY_PROFILE`, `ACCOUNT_GROUP`, `ACCOUNT_REGION`, `SERVICE_NAME`)
3. create or update the new trigger against the target repository
4. confirm the branch is still `main`
5. confirm the target service and region
6. run one manual build
7. verify runtime configuration for each account group or region
8. remove the old trigger only after the new one works

For LongBridge, repeat this validation for both HK and SG.

For IBKR, repeat this validation for each account group.

## Repository rename advice

Repository rename should happen **after**:

- dependency versions are aligned
- platform runtime configuration is defined
- new GCP triggers have been tested

Rename affects:

- Cloud Build triggers
- Cloud Run GitHub source deploys
- local git remotes
- clone URLs in docs
- dependency URLs in `requirements.txt` / lock files

## One-line rule

- platform code lives in `QuantPlatformKit`
- one broker platform should map to one deployable runtime repository
- strategy selection can happen inside one broker platform via config like `STRATEGY_PROFILE`
- LongBridge HK/SG and IBKR multi-account should be modeled as service or trigger splits, not broker-mixing logic
- versions are managed with fixed tags
