# 生命周期一次性迁移契约

本次升级把生命周期的写入真相源一次性切换为：

```text
research_active
shadow_active
paper_active
live_candidate
live_enabled
```

## 写入规则

- 新 catalog、inventory、控制台配置和 evidence 只能写规范状态。
- `research_backtest_only`、`ai_monitored_candidate`、`shadow_candidate`、
  `runtime_enabled` 只允许在一次性迁移快照中读取。
- 完成消费者验证后删除旧读取兼容层，不在核心架构长期维护双写。
- inventory 和 evidence 永远没有权限效果。

## 旧 live 回滚边界

旧 `runtime_enabled` 不能仅凭名称迁为 `live_enabled`。只有
`source_kind=runtime_deployment`，并同时记录未过期的外部
`live_authority_ref` 和可执行的 `rollback_ref`，迁移快照才能描述为
`live_enabled`。该快照不会创建、扩大或刷新授权。

无法验证上述引用时，保守迁为 `live_candidate`；原 broker runtime 和资金权限
保持不变，待部署消费者完成对照后再决定切换。迁移过程不删除旧 runtime，
不自动复位熔断，也不修改资金、杠杆、品种和 broker 权限。

契约 schema：
[`lifecycle-migration-snapshot.v1.schema.json`](../src/quant_platform_kit/schemas/lifecycle-migration-snapshot.v1.schema.json)。
