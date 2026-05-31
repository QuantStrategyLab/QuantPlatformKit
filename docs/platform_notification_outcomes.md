# Platform Notification Outcomes


## 中文摘要

- 完整中文版见 [`platform_notification_outcomes.zh-CN.md`](platform_notification_outcomes.zh-CN.md)；本节保留在英文文件顶部，方便从当前文件直接找到中文入口。
- 用途：本文档围绕 `Platform Notification Outcomes`，用于理解 `QuantPlatformKit` 的配置、运行、部署、研究或验收边界。
- 主要覆盖：`Execution Stages`、`Skip Reasons`、`Notification Envelope`、`Platform Responsibilities`。
- 阅读顺序：先确认边界、输入输出和权限要求，再执行文档里的命令、CI、dry-run、发布或切换步骤。
- 风险提示：涉及实盘、密钥、权限、Cloud Run、交易所或券商 API 的变更，必须先在测试环境或 dry-run 验证；不要只凭示例直接修改生产。
- 英文正文保留更完整的命令、字段名和配置键；如果摘要和正文不一致，以正文中的实际命令和配置为准。
Platform runtimes should use the shared execution outcome and notification
envelope helpers in `quant_platform_kit` instead of defining private stage or
notification sink semantics in each repository.

## Execution Stages

`quant_platform_kit.common.execution_outcomes` defines the shared strategy-run
stages used by platform persistence, API responses, logs, and notifications:

| Stage | Terminal | Meaning |
| --- | --- | --- |
| `ORDERS_PLANNED` | No | A plan was built before execution. |
| `DRY_RUN_COMPLETED` | No | Dry-run execution finished without live orders. |
| `NO_ACTION` | No | Live cycle completed with no order needed. |
| `SUBMITTED` | Yes | One or more live orders were submitted. |
| `EXECUTION_BLOCKED` | No | No order was submitted because of a retryable execution blocker. |
| `PARTIAL_SUBMITTED` | No | Some orders were submitted, but at least one execution blocker remains. |
| `FUNDING_BLOCKED` | Yes | No order was submitted because available cash cannot buy the required whole share. |
| `RECONCILED` | Yes | A submitted run was reconciled by a platform-specific process. |
| `COMPLETED` | Yes | A run was marked complete by a platform-specific process. |

Terminal stages block duplicate live order submission for the same
account/profile/period. Non-terminal execution blockers can be retried by the
platform runtime while the strategy execution window remains open.

## Skip Reasons

The shared helper treats these skip reasons as execution blockers by default:

- `buy_quantity_zero`
- `insufficient_cash_for_whole_share`
- `quote_unavailable`
- `sell_quantity_zero`

`insufficient_cash_for_whole_share` is a terminal funding block when it is the
only blocking reason and no live order was submitted. This keeps logs and
notifications explicit without repeatedly retrying the same underfunded run.

## Notification Envelope

`quant_platform_kit.notifications.events` provides:

- `RenderedNotification(detailed_text, compact_text)`
- `NotificationPublisher(log_message, send_message)`
- `publish_rendered_notification(...)`

Platform renderers may keep broker-specific layout and order details, but they
should publish through the shared envelope so logs and user notifications have a
consistent delivery contract.

## Platform Responsibilities

Platform repositories should:

- use shared stage constants and stage resolution helpers
- include the resolved stage in persisted run state and API responses
- render execution blockers consistently in logs and notifications
- keep broker-specific order payloads, account labels, and transport wiring local
