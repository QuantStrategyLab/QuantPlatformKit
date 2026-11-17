# B3：统一净收益研究报告

状态为 **DEVELOPMENT_ONLY**。该补丁以 A3 PR #662 的 `f6d9736f` 为基础，
PR 的比较目标应为 `claude/a3-qpk`，避免重复提交 A3 的改动。
模块只计算离线报告，不更改生产消费者、依赖 pin、阈值、账本或预算。
`live_ready=False`、`no_order=True` 是校验过的固定边界。

现有 `BacktestReportV1` 是报告数据结构，未统一计算下列指标；本模块
通过 `metric_entries(scenario_multiplier=...)` 生成其既有 `MetricEntry`，
保留原 schema 和读写合同。单独的 `to_dict()` 仅是标明版本的研究摘要，
不是完整的 `qsl.backtest_report.v1`，也不能替代数据 manifest、预注册、
walk-forward、授权或验收记录。

## 输入与缺失值

```python
from quant_platform_kit.research_stats.unified_report import (
    TrialEvidence, build_unified_net_report,
)

# 仅合成输入；零成本显式给出 gross == net，并不代表真实摩擦覆盖。
net = (0.01, -0.012, 0.01) * 20
report = build_unified_net_report(net, gross_returns=net)
assert report.live_ready is False and report.no_order is True
# 没有累计试验证据，DSR 明确 UNCOMPUTABLE，不把缺失值填成零。
assert report.metric("deflated_sharpe_ratio").value is None
```

净收益序列须为相同频率的有限简单收益，严格大于 -1，不能为空；不进行
补零、丢行、日期相交、年化或隐式扣费。输入无效抛 `ResearchInputError`。
调用者须确保日历、窗口、现金/公司行动和成本口径一致。
本 API 没有 cadence/date 字段，不能自动检测混入周频或年化 Sharpe。
调用者必须在外层数据 manifest / `TimingSpec` 中明确原始频率，给定的
Sharpe 基准和所有累计试验 Sharpe 必须为该同一原始频率、未年化数值；
不能把年化 Sharpe 或另一个频率的试验方差直接传入。
可选 gross 必须与 net 逐项对应、长度相同，且 gross >= net；成本是
同一路径的非负扣减。不同持仓路径不能解释为此处的成本拖累。

唯一的数值例外为浮点舍入：`(1+0.1)-1` 得到
`0.10000000000000009`，比原 gross 略大。每对输入只允许
`net-gross <= 4*ulp(1+gross)` 的微小逆差，
其中财富因子 `1+gross` 的 ULP 覆盖近零收益的减法消去误差。
接近 -1 时不使用收益本身的 ULP 放宽边界，避免宽容相对剩余财富很大的逆差。
越过该界或实质负成本仍拒绝。原 net 输入完全保留用于增长/风险；
只有这些容许的微负对数成本项归零。成本指标 details 记录明确 ULP
规则、归零项数及最大逆差，不把该例外当成负成本或返佣模型。

统计样本不足、零方差、缺少 gross 或试验证据、数值不可计算时，指标
为 `UNCOMPUTABLE`、`value=None`，保留具体原因。其他可计算的描述指标
仍保留。默认推断结构下限 30 个观察，可显式指定 >= 3；这不是通过阈值。

## 指标定义

| 输出名称 | 定义 / 单位 |
| --- | --- |
| `net_log_growth_per_period` | `sum(log1p(net))/n`，每观察期净对数增长 |
| `sharpe_per_period` | 净收益均值 / 样本标准差，`ddof=1`，不年化 |
| `probabilistic_sharpe_ratio` | 复用既有 PSR，默认每期 Sharpe 基准 0 |
| `deflated_sharpe_ratio` | 累计试验预期最大 Sharpe 为基准的 PSR |
| `minimum_track_record_periods` | 同一 PSR 矩估计下达到给定置信度的最小观察期数 |
| `cvar95_return_per_period` | 经验最差 5% **概率质量**的平均净收益，负数表示损失 |
| `max_drawdown` | 含初始 NAV=1 的净收益复利路径最大回撤，负数表示损失 |
| `cost_log_drag_per_period` | `sum(log1p(gross)-log1p(net))/n`，每期对数成本拖累 |

回撤使用对数 NAV 累积以避免大收益连乘溢出，初始峰值为 0。
同一频率与 `ddof=1` 与 A3 的显式研究口径一致；未改变历史窗口指标的
默认 `ddof=0` 或旧快照字段。净收益的 rf/MAR 扣除（若需）由调用者先做，
Sharpe 基准、累计试验 Sharpe 和 PSR 必须使用同一收益/频率口径。

### 累计试验与 DSR

`TrialEvidence(cumulative_total, sharpe_variance, ledger_sha256)` 接受调用者
提供的累计汇总：总数包含失败/拒绝试验，方差为全部累计试验的同频率、
净成本 Sharpe 的样本方差 `ddof=1`，digest 为其来源账本 SHA-256。
总数只接受正整数，方差只接受有限非负值，digest 为 64 位小写十六进制。
小于两次试验或零方差不可计算；接口没有下调“有效试验数”的参数。

模块不读取、更新或验证真实账本。digest 仅标识调用者声明的来源，不能
证明汇总完整或真实，结果显式记录 `caller_supplied_not_attested`。
所有失败/拒绝试验的计数与同频率方差仍需外部独立审计。不是用本次调用
次数、当前批次或历史报告中的“48”替代真实累计计数。

### MinTRL

复用已有 PSR 的每期 Sharpe、偏度和非超额峰度。令
`V = 1 - skew*SR + (kurtosis-1)*SR²/4`，在 `SR > SR*` 时计算
`ceil(1 + V*(Phi^-1(confidence)/(SR-SR*))²)`，同时保留默认结构下限。
置信度只接受 `(0.5, 1)`；不足样本、零方差、Sharpe 不超过基准或无法
表示的结果均给出原因与 None，不把无限等待写成 0。

这是 **独立、平稳、前四矩有限** 的渐近 PSR 近似，不处理序列相关、
非平稳或无限矩，也不是已批准的生产晋级标准。单位为输入观察期；
日频输入才对应日数。它衡量超过给定 Sharpe 基准的样本长度，不替代
累计试验校正或 stationary bootstrap。

已联网核对作者公开原论文 Bailey、López de Prado (2012)，
[*The Sharpe Ratio Efficient Frontier*](https://www.davidhbailey.com/dhbpapers/sharpe-frontier.pdf)，
July 2012 版本：第 9 页式 (11) 给出 PSR，第 11 页式 (13) 给出 MinTRL；
第 9 页正文与脚注 5 要求原始采样频率的未年化 Sharpe，第 11 页说明
观察数单位与渐近样本条件。上述公式与这两个原式一致；本模块额外进行
向上取整与结构下限处理。论文也讨论更一般平稳遍历条件，但本模块没有
验证此类扩展或推断输入的序列相关性，因此报告保留较窄的独立平稳假设。

### CVaR95 的小样本与并列值

排序后每个观察有质量 `1/n`，精确积分最差 0.05 的质量。
尾部观察质量为 `0.05*n`；完整观察权重 1，边界观察使用剩余分数权重。
例如 n=21 时，最差观察权重 1、次差观察权重 .05，再除以 1.05。
n<20 时整个尾部落在最差观察，结果等于最差值；并列边界值不改变均值。
这是描述性经验尾部，小样本不提供总体尾部精度或风险保证。全部为正收益
时 CVaR 可为正，不能据此提高预算；本模块没有任何预算输出或执行路径。

## 验证

```sh
PYTHONPATH=src python -m unittest discover -s tests -p test_unified_net_report.py -v
PYTHONPATH=src python -m unittest discover -s tests -v
PYTHONPATH=src python -m pytest -q tests/test_unified_net_report.py tests/test_research_stats_import_boundary.py
ruff check src/quant_platform_kit/research_stats/unified_report.py tests/test_unified_net_report.py
```

合成验收覆盖解析增长/成本/回撤/样本 Sharpe、初始 NAV、分数尾质量、
小样本与并列、累计试验增加时 DSR 降低、MinTRL 与相同 PSR 的反解、
缺失/坏输入/溢出和禁止 live permit。没有真实收益、账户数据或市场调用。
