# 策略插件运行时契约


## English summary

- Full English version: [`strategy_plugin_runtime_contract.md`](strategy_plugin_runtime_contract.md). This summary keeps an English entry point in the Chinese file.
- Purpose: this document covers `策略插件运行时契约` for `QuantPlatformKit`.
- Main topics: `职责边界`, `平台挂载配置`, `插件定义`, `Runtime Loader`, `行为边界`.
- Read the boundaries, inputs, outputs, and permission requirements before running commands, CI jobs, dry-runs, releases, or runtime switches.
- For live trading, secrets, Cloud Run, exchange, or broker API changes, validate in test or dry-run mode first and do not change production only from examples.
- If this summary differs from the detailed Chinese body, follow the concrete commands, configuration keys, and constraints in the body.

[English](./strategy_plugin_runtime_contract.md)

本文档说明平台运行时如何消费侧车策略插件 artifact，例如上游 snapshot
或研究 pipeline 生成的 crisis response、macro risk governor 或统一
`market_regime_control` 信号。

## 职责边界

- 策略插件 artifact 由上游 snapshot / research pipeline 生成。
- 平台运行时只加载最新插件 artifact，并把它挂到日志、运行报告和通知上下文。
- 券商下单仍属于平台仓库。
- 策略公式仍属于策略仓库。

## 平台挂载配置

平台配置只决定某个策略挂载哪些插件 artifact，不选择插件模式。插件模式写在
artifact 内，并固定为通知/观察用途的 `shadow`。

建议环境变量名：`STRATEGY_PLUGIN_MOUNTS_JSON`。

推荐配置：

```json
{
  "strategy_plugins": [
    {
      "strategy": "tqqq_growth_income",
      "plugin": "crisis_response_shadow",
      "signal_path": "/path/to/strategy-artifacts/us_equity/tqqq_growth_income/plugins/crisis_response_shadow/latest_signal.json",
      "enabled": true
    }
  ]
}
```

`expected_mode` 只能作为 fail-closed 运行时校验，不选择或重解释插件模式：

```json
{
  "strategy_plugins": [
    {
      "strategy": "tqqq_growth_income",
      "plugin": "crisis_response_shadow",
      "signal_path": "/var/strategy-artifacts/tqqq_growth_income/plugins/crisis_response_shadow/latest_signal.json",
      "enabled": true,
      "expected_mode": "shadow"
    }
  ]
}
```

不要在平台挂载配置里写 `mode`。如果使用 `expected_mode`，它只能是
`shadow`。声明为 `paper`、`advisory` 或 `live` 的 artifact 会被拒绝。

## 插件定义

共享 kit 通过 registry 风格的 `StrategyPluginDefinition` 管理插件兼容性。
平台仓库不应硬编码某个插件支持哪些策略，而应调用共享 parser / loader，
由它拒绝不支持的挂载或 artifact。

默认 registry 当前定义这些版本化插件契约：

| 插件 | Schema versions | 支持策略 | 状态 | 支持模式 | 升级告警通道 |
| --- | --- | --- | --- | --- | --- |
| `market_regime_control` | `market_regime_control.v1` | `tqqq_growth_income`, `global_etf_rotation`, `russell_1000_multi_factor_defensive`, `tech_communication_pullback_enhancement`, `mega_cap_leader_rotation_top50_balanced` | default | `shadow` | `email`, `sms`, `push`, `telegram` |
| `crisis_response_shadow` | `crisis_response_shadow.v1` | `tqqq_growth_income` | deprecated; successor `market_regime_control` | `shadow` | `email`, `sms`, `push`, `telegram` |
| `macro_risk_governor` | `macro_risk_governor.v1` | `tqqq_growth_income` | deprecated; successor `market_regime_control` | `shadow` | `email`, `sms`, `push`, `telegram` |
| `taco_rebound_shadow` | `taco_rebound_shadow.v2` | `tqqq_growth_income` | deprecated; successor `market_regime_control` | `shadow` | `email`, `sms`, `push`, `telegram` |

已废弃插件仍可用于历史回测和分阶段迁移。新的策略集成应优先挂载
`market_regime_control`，并读取 artifact 的 `notification` 和
`position_control` 字段。旧 TACO artifact 仅用于通知；它可以在 TACO
反弹上下文激活时升级人工复核告警，但不能建议仓位、修改实时 allocation，
也不能暗示券商下单权限。

如果未来扩展插件支持范围，应更新共享 definition，或显式传入 definition
registry 给 parser / loader。这样平台运行时代码不用承载未来插件资格变更。

SOXL/SOXX 故意不列入 `market_regime_control` 的运行时挂载清单。SOXL
相关宏观和危机信号应通过通用
`notification_targets.market_regime_notification` artifact 分发，并由人工复核；
除非未来回测证明策略级 opt-in 有优势，否则不默认自动消费仓位控制。

## Runtime Loader

使用 `quant_platform_kit.common.strategy_plugins`：

```python
from quant_platform_kit.common.strategy_plugins import (
    build_strategy_plugin_alert_messages,
    build_strategy_plugin_notification_lines,
    build_strategy_plugin_report_payload,
    load_configured_strategy_plugin_signals,
    parse_strategy_plugin_mounts,
)

mounts = parse_strategy_plugin_mounts(raw_json_config)
signals = load_configured_strategy_plugin_signals(
    mounts,
    strategy_profile=current_strategy_profile,
)
report_section = build_strategy_plugin_report_payload(signals)
notification_lines = build_strategy_plugin_notification_lines(signals, locale="zh-CN")
alert_messages = build_strategy_plugin_alert_messages(signals)
```

通用通知 artifact 使用 `notification_targets`，不是 synthetic strategy。它们
可以复用同一套通知和告警 builder，但不会附加到策略 runtime metadata，也不能
授权仓位变化：

```python
from quant_platform_kit.common.strategy_plugins import (
    load_configured_strategy_plugin_notification_target_signals,
    parse_strategy_plugin_notification_targets,
)

targets = parse_strategy_plugin_notification_targets(raw_json_config)
notification_signals = load_configured_strategy_plugin_notification_target_signals(targets)
notification_lines = build_strategy_plugin_notification_lines(
    notification_signals,
    locale="zh-CN",
)
```

loader 会校验：

- artifact 是 JSON object
- `strategy` 和 `plugin` 与配置挂载一致
- `mode`、`configured_mode` 和 `effective_mode` 都是 `shadow`
- 可选 `expected_mode` 与 `effective_mode` 一致
- 不允许重复平台挂载
- 平台挂载配置不能设置 `mode`

## 行为边界

对于 `shadow` 插件，平台运行时只能附加日志、运行报告字段和通知上下文。

artifact 可以包含展示层 i18n 字段：

- `localized_messages.schema_version = strategy_plugin_messages.v1`
- `localized_messages.notification.en-US` / `localized_messages.notification.zh-CN`
- `localized_messages.log.en-US` / `localized_messages.log.zh-CN`
- `log_record.schema_version = strategy_plugin_log.v1`

平台 renderer 可以使用这些字段渲染通知和日志文案。交易逻辑必须继续读取
`schema_version`、`canonical_route`、`suggested_action`、`reason_codes`
和 `position_control` 等机器字段。

共享契约不支持 `paper`、`advisory` 和 `live` 插件模式。平台不应从这条
sidecar 路径维护插件账本或执行插件驱动的 allocation 变更。

## 升级告警

共享 kit 负责平台无关的告警升级规则。满足以下任一条件时，插件信号会升级：

- `canonical_route` 不是 `no_action`
- `suggested_action` 是 `defend` 或 `blocked`
- `would_trade_if_enabled` 是 `true`

平台仍可选择自己的投递 sink；共享 helper 已提供 email、SMS、push 和
Telegram 的聚合入口：

- `quant_platform_kit.notifications.strategy_plugin_alerts.publish_strategy_plugin_alerts()`
- `quant_platform_kit.notifications.strategy_plugin_email.publish_strategy_plugin_email_alerts()`
- `quant_platform_kit.notifications.strategy_plugin_sms.publish_strategy_plugin_sms_alerts()`

publisher 会构造共享 subject/body、追加平台上下文、返回结构化
sent/skipped/failed diagnostics，并可使用 marker store 跳过某个通道已发送过的
alert key。

投递凭据、路由和 transport settings 属于平台运行时配置。插件 artifact
和策略代码只决定是否应该存在升级告警，不决定平台如何投递。

这个边界让 Crisis Response、Macro Risk Governor、TACO 和统一
`market_regime_control` 在 IBKR、Schwab、LongBridge、Firstrade 以及未来
平台运行时中保持一致。
