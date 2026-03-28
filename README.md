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
