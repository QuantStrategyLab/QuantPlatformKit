# 前瞻观察自动化契约

`quant_platform_kit.strategy_lifecycle.forward_observation` 是策略、插件和平台共用的纯决策层。它不连接券商、不写运行时目标、不部署服务，也不产生订单。

每个冻结候选必须显式提供自己的 `ForwardObservationPolicy`：候选 ID、策略 profile、无杠杆基准、前瞻交易日数量、复核里程碑、恢复前需要的连续健康周期、市场日历、固定或滚动窗口、窗口起点、窗口理由引用，以及精确的非 Live 证据模式。控制器没有“252 天”“20/60 天”或某个策略的隐性默认值；新候选缺少这些字段会被拒绝，不能继承 SOXL 的参数。没有已验证的 P3 历史证据和证据引用时，状态固定为 `PARKED`。

P3 通过后，控制器可以自动给出 `start_shadow`、`start_paper`、`continue_*` 和在短暂数据/运行故障恢复后的 `resume_*` 意图。证据模式必须明确为 `shadow_decision + simulated_replay` 或 `shadow_decision + broker_paper`，不能把模拟回放、订单预览和券商 Paper 混称为同一种 Paper。数据过期或 Shadow/Paper 不一致时，才会进入可自动恢复的 `PAUSED`；风险阻断、人工冻结、身份不匹配、撤销或被新候选替代，分别进入不可自动恢复的终止状态。

真正的候选 Shadow 必须在同一份带时间戳的输入快照下，同时保存候选与基线的信号、
假设订单、仓位、成本和收益，并按 `candidate_id` 隔离。生产策略的近期绩效快照
只能用于监控，不能替代候选的并行 Shadow 证据。

达到候选自己的完整前瞻窗口（例如 SOXL V7 基于其回测与风险验证采用 252 个交易日）后，控制器会停止两种非 Live 意图，并进入 `FORWARD_COMPLETE_HUMAN_REVIEW`。不同策略可以采用不同观察期，但必须由冻结候选与回测证据明确证明，不能在运行中自动修改。返回值永久包含：

- `no_order=true`
- `live_authority_granted=false`
- `live_action=human_approval_required`

因此调度器可以自动完成非实盘观察、记录和安全暂停/恢复；任何平台适配器都必须把该结果视为非 Live 意图。首次 Live、重新启用 Live、资金扩大和策略参数修改仍须独立人工批准与重新验证。

每个有效观察周期还应输出 `forward_observation_receipt.v1`。收据只保存候选、完整 policy 摘要、观察交易日/序号、前一收据摘要、P1/P2/P3/风控/发布/插件的摘要和精确证据模式；它不保存原始价格、账户、订单或密钥。验证器要求收据连续追加、候选与 policy 一致，且不能越过冻结窗口。
