# Unified operator notification format

This display contract extends [routine delivery](routine-daily-digest.md),
[notification routing](notification-routing-policy.md) and the existing
`NotificationEvent`, digest candidate and execution-receipt contracts. It does
not replace their schemas, classification, accounting or delivery policy.

Every strategy-risk alert, daily trading summary, run-guard alert,
execution-receipt check and candidate-confirmation warning uses one locale and
five sections, in this order. `notifications.presentation` owns the section
names and the pure renderer; QRS consumes a byte-verified snapshot so its digest
image does not need another runtime dependency.

| Section | Existing facts and display rule |
| --- | --- |
| Result / 结果 | Caller-proven outcome or review requirement. Keep `reason_code` with its existing localized explanation. A guard failure is not a broker outcome. |
| Scope / 范围 | Supplied `occurred_at`, `observed_at`, `due_at`, lookback or business window. A missing time is unknown. Never substitute render time. |
| Evidence / 证据 | Actual run link, risk observations, receipt categories, `order_count`, `fill_count`, known state and per-run diagnostics. Urgent diagnostics precede optional snapshots. |
| Coverage / 覆盖 | The scope actually inspected, expected/covered target counts and source status. Daily reports always name IBKR, Schwab, Firstrade, LongBridge, Binance and management console. |
| Next step / 下一步 | Review the source run, receipt and missing sources when evidence needs attention; retain execution restrictions. A verified routine window needs no action. Existing risk-specific next steps remain more specific. |

## Field semantics

- Keep `platform_id`, `opaque_account_uid`, `target_id`, `strategy_profile` and
  `source_run_id` as existing protected identity fields. Never derive missing
  identities, run links or account names from each other.
- `order_count` and `fill_count` retain their independent known/unknown status.
  Zero requires affirmative count evidence. Accepted receipts, inspected report
  counts, skipped reports, workflow success and explicit non-execution do not
  create zero orders or fills. Missing category counts remain unknown.
- Whole-window totals cover only the existing bound targets and require their
  existing complete evidence gate. No data connection is shown as unknown;
  an explicitly unbound source is not included, with run state unknown.
- `actually_ran=false` remains non-execution evidence. Unknown, missing, stale,
  invalid and read failure states remain distinct in existing diagnostics.
- A candidate warning establishes unconfirmed persistence only. It does not
  establish a failed trade, successful daily inclusion or delivery receipt.
- Preserve the producer's window. QRS consolidated display uses its existing
  half-open `[D 06:00, D+1 06:00)` Singapore window. Formatters do not reinterpret
  legacy date contracts or move observations across windows.
- Links must be caller-supplied HTTPS URLs. Drop query and fragment; unavailable
  or invalid links are explicitly unavailable. Private storage URIs, account
  identifiers and raw exception payloads are not link fallbacks.

## Compatibility and rollout

Existing QPK formatter signatures remain compatible. Risk, guard and receipt
message copy changes to these sections when consumers adopt this revision.
Healthy heartbeat routing and its existing renderer remain unchanged. Daily
idle copy now says “No trades in verified targets” inside a complete report,
not “No trades across all accounts today”. Unknown unbound sources still appear
in coverage. This is a deliberate display change, not a new data connection.

The renderer reserves result, scope, coverage and next step before truncating
optional evidence. It reports omitted evidence explicitly. Normal production
uses the existing 3900 UTF-16-unit single-message budget. An artificial budget
that cannot hold the mandatory fields raises a fixed error instead of silently
omitting coverage. No extra send is created.

Downstream source adoption must be coordinated with platform fault fixes.
QPK consumers remain at their current pins until a separately reviewed adoption;
QRS may snapshot only the pure presentation module with recorded source bytes.
Source PRs do not change runtime flags, schedules, recipient/date reservations,
receipt acceptance, deployment or execution authority.
