# 账户 Owner Fence 运维说明

`claim_account_owner` 在真正提交券商订单前，为**物理账户**建立独占 fence。它与按信号日 / `strategy_profile` 的执行 claim 分开：后者防同信号重复下单，前者防同一资金账户被多个 writer 同时管。

## 语义（稳定）

| 项 | 行为 |
|---|---|
| Marker key | `v1/account-owner/{broker}/{account_id}`（**不含** strategy profile） |
| 创建成功 | 本 writer 成为 owner，允许继续 |
| 已存在且 `owner_id` 相同 | 放行，不改写 |
| 已存在且 `owner_id` 不同 | `contested=True`，拒绝提交（fail-closed） |
| TTL | **无**。不会自动过期，也不会被后来的 writer 抢占 |
| 释放 API | **无**。换手须人工删除 durable marker 对象 |

平台运行身份只需对 marker 前缀有**创建 + 读取**权限；删除属于受控运维操作，不应交给日常交易服务账号。

## 同账户必须共用同一个 durable URI

Fence 只在**同一对象存储前缀**内有效。碰同一 `{broker, account_id}` 的所有 Cloud Run / 作业必须配置同一个 execution-marker `cloud_prefix_uri`（或等价后端根）。

若两个实例各写各的 bucket/前缀：

- 代码层看起来都 `claim` 成功；
- 实际互斥**不存在**；
- 这是运维闭合问题，不是再造一把分布式锁能 internally 证明的。

上线前核对清单：

1. 各 writer 的 marker 前缀 URI 字符串完全一致（含尾斜杠约定）。
2. `{broker, account_id}` 在各平台解析到**同一物理账户身份**（不要用 region / PAPER 标签冒充账户号，除非该标签已是你选定的 durable id，且全路径一致）。
3. contested 时日志/通知能看到脱敏后的 `marker_key` 与当前 `owner_id`，且 `submit=0`。

## Owner 换手（换策略 / 换 profile / 换服务）

无 TTL，因此换手是显式变更，不是“等过期”。

1. **停写**：暂停会碰该物理账户的调度与手动 invoke；确认无在途 submit / UNKNOWN 待对账项（按各平台既有 UNKNOWN 流程处理，不在本文件展开）。
2. **读回确认**：用运维身份读取 marker，记录当前 `owner_id`、`marker_key`、对象 URI。
3. **删除 marker**：仅删除该 `v1/account-owner/{broker}/{account_id}` 对象（不要批量清 `execution_markers/`）。
4. **启动唯一新 writer**：只拉起目标服务；由其在下次 submit 前重新 `claim_account_owner`。
5. **验证**：同 owner 重跑放行；故意用旧 owner / 第二 profile 路径应 `submit=0` 且 contested。
6. **保留证据**：换手时间、操作者、旧/新 `owner_id`、对象 URI 记入运维记录（不要写入账户号明文到公开渠道路径以外的地方时，遵循各平台脱敏约定）。

禁止：

- 在未停写时删除 marker（竞态下可能双写）。
- 为了“方便恢复”给 fence 加 TTL 或自动 steal。
- 用信号 claim / 本地文件锁冒充跨实例账户独占。

## LongBridge 物理账户 id

当前可用（token 绑定）形态：

- 显式：`LONGBRIDGE_PHYSICAL_ACCOUNT_ID=lb:<name>`
- 回退：`lb:<LONGPORT_SECRET_NAME>`（与 runtime / env-sync 一致；broker 字段为 `longbridge`）

这已能区分 hk / paper / sg 的凭证边界。长期若取得券商真实账户号，再迁到 `lb:<broker_account_no>`。

### 迁移步骤（有真实账户号时）

1. 停写对应服务；确认无在途订单争议。
2. 删除旧 key：`v1/account-owner/longbridge/lb:<old_id>`。
3. 更新 GitHub Environment / Cloud Run：`LONGBRIDGE_PHYSICAL_ACCOUNT_ID=lb:<broker_account_no>`（三环境分别核对）。
4. 跑 env sync 或 Deploy，确认变量未进 `remove_env_vars`、Cloud Run 上值正确。
5. 启动唯一 writer；验证新 key 被创建，旧 token 绑定 id 不再出现在 fence 路径。

无真实账户号前**不要**强行改 id；改名等于换 fence 身份，必须按换手流程做。

## 相关代码

- `quant_platform_kit.common.execution_state.build_account_owner_marker_key`
- `quant_platform_kit.common.execution_state.claim_account_owner`
- 执行 claim / outcome 分离见 [execution_outcomes.zh-CN.md](./execution_outcomes.zh-CN.md)
