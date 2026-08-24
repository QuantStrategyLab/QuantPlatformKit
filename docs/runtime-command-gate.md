# Runtime command gate

`quant_platform_kit.common.runtime_command_gate` is the shared, broker-agnostic
pre-adapter policy contract. It is intentionally separate from research-time
`risk_gate`: research can reject a proposed decision; the runtime command gate
protects the final broker call and records what it would permit.

The only modes are:

- `active`: a complete, on-session durable command may proceed.
- `reducing`: cancellation, queries, and orders proven from reconciled
  positions to reduce net exposure may proceed; no exposure increase is
  permitted.
- `halted`: only cancellation and queries may proceed. It is used for an
  unknown broker outcome, corrupt/replayed durable command history, a position
  reconciliation mismatch, or an explicit kill switch.

The caller supplies `RuntimeCommandExposureEffect`; the gate does not infer it
from a buy/sell label because that is unsafe for shorts, options and partially
filled orders. The caller must persist `decision.to_receipt()` with its run
audit data before it invokes a broker adapter.

## Staged activation

`RuntimeCommandGatePolicy` is `observe` by default. It emits the exact
would-block result without changing an existing broker call. A platform may
switch to `enforce` only after its adapter has passed paper tests covering:

1. durable command creation and create-only claim;
2. exact release-receipt matching;
3. due-session validation and reconciled exposure classification;
4. broker lookup/reconciliation after an uncertain outcome; and
5. persistence of the gate receipt before the broker call.

The gate never changes a strategy parameter, creates an offsetting order, or
automatically liquidates a position. `reducing` only permits a reduction that
the platform already calculated and classified from reconciled positions.
