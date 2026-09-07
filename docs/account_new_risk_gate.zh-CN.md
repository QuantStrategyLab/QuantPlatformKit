# 账户新增风险门（D2/D3 已合；W2 只读 probe；未授权 live）

> 状态：`D2_D3_MERGED_W2_PROBE_NOT_LIVE_WIRED`

`quant_platform_kit.risk.account_new_risk_gate` 提供账户级「是否禁止新增风险」的
**注入式只读 adapter**。它与订单级 `RiskEngine` / `risk.gate` 互补，不替代它们。

| 阶段 | 内容 | 接线状态 |
| --- | --- | --- |
| D1 | `evaluate_capital_risk_envelope` 纯函数信封 | 已合 (#576) |
| D2 | 账户门注入权益摘要并消费信封 | 已合 (#577) |
| D3 | 多账户汇总权益 + 每账户信封只读视图 | 已实现；不含 allocator/下单 |
| W1 | 平台仓接线：真账户读回 → 注入快照 | 独立后续工作 |
| W2 | 只读 probe：手工 equity/peak/vol → 信封 + gate disposition | 已合；**不读券商** |

**仍未授权 live、未自动 enable 账户、未接生产部署。**

## 模块边界

| 会做 | 不会做 |
| --- | --- |
| 接受调用方注入的脱敏对账快照投影（含可选权益摘要） | 读取真账户、券商、凭据或网络 |
| W2：`reconciliation_snapshot_binding` 把权益摘要 dict/dataclass 严格绑定为 `InjectedReconciliationSnapshot` | 自动 flatten、自动 reset 熔断 |
| W2：`capital_envelope_w2_probe` / `python -m quant_platform_kit.risk.capital_envelope_w2_probe` 打印信封与 gate | 部署、改账户启停、授予 live |
| 不健康快照 / 权益缺失或非法 / 信封禁新风险 → `NEW_RISK_PROHIBITED` | 削弱或绕过 `RiskEngine` |
| 保持 `live_authority_granted=false` | |

允许 `ALLOW_NEW_RISK` 的条件（全部满足）：

- `observation_status == COMPLETE`
- `reconciliation_status == VERIFIED`
- `circuit_breaker_state == CLOSED`
- 注入 `equity_usd` 合法，且资本信封 `new_risk_allowed=True`

### 交易周期健康语义（cycle-health，异于 RECONCILE_ONLY 恢复）

平台执行周期应通过 `cycle_new_risk_health.project_cycle_new_risk_health_axes` /
`apply_cycle_new_risk_health_axes` 投影三轴：

| 轴 | 周期健康口径 |
| --- | --- |
| `COMPLETE` | 本周期只读权益/持仓面成功（不冒充实全量 GTC/成交账本） |
| `VERIFIED` | 无 UNKNOWN 未决；未配置 expected digests 时走周期健康；已配置则须全匹配 |
| `CLOSED` | 无 durable OPEN，且本周期未因 UNKNOWN/trip 打开；**绝不**自动清除 OPEN |

旁路 `/reconcile`（`RECONCILE_ONLY` + digests）仍只服务冻结基线恢复，不得与 cycle-health 混称。

可选：`peak_equity_usd` / `drawdown_from_peak` / `realized_vol`。缺权益 →
`EQUITY_UNKNOWN_FAIL_CLOSED` 禁止。`ALLOW_NEW_RISK` **不是**下单许可，也不是实盘授权。

### W2 只读 probe 用法

```bash
python -m quant_platform_kit.risk.capital_envelope_w2_probe --equity 40000
python -m quant_platform_kit.risk.capital_envelope_w2_probe --equity 85000 --peak 100000
python -m quant_platform_kit.risk.capital_envelope_w2_probe --equity 100000 --drawdown 0.10 --json
```

程序内：`probe_capital_envelope_w2(equity_usd, peak_equity_usd=..., realized_vol=...)`。

权益摘要绑定：`build_injected_snapshot_from_equity_summary({"equity_usd": 40000.0})`。

### D3 多账户汇总视图

`evaluate_multi_account_envelope_view(accounts)` 接受调用方注入的
`account_id`、`equity_usd` 及可选 `peak_equity_usd` /
`drawdown_from_peak` / `realized_vol`：

- 汇总权益复用 D1 的同一资金分档表；
- 每账户保留独立信封，不从汇总档位抬高任何账户执行权；
- 任一账户 `new_risk_allowed=false` 时，聚合信号也为 false；
- 任一权益缺失或非法时 fail-closed，汇总权益记为未知；
- 输出仅供控制台/诊断解释，不分配仓位、不跨账户下单、不授予 live。

## 与 QRT 确定性内核的关系

完整限额/频率判定内核在 QRT `python/scripts/deterministic_risk_gate.py`（仓库 QuantRuntimeSettings）。
本模块固定「对账健康 + 资金信封 → 禁止新增风险」边界与注入点；W1 挂真账户读回、持久化
OPEN 熔断与执行网关接线仍属后续独立工作，完成前不得宣称 P4/P5 已接通。

## 晋级仓位双口径（勿混淆）

- Composer 相对无杠杆基准 MDD 天花板：`CAPITAL_PRESERVATION` 1.00 / `BALANCED_COMPOUNDING` 1.25 / `GROWTH_COMPOUNDING` 1.50
- 晋级 `promotion_sizing` 仓位缩放：0.50 / 0.75 / 1.00，且仅用于新晋级/材料变更；插件 scalar ≤ 1
- 不得把 1.50× 当成仓位×1.5，不得用晋级缩放重算旧 live
