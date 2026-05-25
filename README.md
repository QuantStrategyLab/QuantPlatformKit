# QuantPlatformKit

Shared platform contracts, broker adapters, strategy-plugin helpers, and notification primitives for QuantStrategyLab repositories.

[中文](./README.zh-CN.md)

## What This Repository Is

`QuantPlatformKit` is the public shared platform layer. It keeps cross-repository interfaces stable so strategy repositories and broker platform repositories can evolve without copying runtime glue.

It contains:

- common domain models and runtime target helpers
- narrow ports for market data, portfolio snapshots, order execution, notifications, and state
- reusable broker adapter utilities
- strategy loading, strategy-plugin, and alert-message contracts
- synthetic-data tests for public behavior

It does not contain private runtime wiring or generated strategy outputs.

## Repository Workflow

QuantStrategyLab repositories are split by responsibility:

- Strategy repositories own strategy metadata, input requirements, and `manifest + evaluate(ctx)` entrypoints.
- Platform repositories own broker sessions, runtime config loading, runtime entrypoints, decision mapping, and order submission.
- Snapshot or data pipeline repositories own generated artifacts and their publication process.
- `QuantPlatformKit` owns the shared contracts and helper APIs used by those repositories.

The normal flow is:

```text
Platform repository
  builds StrategyContext from broker/runtime inputs
  loads a strategy entrypoint from a strategy repository
  receives a StrategyDecision
  maps that decision into broker-specific execution and notifications

QuantPlatformKit
  provides shared contracts, loaders, adapters, and plugin alert helpers
```

Strategy code should not branch on a broker platform, and platform code should not duplicate strategy rules.

## Strategy Plugins

Strategy plugins are sidecar artifacts that platform repositories may read when a strategy profile opts in. This repository defines the public plugin contract, compatibility checks, alert-message building, and duplicate-suppression helpers.

Generated plugin artifacts and platform-specific notification routing stay with the producing pipeline or consuming platform repository. Tests in this repository use synthetic price history and synthetic payloads only.

## Package Layout

```text
src/quant_platform_kit/
  common/
  ibkr/
  binance/
  schwab/
  longbridge/
  notifications/
tests/
```

## Development

Run the public test suite:

```bash
PYTHONPATH=src pytest
```

Run linting:

```bash
PYTHONPATH=src ruff check .
```

## License

MIT License. See [LICENSE](./LICENSE).
