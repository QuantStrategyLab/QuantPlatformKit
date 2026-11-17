# Execution Receipt Contract v1

[简体中文](execution-receipt-contract.zh-CN.md)

`qsl_execution_receipt.v1` is a **read-only, minimal** execution-outcome fact. It lets the console distinguish among "not in trading window", "strategy emitted no orders", "blocked by risk controls", "submitted", "broker acknowledged", "filled", and "reconciliation required". It never includes or leaks accounts, order IDs, symbols, prices, quantities, positions, cash, raw exception text, or credentials.

## Fixed fields

```text
schema_version
receipt_id                 # truncated content SHA-256 digest, never a broker order ID
platform                   # canonical platform name
strategy_profile
strategy_revision          # fixed 40-char revision
execution_mode             # paper or live
outcome
broker_confirmation
observed_at
```

`receipt_id` is derived from canonical JSON over these public minimal fields; mutating any field fails verification. Platform aliases are normalized (e.g., `interactive_brokers` to `ibkr`).

## Outcome semantics

| `outcome` | `broker_confirmation` | Meaning |
|---|---|---|
| `not_due` | `not_applicable` | Outside the strategy's trading window |
| `no_action` | `not_applicable` | Strategy ran and produced no orders |
| `risk_blocked` | `not_applicable` | Blocked before submission by deterministic risk gates |
| `submitted` | `not_observed` | Request sent, no verifiable broker confirmation yet |
| `broker_acknowledged` | `acknowledged` | Broker acknowledged receipt without claiming fill |
| `partially_filled` | `partially_filled` | Partial fill confirmed |
| `filled` | `filled` | Fill confirmed |
| `reconciliation_required` | `reconciliation_required` | Outcome uncertain; reconciliation mandatory |
| `failed` | `not_applicable` / `not_observed` / `reconciliation_required` | Failure must preserve uncertainty rather than guessing |

Failures or timeouts never imply "no order placed". Unless the producer can prove the broker never received the request, it must emit `not_observed` or `reconciliation_required` and keep existing new-risk halts active.

Simulated runs never claim live submission or broker acknowledgment: technical errors emit `failed / not_applicable`, while normal simulated runs emit `no_action / not_applicable`. Downstream platforms adopt this classification via pinned library revisions; library source updates alone do not change deployed behavior.

## Integration

Platforms attach receipts to an already self-attested `runtime_report.v1` via `attach_execution_receipt(report, receipt)`. The helper accepts only receipts matching platform, strategy, 40-char revision, and execution channel, performing no file I/O, network calls, or broker requests. `QuantRuntimeSettings` read-only projections re-verify the same bindings after persistence.

Legacy platforms lacking receipts stay compatible, though consoles must show "not collected" rather than treating heartbeats, workflow green status, or health checks as submissions or fills. Receipts themselves never grant paper, canary, or live authority; independent risk gates, reconciliation, and `P0`-`P6` workflows govern authorization.
