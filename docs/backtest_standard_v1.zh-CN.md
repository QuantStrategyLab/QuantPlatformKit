# QSL 回测标准 v1（研究侧）

版本：v1（2026-10-10）。状态：研究标准，**仅文档**。

本文是 [策略晋级与风险标准](strategy_promotion_risk_standard.zh-CN.md) 的补充，规定研究回测「必须报告什么、怎么算、怎么标身份、最少要多少观察」。它不替代、不修改晋级标准的指标清单、`strategy_evidence_package.v2/v3` schema、`BacktestOrchestrator.run_promotion` 结构门或 [Kelly 契约](kelly_contract_v2.zh-CN.md)。

## 0. 边界

- **本文不设任何及格线。** 不存在全系统统一的 Sharpe、CAGR、回撤、DSR、PBO 或成本门槛。每个候选的报告项、排序项和否决项（含指标、比较符、阈值、窗口、成本档和不可计算处理）必须在读取留出结果**之前**由该候选预先登记，并经人工验收（human acceptance）后才生效。未登记或未验收的阈值不能用来宣称「通过」。
- 研究回测结果只产生研究证据：`live_ready=false`、`no_order=true`。不授予 paper/shadow/live 权限，不改变风险预算、平台 sizing 或 RiskEngine 否决。
- 合成数据只验证实现正确性，不是策略成绩。没有按本文第 6 节写明数据源、区间和身份的数字，不得出现在网站、日报、通知或 PR 描述里。

## 1. 工具与模板

| 用途 | 实现 |
| --- | --- |
| 概率 / 去膨胀 Sharpe（PSR / DSR） | `quant_platform_kit.research_stats.probabilistic_sharpe_ratio` / `deflated_sharpe_ratio` |
| 回测过拟合概率（PBO，CSCV） | `quant_platform_kit.research_stats.probability_of_backtest_overfitting` |
| 置信区间（平稳块自助法，固定 seed） | `quant_platform_kit.research_stats.stationary_bootstrap_ci` |
| 成本压力重算（默认 1×/2×/3×） | `quant_platform_kit.research_stats.cost_stress_recompute` |
| 报告模板 | `BacktestReportV1` + `schemas/backtest-report.v1.schema.json`（`qsl.backtest_report.v1`） |
| 共同指标（CAGR、波动、Sharpe、Sortino、Calmar、MDD 等） | `strategy_lifecycle.performance_metrics`（口径差异见 [#659](https://github.com/QuantStrategyLab/QuantPlatformKit/issues/659)） |
| 晋级结构门 | `BacktestOrchestrator.run_promotion`（`purged_walk_forward.v1`） |

函数口径和失败语义见 [research_stats 说明](research_stats.zh-CN.md)。所有工具在数据不足或无定义时返回 `UNCOMPUTABLE` / `PARKED` 且不给数字；**缺失不是 0**。

## 2. 必须报告的内容

除晋级标准已要求的 `risk.metrics.*` 外，研究回测报告还必须包含下表各项；不可计算时写明状态与原因，不能省略。

| 项 | 口径 | 默认角色 |
| --- | --- | --- |
| 期望对数增长 g | 单期 `mean(log(1+r))`，并注明年化方式与基数 | 报告；最大复利研究的主比较量 |
| CAGR、年化波动、MDD | 回撤含初始净值；注明 ddof 与年化基数 | 报告 |
| MDD 金额、最长回撤恢复期 | 恢复期以交易日计，未恢复按截尾注明 | 报告 |
| CVaR95（ES） | 注明尾部比例、符号、分位/并列处理与尾部观察数 | 报告 |
| PSR、DSR | DSR 的试验数必须覆盖**全部**试验（含失败、拒绝）；试验数不足即 `UNCOMPUTABLE` | 报告 |
| PBO | 全部试验在同一日期上的收益矩阵；块数与丢弃行数写入报告 | 报告 |
| 置信区间 | 至少 g、Sharpe、MDD；写明方法、块长、重抽样次数、seed、置信水平 | 报告 |
| 成本 | 换手、成本占毛收益比例、各成本档下的 g | 报告 |
| 基准对比 | 同日期、同成本口径的 g、MDD、超额 g、beta | 报告 |
| 交易级 | 交易数、逐笔胜率、逐笔 expectancy（不得与「正收益日比例」混称） | 报告 |
| 试验登记 | 总数、失败数、拒绝数、预先声明的选择规则、试验日志 SHA-256 | 必填 |

排序项和否决项只能从已登记的报告项中选择，并按第 0 节预先登记。同一指标可同时承担多种角色，但每个角色都要写明。

## 3. 成本模型

- 成本按**单边**计：每单位成交额支付「佣金 + 半价差 + 冲击」（bps）。现金腿是否计费必须写明；半 L1 口径要换算后再与其他研究比较。
- 至少报告三档成本情景；默认倍数为 1×/2×/3×（`cost_stress_recompute` 默认值）。基准档的 bps 取值及其来源由候选声明，不由本文规定。
- 小账户研究须声明是否整股取整、最小佣金或固定票费；卖出资金须按声明的结算规则（如 T+N 队列）才可再用。
- 杠杆 ETF 的费用率与衰减已含在价格中，不重复扣；融资/借券如适用单列。
- 同一成本不得扣两次；毛收益输入必须明确已含/未含哪些成本。
- 成本压力是否构成否决、在哪一档否决，由候选按第 0 节预先登记。
- 没有成本模型的回测（例如尚未补费用的加密研究回测）只能标为「未计成本」，不进入任何同窗比较。

## 4. 数据卫生与时点

1. 每份结果绑定 `data_manifest`：来源、许可、区间、生成时间、SHA-256。
2. **信号可知截止**：信号只用 `as_of` 及以前已可知的数据。
3. **成交时点**必须三选一并写入报告 `timing.execution`：
   - `next_open`：信号日收盘后，下一交易日开盘成交；
   - `next_close`：下一完成交易日收盘成交；
   - `same_close_research_only`：信号当日收盘价成交。只能作对照，**不得**用于晋级比较或与另两种口径的结果混比。
   同窗比较的候选必须使用相同成交时点；不同时点的结果不得直接比较。
4. 复权：价格类信号用拆分复权价；收益用总回报（股息再投或现金入账二选一并写明）。两种口径不得混用。
5. 公司行为按生效日记账；无法核实公告时点的，作为局限写入报告。
6. 成分股类策略必须使用时点成分（含已退市标的）；否则标 `SURVIVORSHIP_UNVERIFIED`，不得晋级。
7. 缺价不补 0、不前向填充收益；基准与策略日期不一致时报告不可计算，不静默取交集。
8. 日历（XNYS / XHKG / 24×7 等）与年化基数显式声明。

## 5. 样本外与前推（walk-forward）

- 晋级沿用 `purged_walk_forward.v1` 结构门：至少 3 个有序 fold、正的 purge/embargo、锁定且独立的至少 12 个日历月 OOS。本文不改该门。
- purge 至少覆盖信号最长回看窗口与持有/标签窗口；embargo 至少覆盖持有期。具体天数由候选声明并写入报告。
- 参数选择只能使用训练段；每折严格「估计 → 应用到下一段」，前推方式（anchored / rolling）事先声明。
- 锁定 OOS 只跑一次；跑完后参数不得回调，要改只能开新试验、新证据包。

### 数据身份

报告 `data.data_identity` 必须三选一：

| 身份 | 含义 |
| --- | --- |
| `development` | 已被看过或用于调参的区间。已多次复用的历史区间一律属于此类，不得改名为 OOS |
| `locked_oos` | 候选冻结后只运行一次的留出区间 |
| `forward` | 冻结后实时积累的影子/纸面观察 |

`development` 数据不得标为 `OOS_EVALUATED`（报告模板与 schema 均强制）。

## 6. 最小观察门

本文不新增数字门槛。下表只汇总**现有**约定；表中未列的评估目的，最小观察数由候选声明并人工验收。

| 评估目的 | 现有约定 | 来源 |
| --- | --- | --- |
| Kelly 风险份额估计 | 至少 30 个收益样本，正负两侧齐全，须有 MDD 观测 | [Kelly 契约 v2](kelly_contract_v2.zh-CN.md) |
| PSR / DSR 结构下限 | 默认 `min_observations=30`（沿用上行，仅为结构下限，不是质量阈值）；DSR 至少 2 个试验 | `research_stats` |
| PBO | 至少 2 个试验，每块至少 `min_rows_per_block` 行 | `research_stats` |
| 晋级用锁定 OOS | 至少 12 个日历月，至少 3 个 purged fold | `run_promotion` |
| 前瞻观察 | 由候选的 `ForwardObservationPolicy` 声明（例如 SOXL V7 为 252 个 XNYS 有效观察日并完成影子对比） | [前瞻观察契约](forward_observation_runtime_contract.zh-CN.md) |

达不到门槛时结果为 `PARKED` / `UNCOMPUTABLE`，不外推，不给建议仓位。

## 7. 报告模板与摘要

结构化结果使用 `qsl.backtest_report.v1`（`BacktestReportV1.to_dict()`，可用打包的 JSON Schema 校验）。模板强制：

- `live_ready=false`、`no_order=true`；
- 非 `COMPUTED` 指标必须 `value=null` 并给出 `reason_code`；
- 基准比较 `same_dates=true`；
- 每个指标的成本倍数必须在 `cost_model.scenario_multipliers` 中声明；
- 否决项记录 `frozen_at` 与 `frozen_by`。

人读摘要固定包含：数据源与区间、数据身份、成交时点、成本档、试验总数（含失败）、DSR/PBO 是否计算、置信区间方法、局限。缺任一项，该报告的数字不得对外引用。

## 8. 组合分配方法

最大复利（fractional Kelly / 带回撤约束的增长最优）与 Markowitz（均值–方差、最小方差、风险平价）属于组合分配研究，沿用 UES [组合风险预算研究契约](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/main/docs/research/portfolio_risk_budget_contract.md)。它们的结果必须：

- 在相同可执行约束、相同日期、相同成本口径下，与 1/N、固定权重和无杠杆基准对照；
- 用严格前推（训练段估计、下一段应用）评估，并按本文报告；
- 只作为研究建议，经 `portfolio_risk_budget` 得到 APPROVE / REDUCE / PARKED；不提高任何风险预算，不允许满凯利。

## 9. 已知缺口（登记，不在本文修复）

- 共享指标口径冲突：基准静默取交集、`win_rate` 实为正收益日比例、`profit_factor` 基于日收益 —— [#659](https://github.com/QuantStrategyLab/QuantPlatformKit/issues/659)。
- 各模拟器成交时点不一致（当日收盘 / 下一收盘 / 下一开盘）—— [UES #575](https://github.com/QuantStrategyLab/UsEquityStrategies/issues/575)。
- Binance 研究回测未计手续费与滑点 —— [BinancePlatform #366](https://github.com/QuantStrategyLab/BinancePlatform/issues/366)。
