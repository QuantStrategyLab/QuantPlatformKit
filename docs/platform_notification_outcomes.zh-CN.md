# 平台通知与执行结果语义

平台运行时应复用 `quant_platform_kit` 里的共享执行结果和通知 envelope
helper，不要在每个仓库里各自定义一套 stage 或通知投递语义。

## 执行 Stage

`quant_platform_kit.common.execution_outcomes` 定义了平台持久层、API 返回、
日志和通知共用的 strategy-run stage：

| Stage | 是否终态 | 含义 |
| --- | --- | --- |
| `ORDERS_PLANNED` | 否 | 已生成执行计划，尚未完成执行。 |
| `DRY_RUN_COMPLETED` | 否 | 模拟运行完成，没有提交真实订单。 |
| `NO_ACTION` | 否 | 实盘周期完成，但不需要下单。 |
| `SUBMITTED` | 是 | 已提交一个或多个真实订单。 |
| `EXECUTION_BLOCKED` | 否 | 因可重试的执行阻塞导致没有提交订单。 |
| `PARTIAL_SUBMITTED` | 否 | 部分订单已提交，但仍有执行阻塞需要关注。 |
| `FUNDING_BLOCKED` | 是 | 现金不足以买入所需的一整股，因此没有提交订单。 |
| `RECONCILED` | 是 | 已由平台自己的 reconciliation 流程完成核对。 |
| `COMPLETED` | 是 | 已由平台自己的流程标记为完成。 |

终态会阻止同一账户、同一 profile、同一周期重复提交实盘订单。非终态执行阻塞
可以在策略执行窗口仍然开放时，由平台 scheduler 后续重试。

## 跳过原因

共享 helper 默认把这些 skipped-order reason 视为执行阻塞：

- `buy_quantity_zero`
- `insufficient_cash_for_whole_share`
- `quote_unavailable`
- `sell_quantity_zero`

当 `insufficient_cash_for_whole_share` 是唯一阻塞原因，并且没有任何真实订单已提交时，
该周期会记为终态 `FUNDING_BLOCKED`。这样日志和通知会明确说明资金不足，同时避免
每天重复重试同一个资金不足的运行周期。

## 通知 Envelope

`quant_platform_kit.notifications.events` 提供：

- `RenderedNotification(detailed_text, compact_text)`
- `NotificationPublisher(log_message, send_message)`
- `publish_rendered_notification(...)`

各平台可以保留券商自己的通知布局和订单细节，但应通过共享 envelope 投递，
使日志和用户通知具备一致的交付契约。

## 平台仓库职责

平台仓库应当：

- 使用共享 stage 常量和 stage 解析 helper
- 在持久状态和 API 返回中包含解析后的 stage
- 在日志和通知里一致展示执行阻塞
- 将券商专属订单 payload、账户标签和传输层逻辑留在本仓库内
- 不在公开文档里写部署实例当前选择的实盘策略
