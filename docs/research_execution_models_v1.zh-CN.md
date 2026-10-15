# 研究成交与成本口径 v1（A2）

`quant_platform_kit.research_stats.execution_models` 提供标准库纯函数接口，
不会读取账户、报价、文件或配置，也不会调用券商。现有回测入口不自动迁移。

`FillModel(timing).resolve(signal_index=..., available_index=..., bar_count=...)`
返回 `FillPoint(index, price_field, timing)`，最后一个信号没有下一根 bar 时返回
`None`。索引由调用方的严格有序交易日历定义；可用时间不能晚于信号日收盘。

| timing | 成交约定 | 新持仓首次收益 |
| --- | --- | --- |
| same_close | 信号日收盘价；完成收盘后才得到信号，属于显式假设 | 下一交易日 |
| next_close | 下一交易日收盘价 | 再下一交易日 |
| next_open | 下一交易日开盘价 | 成交日开盘到收盘 |

不插值、不沿用缺失报价。调用方必须校验价格、交易日和公司行动。
原始未复权 OHLC 不能直接混入总回报序列。

`CostModel(commission_bps, slippage_bps, multiplier)` 按交易的证券金额计费，
买卖各计一边、现金腿免费。手续费和滑点都是每边 bps，两者相加后乘压力倍数。
`fraction(turnover)` 返回相对成交前 NAV 的成本。

`net_return(gross_return, turnover, charge_at="start")` 使用
`(1-cost)*(1+gross)-1`，与已有 `cost_stress_recompute` 位级兼容；
`charge_at="end"` 使用 `gross-cost`。调用方必须选择成本扣除时点，
不能在已有净收益上重复扣费，也不能把收盘成交成本推迟到区间外而遗漏。
模型不估计容量、冲击、税费、分红或借贷成本；本接口不授权真实数据实验或上线。

验证使用固定种子的合成数据，包括三种时点、未可用信号、终端未成交、
入场与退出费用、无效输入，以及 100 个样本与现有成本函数的位级差分。
