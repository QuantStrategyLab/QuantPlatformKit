# QuantPlatformKit

`QuantPlatformKit` 是 QuantStrategyLab 的共享平台契约、券商适配工具、策略插件 helper 和通知基础能力仓库。

[English](./README.md)

## 这个仓库是什么

这是一个公开的共享平台层仓库。它负责稳定跨仓库接口，让策略仓库和券商平台仓库可以各自演进，而不需要复制运行时胶水代码。

这个仓库包含：

- 通用领域模型和运行目标 helper
- 市场数据、持仓快照、订单执行、通知、状态存储等窄接口
- 可复用的券商适配工具
- 面向混合托管/自托管运行时的 QuantConnect Cloud 部署 helper
- 策略加载、策略插件、告警消息契约
- 可选的策略插件 email、SMS、push 和 Telegram 告警通道
- 使用合成数据的公开测试

它不包含私有运行时接线和生成的策略输出。

## 和其他仓库如何协作

QuantStrategyLab 的仓库按职责拆分：

- 策略仓库负责策略 metadata、输入需求，以及 `manifest + evaluate(ctx)` 入口。
- 平台仓库负责券商 session、运行时配置加载、运行入口、决策映射和下单。
- 快照或数据流水线仓库负责生成 artifact 以及发布流程。
- `QuantPlatformKit` 负责这些仓库共同使用的契约和 helper API。

典型工作流是：

```text
平台仓库
  从券商/运行时输入构造 StrategyContext
  从策略仓库加载策略入口
  得到 StrategyDecision
  映射为券商专属执行和通知

QuantPlatformKit
  提供共享契约、加载器、适配器和插件告警 helper
```

策略代码不按券商平台分支；平台代码不复制策略规则。

## 策略插件

策略插件是平台仓库按需读取的 sidecar artifact。这个仓库只定义公开插件契约、兼容性校验、告警消息构造、可选告警发送 helper 和重复告警抑制 helper。

生成的插件 artifact 和平台专属通知路由由生成它的 pipeline 或消费它的平台仓库管理。这个仓库的测试只使用合成价格历史和合成 payload。

插件 artifact 可以携带展示层 `strategy_plugin_messages.v1` 和
`strategy_plugin_log.v1` 中英文通知 / 日志文案。平台 renderer 可以使用这些文案，但策略和平台逻辑应继续依赖 `canonical_route`、`suggested_action`、`reason_codes`、`position_control` 等机器字段。

插件告警发送在平台边界保持 provider-neutral。平台仓库只把 runtime settings 传入 `publish_strategy_plugin_alerts`；这个仓库负责按配置发送 `email`、`sms`、`push` 和 `telegram`，不让插件逻辑耦合某个券商平台。

## 目录结构

```text
src/quant_platform_kit/
  common/
  ibkr/
  binance/
  schwab/
  longbridge/
  quantconnect/
  notifications/
tests/
```

公开的 QuantConnect 连接器契约和仅含占位符的示例见 [docs/quantconnect.md](./docs/quantconnect.md)。
策略插件运行时契约见
[docs/strategy_plugin_runtime_contract.zh-CN.md](./docs/strategy_plugin_runtime_contract.zh-CN.md)，
英文版见 [docs/strategy_plugin_runtime_contract.md](./docs/strategy_plugin_runtime_contract.md)。

## 开发

运行公开测试：

```bash
PYTHONPATH=src pytest
```

运行 lint：

```bash
PYTHONPATH=src ruff check .
```

## License

MIT License. 见 [LICENSE](./LICENSE)。
