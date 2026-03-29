# Platform Repo Boundaries

## Why this document exists

At the moment there are three layers in play:

1. `QuantPlatformKit`
2. broker platform runtime repositories
3. future strategy repositories that do not fully exist yet

The codebase is in a transitional state, so this document is meant to answer a simple question:

> what belongs in each layer, and what should stay out?

For the platform / strategy-domain / configurable-profile matrix, see [`platform_strategy_matrix.md`](./platform_strategy_matrix.md).

## 1. `QuantPlatformKit`

`QuantPlatformKit` is the shared dependency.

It should own:

- shared domain models
- shared ports / interfaces
- broker adapters
- shared notification helpers
- shared strategy contract definitions
  - strategy domain
  - strategy profile definition
  - platform compatibility rules

It should **not** own:

- Cloud Run services
- GitHub Actions workflow wiring
- scheduler definitions
- project-specific secret names
- one platform's runtime environment layout
- one strategy's deployment schedule

## 2. Platform runtime repositories

Examples today:

- `InteractiveBrokersPlatform`
- `CharlesSchwabPlatform`
- `LongBridgePlatform`
- `BinancePlatform`

These repositories are the actual deployment units.

They should own:

- runtime entrypoints
- orchestration
- deployment workflows
- Cloud Run / scheduler / Oracle runtime configuration
- runtime secret selection
- account or region selection
- current platform-specific strategy implementations

They should **not** try to become:

- a giant shared package for every broker
- a generic strategy marketplace
- a single deployable repository switching between unrelated brokers

## 3. Future strategy repositories

These are not required yet, but the target shape is already visible.

When they become worth introducing, they should own:

- reusable strategy math
- domain-specific parameters
- cross-platform strategy logic where it is truly shared

They should **not** own:

- broker login
- Cloud Run entrypoints
- GitHub deployment configuration
- scheduler definitions
- platform runtime identities

## What overlap is acceptable right now

Some duplication is still acceptable during the transition.

### Acceptable today

- one `strategy_registry.py` per runtime repository
- one `runtime_config_support.py` per runtime repository
- strategy code still living inside a platform runtime repository

This is acceptable because each platform still has different runtime constraints:

- IBKR needs account-group handling
- LongBridge needs region handling
- Schwab has token-refresh concerns
- Binance does not run on Cloud Run at all

### Not worth forcing right now

Do **not** try to prematurely centralize:

- all runtime env parsing
- all notification wording
- all strategy execution entrypoints

That kind of refactor usually makes the code harder to read before there is enough real sharing to justify it.

## Practical rule of thumb

If a piece of code answers:

- **how does this broker runtime run and deploy?**
  - keep it in the platform runtime repository

- **what is shared across multiple brokers or runtimes?**
  - move it into `QuantPlatformKit`

- **what is reusable strategy logic independent of one platform's runtime wiring?**
  - that is a future strategy-repository candidate

## Current recommended next step

Do **not** start with a large strategy split.

Instead:

1. keep the shared strategy contract in `QuantPlatformKit`
2. keep real strategy implementations in the platform runtime repositories for now
3. wait until at least one `us_equity` strategy is genuinely ready to be reused across IBKR / Schwab / LongBridge
4. then extract that strategy by domain, not by broker
