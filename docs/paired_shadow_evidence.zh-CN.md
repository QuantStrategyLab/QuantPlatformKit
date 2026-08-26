# P2 真实并行 Shadow 证据契约

`quant_platform_kit.strategy_lifecycle.paired_shadow_evidence` 定义
`paired_shadow_evidence.v1`。它是 `forward_observation_receipt.v1` 的伴随
工件，不替代 `ForwardObservationPolicy`、既有收据或生命周期状态机。

每条证据必须绑定一个已验证的 Forward Observation 收据，并包含：

- 同一个 `observed_at` 和 `input_snapshot_sha256`；
- 同一份输入下分别由候选与基线产生的 `signal`、`hypothetical_order`、
  `position`、`cost`、`return`；
- `candidate_id`、稳定的 `baseline_id`、Forward Observation 收据摘要；
- 前一条 paired-shadow 证据摘要，以及始终固定的
  `no_order=true` / `live_authority_granted=false`。

该模块不计算策略数值、不产生订单、不访问市场数据、账户、券商或密钥。它只把
非 Live adapter 已经得到的结果按规范冻结并验证。`signal` 等五类字段是
策略专属 JSON 值；合同会保留它们的精确内容和摘要，但不解释其含义或重算收益。

## 连续性与隔离

从第二条开始，写入方必须同时提供前一条 paired-shadow 证据和前一条 Forward
Observation 收据。验证器检查：候选与基线标识不变、观察序号和时间前进、两条
paired-shadow 证据相连，并且 Forward Observation 收据链也一一对应。因此不能把
不同候选、不同基线或不同前瞻窗口的记录混入同一链。

持久化平台仍须使用条件追加：以 `(candidate_id, baseline_id)` 保存当前链头，并
对 `forward_observation_receipt_sha256` 建立唯一约束。纯合同无法替代数据库/对象
存储的原子写入，也不能阻止两个独立 writer 同时尝试从同一链头分叉。

## 与旧 ShadowValidator 的关系

现有 `ShadowValidator` 读取的是生产近期绩效快照。它现在会明确返回：

```json
{
  "evidence_kind": "recent_performance_proxy",
  "paired_shadow_evidence": false,
  "no_order": true,
  "live_authority_granted": false
}
```

这类代理数据可继续作为诊断信息，但它没有候选/基线在同一时点、同一输入快照下的
五类输出，不能被当作 `paired_shadow_evidence.v1`，也不能用于证明 P2 已完成。

## 平台接线边界

后续 non-live adapter 应在每个 Forward Observation 收据生成后：冻结输入快照摘要，
并行运行候选与基线，生成本工件，再以条件追加方式持久化。Forward Observation
调度器和任何实盘 adapter 都不能从该工件推导下单或 Live 权限；完成窗口后仍须走
独立人工审批。

QPK 的 `runtime_reports` 已提供所有平台共用的 `artifacts` 扩展位。因此平台升级
QPK 后，可以只调用纯函数 `build_paired_shadow_evidence_report_artifacts(...)`，并把
返回值传给 `build_runtime_report_base(..., artifacts=...)` 或
`finalize_runtime_report(..., artifacts=...)`：

```python
artifacts = build_paired_shadow_evidence_report_artifacts(
    evidence,
    policy=policy,
    forward_observation_receipt=receipt,
)
report = build_runtime_report_base(..., artifacts=artifacts, dry_run=True)
```

函数会验证 policy/收据绑定后，将完整证据作为
`paired_shadow_evidence_json`（canonical JSON 字符串）和摘要放入 `artifacts`，同时附加
`paired_shadow_evidence_no_order=true` 与
`paired_shadow_evidence_live_authority_granted=false`。它不接收、修改或部署 runtime
target，也不写云端、提交订单或改变运行模式。`PlatformRunner` 本身不拥有报告
schema 内容，因此无需为这个通用附件增加分支或平台专用逻辑。使用 JSON 字符串而非
嵌套 mapping，是为了避免既有报告序列化为清理空值而移除首条证据的
`previous_paired_shadow_evidence_sha256: null`，从而保持收据摘要可复验。
