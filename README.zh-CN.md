# QuantPlatformKit

`QuantPlatformKit` 是 `QuantStrategyLab` 下面的共享平台代码仓库。

它负责放这些内容：

- 统一领域模型
- 市场数据、持仓、执行这些窄接口
- IBKR / Schwab / LongBridge / Binance 的平台适配层
- Telegram 通知和少量通用工具

它**不负责**放这些内容：

- 具体策略规则
- 调仓参数
- Cloud Run 入口
- 某一个策略仓库自己的调度编排

## 策略契约边界

当前主线边界已经固定为：

- 平台仓库负责组装 `StrategyContext`
- 平台仓库通过 `load_strategy_entrypoint(...)` 加载策略入口
- 策略仓库只返回统一的 `StrategyDecision`
- 平台自己的 decision mapper 再把决策映射成券商订单、通知和运行时状态更新

策略仓库应该暴露 `manifest + evaluate(ctx)`；如果迁移窗口里还需要少量运行时元数据，就放在 `StrategyRuntimeAdapter` 里，不要把券商专属下单顺序或展示布局塞回策略输出。

迁移说明和后续约束见 [`docs/strategy_contract_migration.md`](./docs/strategy_contract_migration.md)。

[English README](./README.md)

## 目录结构

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

## 开发

运行测试：

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
```

## 发布和部署

`QuantPlatformKit` 是共享依赖，不单独部署。策略仓库应该固定依赖某个 Git tag，例如：

```text
quant-platform-kit @ git+https://github.com/QuantStrategyLab/QuantPlatformKit.git@v0.7.1
```

部署相关说明见：

- [英文部署说明](./docs/deployment_model.md)
- [中文部署说明](./docs/deployment_model.zh-CN.md)
