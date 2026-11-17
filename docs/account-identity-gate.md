# Account Identity Gate

[简体中文](account-identity-gate.zh-CN.md)

The account identity gate sits in front of a platform's order-submission port and stays separate from strategy formulas, position sizing, and plugin signals. It compares read-only broker account metadata against the reviewed target in `RUNTIME_TARGET_JSON`. Strategies and plugins cannot bypass or alter this check.

## Runtime target configuration

Optionally add `account_identity` inside `RUNTIME_TARGET_JSON`:

```json
{
  "enforcement": "observe",
  "expected_account_types": ["cash"],
  "expected_account_modes": ["paper"],
  "expected_account_id_fingerprint": "sha256:<64-char-lowercase-hex>",
  "required_fields": ["account_type", "account_mode", "account_id"]
}
```

- `observe`: emits redacted receipts and monitoring signals without blocking existing order calls, allowing verification of broker API capabilities first.
- `enforce`: rejects orders before calling the broker when evidence is missing or any field mismatches.
- Account IDs may only be passed as `sha256:` fingerprints. Raw account numbers and credentials must never appear in runtime targets, logs, plugin payloads, or execution reports.

Configuring an expected account type, mode, or account fingerprint automatically marks the corresponding field as required evidence. Missing expected values produce `account_identity_configuration_invalid` rather than silently passing.

## Platform integration rules

1. Query account metadata read-only after the platform adapter initializes the broker context.
2. Construct `BrokerAccountIdentity` and call `evaluate_account_identity`.
3. Wrap all order paths with `AccountIdentityGuardedExecutionPort` so strategies, plugins, and manual triggers share the same gate.
4. Write `decision.to_receipt()` into the runtime report and pass findings to `runtime_command_gate` for platforms using durable commands.
5. Observe each account across multiple trading days before an operator explicitly switches the target to `enforce`; never rotate credentials or switch accounts automatically.

## LongBridge current boundary

LongBridge OpenAPI position channels return the account type, so `account_type` can be verified first. The public account-balance endpoint does not expose a comparable account number or direct proof of paper vs. live mode. LongBridge targets must start in `observe`; a secret named PAPER does not count as proof of a paper account without trusted broker evidence. Setting missing fields under `enforce` fails closed and rejects orders.

## Stable finding codes

- `account_identity_evidence_unavailable`
- `account_identity_configuration_invalid`
- `account_identity_platform_mismatch`
- `account_identity_type_mismatch`
- `account_identity_mode_mismatch`
- `account_identity_id_mismatch`

These codes omit account numbers and credentials and can be forwarded to platform reports, strategy reports, plugin alerts, and the unified Runtime Command Gate.
