# 窗口指标口径（`compute_window_metrics`，qpk.window_metrics.v2）

适用：`quant_platform_kit.strategy_lifecycle.performance_metrics.compute_window_metrics` / `compute_windows` 产出的 `WindowPerformance`。背景见 [#659](https://github.com/QuantStrategyLab/QuantPlatformKit/issues/659)。

v2 **只新增字段**。在相同输入、默认参数下，v1 已有字段（`volatility`、`sharpe_ratio`、`win_rate`、`profit_factor`、基准各项等）数值逐位不变（`tests/test_lifecycle_metrics_semantics_v2.py::LegacyFieldRegressionTest`）。由该函数产出的记录带 `metric_semantics_version="qpk.window_metrics.v2"`；手工构造或旧快照反序列化的记录该字段为空串，新增字段为 `None`（`volatility_ddof` 为 0），表示"未声明"，不是 0。

## 1. 波动率与 Sharpe 的 ddof

| 位置 | 标准差 | 年化 |
| --- | --- | --- |
| `compute_window_metrics`（默认） | 总体标准差 `ddof=0` | ×√`periods_per_year` |
| `compute_window_metrics(volatility_ddof=1)` | 样本标准差 `ddof=1` | ×√`periods_per_year` |
| `research_stats.sharpe_inference`（PSR/DSR） | 样本标准差 `ddof=1` | 不年化（单期） |

- 两者只差 Bessel 因子：`Sharpe_ddof0 = Sharpe_ddof1 × √(n/(n−1))`；n=21 时约 +2.5%，n=126 约 +0.4%，n=252 约 +0.2%。
- 默认值保持 0：既有快照、`compare_with_backtest` 的 `sharpe_deviation` / `volatility_deviation_pct` 阈值与回测基线都按 ddof=0 记录，静默改默认会制造伪漂移。
- 实际使用的值写在 `volatility_ddof` 字段里。只接受 0 或 1，其它值抛 `ValueError`。
- Sortino（全样本下行 RMS）、beta（总体协方差）、信息比率（总体标准差）不受该参数影响。
- 跨口径比较 Sharpe 时，先统一 ddof：要么传 `volatility_ddof=1`，要么按上式换算。

## 2. 胜率与盈亏比（日级，不是逐笔）

这里的 `profit_factor` 是盈利因子（盈利总和/亏损总和），不是平均盈亏比（平均盈利/平均亏损）。窗口对象仍未单列平均盈亏比；研究侧 B3 可选单期诊断和完整能力目录见[统一量化指标](unified-metric-catalog.zh-CN.md)。

| 字段 | 定义 | 零收益日 |
| --- | --- | --- |
| `win_rate`（v1，不变） | 正收益日数 / 全部交易日数 | 计入分母（算作"非胜"） |
| `daily_win_rate_ex_zero`（v2 新增） | 正收益日数 / (正 + 负收益日数) | 排除；全为零时为 `None` |
| `zero_return_days`（v2 新增） | 收益恰为 0 的交易日数 | — |
| `profit_factor`（v1，不变） | 正日收益之和 / \|负日收益之和\| | 不影响；无亏损日时为 `None` |

- `daily_win_rate_ex_zero` 与 `position_sizing.estimate_kelly` 的 `win_rate` 定义一致（测试 `test_ex_zero_rate_matches_estimate_kelly_definition`）。
- 空仓/持现金的策略零收益日多，`win_rate` 会被系统性压低；比较不同持仓率的策略时用 `daily_win_rate_ex_zero` 并同时报告 `zero_return_days`。
- `compare_with_backtest` 的 `win_rate_deviation_pct` 仍比较 v1 `win_rate`，回测基线必须用同一日级口径。
- **逐笔交易胜率 / 盈亏比**需要成对开平仓记录，本函数的输入只有日收益，因此不计算、也不得从日收益推断。需要时应另建以交易记录为输入的函数，并单独命名。

## 3. 基准对齐报告

基准比较仍只使用策略窗口与基准共同的日期（内连接）。v2 新增三个计数，未提供基准时均为 `None`：

| 字段 | 含义 |
| --- | --- |
| `benchmark_aligned_days` | 参与基准比较的共同日期数 |
| `benchmark_dropped_strategy_days` | 窗口内有策略收益、无基准收益的日期数 |
| `benchmark_dropped_benchmark_days` | `[start_date, end_date]` 内有基准收益、无策略收益的日期数（窗口外的基准历史不算"丢弃"） |

报告基准相关指标时应同时给出 `benchmark_aligned_days`；任一 dropped 计数大于 0 时，说明基准 CAGR / alpha / IR 基于的天数少于 `observation_count`。是否据此判为"不可比"由调用方预先登记，本模块不设阈值。

## 4. 离线复利研究的统一净指标（qpk.net_compounding.v1）

研究侧 `research_stats.unified_report.build_unified_net_report(..., periods_per_year=P)` 显式选择年化基数后，在原报告末尾增加 `net_cagr` 和 `net_calmar_ratio`，不改生命周期监控函数或默认报告。原 `max_drawdown` 继续使用非正的带符号值。该入口只接受调用方提供的完整、同频、同窗口净简单收益，不读取行情、账户或文件。

- `n` 是真实收益观察数，包含真实零收益观察；初始 NAV=1 不是额外一日。调用方须去掉仅为初始状态占位的零，不能删掉真实空仓/持现金的零收益日。
- `L=sum(log1p(r_t))`，每观察净 log 增长为 `L/n`，几何 CAGR 为 `expm1(P*L/n)`；不使用算术均值乘 P，不对每年 CAGR 再算术平均。日线股票本次规范采用 P=252，其他频率不得混用。净收益须已包含同路径实际成本、现金收益和资金流调整；原始现金流不当成投资收益。
- `W_0=1, W_t=product(1+r_i)`；峰值包含 W_0，带符号 MDD=`min(W_t/max(W_0..W_t)-1)`，损失幅度为 `abs(MDD)`。CAGR 与 MDD 必须来自完全相同的净路径和窗口。
- Calmar=`net_cagr/abs(MDD)`；CAGR 为负时保留负比率。MDD=0 时为 `null/UNCOMPUTABLE/zero_drawdown`，不能使用无穷大或据此自动通过门槛。空、缺失、非有限、r≤-1 输入拒绝；数值溢出为不可计算，不以 0 代替。
- 本次复利比较要求策略与基准的 sessions 完全相同；不接受静默 inner join。现有 v2 生命周期指标的显式丢弃诊断保留，不静默修改已有监控行为。周期 outcome 继续不是逐笔交易成绩；Q06 的费用/FX/完整闭合交易事实仍缺。

这是 REPORT_ONLY 的计算定义，不添加统一晋级阈值。候选的 CAGR/Calmar/MDD 报告、排序、否决角色及比较符、阈值、净成本情景和不可计算处理仍须在查看 holdout 前冻结。缺冻结包时不宣布 PASS；CI 不是研究优势或交易授权。
