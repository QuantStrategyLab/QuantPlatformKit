# QuantPlatformKit

Shared broker adapters, domain models, execution ports, and notification utilities for QuantStrategyLab strategies.

## Scope

This repository is the shared platform layer for QuantStrategyLab strategy services.

It is intended to contain:

- common domain models
- narrow ports for market data, portfolio snapshots, execution, notifications, and state
- broker-specific adapters
- small reusable notification utilities

It is not intended to contain:

- strategy rules
- target allocation logic
- Cloud Run entrypoints
- scheduler or workflow orchestration specific to one strategy

## Package layout

```text
src/quant_platform_kit/
  common/
    models.py
    ports.py
  ibkr/
    connection.py
    market_data.py
    portfolio.py
    execution.py
  binance/
    client.py
    account.py
    market_data.py
    execution.py
  schwab/
    auth.py
    market_data.py
    portfolio.py
    execution.py
  longbridge/
    auth.py
    market_data.py
    portfolio.py
    execution.py
  notifications/
    telegram.py
tests/
```

## Development

Run tests with:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
```

## Release and deployment model

`QuantPlatformKit` is a shared dependency, not a runtime service. Strategy repos should pin a fixed Git tag such as:

```text
quant-platform-kit @ git+https://github.com/QuantStrategyLab/QuantPlatformKit.git@v0.4.0
```

Cloud Run and self-hosted runner deployments should continue to deploy the strategy repositories only. See [docs/deployment_model.md](./docs/deployment_model.md) for:

- service naming suggestions
- fixed-tag dependency rules
- Google Cloud trigger rebind steps after repo rename
- HK / SG multi-service guidance for `LongBridgeQuant`
