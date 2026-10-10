# 策略晋级与风险标准

本文定义策略晋级、插件自动化、AI 自动优化和 Kelly readiness 的统一门槛。

研究回测的报告内容、成本、时点、数据身份与最小观察约定见 [QSL 回测标准 v1](backtest_standard_v1.zh-CN.md)（工具：`research_stats`，模板：`qsl.backtest_report.v1`）；该标准不设数值及格线。

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

## 统一评价口径与分类验收

本节对齐现有研究和风险评估文档，不修改指标实现、证据 schema、冻结候选、
数值阈值或运行权限。当前机器门仍按下文 v2/v3 的实际校验范围工作；文档
齐全不表示 producer 已采用共同口径或真实验证已完成。

### 共同指标口径

新候选在既有配置、风险报告和验收文档中记录以下口径，并绑定实际 producer
源码与消费者依赖版本。不向封闭 schema 临时增字段，也不重写旧证据或沿用
语义改变前的 acceptance。尚未接入的口径明确列为待接入。

| 核对项 | 共同声明 |
| --- | --- |
| 样本和期望 | 区分账户/策略日净值收益、资产收益、逐笔交易收益及情景终值；声明简单/对数收益、观察数、有效样本、暖机/零收益处理与交易配对规则。历史日均值、每笔净 expectancy 和期望对数增长分别命名，不把正收益日比例当交易胜率 |
| 时间和估值 | 声明币种、估值时点、日历/时区、信号可知截止、执行时点、窗口与基准；同一比较使用一致的日期/现金流处理和可比经济起点，缺失日期不能靠补零或静默取交集修饰 |
| 成本和现金 | 区分毛/净收益；记录佣金、滑点、冲击、融资等适用成本及来源/假设，现金收益、股息、FX 与外部资金流的处理。适用项缺证据不能默认为已覆盖，同一成本/公司行为不重复扣计 |
| 年化和统计 | 显式记录 rf/MAR、频率与年化基数、日历年或观察数口径、方差自由度及 benchmark 对齐方法；rf=0 是声明的基准假设，不等于实际无融资/机会成本。相同名字不掩盖不同公式或单位 |
| 尾部和回撤 | 声明 VaR/ES/CVaR 的尾部比例、符号、分位数/并列值处理与尾部观察数；回撤含初始净值，恢复时长说明会话单位及未恢复截尾。经验尾部和重采样路径不是总体风险保证 |
| 不可计算和不确定性 | 区分实际零值、无定义、样本不足和不适用并保留原因。现有 NaN/None/有限零 sentinel 的差异按 producer 如实披露，不把 sentinel 当估计值；当前 schema 不接受的缺值仍不能填好看数值过门 |

同窗比较先核上述口径可比，再比较表现；不能把资产收益协方差、策略净收益、
交易 expectancy 和情景增长分数互换。样本有序列依赖时，报告使用了什么
不确定性方法及其限制；普通年化 Sharpe 或 block bootstrap 不自动构成
自相关校正、独立 OOS 或多重试验校正。PBO/DSR 等未计算时保留原未计算
状态，不能仅凭报告字段或算法说明宣称实现。

### 报告 排序 否决分别登记

- **报告项**说明已计算值、样本与限制，不因字段存在或数值有限而通过。
- **排序项**在看候选结果前明确主目标、比较对象、排序/并列规则；现有启发式
  score 只按其原研究用途解释，不升级成全系统万能分数。
- **否决项**在读取留出结果前冻结适用指标、比较符、阈值、窗口、成本压力、
  不可计算处理和失败处置，并由当前候选版本及 human acceptance 绑定。
  必需证据缺失、无效或未验收不能由其他指标较好抵消。

同一指标可以承担多种角色，但每个角色须明确。AI 生成或优化的候选复用
同一口径与验收，不另设宽松通道；展示层读取 producer 的结果和角色，不
重复计算金融指标或把结构性 PASS 显示成策略经济有效。

### 分类验收与独立组合风险

统一的是数据、计算语义、证据和冻结流程，不是把所有策略套入同一个 Sharpe
或 MDD 数字。趋势、均值回归、现金防守、杠杆 ETF 等类别在既有候选文档中
先声明目标、适用基准、主比较与成本/风险门槛；不借其他类别阈值自动授权。
开发、选参、独立 OOS 与后续观察各自保留身份，已见数据不改名为未触碰 OOS。

Markowitz、fractional Kelly 与经验 log-growth 属于组合分配/风控分析的
不同方法，不作为单策略评分项相加。其共同账户约束、同窗净成本比较和
实现边界由 [UES 组合风险预算研究契约](https://github.com/QuantStrategyLab/UsEquityStrategies/blob/main/docs/research/portfolio_risk_budget_contract.md)
记录；QPK Kelly 单位与现有限制沿用
[Kelly 契约](kelly_contract_v2.zh-CN.md)。任何研究最优解或正增长估计都不能
覆盖独立的杠杆、集中度、流动性、回撤/熔断约束与 RiskEngine 最终否决。

本次文档对齐归入已有 `STRAT-02`（策略评估）、`STRAT-04`（组合证据）
与 `STRAT-05`（风险/Kelly 边界），不新增任务 ID，也不关闭真实验证缺口。

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

### Drift reopt 到 shadow 的绑定

`run_research_promotion_cycle` 在预算检查通过后、记录 shadow 前，必须调用
`enforce_promotion_backtest_gates`。调用方注入以下任一结果：

- `BacktestOrchestrator.run_promotion` 返回的 `PromotionBacktestRun`；或
- 显式摘要：`status=PASS`，并复用 evidence package `backtest` 字段的
  `BacktestOrchestrator`、`purged_walk_forward.v1`、≥3 个有序 folds、
  正数 purge/embargo，以及锁定、独立且未用于选参的 ≥12 日历月 OOS。

缺少回调、缺字段、状态非 `PASS`、身份不匹配或回调异常均 fail-closed：
ticket 进入 `PARKED`，且不会调用 shadow。该门只确认严格回测证据，不授予
paper/shadow/live 权限。

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

晋级重跑必须由 producer 生成新的显式版本证据包（v2 或下述 v3）；v1/alias 只保留研究与监控兼容，不自动迁移成新版。v2 必须同时绑定：

- strategy/source revision、input provenance/license/range/timestamp/manifest digest；
- `BacktestOrchestrator` 的 `purged_walk_forward.v1` 输出、至少 3 个有序 folds、正数 purge/embargo，以及锁定且独立的至少 12 个日历月 OOS；
- calendar/timezone/signal/execution timing、config/data-manifest/backtest/risk/IC/cost artifacts 及其实际 bytes/SHA-256；
- 上述全部风险指标及 `information_coefficient`。所有 metric/cost 必须存在、非 bool 且有限，cost/risk 状态必须为 `PASS`；
- human acceptance 的 decision/id/actor/time/authority-receipt SHA-256，并以 evidence-core SHA-256 绑定当前证据。

机器只判断结构、身份、有限性、日期、digest 与 PASS 状态；本文未冻结 Sharpe、return、MDD 或 IC 数值阈值，指标质量仍由绑定的人类 promotion acceptance 判断。

本 v2 门只产生研究晋级资格，不产生 paper/shadow/live 权限：`live_ready=false`、`size_zero_required=true`、`no_order=true` 始终成立。`requested_stage`、CI、PR、review、health 或 notification 不能改变这些真值；legacy/v2 live 或 runtime 请求都必须 `HOLD`。

本门完成也不改变 P3 的 `TERMINALLY_PARKED_NO_MEMBER` 状态。

### v3：仅修订 IC 的适用性表达

`strategy_evidence_package.v3` 只改变 `metrics.information_coefficient`：

- 已计算：`{"status":"computed","value":-0.2}`。value 必须为非 bool 的有限数值，范围 [-1, 1]；负值合法，不新增正 IC 晋级阈值。
- 不适用：`{"status":"not_applicable","reason_code":"no_prediction_target","reason":"固定 producer 未定义预测目标及未来标签"}`。必须给出非空原因，不允许 value（包括 null）或额外字段。

预测 IC 衡量决策时已可用的预测分数与随后实现的对应标签之间的相关性；报告必须说明预测目标、标签区间、对齐时点和计算方法。策略收益与同期基准收益的相关性只能称为基准收益相关性，不能替代预测 IC。

不适用声明只能来自已核对的固定 producer 设计，不能由 CLI 开关或调用者临时豁免。已有预测定义但缺样本、缺标签、常量导致不可计算，或计算失败，均不是 `no_prediction_target`；不得转成 N/A、零或好看数值生成合格 IC。当前 SOXL 路线仅在 producer 定向采用后表达该声明，不凭本契约认定任何已有候选已迁移。

沿用现有 IC report artifact、artifact digest、evidence core 和 human acceptance：report 保存同一声明及实际统计指标，未改变的风险、成本、OOS 和人工验收要求继续适用。语义改变后的新 core 不得沿用旧 acceptance。机器仅验证类型、结构和绑定，不能证明预测金融正确性、任意源码没有预测目标，或鉴定任意 caller 的声明；本次不新增 receipt verifier 或人工门。

v2 schema、常量与 `validate_evidence_package_v2` 的有限数字语义保持不变，v3 经现有 dispatcher 验证；旧入口拒绝新包。v3 packaged schema 引用同包 v2 字段，离线消费者须从安装包注册这两个 schema，不能依赖网络解析。旧 artifact 只读保留，不转换、覆盖或继承验收。无人工验收仍为 `HUMAN_REQUIRED`，`live_ready=false`、`size_zero_required=true`、`no_order=true` 不变，live/runtime 请求仍 HOLD。本契约与 CI 不授权真实数据重跑或运行采用。
