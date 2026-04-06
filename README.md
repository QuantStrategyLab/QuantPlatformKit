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

## Strategy contract boundary

The current mainline split is:

- platform repositories assemble `StrategyContext`
- platform repositories load a strategy entrypoint through `load_strategy_entrypoint(...)`
- strategy repositories return a unified `StrategyDecision`
- platform-local decision mappers turn that decision into broker orders, notifications, and runtime state updates

Strategy repositories should expose `manifest + evaluate(ctx)` and keep any migration-window runtime metadata behind `StrategyRuntimeAdapter`. Broker-specific order sequencing and UI layout should stay out of strategy outputs.

Migration details and follow-up guidance live in [`docs/strategy_contract_migration.md`](./docs/strategy_contract_migration.md).

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
quant-platform-kit @ git+https://github.com/QuantStrategyLab/QuantPlatformKit.git@v0.7.0
```

Cloud Run and self-hosted runner deployments should continue to deploy the strategy repositories only. See [docs/deployment_model.md](./docs/deployment_model.md) for:

- service naming suggestions
- fixed-tag dependency rules
- Google Cloud trigger rebind steps after repo rename
- HK / SG multi-service guidance for `LongBridgePlatform`

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

### 策略契约边界

当前主线边界已经固定为：

- 平台仓库负责组装 `StrategyContext`
- 平台仓库通过 `load_strategy_entrypoint(...)` 加载策略入口
- 策略仓库只返回统一的 `StrategyDecision`
- 平台自己的 decision mapper 再把决策映射成券商订单、通知和运行时状态更新

策略仓库应该暴露 `manifest + evaluate(ctx)`；如果迁移窗口里还需要少量运行时元数据，就放在 `StrategyRuntimeAdapter` 里，不要把券商专属下单顺序或展示布局塞回策略输出。

迁移说明和后续约束见 [`docs/strategy_contract_migration.md`](./docs/strategy_contract_migration.md)。

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
