# 策略晋级证据包

这份模板定义了请求 `live_candidate` 复核时最少应提交的内容。

## 必要内容

- 策略 profile 名称
- 目标平台
- 回测摘要
- drift / regime 观察
- 平台兼容性证据
- 插件门槛状态（如适用）
- 操作备注与 rollout 限制

## 建议结构

```text
profile: cn_chinext_growth_momentum_quality
market: cn_equity
requested_stage: live_candidate

1. 回测摘要
2. drift 与 regime 观察
3. 风险复核
4. 平台兼容性证据
5. 插件门槛状态
6. rollout 备注
```

## 接受规则

如果缺少以下任一项，就应继续留在 live 之外：

- profile 与目标平台不兼容
- 插件门槛不是明确 approved 或 notification-only
- 证据没有同时覆盖收益表现和 regime 敏感性
- 只依赖单一好窗口

## 责任划分

- 策略仓库：产出证据包
- 平台仓库：验证 runtime 兼容性和门槛状态
- 操作审批：做最终 live 决策

## Canonical 晋级包（v2）

promotion rerun 必须重新生成 `strategy_evidence_package.v2`，并同时通过 packaged schema 与 dependency-free Python validator。不得把 v1/alias 静默补默认值或改标签后冒充 v2。

封闭的 v2 object 必须绑定 strategy/input provenance、`BacktestOrchestrator` 的 `purged_walk_forward.v1` 原始输出、至少 3 个有序 folds、正数 purge/embargo、至少 12 个日历月的锁定独立 OOS、calendar/timezone/signal/execution timing、cost/risk/全部指标，以及 repo-relative artifact 实际 bytes 与 SHA-256。human acceptance 必须用 evidence-core SHA-256 绑定当前证据。

生命周期真值必须 fail closed：

- learning：`learning_only=true`、`promotion_eligible=false`、`live_ready=false`、`size_zero_required=true`、`no_order=true`；
- 完整且经绑定的人类接受的证据可以 `promotion_eligible=true`，但仍必须 `live_ready=false`、`size_zero_required=true`、`no_order=true`。

结构验证不臆造性能阈值；指标质量仍由绑定的人类 promotion acceptance 判断。requested stage、CI、PR、review、health 或 notification 都不能产生 paper/shadow/live、order 或 capital 权限；live/runtime 请求一律 `HOLD`。
