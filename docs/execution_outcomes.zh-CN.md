# 不可变执行 outcome

`ExecutionMarkerStore` 将执行去重 claim 与执行 outcome 分离存放：

- `execution_markers/`：执行前以原子仅创建方式写入 claim；它是防重复下单的唯一权威，永不覆盖。
- `execution_outcomes/`：执行周期结束后以同样的仅创建方式写入终态 outcome；已存在时保持不变并返回 `False`。

此设计适用于 GCS、S3、Azure 与本地后端。运行账户只需创建和读取对象，不需要为了更新 marker 而获得删除或全量对象管理权限。平台调用方应在成功获得 claim 后调用 `record_outcome`，不得用 `record_marker` 覆盖 claim。

`record_marker` 保留给未采用执行前 claim 的旧调用方，以保持兼容；新执行路径应使用 claim + outcome。

账户级独占见 `claim_account_owner`（key：`v1/account-owner/{broker}/{account_id}`，无 TTL）。换手与同账户共用 durable URI 的运维步骤见 [account_owner_fence_ops.zh-CN.md](./account_owner_fence_ops.zh-CN.md)。
