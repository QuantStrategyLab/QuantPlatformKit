# 跨资产主线接入计划

此前生命周期矩阵主要覆盖美股策略。本清单补上中国股票、港股和加密策略的统一入口，但它是 inventory，不把各仓库已有的 `runtime_enabled` 字样误当成完整 P0-P6 证据。

接入顺序：

1. 将各仓库 catalog 导出到统一 inventory。
2. 为每个策略绑定 owner、数据 manifest、evidence package 和 RiskSnapshot。
3. 先接入 research/shadow，每日记录运行结果。
4. 再按策略自身证据推进 P4/P5。
5. live 权限继续由原有 broker gate 控制，自动系统不能扩大权限。

当前覆盖：CN equity 8 条、HK equity 3 条、crypto 5 条；详见
`docs/registry/cross_asset_strategy_inventory.json`。

P1–P3 生产者统一写出 `research_driver_terminal.v1`，包括正常、等待和失败
分支；具体字段、终态推导和 no-order 边界见
[`cross_asset_research_driver.zh-CN.md`](cross_asset_research_driver.zh-CN.md)。
