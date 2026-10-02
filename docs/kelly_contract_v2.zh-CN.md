# Kelly 契约 v2（研究-only）

更新：2026-10-03。对应 2026-10-02 长期复利/Kelly 审计 F04 与次级 API 修复。本文只定义 QPK helper 单位与兼容边界，不授予 paper/live 权限，也不修改交易消费者。

## 单位

| 单位 | 含义 | 主要 API |
|---|---|---|
| `bet_loss_risk_share` | 二元赌注在亏损时全部损失时的风险份额 | `estimate_kelly`、`constrained_kelly_recommendation` |
| `capital_exposure` | 资产资金暴露；需显式 `loss_fraction_per_unit` 从风险份额换算 | `research_capital_exposure_kelly` |

契约版本字段：

- `kelly.bet_loss_risk_share.v1`
- `kelly.capital_exposure.v1`

## 兼容约定

- 旧字段 `KellyResult.kelly_fraction` / `half_kelly` / `max_position_pct` 仍返回，语义仍是 `bet_loss_risk_share`。
- `max_position_pct` 是历史命名，等于 `min(half_kelly, 0.10)` 的风险份额上限，**不能**当作资产资金暴露。
- 新增 `contract_version` 与 `unit` 字段带默认值，现有构造与相等比较保持低成本兼容。
- `constrained_kelly_recommendation` 同样标注风险份额单位；`recommended_position_pct` 不是资本暴露。

## 二元 Kelly 规则

- 零收益不参与胜负概率与均值；混合零收益不得改变最优风险份额。
- 非有限、`bool` 或错误类型输入 fail-closed：`estimate_kelly` 返回零解，约束/暴露 API 返回 `PARKED`。
- 非法/非有限 drawdown 返回 `PARKED`，不抛异常。
- 不允许 full Kelly（`fractional_kelly >= 1`）。

## 资金暴露研究 API

`research_capital_exposure_kelly`：

1. 先得到 `bet_loss_risk_share`；
2. 用显式可信 `loss_fraction_per_unit` 换算：`theoretical = risk_share / loss_fraction_per_unit`；
3. fractional 只应用到该理论解一次；
4. 再与 `risk_budget_cap`、`position_cap` 取小；
5. 未缩放部分视为现金，禁止把风险权重重新归一化为满仓并冒充 half。

本 API 固定沿用至少 30 个样本、正负收益两侧齐全、必须提供最大回撤观测且不超过 25% 的 fail-closed 门槛；不能通过本 API 调低样本门槛或放宽回撤门。缺少可信亏损比例时必须 `PARKED`；不得用平均亏损偷造硬风险保证。资本暴露 cap 必须在 (0, 1]，超 100% 的杠杆建议停放。本 API 为 research-only，不接入交易下单链。

验收算例：`(+20%, +20%, -10%)` 风险份额 `0.5`；若每单位损失 `10%`，未约束理论资金暴露为 `5`；独立资金上限仍可裁到 `≤ 0.1`。

## 组合诊断与 shadow 排序（次级）

- 空头未实现盈亏使用有符号成本：`market_value - quantity * average_cost`。
- 部分成本覆盖不得当作完整 PnL；诊断返回 `unrealized_pnl_coverage`，缺价/非有限成本为未知。
- metadata 中的 `unrealized_pnl_pct` override 仍优先，并标记 `unrealized_pnl_source=metadata`。
- adaptive shadow 排序中合法 `score=0` 高于负分；较小 `risk_multiplier` 不得使负分更有吸引力。`shadow_only` / `no_order` / 零权重不变。

## 非目标

- 不实现分布鲁棒求解器，不新增依赖。
- 不修改交易消费者、运行策略、风险预算授权或 full-Kelly 政策。
