# Account Owner Fence Operations

[简体中文](account-owner-fence-ops.zh-CN.md)

`claim_account_owner` establishes an exclusive fence for a **physical account** before submitting broker orders. It is distinct from per-signal-day / `strategy_profile` execution claims: execution claims prevent duplicate orders for the same signal, while the owner fence prevents multiple writers from concurrently managing the same funded account.

## Stable semantics

| Item | Behavior |
|---|---|
| Marker key | `v1/account-owner/{broker}/{account_id}` (no `strategy_profile` segment) |
| Created | Current writer becomes owner and may proceed |
| Exists with same `owner_id` | Allowed without modifying the marker |
| Exists with different `owner_id` | `contested=True`, fails closed and rejects submission |
| TTL | **None**. Markers never expire and cannot be preempted by another writer |
| Release API | **None**. Ownership handoff requires manually deleting the durable marker object |

Platform runtime identities only need **create + read** permissions on the marker prefix. Delete permission is a controlled operational privilege and should not be granted to routine trading service accounts.

## Shared durable URI per physical account

The fence is effective only within the **same object-storage prefix**. Every Cloud Run service or job touching the same `{broker, account_id}` must configure the identical execution-marker `cloud_prefix_uri` (or equivalent backend root).

If two instances write to different buckets or prefixes:

- Both appear to `claim` successfully in code.
- Real mutual exclusion **does not exist**.
- This is an operational wiring requirement, not something an extra distributed lock inside one bucket can prove.

Pre-launch checklist:

1. Every writer shares the exact same marker prefix URI string (including trailing-slash convention).
2. `{broker, account_id}` resolves to the **same physical account identity** across platforms (do not substitute region or `PAPER` labels unless that label is the chosen durable ID across all paths).
3. When contested, logs and notifications expose the redacted `marker_key` and current `owner_id` with `submit=0`.

## Owner handoff (switching strategy, profile, or service)

Because there is no TTL, handoff is an explicit operation rather than waiting for expiry.

1. **Stop writers**: pause schedules and manual triggers touching the physical account; verify no in-flight `submit` or pending `UNKNOWN` reconciliation items remain (follow each platform's `UNKNOWN` procedure).
2. **Read back**: with an operator identity, read the marker and record current `owner_id`, `marker_key`, and object URI.
3. **Delete marker**: delete only the specific `v1/account-owner/{broker}/{account_id}` object (never bulk-delete `execution_markers/`).
4. **Start the single new writer**: start only the target service so it calls `claim_account_owner` before its next `submit`.
5. **Verify**: re-running the same owner succeeds; testing the previous owner or a second profile path must yield `submit=0` and `contested`.
6. **Record evidence**: log handoff timestamp, operator, old/new `owner_id`, and object URI in operational records using each platform's redaction rules.

Prohibited actions:

- Deleting the marker while writers are still running (risks concurrent writes).
- Adding a TTL or automatic steal mechanism to the fence.
- Treating signal claims or local file locks as cross-instance account exclusivity.

## LongBridge physical account ID

Current token-bound format:

- Explicit: `LONGBRIDGE_PHYSICAL_ACCOUNT_ID=lb:<name>`
- Fallback: `lb:<LONGPORT_SECRET_NAME>` (aligned with runtime and env-sync; broker field is `longbridge`)

This separates credential boundaries across HK, paper, and SG environments. Once real broker account numbers are retrieved, migrate to `lb:<broker_account_no>`.

### Migration steps (when using real account numbers)

1. Stop writers for the target service and confirm no in-flight order disputes exist.
2. Delete the legacy key `v1/account-owner/longbridge/lb:<old_id>`.
3. Update GitHub Environments and Cloud Run: `LONGBRIDGE_PHYSICAL_ACCOUNT_ID=lb:<broker_account_no>` (verify across all three environments).
4. Run env-sync or deploy and verify the variable is not in `remove_env_vars` and holds the expected value on Cloud Run.
5. Start the single writer and verify the new key is created while the legacy token-bound ID no longer appears in fence paths.

Do not force an ID change before obtaining the real account number; renaming changes the fence identity and requires the full handoff procedure.

## Related code and docs

- `quant_platform_kit.common.execution_state.build_account_owner_marker_key`
- `quant_platform_kit.common.execution_state.claim_account_owner`
- Execution claim/outcome separation: [execution-outcomes.md](./execution-outcomes.md)
