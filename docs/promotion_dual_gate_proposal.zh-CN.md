# E1：运营 shadow 与统计优势双门槛提案

状态：**PROPOSAL / OWNER_APPROVAL_REQUIRED**。这是审计任务 E1 的待审批设计，
不是新的已生效晋级政策。只有文档改动；不执行 promotion、不改阈值、
预算、生产 pin、策略状态、数据窗口或真实试验账本。两个门槛都通过也只
允许提交人工验收，未取得绑定候选版本的批准不得自动晋级。

English scope: this proposal separates operational shadow correctness from
statistical edge. Neither gate grants execution authority; both passing only
permits owner review. It changes no runtime policy, allocation or trial ledger.

## 现有合同与本提案的区别

继续遵守[策略晋级与风险标准](strategy_promotion_risk_standard.zh-CN.md)：
`live_ready` 与 `kelly_ready` 分开，Kelly 只能收紧既有上限；样本不足、
身份不一致、证据缺失不能以零值代替，也不能变为交易资格。
[B3 统一净收益报告](unified_net_report.zh-CN.md) 固定
`live_ready=False`、`no_order=True`，报告指标不是授权。

本提案将 **252 个合格运营 shadow 日**作为拟议运营门槛，须由 owner
明确适用策略、交易日历、每日覆盖要求、缺失处理和版本变更重启规则后批准。
“252”不是 252 条历史收益、年化常数或自然日，也不能以回测补足。
本仓库现有[参数更新策略](../src/quant_platform_kit/strategy_lifecycle/update_policy.py)
默认 `min_shadow_days=5`、`max_shadow_days=10`；
[前向观察](../src/quant_platform_kit/strategy_lifecycle/forward_observation.py)
也不把 SOXL 的 252 个交易日统一施加于所有策略。这些行为均不变。
SOXL 的 252 个 XNYS 日非 live 前向窗口不能冒称已经执行的 broker paper
或运营 shadow。具体候选目前完成几天、获何授权，本提案均未判定。

## 门槛 O：运营正确性

运营观察须是预先批准的、隔离且不会触发真实订单的 shadow 路径。只做
离线报告、历史重放或监控心跳不能自动算合格 shadow 日。每日记录至少
绑定候选源码、运行 artifact、配置与风险摘要、依赖实际版本、目标身份、
日历及窗口；这些身份必须与被审查候选一致，不能仅使用浮动 branch/tag。

拟议验收项目：计划运行与覆盖完整；可用数据时点正确；目标/账户隔离；
配置和输出可复现；现金、公司行动、成本与估值对账；异常、恢复及重复
事件处理符合批准的非 live 方案；执行路径没有真实订单权限。owner 应
为每项定义可复核的证据和否决条件，而不是用“日志没有报错”代替。

合格日必须满足同一批准版本和完整覆盖要求。缺失、部分覆盖、时点不明
和回执未知不计合格日，保留原因；不能补零收益、伪造运行或跳过坏日。
候选代码/参数/成本/风险/部署身份发生变化时，先停止累计并重审变更。
是否全量重启观察由批准的变更规则决定；不得自行拼接不同版本的 252 天。
合格日总数只是运营条件，不能证明正收益或样本独立性。

## 门槛 S：统计优势

先冻结候选、评估角色和预注册方案，再评估独立的净成本样本。继续保留
既有 walk-forward、purge/embargo、独立锁定 OOS 及风险否决合同；这里的
PSR、DSR、MinTRL 不能替代这些要求，也不替代 stationary bootstrap/PBO。
不得为了过门槛重新挑选 holdout 或调整同一轮候选。

| 项目 | 拟议验收证据 | 不可判定时 |
| --- | --- | --- |
| PSR | 明确同频率、未年化 Sharpe 基准与 owner 批准的概率阈值 | `UNKNOWN`，不通过 |
| DSR | 累计全部成功、失败、拒绝及终止试验；独立核验累计数、同频率净 Sharpe 方差与账本摘要 | `UNKNOWN`，不能用当前批次或调用次数代替 |
| MinTRL | 相同 Sharpe 基准、置信度、频率及假设下，可用样本数达到要求的观察期数 | 无法计算或样本不足不通过 |
| 净增长和风险 | B3 的净对数增长、成本拖累、CVaR95、初始 NAV 回撤，及既有标准要求的其他风险证据 | 指标缺失不能填零；风险 veto 独立保留 |

PSR/DSR 的概率阈值、Sharpe 基准、成本压力、风险上限及 MinTRL 置信度
均须预注册并由 owner 批准；本提案不凭空设立通用通过数值。
B3 默认 MinTRL 置信度 0.95 和结构下限 30 是估计设置，不是已批准的
晋级门槛。B3 的 `caller_supplied_not_attested` 表示真实试验账本尚未由
模块核验，仅填写 digest 不足以通过 DSR 证据验收。

MinTRL 的单位是输入观察期。只有日频样本才可与统计观察日数比较，周频
MinTRL 不能直接拿 252 日抵扣。其独立、平稳、前四矩有限的渐近假设及
不能处理序列相关的限制见 B3 文档和作者原论文
[*The Sharpe Ratio Efficient Frontier*](https://www.davidhbailey.com/dhbpapers/sharpe-frontier.pdf)
第 9 页式 (11)、第 11 页式 (13)。假设无证据支持时须另行审定合适推断，
不能仅累计更多天数就称已解决。运营日志日数也不能冒充统计有效样本数。

## 独立决策与失败语义

下表的 O/S `PASS`、`FAIL`、`UNKNOWN` 是**拟议审查结果标签**，不是新
runtime schema、状态机或权限字段。

| O 运营门槛 | S 统计门槛 | 拟议处置 |
| --- | --- | --- |
| PASS | PASS | 提交绑定版本的人工验收；未批准仍不 promotion |
| PASS | FAIL / UNKNOWN | 运营正确不代表优势，候选保持不具备晋级资格 |
| FAIL / UNKNOWN | PASS | 收益证据不能掩盖运营问题，候选保持不具备晋级资格 |
| FAIL / UNKNOWN | FAIL / UNKNOWN | 修复或补证后按批准方案重新审查 |

验收包应分别记录两门槛的证据摘要、候选身份、评估方案版本、统计样本
窗口/频率、合格 shadow 日窗口/日历、缺失原因和独立验收人。批准记录
须绑定上述身份、有效期、目标及既有风险上限；过期、证据或身份变化
须重审。观察完成、CI 绿色、报告计算完成都不能自动修改 `live_ready`。

owner 后续需决定适用范围、252 合格日计数规则、统计阈值、独立核验职责
和批准合同，之后另开实现及验证 PR。本补丁不实测、不冻结真实 holdout、
不创建真实 trial、不修改现有 promotion 控制面或生产状态。
