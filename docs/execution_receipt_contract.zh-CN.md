# 执行回执契约 v1

`qsl_execution_receipt.v1` 是一条**只读、最小化**的执行结果事实。它用于让控制台区分
“今天不该下单”“策略决定不下单”“风控拦截”“已提交”“券商确认”“成交”与“必须对账”。
它不包含、也不能推导出账户、订单号、标的、价格、数量、持仓、资金、异常原文或任何凭证。

## 固定字段

```text
schema_version
receipt_id                 # 内容 SHA-256 的截断摘要，不是 broker order id
platform                   # 规范化平台名
strategy_profile
strategy_revision          # 固定 40 位 revision
execution_mode             # paper 或 live
outcome
broker_confirmation
observed_at
```

`receipt_id` 由上述公开最小字段的规范 JSON 计算；修改任一字段都会使校验失败。
平台别名会被归一化，例如 `interactive_brokers` 为 `ibkr`。

## 结果语义

| outcome | broker_confirmation | 含义 |
| --- | --- | --- |
| `not_due` | `not_applicable` | 当前不在策略应交易窗口 |
| `no_action` | `not_applicable` | 已运行，但策略没有产生订单 |
| `risk_blocked` | `not_applicable` | 下单前被确定性风险闸门拦截 |
| `submitted` | `not_observed` | 已发送请求，尚无可验证确认 |
| `broker_acknowledged` | `acknowledged` | 已收到券商确认，但未宣称成交 |
| `partially_filled` | `partially_filled` | 已有部分成交事实 |
| `filled` | `filled` | 已有成交事实 |
| `reconciliation_required` | `reconciliation_required` | 状态不确定，必须对账 |
| `failed` | `not_applicable` / `not_observed` / `reconciliation_required` | 失败时必须明确未知边界，不能猜测 |

失败或超时不会自动证明“没有下单”。如果无法证明券商未收到请求，生产者必须写
`not_observed` 或 `reconciliation_required`，并保持停止新增风险的现有流程。

## 接入方式

平台在已经生成、自证 strategy release 的 `runtime_report.v1` 上调用
`attach_execution_receipt(report, receipt)`。该函数只接受平台、策略、40 位 revision 和
执行通道都完全匹配的回执；它不写文件、不联网、不调用 broker。运行报告持久化后，
QuantRuntimeSettings 的只读投影会再次验证同样的边界。

缺少回执的旧平台保持兼容，但控制台必须显示“未采集”，不能把 heartbeat、workflow 成功
或 Green status 当作提交/成交。回执本身也不授予 paper、canary 或 live 权限；这些权限
继续由独立风险闸门、对账和 P0–P6 流程决定。
