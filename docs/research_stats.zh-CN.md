# research_stats（RS-01，研究-only）

`quant_platform_kit.research_stats` 是回测证据的研究统计原语。它**不**读取账户、不调用券商、不下单、不写风险政策，也不授予 paper/shadow/live 权限。运行时、执行内核和通知模块不得 import 它（`tests/test_research_stats_import_boundary.py` 强制）。

安装：`pip install 'quant-platform-kit[research]'`。numpy/pandas 只在 `research` extra（以及原有 `dev` extra）里，核心 `dependencies` 仍为空。PSR/DSR 与成本压力只用标准库；只有 bootstrap 延迟 import numpy。

本模块与测试只使用合成数据，不包含任何真实回测数字。

## 组件

| 组件 | 函数 | 失败语义 |
| --- | --- | --- |
| 概率 Sharpe（PSR，Bailey & López de Prado 2012） | `probabilistic_sharpe_ratio(returns, sr_benchmark=0, min_observations=30)` | 样本不足、零方差、非有限、≤−1、bool → `UNCOMPUTABLE`，`value=None` |
| 去膨胀 Sharpe（DSR，2014） | `deflated_sharpe_ratio(returns, trial_sharpes, n_effective_trials=None)` | 试验数 < 2、有效试验数 > 已登记数、试验 Sharpe 方差为 0 → `UNCOMPUTABLE` |
| 期望最大 Sharpe | `expected_max_sharpe(variance, n_trials)` | 同上 |
| 平稳块自助法（Politis & Romano 1994） | `stationary_bootstrap_ci(returns, *, seed, mean_block_length, n_resamples=1000, confidence=0.95)` | seed 必填；块长 > 样本、重抽样 < 100 → `UNCOMPUTABLE`；某个统计量无定义时只有该项 `UNCOMPUTABLE` |
| 成本压力 | `cost_stress_recompute(gross, turnover, *, cost_bps_per_side, multipliers=(1,2,3))` | 长度不等、负换手、非有限、重复倍数 → `PARKED` |
| 报告模板 | `BacktestReportV1` + `schemas/backtest-report.v1.schema.json` | `live_ready=False`、`no_order=True` 恒定；非 COMPUTED 指标必须 `value=None` + `reason_code`；development 数据不得标 `OOS_EVALUATED` |

## 口径

- Sharpe 一律是**单期、未年化**（均值 / 样本标准差 ddof=1），rf/MAR 由调用方先扣。`trial_sharpes` 必须包括全部试验（含失败、拒绝），频率与 `returns` 一致。
- 偏度/峰度用总体矩估计，峰度为非超额（正态 = 3）。
- `min_observations=30` 只是沿用 Kelly 契约 v2 的结构下限，不是质量阈值。
- bootstrap 统计量：单期对数增长 `mean(log1p r)`、单期 Sharpe、含初始净值的最大回撤；百分位区间，不做自相关以外的校正，不构成未来风险保证，也不替代多重试验校正。
- 成本：`turnover[t]` = 期初买卖成交额合计 / 交易前净值，每单位成交额付 `cost_bps_per_side × 倍数`；`net = (1 − τ·c)(1 + gross) − 1`。半 L1 口径（现金腿不计费）须由调用方先换算。
- 报告模板只验结构与诚实性约束，不判断经济有效性，不设任何 Sharpe/回撤及格线；否决项阈值必须由候选在读取留出结果前冻结（`gates.veto_items[].frozen_at/frozen_by`）。

## 非目标

- 不修改 `strategy_lifecycle/performance_metrics.py` 等现有共享指标函数的语义。
- 不接入任何消费者，不升级任何下游 QPK pin，不改 `QPK_PIN`。
- PBO（CSCV）、与 UES trial journal 的接线留给后续 RS-02。
