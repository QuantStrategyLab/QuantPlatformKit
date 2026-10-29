# 跨资产 P4/P5 观察适配契约

## 当前架构理解

P1–P3 research driver 负责绑定输入、冻结配置和历史/OOS 证据；P4/P5 的时间属性和账户/组合属性不同，不应塞回同一个 artifact。`forward_risk_terminal.v1` 因此作为第二个纯观察 envelope：

```text
P1–P3 terminal digest
→ P4 shadow/forward（或已有 paper 结果）身份
→ P5 portfolio RiskSnapshot 身份
→ READY / DEFERRED / PARKED terminal artifact
```

## 权限边界

该适配器固定：

- `no_order=true`；
- `permission_effect=none`；
- `broker_dependency=false`；
- 不启动 paper、shadow 或 live runtime；
- 不抓行情、不运行策略、不计算仓位、不连接 broker；
- `READY` 只描述证据齐全，不授予 shadow、paper 或 live 权限。

P4 的 `mode=paper` 仅表示消费了其他平台已经产生并验证的模拟结果；QPK 适配器本身仍不连接 paper broker。没有 paper 能力的平台直接使用 `mode=shadow`，不会因此被阻塞。

## P4/P5 READY 条件

| 阶段 | artifact schema | 额外约束 |
|---|---|---|
| P4 | `forward_observation.v1` | P1–P3 terminal 必须 READY；candidate 必须一致；artifact 在 terminal 生成时未过期 |
| P5 | `portfolio_risk_snapshot.v1` | P4 必须 READY；candidate 必须一致；RiskSnapshot 身份未过期 |

缺少正常上游时输出 `DEFERRED`；格式错误、过期、candidate 不一致或越过阶段依赖时输出 `PARKED`。每个合法 P1–P3 terminal 都可生成一个 P4/P5 terminal artifact，不能以 workflow 绿色代替终态文件。

## 现有样板评估

- `ShadowValidator` 已能读取近期 performance snapshot 并比较候选，但尚未定义跨资产不可变 P4 artifact；各策略 producer 需要后续输出 `forward_observation.v1`。
- `RiskSnapshot` 已有 fail-closed、expiry、Kelly fraction、风险预算和熔断状态校验，适合作为 P5 producer；本契约只绑定其不可变身份，不复制风险算法。
- `lifecycle_matrix_runtime` 已能只读聚合 P4/P5 terminal 状态，可在 producer 接线后继续复用。
- paper 不是通用前置条件。支持 paper 的平台可提供 P4 paper observation；不支持的平台以 no-order shadow/forward observation 完成 P4。

## 低风险迁移

1. 所有资产先输出 P1–P3 terminal；缺证据时如实 `DEFERRED/PARKED`。
2. 各策略将现有 shadow 日报适配为 `forward_observation.v1`，不改变策略计算。
3. 将现有 `RiskSnapshot` 序列化、摘要后注册为 `portfolio_risk_snapshot.v1`。
4. workflow 的 `always()` 终态步骤输出 P4/P5 envelope。
5. 只读 matrix 消费这些 artifact；live/runtime 继续使用独立 authority 和 Risk Gate。

不推荐新增第二套 scheduler、通用事件总线或让此模块直接运行 paper/broker；这些会把证据适配层与执行层重新耦合。
