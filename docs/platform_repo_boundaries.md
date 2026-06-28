# Platform Repository Boundaries

[简体中文](platform_repo_boundaries.zh-CN.md)

This document describes how `QuantPlatformKit` fits with strategy repositories
and broker platform repositories.

## QuantPlatformKit

`QuantPlatformKit` is the shared package. It owns contracts and helpers that are
useful across repositories:

- shared domain models
- ports and interfaces for market data, portfolio snapshots, execution,
  notifications, and state
- broker adapter utilities
- strategy manifest, context, decision, loader, and validation contracts
- strategy-plugin parsing, compatibility, and alert-message helpers

It should stay platform-neutral. It should not contain broker sessions,
platform-specific runtime wiring, generated artifacts, or strategy formulas.

## Strategy Repositories

Strategy repositories own reusable strategy behavior:

- profile metadata and manifests
- pure `evaluate(ctx)` entrypoints
- strategy parameters and diagnostics
- artifact schema expectations when a strategy needs upstream generated data

They should not import broker SDKs or branch on a broker platform.

## Platform Repositories

Platform repositories connect brokers and runtime inputs to the shared
contracts:

- create broker sessions
- load runtime configuration
- assemble `StrategyContext`
- call a strategy entrypoint
- map `StrategyDecision` into broker-native execution
- render and send platform-specific notifications
- persist platform-owned run state and reports

They may keep broker-specific adapters, request handlers, and decision mappers
locally. If a helper becomes useful across more than one platform, move the
shared part into `QuantPlatformKit` and keep only the platform edge local.

## Practical Rule

Use this split when deciding where code belongs:

- shared contract or reusable adapter: `QuantPlatformKit`
- strategy formula or profile semantics: strategy repository
- broker session, runtime assembly, execution, notification routing, or state:
  platform repository

## Cloud Provider Abstraction

`QuantPlatformKit` provides cloud provider protocol interfaces in
`quant_platform_kit.cloud`. Platform repositories interact with secrets,
object storage, and document databases through these interfaces rather than
directly importing cloud SDKs.

- Default provider is **Google Cloud** (same behavior as before).
- Switch to **local** (`QSL_CLOUD_PROVIDER=local`) for development without
  cloud credentials.
- To add a new provider, implement the protocol interface and register it in
  the factory (`cloud/__init__.py`).

See [README.md](../README.md#cloud-provider-abstraction) for details.
