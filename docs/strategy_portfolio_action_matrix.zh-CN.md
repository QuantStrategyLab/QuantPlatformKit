# 策略组合行动矩阵

[English](./strategy_portfolio_action_matrix.md)

这份文档把当前跨仓库 review 结果整理成可执行方案。它以现有仓库状态为准，
把结论分成：

- 继续调参
- 重构 / 重设
- 降级 / 废弃
- 值得新增的方向

## 判定规则

- 如果 profile 仍然是 `runtime_enabled`，而且证据清楚，就继续调参。
- 如果策略思路有价值，但形态不对，就保留思路、重构 wrapper / orchestrator。
- 如果某条线明显弱于主 live 线，就降级到 `shadow_candidate`、
  `research_backtest_only`，或者直接归档。
- 如果某个市场还没有合适的 live 候选，就优先改架构，不要继续堆变体。

## 跨市场矩阵

| 市场 | 继续调参 | 重构 / 重设 | 降级 / 废弃 | 值得测试的新方向 |
| --- | --- | --- | --- | --- |
| 美股 | `global_etf_rotation`、`tqqq_growth_income`、`soxl_soxx_trend_income`、`russell_top50_leader_rotation`、各 DCA 线 | `us_equity_combo`、`us_equity_combo_leveraged` 更适合作为 shadow / orchestrator 层，而不是 live profile | `tecl_xlk_trend_income` 保持 research-only | LEAPS 增强层可以继续研究，但必须单独门控 |
| 港股 | `hk_global_etf_tactical_rotation`、`hk_low_vol_dividend_quality_snapshot` | `hk_equity_combo` 应该是 research/orchestration wrapper，不应当是 live profile | 任何 combo 型 live 推进都应先阻断，直到证据补齐 | 只有核心线稳定后，才考虑独立的因子增强 wrapper |
| A 股 | `cn_industry_etf_rotation`、`cn_industry_etf_rotation_aggressive` | `cn_equity_combo` 应重做成 orchestrator / dual-track composition，而不是直接 live profile | `cn_index_etf_tactical_rotation` 保持 legacy / research；`cn_chinext_tactical_rotation` 和 `cn_chinext_growth_momentum_quality_snapshot` 应重设计，不是简单废弃 | `cn_dual_track_combo`、独立的创业板成长 sleeve、以及独立的科创板成长 sleeve |
| 加密 | `crypto_live_pool_rotation`、`crypto_btc_dca` | `crypto_trend_rotation`、`crypto_equity_combo` 需要重构后再谈 live | 其余非 live crypto profile 保持 research/shadow，直到证据充分 | 先加波动率 regime 过滤或 stablecoin 资金投放层，再考虑更多轮动变体 |

## 各市场解释

### 美股

美股已经有较强的主 live 线，重点不是再加 live 变体，而是分层更清楚：

- 主 live 线继续稳定
- combo 逻辑保留为 shadow / orchestrator
- TECL 这类弱线继续退场

### 港股

港股应该保持窄而稳：

- 保留 ETF 轮动和 snapshot 红利质量线
- combo 只做 research wrapper
- 在证据缺口补齐前，不要扩 live 面

### A 股

A 股还有改进空间，但当前最强路径仍然是：

- 一条直接 ETF 轮动主线
- 一条受控的 aggressive 变体
- 一条未来可组合的 orchestrator / dual-track 线

创业板和科创板不应当被当成可随手丢弃的研究分支；它们是板块级
成长 sleeve，设计必须贴合真实市场 regime。

combo 现在不该和主 live 线争位置，应该先重做成 composition engine。

### 加密

加密是 regime 切换最快的域，所以 live 门槛要更严格：

- 保持 live pool rotation 作为主 runtime 策略
- 保持 BTC DCA 作为简单、可调的积累线
- trend 和 combo 变体先重构，再谈 live

## 插件和门槛含义

- `notification_only` 适合监控和研究可见性
- `automation_candidate` 适合 shadow 和 pre-live 验证
- 旧 `automation_approved + position_control_allowed` 插件元数据只用于回放；
  自动仓位影响必须由归属策略候选生成，并通过中央 Risk Gate
- AI monitored 不等于 live enabled

## 推荐的下一步

1. 先稳住当前 live 主线
2. 把 combo / orchestrator 做成真正的 composition，而不是复制主线
3. 新策略只在能补齐真实缺口时再加
4. 用证据包晋级，不用临时特批

## 参考策略家族

和这份矩阵最吻合的外部研究主要还是：

- 时间序列动量 / 趋势跟随
- 因子投资：质量、动量、低波动、股息收益
- 多资产 value + momentum overlay

官方参考：

- AQR Trends Everywhere
- AQR Value and Momentum Everywhere
- Kenneth French Data Library
- MSCI Factor Indexes
- EDHEC 趋势跟随研究
