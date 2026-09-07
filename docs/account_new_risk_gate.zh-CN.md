# 账户新增风险门（库与平台接线已合；不授予 live）

> 2026-09-08 源码核对：库与所选平台 adapter 已合并；生产数据可用性及交易周期验收另行确认。

`quant_platform_kit.risk.account_new_risk_gate` 提供账户级「是否禁止新增风险」的
**注入式只读 adapter**。它与订单级 `RiskEngine` / `risk.gate` 互补，不替代它们。

| 阶段 | 内容 | 接线状态 |
| --- | --- | --- |
| D1 | `evaluate_capital_risk_envelope` 纯函数信封 | 已合 (#576) |
| D2 | 账户门注入权益摘要并消费信封 | 已合 (#577) |
| D3 | 多账户汇总权益 + 每账户信封只读视图 | 已实现；不含 allocator/下单 |
| W1 | 平台仓接线：账户读回 → 注入快照 | Schwab / LongBridge / IBKR 已有 adapter；不等于本轮核验了真实账户 |
| W2 | 只读 probe：手工 equity/peak/vol → 信封 + gate disposition | 已合；**不读券商** |
| Policy A | 注入生产 drift → 禁新增风险 | QPK #589/#590、Schwab #391、LongBridge #457 已合；不自动 reopt |

**本库不授予 live，不自动 enable 账户。** 平台接线已存在，不能再笼统描述为“未接生产部署”；既有交接报告的部署与本次源码核对分开，Cloud Run 配置、真实分数及交易周期仍须独立验收。

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
- 已注入的 `production_drift_status` 不是 `review` / `critical`，也不是非法状态

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

### Policy A：生产偏离只禁新增风险

`risk.production_drift_new_risk` 的映射复用上述账户门：

- `review` / `critical` → `PRODUCTION_DRIFT_REVIEW` / `PRODUCTION_DRIFT_CRITICAL` → `NEW_RISK_PROHIBITED`。
- `healthy` / `watch` 不增加 drift 禁止原因；非法已注入状态 fail closed。
- `resolve_production_drift_status_from_store` 是已有 lifecycle store 的只读 adapter，返回可注入状态；不创建第二份分数，不优化、不启用账户、不复位熔断。
- **缺轴边界保持原实现**：缺分、parked、不可用或读取异常返回 `None`；账户门不会将 `None` 当健康，但也不会仅凭它禁止新增风险。这不是“生产 drift 已有效”的证明，须单独核验启用该保护的消费者及数据可用性；本文不修改缺轴策略。

Schwab / LongBridge 的交易 adapter 使用实际 runtime target 的 `strategy_profile`；observe 的 `PRODUCTION_DRIFT_STRATEGY_PROFILE` override 不证明交易链消费了同一 profile。
平台 env-sync 接线分别由 [Schwab #393](https://github.com/QuantStrategyLab/CharlesSchwabPlatform/pull/393)、[LongBridge #459](https://github.com/QuantStrategyLab/LongBridgePlatform/pull/459) 补齐。GitHub Variables、同步计划和 CI 都不证明 Cloud Run 已应用变量或能够读取分数。lifecycle 写入只使用获准 GHA / Cloud Run WIF，不用本机 ADC 补写分数。

有界研究优化属于另获授权的候选研究链；生产 Policy A 不自动调用 `run_research_promotion_cycle` / `optimize`，不调整现行策略参数。禁新增风险不等于自动撤单、平仓或恢复。

### 生产 drift 轴（Policy A：禁新风险，零优化）

可选注入 `production_drift_status`（`healthy` / `watch` / `review` / `critical`）：

| 注入 | 门控效果 |
| --- | --- |
| 缺省 / 空白 | 不发明状态；本轴不加禁止理由 |
| `healthy` / `watch` | 本轴允许 |
| `review` / `critical` | `NEW_RISK_PROHIBITED`（`PRODUCTION_DRIFT_REVIEW` / `PRODUCTION_DRIFT_CRITICAL`） |
| 非法值 | `PRODUCTION_DRIFT_STATUS_INVALID_FAIL_CLOSED` |

本轴**只**禁止新增风险；不启动 reopt、不写研究 ticket、不授 live。研究侧有界 reopt 仍须人工/独立 ticket 触发。助手：`production_drift_new_risk_reasons` / `production_drift_status_from_result`。平台可调用 `resolve_production_drift_status_from_store` 从 PerformanceStore 只读 probe 注入状态；无 store / parked / 探针失败时省略本轴（不发明 CRITICAL）。

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
本模块固定「对账健康 + 资金信封 + 已注入 drift → 禁止新增风险」边界与注入点。
W1 平台 adapter 已有实现；持久化 OPEN 熔断、实际账户读回和最终下单限制的运行验收须按具体消费者确认，不能从库存在、CI 或旧 P4/P5 编号推导完成。

## 晋级仓位双口径（勿混淆）

- Composer 相对无杠杆基准 MDD 天花板：`CAPITAL_PRESERVATION` 1.00 / `BALANCED_COMPOUNDING` 1.25 / `GROWTH_COMPOUNDING` 1.50
- 晋级 `promotion_sizing` 仓位缩放：0.50 / 0.75 / 1.00，且仅用于新晋级/材料变更；插件 scalar ≤ 1
- 不得把 1.50× 当成仓位×1.5，不得用晋级缩放重算旧 live
