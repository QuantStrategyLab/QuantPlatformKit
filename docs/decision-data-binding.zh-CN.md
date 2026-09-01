# 决策数据绑定（v1）

`DecisionDataBinding` 用来说明某次策略决策依赖的历史市场数据证据，和券商账户、实时执行报价、订单执行是三条不同的通道。

```text
P1 数据采集 / 多源校验 → 冻结数据工件 → 策略决策
券商账户 / 持仓 ----------------------------→ 执行风控
执行端实时价格 ----------------------------→ 数量换算与价格保护
订单意图 ----------------------------------→ 券商执行
```

绑定中仅允许保存稳定 ID、日期、复权口径、来源 ID 和 SHA-256 摘要。不得保存：API key、账户号、供应商 URL、签名链接、原始行情或供应商错误正文。

迁移阶段有三种模式：

- `legacy_runtime_fetch`：旧运行时取数路径，必须显式标为 `LEGACY`，用于观察而非默认为已验证。
- `artifact_optional`：可同时比较冻结工件与旧路径，工件不能替代执行端报价。
- `artifact_required`：策略历史输入必须匹配冻结工件和绑定哈希；缺失或非 `VERIFIED` 时，运行时应禁止新增风险。

`DecisionDataArtifactPort` 仅加载已验证的历史决策数据；`ExecutionQuotePort` 仅提供短时执行报价。原有 `MarketDataPort` 在迁移期间保留兼容，新的策略代码不应再把它同时用于历史决策和实时下单保护。

## 可移植日线投影（v1）

P1 的原始根目录可以随策略而不同：例如 TQQQ 是 OHLCV，SOXL 的部分候选只需要复权收盘价。运行平台不能猜测这些私有格式。因此，准备让运行时消费的 P1 根目录必须额外包含：

- `decision-price-series.json`：`qpk.decision_price_series_artifact.v1`；按标的提供日线 `as_of`、`close` 和可空的 `volume`。
- `manifest.json`：继续使用 `research_input_manifest.v1`，并把上面文件的大小和 SHA-256 作为成员写入。

运行端先用公开绑定中的 `artifact_sha256` 校验 **规范化** `manifest.json`，再校验 `decision-price-series.json` 的成员哈希，最后比对 `strategy_scope`、最后交易日、复权口径和来源 ID。任何一步不匹配都不能返回历史序列。

这里没有把 `binding_sha256` 写进投影，以避免“绑定包含清单摘要、清单又包含投影”的循环哈希。运行时会在读回投影后重新计算并验证绑定身份。

存储地址只能由部署环境的私有解析器提供，不能出现在 `RuntimeTarget`、控制台页面或执行回报中。P1 仍须先完成自身多源校验；这个投影只是经过 P1 验证后给平台使用的通用出口，不替代 P1、P3 或 P4--P6 的晋升门槛。
