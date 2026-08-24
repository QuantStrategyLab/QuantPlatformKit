# Durable execution commands

`quant_platform_kit.common.execution_commands` is the shared, opt-in contract
for strategies whose signal date and broker-execution date are different.  It
does not enable a broker consumer or change a strategy parameter by itself.

## Contract

1. The signal producer constructs an immutable, content-addressed
   `ExecutionCommand`.  Its identity includes platform, account scope,
   strategy, signal date, effective date, timing contract, decision digest, and
   canonical intent.
2. `ExecutionCommandStore.enqueue()` creates that command exactly once.
3. A consumer lists only the matching effective-date queue and atomically
   writes the `claimed` event.  A late or second claim returns no claim.
4. The same command records broker evidence through distinct events:
   `submitted`, `accepted`, `partially_filled`, `filled`, `cancelled`, or
   `rejected`.
5. If a worker crashes after claiming or broker submission is uncertain, it
   writes or remains in `reconciliation_required`.  It is deliberately not
   auto-retried as a fresh order.

The terminal states are `filled`, `cancelled`, and `rejected`.  Event objects
are create-only and strictly sequenced, so a stale concurrent worker cannot
overwrite a later broker outcome.

## Storage and rollout

Set a dedicated per-platform `*_EXECUTION_COMMAND_CLOUD_URI` to use a cloud
object store with `create_text` support.  The local `*_EXECUTION_COMMAND_DIR`
backend is intended only for tests and controlled development.  The queue does
not fall back to an execution-report location: an absent durable backend must
leave the consumer disabled.

Adapters must first use this contract in paper mode, look up broker orders by
the command identity before any recovery, and prove reconciliation behavior.
No live adapter is enabled by this module.  That staged migration remains
tracked in QuantPlatformKit issue #342.
