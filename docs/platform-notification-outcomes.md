# Platform Notification Outcomes

[简体中文](platform-notification-outcomes.zh-CN.md)

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
| `FUNDING_BLOCKED` | No | Funding was insufficient and no order was submitted; retry only while the execution window is open. |
| `RECONCILED` | Yes | A submitted run was reconciled by a platform-specific process. |
| `COMPLETED` | Yes | A run was marked complete by a platform-specific process. |

Terminal stages block duplicate live order submission for the same
account/profile/period. Non-terminal execution blockers can be retried by the
platform runtime while the strategy execution window remains open.

## Skip Reasons

Chinese notification renderers translate cash-shortage codes as user-facing
reasons; persisted execution codes stay unchanged. Operational alerts show a
localized summary and a workflow link instead of embedding raw exception or
provider audit payloads. Detailed investigation uses the existing workflow and
cloud logs. Downstream consumers must adopt the notification-only patch at their
pinned runtime revision before these display changes take effect.

The shared helper treats these skip reasons as execution blockers by default:

- `buy_quantity_zero`
- `insufficient_cash`
- `insufficient_cash_for_whole_share`
- `quote_unavailable`
- `sell_quantity_zero`

`insufficient_cash` and `insufficient_cash_for_whole_share` are retryable
funding blocks when they are the only blocking reason and no live order was
submitted. The platform may retry only while the strategy execution window is
open, and must acquire its durable create-only submission claim immediately
before the first broker request. A broker-accepted, pending, or unknown
submission is never automatically retried.

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

## Credential-free delivery and redaction

`quant_platform_kit.notifications` exports `NotificationIntent`,
`NotificationReceipt`, `send_notification_intent`, `redact_sensitive_text`,
`redact_sensitive_data`, `redact_exception`, `SensitiveDataFilter` and
`install_log_redaction`.

Build an intent from non-credential data and serialize it with `to_dict()`:

```python
import json
from quant_platform_kit.notifications import NotificationIntent, send_notification_intent

intent = NotificationIntent(
    text="Execution complete", run_id="example-run", chat_ids=("example-chat",),
    dry_run=True, metadata={"source": "scheduler"},
)
json.dumps(intent.to_dict())
receipt = send_notification_intent(intent, bot_token_env="TELEGRAM_TOKEN")
json.dumps(receipt)
```

The frozen intent recursively copies and freezes metadata. Credential-like keys
(such as `token`, `secret`, `password`, `api_key`, `authorization` and
`private_key`) and credential-shaped strings are rejected without echoing their
contents. This is a guard against accidental secret insertion, not a classifier
for arbitrary opaque strings. Keep all credentials out of intent data.

The plugin alert publisher has its own
[settings precedence](strategy-plugin-runtime-contract.md#escalated-alerts),
including org bot and chat defaults. The intent sender below still reads only
the explicitly named credential source.

Only the send function reads the named environment variable. Pass
`bot_token_env="STRATEGY_PLUGIN_ALERT_TELEGRAM_BOT_TOKEN"` to use the existing
plugin environment variable, or pass `secret_name` and optional `project_id` to
use the existing cloud `get_secret_store().get_secret(...)` abstraction instead.
An explicit secret name takes precedence; a failed secret lookup does not fall
back to another identity. A dry run reads no credentials and makes no request.
No new credential cache or token-bearing settings object is created.

The JSON-compatible receipt has exactly `status`, `http_status`, `sha256`,
`length`, `run_id` and `ok`. `sha256` hashes the original intent text as UTF-8;
`length` counts its characters before the existing transport normalization.
`status` is `sent`, `failed` or `dry_run`; `ok` means every recipient received an
HTTP success with an affirmative Telegram API acknowledgement, or the dry run
completed. It does not mean the recipient read the message. `http_status` is
`null` when no HTTP response was observed or recipients returned different
statuses. Provider errors and response bodies are never included.
Persist the receipt when the report does not need message text or chat identifiers.

The existing `send_telegram_message` and `send_strategy_plugin_telegram`
signatures and boolean return values remain supported. Consumer migration is
separate and requires updating pinned QPK revisions.

### Logging and text streams

Configure logging first, then install the filter:

```python
import logging
from quant_platform_kit.notifications import install_log_redaction

logging.basicConfig(level=logging.INFO)
install_log_redaction(wrap_streams=True)
```

Installation is idempotent. It filters the root logger and all current handlers,
including handlers on child loggers, so propagated records are covered. Call it
again after adding handlers. It redacts formatted messages, structured arguments,
cached exception text, chained tracebacks and stack information. Existing
Telegram error paths use `redact_exception` before printing or recording failures.

The optional stdout/stderr wrappers buffer text until newline or explicit flush,
redacting a line assembled across multiple writes. Explicit flush ends that
buffering boundary; do not split credentials across flushes. Binary writes,
previously captured stream references and handlers installed later require their
own filtering. The installer does not replace logging configuration.

`redact_sensitive_data` returns a new dict/list/tuple tree, preserving non-secret
fields. It masks credential-key values, bare Telegram token literals and bot URL
paths. `redact_sensitive_text` also handles JSON text; `redact_exception` renders
exception messages and chained causes, including requests/urllib URL errors.

### Repository scanning

`.gitleaks.toml` extends the default rules with `telegram-token-literal`, a pure
format rule with no keyword requirement. The existing pre-commit and PR/main
Gitleaks checks discover this configuration automatically. The weekly secret
scan uses the same configuration across all fetched branches, tags and history,
including data branches. Findings contain file paths and rule names only; no
scan report is uploaded or committed. A failed scheduled run uses the existing
GitHub Actions failure notification mechanism. Repository and organization
notification settings are unchanged.

## Risk-block attention messages

`risk.attention.render_attention_compact` and the shared Telegram publisher render
broker, a masked account suffix (at most two characters), strategy, status, every
reason code with a localized explanation, optional financial evidence, SGT run
time, a caller-supplied HTTPS console run link, and one action line. Chinese
variants and English use the same fields. Missing or invalid evidence is shown
as unknown; a missing link is explicit. Links are never built from account IDs,
and URL credentials, query strings and fragments are not displayed.

The optional display arguments are `daily_loss_context`, `occurred_at` (an aware
datetime or ISO timestamp), and `run_url`. Existing callers remain valid.
`daily_loss_context` accepts `daily_loss_fact_status`, `daily_loss_usd`,
`max_daily_loss_usd`, and `daily_loss_baseline_as_of`. A loss is displayed only
when its fact status is `verified`; it is described as baseline-relative loss,
not assumed to be intraday trading P&L. Limits must be explicit, never inferred
from account equity. These fields do not change admission or notification dedup.

Consumers need a coordinated QPK pin update before the new fields take effect.
Schwab's adapter uses `render_attention_notification` as a feature marker and
retains its legacy rendering until that update. Its existing notification report
context supplies `started_at` and, when available, `console_run_url`. A console
producer must supply the actual run URL; the renderer does not invent a route.
Rollout and pin changes are separate from this presentation patch.
