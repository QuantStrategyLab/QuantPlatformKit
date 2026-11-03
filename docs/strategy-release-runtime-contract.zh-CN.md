# 策略发布与运行时回执契约（v1）

`StrategyReleaseManifest` 是策略、配置、风险规则、证据和插件包的不可变发布记录。它不是一次回测结果，也不能单独授权交易。

每个运行实例仅接收精简的 `StrategyReleaseIdentity`。运行报告始终包含 `runtime_release_receipt`：

- `self_attested`：该进程已加载完整 release identity；这不是跨平台一致性的结论。
- `legacy_unattested`：旧运行实例没有 release identity。监控必须将其作为迁移缺口，而不能把空版本当成正常。

在后续命令门上线前，旧实例仍保持现有执行语义；但是任何风险增加型的新发布不得以 `legacy_unattested` 状态进入 ACTIVE。

插件 V2 可以把影子信号提供给策略做展示、诊断和研究。共享库注入快照的副本会把所有下单、仓位和 allocation 授权明确降为 `false`，原始 artifact 仍由 `StrategyPluginSignal.payload` 保留用于审计。插件自身不能借由 metadata 授权策略改仓。

跨平台发布必须依次满足：所有目标预装同一 release、所有运行时回传相同 identity、统一交易日生效、观察期完成。任何一个目标缺回执或 digest 不符，发布不得进入 ACTIVE。

## 一次确认的自动化 setup intent

`common.automation_setup.SetupIntent` 和随包发布的
`schemas/automation-setup-intent.v1.schema.json` 提供独立、非执行的意图合同。
现有 RuntimeTarget、RuntimeControl、候选晋级和 research mandate 接口不变。
消费者采用前须固定经审查的 QPK 版本；本合同尚未接入 QRS 或执行器。

`SetupIntent.create(subject, decision=None)` 验证并冻结合同；
`to_dict()` / `from_dict()` 用于受保护的合同传输与往返验证，不能直接用于公开列表。
schema 负责结构检查；Python 合同还检查摘要、金额上下限、目标与控制一致性、
有效期顺序。JSON 反序列化不能续期或恢复已撤销意图。

subject 明确记录不透明的账户引用列表、币种、十进制字符串金额及 cap、
`one_time` 或带不可变 plan_ref 的 `standing_plan`、费用及储备处理、
instrument/action 范围、policy_ref 和显式环境。账户真实映射由下游受保护存储负责；
禁止传入账户选择器、账户别名、主机、凭据或自由文本。
目标和 release 使用既有公开构建器校验，control 使用既有 RuntimeControl 校验，
且必须 disabled。控制储备不是确认的预算。LIVE 只能表示请求意图，不能启用。
初始 revision 为 1；后续 revision 必须引用前一 subject 摘要。
摘要绑定内容，不认证所有者，也不匿名化真实资源。

decision 记录同一 subject 摘要和 revision、human actor_ref、decision_ref、
confirmed/rejected、reviewed/effective/expires 时间及 state_version/epoch。
本版本要求明确、有限且带时区的有效期；无默认无限期。
不嵌入候选 PromotionDecision，也不把 setup 伪装成候选或消耗 research nonce。

`classify_setup_intent(intent, now=..., current=..., proposed_subject=...)` 是纯描述函数。
current 必须每次从现有认证来源读取，包含 setup/revision/digest、decision_ref、
state_version/epoch、source_ref、checked_at/valid_until、current/revoked/superseded、
独立 prerequisites 和 activation_readback。缺失、非法、失配或不在有效区间的
current 产生阻塞；当前撤销和替代状态不能被旧 confirmed decision 覆盖。
函数不认证来源、不保存状态、不锁定跨进程写入。

返回值只有 intent_status、requires_owner_setup、blocker_codes、changed_fields、
resume_condition、activation_readback 和两个恒 false 的 authority 字段。
公开列表及通知摘要只使用这份允许字段投影；不输出账户引用、原始 subject 或 actor。
同一有效且当前的 confirmed revision 重复分类时 requires_owner_setup=false，
不为每笔交易或每个周期创建确认。账户、金额、环境、release、policy、instrument 或
plan 等变更列入 changed_fields，须由下游创建并确认后继 revision，不能扩大原范围。
拒绝、过期或撤销不会自动触发重试审批。

Paper minimum 必须是整数 3、4 或 5；这是需求值，不是完成证明。
本模块不能核验真实完整交易日、较长候选观察窗、风险、对账或告警证据，
因此相关 blockers 始终保留；自报 pass、模拟 session 和通知成功均不能清除它们。
activation_readback 始终投影为 unknown，和所有者意图分开。
LIVE 另列 LIVE_ACTIVATION_OWNER_NEEDED。两项 authority 标志在所有路径恒为 false；
没有 may_submit、executor、预算计算或生产开关写入。

QRS 后续在现有 Decisions/list/store 中适配 automation_setup subject：
认证会话提供 actor，写入时原子比较 subject 摘要、revision、state_version/epoch，
持久化 request_id 的相同请求幂等结果并拒绝同 key 不同内容；重启或旧进程不能覆盖撤销。
list/read 返回意图、阻塞、独立应用回执和通知状态；应用证据须由认证后端精确绑定，
完成须有必要 readback 和显式 acknowledgement。通知和网站点击都不能表示运行中。
本补丁不增加 HTTP 路由、数据库、outbox、任务平台、真实审批或应用接口。
账户、金额、激活范围的真实一次确认和任何受保护 apply 仍须各自所有者授权。
