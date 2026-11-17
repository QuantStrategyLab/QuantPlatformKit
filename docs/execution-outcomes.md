# Immutable Execution Outcomes

[简体中文](execution-outcomes.zh-CN.md)

`ExecutionMarkerStore` separates execution deduplication claims from terminal execution outcomes:

- `execution_markers/`: written atomically with create-only semantics before execution; serves as the sole deduplication authority and is never overwritten.
- `execution_outcomes/`: written with the same create-only semantics after an execution cycle finishes; leaves existing records untouched and returns `False`.

This design works across GCS, S3, Azure, and local backends. Runtime service accounts require only create and read object permissions rather than delete or full object-management privileges to update markers. Platform callers should call `record_outcome` after acquiring a claim instead of overwriting claims via `record_marker`.

`record_marker` remains for legacy callers that have not adopted pre-execution claims; new execution paths must use claim + outcome separation.

For physical-account exclusivity, use `claim_account_owner` (`v1/account-owner/{broker}/{account_id}`, no TTL). See [account-owner-fence-ops.md](./account-owner-fence-ops.md) for handoff steps and shared durable URI rules.
