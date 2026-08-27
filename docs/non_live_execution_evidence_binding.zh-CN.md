# 非 Live 运行证据绑定

`quant_platform_kit.strategy_lifecycle.non_live_execution_evidence` 定义
`non_live_execution_evidence_binding.v1`。它把已经存在、但此前分散的三类事实冻结为一条可验证记录：

- 冻结候选及其不可变候选修订摘要；
- 一个目标平台、一个不暴露账户信息的 `runtime_scope_sha256`、一个平台适配器摘要和一个非 Live 通道；
- 一份精确的策略发布身份，以及同一 P4 前瞻收据和非 Live 证据工件的摘要。

这是所有单策略、组合策略与 `plugin_composite` 候选共用的契约；它没有 SOXL、TQQQ 或某个平台的硬编码。`plugin_composite` 是插件参与运行时唯一可用的候选形态，不能把单个插件伪装成独立执行策略。

## 冻结关系

构建器会校验收据中的 `p2_config`、`p3_evidence`、`risk_policy`、`strategy_release` 和 `plugin_bundle` 摘要，分别精确等于 `StrategyReleaseIdentity` 的 config、evidence、risk、manifest 与 plugin 摘要。这样，同一候选不能把另一个策略版本、不同风险政策或不同插件包混入前瞻观察。

`execution_channel` 只能是 `shadow` 或 `paper`，且必须是该候选 policy 已启用的通道。Shadow 需要收据中有 `shadow_decision`；Paper 还必须有 policy 声明的 `simulated_replay` 或 `broker_paper`。任何路径都固定为：

```json
{
  "no_order": true,
  "live_authority_granted": false
}
```

因此它不是订单许可、账户许可、调度器或 Live 晋级器。它也不会读取/写入对象存储、Cloud Run、GitHub、市场数据或券商。

## 账户与运行范围

记录只保存 `runtime_scope_sha256`，不保存账户号、账户 selector、服务名、部署 URL、凭证或券商原始响应。平台在其受控环境内从自己的运行时目标计算该摘要；审计/存储层只按摘要匹配。实际的账户身份核验、Paper 命令范围和订单准入仍由已有的 runtime-target、account-identity、paper-command 和 risk-gate 契约负责。

## 当前 Shadow 与未来 Paper

通用构建器只接受经过调用方验证的 `schema_version + sha256` 证据引用，使未来的 Paper adapter 可以采用自己的、严格验证后的证据 schema。对当前 `paired_shadow_evidence.v1`，平台必须优先使用 `build_paired_shadow_execution_evidence_binding(...)`：它会再验证 paired-shadow 工件、policy 和前瞻收据三者完全一致。

平台可以调用 `build_non_live_execution_evidence_report_artifacts(...)`，将 canonical JSON 与摘要放进既有 `runtime_reports.artifacts`。持久化服务仍应以 `(candidate_id, platform_id, runtime_scope_sha256, execution_channel)` 作为隔离/查询键，并用 create-only 或条件追加保存收据、证据与绑定；纯函数不能替代对象存储的原子性和访问控制。
