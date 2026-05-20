# Platform Repo Boundaries

## Why this document exists

At the moment there are three layers in play:

1. `QuantPlatformKit`
2. broker platform runtime repositories
3. future strategy repositories that do not fully exist yet

The codebase is in a transitional state, so this document is meant to answer a simple question:

> what belongs in each layer, and what should stay out?

For the platform / strategy-domain / configurable-profile matrix, see [`platform_strategy_matrix.md`](./platform_strategy_matrix.md).

For the runtime-target-first architecture and the Bridge / Adapter split, see [`runtime_target_architecture.md`](./runtime_target_architecture.md).

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
  - `RuntimeTarget` / `RuntimeAssembly` bridge objects

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
- `FirstradePlatform`
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

Inside a platform runtime repository, prefer these local boundaries before
considering any shared-library extraction:

- entrypoint / request handler
- cycle orchestrator (`rebalance_service.py`)
- execution service (`execution_service.py`)
- notification renderer / publisher

Prefer wiring these boundaries through small dependency bundles such as
`<Broker>RebalanceRuntime` and `<Broker>RebalanceConfig` instead of passing a
long flat list of callables into the orchestrator.

When a runtime already has a controlled cutover window, prefer removing the old
flat callable entrypoint entirely instead of carrying both shapes in parallel.
Keeping `runtime/config` and legacy one-off call signatures alive at the same
time usually leaks compatibility branches back into execution and notification
code. The shared `RuntimeTarget` / `RuntimeAssembly` bridge exists so
entrypoints can stay thin while runtime identity still flows through logs,
reports, and deployment metadata.

When a dependency already matches a shared interface, entrypoints should adapt
it to the shared port first, for example:

- `MarketDataPort`
- `NotificationPort`
- `PortfolioPort`
- `ExecutionPort`

`QuantPlatformKit.common.port_adapters` exists for this lightweight binding
layer. Quote loaders, history fetchers, and broker-specific notification
senders should usually be wrapped at the entrypoint and then passed inward as
ports. Keep broker-specific closures local, but keep the orchestrator surface
small and explicit.

For account reads, prefer normalizing broker-native payloads into
`PortfolioSnapshot` at the entrypoint or adapter edge. If a strategy contract
still needs `account_state`, derive it locally from the snapshot instead of
letting raw broker account dictionaries flow through the orchestrator.

For order submission, prefer adapting broker submitters to `ExecutionPort`.
If one broker still needs post-submit polling or alert fan-out, keep that as a
small edge callback or observer near the adapter instead of pushing broker
order-monitoring details back into the execution orchestrator.
Polling code should emit structured order lifecycle events, with rendering and
Telegram delivery handled by the notification publisher side.
When one platform has several related edge callbacks, prefer grouping them in a
small local adapter-builder module instead of scattering helper closures across
`main.py`.
The same rule applies to broker adapter glue such as market-data normalization,
portfolio snapshot loading, and execution-port binding: keep those builders in
one local adapter module instead of mixing them into runtime control flow.
Token refresh, broker login/context creation, and initial indicator bootstrap
should follow the same pattern: keep them in a local runtime bootstrap builder
instead of embedding that startup sequence directly in `main.py`.
Structured runtime logging, report construction, and report persistence should
also be grouped in a local reporting builder so the entrypoint keeps only the
run control flow instead of the logging/report transport details.
Strategy-side input assembly, benchmark/history selection, and decision-to-plan
mapping should likewise live in a local strategy adapter builder instead of
being mixed into the entrypoint's runtime wiring.
When several local builders already exist, it is reasonable to add one thin
runtime composer that assembles them into the broker runtime/config objects, so
`main.py` keeps only environment loading and request/run control flow.
If tests or local tooling still patch a few top-level helpers in `main.py`,
keep those helpers as thin delegators into the local builders or composer
rather than letting orchestration logic drift back into the entrypoint.

This keeps runtime-specific sequencing in the deployment repo without forcing
order-routing, notification formatting, and HTTP/report assembly into the same
module.

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
- all strategy execution entrypoints

Notification delivery and renderer extraction inside one platform repo is still
worth doing. The warning here is specifically about forcing all brokers to share
one wording/template layer before their execution payloads have converged.

That kind of refactor usually makes the code harder to read before there is enough real sharing to justify it.

## Practical rule of thumb

If a piece of code answers:

- **how does this broker runtime run and deploy?**
  - keep it in the platform runtime repository

- **what is shared across multiple brokers or runtimes?**
  - move it into `QuantPlatformKit`

- **what is reusable strategy logic independent of one platform's runtime wiring?**
  - that is a future strategy-repository candidate

- **how should this platform publish logs / Telegram / runtime reports for one cycle?**
  - keep the transport and final wording in the platform repo, but feed it with
    structured strategy diagnostics instead of parsing human-readable strings

## Current recommended next step

Do **not** start with a large strategy split.

Instead:

1. keep the shared strategy contract in `QuantPlatformKit`
2. keep real strategy implementations in the platform runtime repositories for now
3. wait until at least one `us_equity` strategy is genuinely ready to be reused across IBKR / Schwab / LongBridge
4. then extract that strategy by domain, not by broker
