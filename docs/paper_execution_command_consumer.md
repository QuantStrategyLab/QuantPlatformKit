# Paper execution-command consumer

`quant_platform_kit.common.paper_execution_command_consumer` is the shared
paper-only lifecycle for a delayed, durable `ExecutionCommand`.  It records
what a platform *would* submit after fresh account and market reconciliation.
It contains no broker SDK import, execution-port parameter, or live-mode path.

## Boundary

The shared consumer owns only the rules that must be identical across
platforms:

1. validate the runtime-loaded strategy release before touching the queue;
2. validate the runtime-owned platform, account scope, and strategy-profile
   binding before reconciling a claimed command;
3. atomically claim only due, still-queued commands;
4. validate the immutable paper-risk admission receipt and release binding;
5. apply the enforced runtime command gate to every reconciled proposal; and
6. append a create-only lifecycle: `claimed` → `submitted` → `accepted` →
   `filled`, or `rejected` / `reconciliation_required`.

Each platform supplies `reconcile_command(command)`.  It owns its broker
specific account snapshot, positions, quote freshness, FX/currency, lot-size,
and venue-order semantics.  The callback returns
`PaperExecutionReconciliation` containing `PaperExecutionProposal` values and
only stable integrity findings.  It must return redacted audit fields; no
account identifier, credential, token, or raw broker response belongs in the
durable proposal details.

This split is intentional.  A common order router would make incorrect
assumptions about shorts, options, funds, fractional shares, and broker account
rules.  The consumer shares the safety proof while platforms retain their own
execution translation.

## Required behaviour

- The consumer must run in an isolated, explicitly enabled paper service or
  endpoint; never attach it directly to an existing broker order route.
- Use a dedicated create-only `*_EXECUTION_COMMAND_CLOUD_URI`.  Do not reuse
  report, marker, or live execution prefixes.
- Pass the currently loaded release receipt and exact promoted
  `StrategyReleaseIdentity`.  Missing or mismatched evidence blocks before a
  command is claimed.
- Pass `PaperExecutionCommandBinding` from the runtime target, with the exact
  platform, account scope, and strategy profile. A command intended for a
  different consumer is rejected without calling the platform reconciler.
- Classify exposure from reconciled before/after positions, not an order side.
  Under a `reducing_only` admission, every proposal must prove `reduces`.
- If reconciliation, storage, or lifecycle progression fails after a claim,
  preserve `reconciliation_required`.  Do not create a new command or retry a
  broker-equivalent action automatically.

## Minimal platform adapter shape

```python
def reconcile_command(command: ExecutionCommand) -> PaperExecutionReconciliation:
    # Read platform-owned portfolio and quotes, validate freshness and totals.
    # Derive proposal exposure from reconciled before/after values.
    return PaperExecutionReconciliation(
        proposals=(
            PaperExecutionProposal(
                symbol="SOXL",
                exposure_effect="reduces",
                details={"side": "sell", "quantity": 2.0},
            ),
        ),
        integrity_findings=(),
    )
```

The platform passes that callback to `consume_due_paper_execution_commands`.
The resulting audit marks `paper_simulation: true`; it is not broker evidence
and must not be promoted to a live fill.
