# 策略晋级与风险标准

本文定义策略晋级、插件自动化、AI 自动优化和 Kelly readiness 的统一门槛。

## 统一原则

- 先满足 `live_ready`，再谈自动化放行和资金影响。
- `kelly_ready` 只表示风险预算上限可计算、可解释、可约束；**不能**作为晋级理由。
- 任何自动化动作都必须绑定可追溯证据包。
- 任何 AI 优化都必须保留完整试验记录，不能只留最终参数。

## `live_ready` 与 `kelly_ready`

| 状态 | 含义 | 可否作为晋级理由 |
| --- | --- | --- |
| `live_ready` | 已满足上线、运行、监控和风险要求，可以进入受控 live 流程 | 可以 |
| `kelly_ready` | 已能给出 Kelly 风险预算上限，但仍可能未满足上线门槛 | 不可以 |

要求：

- `kelly_ready` 只能用于约束最大风险预算、仓位上限和回撤容忍度。
- `kelly_ready` 不能替代回测、OOS、成本、风险、数据完整性和插件门槛。
- 如果只有 `kelly_ready`，策略仍应停留在非 live 状态。

补充约束：Kelly 只能输出研究建议，必须同时受现有组合风险预算、仓位上限和 fractional Kelly 上限约束，不能增加或覆盖既有预算。默认样本不足、缺少正负收益两侧、缺少回撤观测或超过回撤上限时，结果必须为 `PARKED` 且建议仓位为零；不得用小样本外推。

## 风险指标最低标准

证据包里的 `risk` 必须至少包含以下内容：

- `risk.metrics.sharpe_ratio`
- `risk.metrics.sortino_ratio`
- `risk.metrics.max_drawdown`
- `risk.metrics.annualized_return`
- `risk.metrics.annualized_volatility`
- `risk.metrics.calmar_ratio`
- `risk.metrics.information_ratio`
- `risk.metrics.var_95`
- `risk.metrics.cvar_95`
- `risk.metrics.turnover`
- `risk.metrics.trade_count`
- `risk.metrics.win_rate`
- `risk.metrics.profit_factor`
- `risk.benchmark.name`
- `risk.benchmark.alpha`
- `risk.benchmark.beta`
- `risk.cost_stress.slippage_bps`
- `risk.cost_stress.commission_bps`
- `risk.cost_stress.passed`
- `risk.oos.window_start`
- `risk.oos.window_end`
- `risk.oos.locked`

要求：

- 缺任一项，都不算可审计的风险证据包。
- `risk.metrics` 允许保留额外字段，但不能只给一个宽松 object。
- `full_kelly_allowed=false` 仍然只是 Kelly 上限约束，**不能**替代上述风险指标。

## Evidence package 必备文件

策略晋级前，证据包必须同时包含以下文件：

- `returns`
- `trades`
- `positions`
- `config`
- `data_manifest`
- `candidate_registry`
- `benchmark_registry`
- `cost_model`
- `risk_report`
- `kelly_readiness_report`

要求：

- 缺任一项，证据包不完整，不能用于晋级。
- 文件应指向同一个 evidence package id，且内容版本一致。
- `kelly_readiness_report` 只用于说明风险预算，不替代 `risk_report`。

## AI 自动优化要求

AI 自动优化必须遵守以下规则：

1. 所有 trial 都必须记录。
   - 包括失败 trial、被拒绝 trial、短周期 trial 和人工终止 trial。
   - 不能只保留最终最优参数。
2. trial 记录必须能回溯到对应的输入、目标、评估窗口和输出。
3. 一旦 OOS 结果被锁定，参数不得回调。
   - 不得因为后续主观判断、单点波动或临时偏好回改已锁定参数。
   - 如需新参数，只能走新的 trial / 新证据包。
4. AI 优化结论不能直接跳过 live_ready 门槛。

## 插件自动化门槛

当插件声明 `position_control_allowed=true` 时，必须同时满足：

- 绑定一个有效的 `evidence_package_id`
- 明确有效期（start / end 或等价期限字段）
- 输出 `bounded budget`，且该预算是可审计、可验证、可拒绝的

补充要求：

- `position_control_allowed=true` 只允许在该证据包有效期内生效。
- 证据包失效、过期或被替换后，自动仓位权限应失效。
- `bounded budget` 不能写成无限、隐式默认值或仅口头约定。

## 晋级顺序

推荐顺序如下：

1. 研究完成
2. 证据包齐全
3. `live_ready` 通过
4. 插件门槛通过
5. 自动化放行
6. 如需更高风险预算，再单独评估 `kelly_ready`

## 最小检查清单

- [ ] `live_ready` 已通过
- [ ] `kelly_ready` 仅作为上限，不作为晋级依据
- [ ] evidence package 文件齐全
- [ ] 所有 AI trial 已记录
- [ ] OOS 锁定后无参数回调
- [ ] `position_control_allowed=true` 已绑定 `evidence_package_id`
- [ ] 证据包有效期明确
- [ ] `bounded budget` 已输出且可审计

## `strategy_evidence_package.v2` 晋级证据门

晋级重跑必须由 producer 生成新的 `strategy_evidence_package.v2`；v1/alias 只保留研究与监控兼容，不自动迁移成 v2。v2 必须同时绑定：

- strategy/source revision、input provenance/license/range/timestamp/manifest digest；
- `BacktestOrchestrator` 的 `purged_walk_forward.v1` 输出、至少 3 个有序 folds、正数 purge/embargo，以及锁定且独立的至少 12 个日历月 OOS；
- calendar/timezone/signal/execution timing、config/data-manifest/backtest/risk/IC/cost artifacts 及其实际 bytes/SHA-256；
- 上述全部风险指标及 `information_coefficient`。所有 metric/cost 必须存在、非 bool 且有限，cost/risk 状态必须为 `PASS`；
- human acceptance 的 decision/id/actor/time/authority-receipt SHA-256，并以 evidence-core SHA-256 绑定当前证据。

机器只判断结构、身份、有限性、日期、digest 与 PASS 状态；本文未冻结 Sharpe、return、MDD 或 IC 数值阈值，指标质量仍由绑定的人类 promotion acceptance 判断。

本 v2 门只产生研究晋级资格，不产生 paper/shadow/live 权限：`live_ready=false`、`size_zero_required=true`、`no_order=true` 始终成立。`requested_stage`、CI、PR、review、health 或 notification 不能改变这些真值；legacy/v2 live 或 runtime 请求都必须 `HOLD`。

本门完成也不改变 P3 的 `TERMINALLY_PARKED_NO_MEMBER` 状态。
