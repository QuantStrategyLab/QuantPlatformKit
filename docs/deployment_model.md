# Deployment Model

## Conclusion

- `QuantPlatformKit` is a shared platform code repository and is **not deployed as a runtime service**.
- `InteractiveBrokersQuant`, `CharlesSchwabQuant`, `LongBridgeQuant`, and `BinanceQuant` remain the real deployment units.
- Strategy repositories should depend on a fixed Git tag instead of `main`.

## Repository responsibilities

### Platform repository

- `QuantPlatformKit`
  - shared domain models
  - narrow ports for market data, portfolio snapshots, execution, notifications, and state
  - broker adapters
  - small reusable utilities

### Strategy repositories

- `InteractiveBrokersQuant`
- `CharlesSchwabQuant`
- `LongBridgeQuant`
- `BinanceQuant`

These repositories should own:

- strategy rules
- orchestration
- runtime entrypoints
- deployment configuration

### Infrastructure repositories

- `IBKRGatewayManager`
- `SchwabTokenAutoRefresher`

They are neither strategy repositories nor part of the shared platform package.

## Dependency model

Strategy repositories should pin a fixed tag, for example:

```text
quant-platform-kit @ git+https://github.com/QuantStrategyLab/QuantPlatformKit.git@v0.4.0
```

Avoid:

```text
quant-platform-kit @ git+https://github.com/QuantStrategyLab/QuantPlatformKit.git@main
```

Reasons:

- reproducible builds
- simple rollback
- Cloud Run and VPS deployment units do not need to understand two source repositories

## Release order

Recommended order for platform-layer changes:

1. finish the change in `QuantPlatformKit`
2. run tests
3. push to `main`
4. create a new tag
5. update the strategy repositories to the new tag
6. let each strategy repository trigger its own build or deployment

## Deployment units

### Cloud Run

Cloud Run should continue to deploy strategy repositories only.

Recommended service names:

| Repository | Recommended service name |
|---|---|
| `InteractiveBrokersQuant` | `interactive-brokers-quant` |
| `CharlesSchwabQuant` | `charles-schwab-quant` |
| `LongBridgeQuant` | `longbridge-quant-hk` / `longbridge-quant-sg` |

If you later add a second closely related strategy under the same platform, names such as these are fine:

- `interactive-brokers-quant-rotation`
- `interactive-brokers-quant-income`

Do not start by putting unrelated strategies behind one service and switching them with a parameter.

### VPS / self-hosted runner

`BinanceQuant` should continue to use the existing self-hosted runner and external scheduler.

Recommended runtime unit name:

- `binance-quant`

## Parameterization boundary

Reasonable parameters:

- `IB_GATEWAY_MODE`
- `ACCOUNT_PREFIX`
- `SERVICE_NAME`
- `NOTIFY_LANG`
- `SERVICE_VARIANT` / `STRATEGY_PROFILE` for closely related strategy variants

Avoid parameterizing:

- completely different strategy systems
- completely different portfolio models
- completely different scheduling patterns

Prefer:

- same repository
- different services
- different environment variables

instead of one service full of `if STRATEGY == ...`.

## Google Cloud trigger / Cloud Build rules

If you later rename a repository or move it under a different owner, Cloud Build and Cloud Run GitHub sources usually need to be rebound.

Recommended steps:

1. record the current trigger name, region, branch, and target service
2. remove the old GitHub source binding or rebuild the trigger
3. select the new repository path
4. confirm the branch is still `main`
5. confirm the target `service` and `region`
6. run one manual build
7. remove the old trigger only after the new one works

### LongBridge dual-service setup

`LongBridgeQuant` should continue to keep:

- one strategy repository
- two Cloud Run services
- two triggers
- two GitHub Environments

The split should always be defined by:

- `CLOUD_RUN_SERVICE`
- `CLOUD_RUN_REGION`

## Repository rename advice

If the goal is only to make the organization structure clearer, update these first:

- GitHub description
- topics
- README

Repository renames can be left for later because they affect:

- Cloud Build triggers
- Cloud Run GitHub source deploys
- local git remotes
- clone URLs in docs

## One-line rule

- platform code lives in `QuantPlatformKit`
- strategy repositories remain deployment units
- GCP and VPS deploy strategy repositories only
- versions are managed with fixed tags
