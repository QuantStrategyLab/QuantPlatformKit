# 旧实盘基线的券商对账恢复契约

`RECONCILE_ONLY` 是旧实盘基线在迁移、配置漂移或运行异常后使用的
保护状态。它允许只读核验，但禁止普通策略下单。服务健康、API 登录成功或
单独看到持仓，都不能把它恢复为 `ACTIVE_LKG`。

共享库的 `broker_reconciliation_evidence.v1` 定义了一份可跨平台使用的
恢复收据。平台适配器必须在一个只读会话中完成以下核验，并只在收据中写入
摘要和布尔结论：

- 已连接到期望的券商账户；
- 当前持仓与本地执行账本推导的状态一致；
- 现金/购买力核验一致；
- 未完成订单一致；
- 最近成交/订单历史一致；
- 本地幂等执行账本完整且一致；
- 当前 runtime target 的摘要仍等于冻结基线摘要。

持仓、现金、订单、成交和账户范围都不得进入公开仓库、日志或通知。适配器
在本地对规范化只读快照计算 SHA-256；收据只包含这些摘要、`observed_at` 和
稳定的失败原因。私有控制面可保存受访问控制的原始核验材料，以便独立重算
摘要；公开工件只能保存收据。

## 恢复顺序

1. 平台在只读 broker 会话中生成候选收据；不能连上或任何读取失败均为失败。
2. 可信控制面重新验证收据摘要、账户范围、基线 target 和时效（默认 30 分钟）。
3. 控制面以独立来源比对私有快照/本地账本；不能只相信适配器的 `*_match=true`。
4. 全部通过后，受权限保护的控制面才可把同一冻结基线由
   `RECONCILE_ONLY` 改为 `ACTIVE_LKG`。该动作不是策略晋升，也不会放大资金。

只要任一步缺失、过期或不一致，就继续保持 `RECONCILE_ONLY`，并提供不含敏感
明细的稳定失败码供统一管理站点展示。新策略的 P0–P6 生命周期仍是另一条链路；
本契约只处理原本已获授权的旧实盘基线的安全连续运行。

## 首次纳入可信基线（旧实例）

旧实例可能没有可用的本地执行账本或历史摘要，不能把第一次看到的券商状态直接
写为“预期状态”。共享库仅生成**待人工确认的候选**，不具备恢复权限。新候选必须满足：

1. 新申请显式使用既有 `broker_reconciliation_baseline_candidate.v2` 和
   `source_receipts_sha256`；至少一份新鲜收据即可，不要求第二份或固定最小间隔。
   默认最大观察窗口仍为 15 分钟，每份收据不超过 30 分钟；
2. 每份收据都连接成功、账户身份一致、runtime target 绑定同一批准基线，且持仓、
   现金、未完成订单、近期成交和本地账本均已由可信平台 producer 完成对账；
3. 多份收据仍须绑定相同身份和五项状态摘要。本次不改变后续 activation 的五摘要比较；
4. 候选仅保存摘要、来源根和时间，不保存原始账户资料，也不产生执行权限。

**来源根只证明内容绑定，不证明真实、完整或已获授权。** 平台 producer 必须核验实际
账户绑定、查询完成边界、未决订单集、账务起点及差异解释后，再交付收据。共享库不
读取 source record 明细，不能凭摘要、两个相同样本或未经验证的 `*_match=True`
证明账户安全；本次不新增自证 boolean，也不把未对账标志改成 True。

模型审查是 advisory，不是进入人工确认的票数门。省略时保留真实 `unavailable`、
`reviewer_count=0`；已提供的 rejected/unavailable 不改写为 approved。已提供审查
仍绑定候选，防止串用其他候选的意见；人工应看到其真实状态。恢复仍须明确人工确认，
此补丁本身不批准真实账户接管、live、下单或扩大资金。

历史 `v1` 保留原解析与 round-trip，字段不变，不自动升级。兼容调用仍可构建旧 v1
候选，但缺少来源根的 v1 不再进入新的人工确认或 activation。新调用通过 enrollment
的可选 `source_receipts_sha256` 参数显式生成既有 v2，不新增 schema。
`min_separation` 参数保留调用兼容，但不再构成最小间隔门。

## 通用发布与恢复计划接口

`reconciliation_recovery.py` 把跨平台部分固定为三个**无副作用**契约：

1. `ReconciliationRecoverySourceSnapshot` 将已脱敏的候选、可选 advisory 审查、观察时间窗和稳定
   阻断码输出为 `qsl_reconciliation_recovery_source_snapshot.v1`。它可由专用 publisher
   port 发送到统一管理站，但不包含账户、持仓、现金、订单、成交或五项状态摘要。
2. `ReconciliationRecoveryConfirmation` 只读取管理站保存的
   `qsl_reconciliation_recovery_confirmation.v1`。该回执恒为 `no_order=true`、
   `execution_authority_granted=false`，不能被解释为订单或 state-write 权限。
3. `evaluate_reconciliation_recovery_activation` 要求 source-bound v2、人工确认及其候选/既有 binding 一致、
   确认后的**新**只读券商收据、当前状态仍为 `RECONCILE_ONLY`，以及五项摘要仍与候选相同；全部
   通过时仅返回 `RECONCILE_ONLY -> ACTIVE_LKG` 的 compare-and-set 计划。

共享库不实现 publisher 的 HTTP、确认回执读取、真实来源验证或状态写入。
`dual_review_binding_reverified` 参数已弃用但保留兼容，不再阻断或授予恢复权限。平台私有
控制器必须各自以最小 IAM 实现这些 ports，并在同一存储事务/原子比较中检查当前状态、
冻结 target 摘要和五项摘要后才可应用计划。读取失败、确认过期、收据不晚于确认、来源验证失败
或 compare-and-set 失败时，均不得重试为普通执行，必须保持
`RECONCILE_ONLY`。
