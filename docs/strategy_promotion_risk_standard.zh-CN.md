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
