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
