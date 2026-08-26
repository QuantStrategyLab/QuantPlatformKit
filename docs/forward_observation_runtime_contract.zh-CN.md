# 前瞻观察自动化契约

`quant_platform_kit.strategy_lifecycle.forward_observation` 是策略、插件和平台共用的纯决策层。它不连接券商、不写运行时目标、不部署服务，也不产生订单。

每个冻结候选必须显式提供自己的 `ForwardObservationPolicy`：候选 ID、策略 profile、无杠杆基准、前瞻交易日数量、复核里程碑，以及恢复前需要的连续健康周期。控制器没有“252 天”“20/60 天”或某个策略的隐性默认值；新候选缺少这些字段会被拒绝，不能继承 SOXL 的参数。没有已验证的 P3 历史证据和证据引用时，状态固定为 `PARKED`。

P3 通过后，控制器可以自动给出 `start_shadow`、`start_paper`、`continue_*` 和在短暂故障恢复后的 `resume_*` 意图。数据过期、Paper/Shadow 不一致或风险门阻断时，它只会给出 `pause_*`，并产生告警；它不会替换数据源、修改参数、授予 IAM 权限或修改仓位。

达到候选自己的完整前瞻窗口（例如 SOXL V7 基于其回测与风险验证采用 252 个交易日）只会进入 `FORWARD_COMPLETE_HUMAN_REVIEW`。不同策略可以采用不同观察期，但必须由冻结候选与回测证据明确证明，不能在运行中自动修改。返回值永久包含：

- `no_order=true`
- `live_authority_granted=false`
- `live_action=human_approval_required`

因此调度器可以自动完成非实盘观察、记录和安全暂停/恢复；任何平台适配器都必须把该结果视为非 Live 意图。首次 Live、重新启用 Live、资金扩大和策略参数修改仍须独立人工批准与重新验证。
