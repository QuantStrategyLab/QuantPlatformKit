# 多源日线数据一致性关卡

`quant_platform_kit.data.multisource_assurance` 是所有市场、策略、平台与插件共用的纯校验层。它不联网、不存储行情、不访问券商，也不会替某个来源自动补数或改写数据。

每个行情适配器先独立产生一个不可变的 `DailyBarSourceSnapshot`：来源标识、标的、截止日期、复权口径、来源根哈希和完整 OHLCV 序列。适配器不可用时必须产生 `DailyBarSourceObservation(status="UNAVAILABLE")`，并仅记录稳定原因码，例如 `provider_auth_or_entitlement`；不得将原始报错、密钥或行情正文写入控制面。

调用方用 `MultiSourceDailyBarPolicy` 明确指定：

- 哪些来源必须存在，且至少两个独立来源；
- 标的、日线截止日期和复权口径；
- OHLC 与成交量允许的相对偏差。

`assess_multisource_daily_bars` 只会产生三种结论：

- `VERIFIED`：所有配置来源可用，交易日覆盖、复权口径和 OHLCV 校验一致；只有此状态可以发布正式研究输入或用于策略发布。
- `DEGRADED`：至少有一份来源数据，但来源缺失、口径不一致或数据有偏差；只可保留为诊断/影子研究，不能替代主数据。
- `PARKED`：没有可用来源；不能继续研究或发布。

诊断结果只包含状态、稳定原因码和不可变哈希，不含原始价格、路径、密钥或供应商响应正文。`report_sha256` 可写入上游 P1 manifest 和下游证据包，形成数据来源到策略发布的可追溯链。

策略的发布调用方可设置 `require_data_assurance=True` 并传入该报告。只有 `VERIFIED` 报告的哈希才会绑定进不可变 `StrategyReleaseManifest`；缺失或降级报告会使发布准备度失败。

对于 SOXL，Alpaca SIP 与 Twelve Data EOD 必须分别保存为独立根。若免费 EOD 的复权口径不能与策略要求的 `total_return_adjusted` 严格一致，结果会安全地停在 `DEGRADED`，而不是混用数据后继续回测。
