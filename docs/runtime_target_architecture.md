# Runtime Target Architecture

## Goal

Make runtime selection explicit and stable across platforms by separating:

- strategy selection
- platform selection
- account selection
- deployment mode

`STRATEGY_PROFILE` still exists as a compatibility selector, but the running service is now described primarily by `RuntimeTarget` and `RuntimeAssembly`.

## Core idea

The shared control-plane object is `RuntimeTarget`.

It answers:

- which platform is this?
- which strategy implementation is selected?
- is this paper or live?
- which deployment selector is active?
- which account selector is active?
- which service is this bound to?

The runtime target should flow through:

- GitHub env sync
- Cloud Run env
- runtime logs
- reports
- deployment previews

`RuntimeAssembly` is the internal bridge object that carries the deployment identity plus the runtime target into logging, reporting, and platform wiring.

## Design patterns used

### Strategy

`strategy_profile` selects the strategy behavior:

- signal generation
- universe
- cadence
- sizing rules

It must not own broker selection or deployment identity.

### Bridge

Platform and strategy evolve independently.

- strategy axis: `global_etf_rotation`, `tqqq_growth_income`, ...
- platform axis: LongBridge, IBKR, Schwab, PaperSignal

`RuntimeTarget` is the bridge payload that keeps those axes separate.

### Adapter

Each platform still adapts unified ports to broker-specific APIs:

- `ExecutionPort`
- `PortfolioPort`
- `MarketDataPort`
- notification/report adapters

Platform differences stay at the edge.

### Abstract Factory

A runtime factory assembles a runnable service from `RuntimeTarget` and `RuntimeAssembly`:

- runtime config
- broker adapter
- reporting adapter
- notification adapter
- capability validation

### Template Method

GitHub sync and runtime startup follow the same high-level flow:

1. resolve inputs
2. resolve capability
3. build runtime target
4. sync env
5. start service
6. emit report

### Facade

External callers should prefer a small surface:

- `runtime_target`
- `strategy_profile` for compatibility

Do not leak broker-specific wiring into external deployment steps.

## Target module split

### Shared package

`QuantPlatformKit`

Owns:

- `RuntimeTarget`
- runtime config helpers
- shared ports and adapters
- runtime report helpers
- strategy contracts

### Platform runtime repository

Example repositories:

- `LongBridgePlatform`
- `InteractiveBrokersPlatform`
- `CharlesSchwabPlatform`

Own:

- runtime entrypoints
- platform adapters
- deployment sync scripts
- account selection and secret wiring
- platform-specific reporting text

### Strategy repository

Future shared strategy repositories should own:

- reusable strategy math
- platform-independent signal logic
- domain parameters

They should not own:

- Cloud Run entrypoints
- broker auth
- scheduler wiring
- deployment secrets

## RuntimeTarget invariants

- `strategy_profile` is still required for compatibility and strategy routing.
- `platform_id` is required.
- `dry_run_only` determines `execution_mode`.
- `account_selector` is optional and platform-dependent.
- `account_scope` is optional and may mirror region or account-group semantics.
- `service_name` is a deployment identity, not a strategy concept.

## Platform-specific account rules

### LongBridge

- split by region
- `account_scope` can mirror `HK` / `SG`
- `deployment_selector` should reflect the active region
- one service per region is the target shape

### IBKR

- split by account group
- `account_selector` may contain one or more IB account identifiers
- `ACCOUNT_GROUP` stays as the external runtime selector

### Schwab

- typically one service identity
- `account_selector` may stay empty
- `STRATEGY_PROFILE` remains the compatibility selector, not the main control plane

### PaperSignal

- paper/live is controlled by `dry_run_only`
- strategy identity still flows through the same `RuntimeTarget`

## Migration sequence

1. keep `STRATEGY_PROFILE` working
2. emit `RuntimeTarget` in runtime settings and reports
3. emit `RUNTIME_TARGET_JSON` in GitHub env sync
4. move docs and previews to runtime-target-first wording
5. keep `strategy_profile` only as internal compatibility input
6. keep `RuntimeAssembly` as the internal bridge for entrypoints and reports
7. extract more shared orchestration once the target model is stable

## Practical rule

If a piece of code answers:

- "which broker runtime is this?"
- "which account or region is active?"
- "is this paper or live?"

then it belongs in the runtime target / runtime config layer, not in strategy code.
