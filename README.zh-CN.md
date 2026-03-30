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
quant-platform-kit @ git+https://github.com/QuantStrategyLab/QuantPlatformKit.git@v0.6.0
```

部署相关说明见：

- [英文部署说明](./docs/deployment_model.md)
- [中文部署说明](./docs/deployment_model.zh-CN.md)
