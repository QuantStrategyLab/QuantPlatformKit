# 账户身份门禁

账户身份门禁位于平台的下单端口之前，和策略公式、仓位计算、插件信号完全分离。它把券商只读返回的账户事实与 `RUNTIME_TARGET_JSON` 中经过审核的目标进行比对；策略和插件不能绕过或修改这个判断。

## 运行目标配置

在 `RUNTIME_TARGET_JSON` 中可选加入 `account_identity`：

```json
{
  "enforcement": "observe",
  "expected_account_types": ["cash"],
  "expected_account_modes": ["paper"],
  "expected_account_id_fingerprint": "sha256:<64位小写十六进制>",
  "required_fields": ["account_type", "account_mode", "account_id"]
}
```

- `observe`：生成脱敏回执和监控信号，但不影响现有下单；用于先核验券商 API 的实际能力。
- `enforce`：缺少证据或字段不一致时，订单在调用券商前被拒绝。
- 账户号只能以 `sha256:` 指纹传入；原始账户号和凭证不得写入运行目标、日志、插件载荷或执行报告。

如果配置了期望账户类型、模式或账户指纹，对应字段会自动成为必填证据。缺少期望值也会形成 `account_identity_configuration_invalid`，不会被默默放过。

## 平台接入规则

1. 平台适配器在建立 broker context 后只读查询账户元数据。
2. 适配器生成 `BrokerAccountIdentity`，并调用 `evaluate_account_identity`。
3. 将 `AccountIdentityGuardedExecutionPort` 放在所有订单路径外层；策略、插件和人工触发路径均复用它。
4. 把 `decision.to_receipt()` 写入 runtime report，并把 findings 传给 `runtime_command_gate`（使用 durable command 的平台）。
5. 每个账户先连续观察多个交易日，再由运维显式把该目标切到 `enforce`；不能自动改凭证或切换账户。

## LongBridge 的当前边界

LongBridge OpenAPI 的持仓通道可返回账户类型，因此可先校验 `account_type`。但公开账户余额接口没有提供可比对的账户号，也无法直接证明 paper/live 身份。LongBridge 目标必须先使用 `observe`；在没有可信 broker 证据前，不能声称 PAPER 密钥名等于模拟账户证明。若将缺失字段设为 `enforce`，系统会安全地拒绝订单。

## 稳定 finding 代码

- `account_identity_evidence_unavailable`
- `account_identity_configuration_invalid`
- `account_identity_platform_mismatch`
- `account_identity_type_mismatch`
- `account_identity_mode_mismatch`
- `account_identity_id_mismatch`

这些代码不包含账户号或凭证，可用于平台、策略运行报告、插件告警和统一 Runtime Command Gate。
