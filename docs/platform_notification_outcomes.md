# Platform Notification Outcomes

[简体中文](platform_notification_outcomes.zh-CN.md)

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
