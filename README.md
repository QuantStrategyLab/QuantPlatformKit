# QuantPlatformKit

Shared broker adapters, domain models, execution ports, and notification utilities for QuantStrategyLab strategies.

[English](#english) | [中文](#中文) | [中文详版](./README.zh-CN.md)

---

<a id="english"></a>
## English

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
    strategies.py
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
quant-platform-kit @ git+https://github.com/QuantStrategyLab/QuantPlatformKit.git@v0.5.0
```

Cloud Run and self-hosted runner deployments should continue to deploy the strategy repositories only. See [docs/deployment_model.md](./docs/deployment_model.md) for:

- service naming suggestions
- fixed-tag dependency rules
- Google Cloud trigger rebind steps after repo rename
- HK / SG multi-service guidance for `LongBridgeQuant`

---

<a id="中文"></a>
## 中文

`QuantPlatformKit` 是 `QuantStrategyLab` 的共享平台层仓库。

它负责放这些内容：

- 统一领域模型
- 市场数据、持仓、执行、通知相关的公共接口
- IBKR / Schwab / LongBridge / Binance 的平台适配层
- 少量可复用的通知和运行时工具

它不负责放这些内容：

- 具体策略规则
- 目标仓位和调仓计算
- Cloud Run 或 VPS 入口
- 某一个平台仓库自己的调度和部署编排

### 范围

这个仓库是各平台仓库共享的公共依赖。

### 目录结构

```text
src/quant_platform_kit/
  common/
    models.py
    ports.py
    strategies.py
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

### 开发

运行测试：

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
```

### 发布和部署

`QuantPlatformKit` 只作为共享依赖，不单独部署。策略仓库应该固定依赖某个 Git tag，例如：

```text
quant-platform-kit @ git+https://github.com/QuantStrategyLab/QuantPlatformKit.git@v0.6.0
```

部署说明见：

- [英文部署说明](./docs/deployment_model.md)
- [中文部署说明](./docs/deployment_model.zh-CN.md)
