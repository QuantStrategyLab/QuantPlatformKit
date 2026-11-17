# P2 Real Paired Shadow Evidence Contract

[简体中文](paired-shadow-evidence.zh-CN.md)

`quant_platform_kit.strategy_lifecycle.paired_shadow_evidence` defines `paired_shadow_evidence.v1`. It is a companion artifact to `forward_observation_receipt.v1` and does not replace `ForwardObservationPolicy`, existing receipts, or the lifecycle state machine.

Every evidence record must bind to a verified Forward Observation receipt and include:

- Identical `observed_at` and `input_snapshot_sha256`.
- Candidate and baseline `signal`, `hypothetical_order`, `position`, `cost`, and `return` computed over that identical input.
- `candidate_id`, a stable `baseline_id`, and the Forward Observation receipt digest.
- The previous paired-shadow evidence digest plus fixed `no_order=true` and `live_authority_granted=false`.

This module computes no strategy values, emits no orders, and accesses no market data, accounts, brokers, or secrets. It canonically freezes and validates results produced by non-live adapters. The five payload fields (`signal`, etc.) are strategy-specific JSON values; the contract preserves their exact contents and digests without interpreting or recomputing returns.

## Continuity and isolation

From the second record onward, writers must supply both the previous paired-shadow evidence and the previous Forward Observation receipt. Validators check that candidate and baseline IDs remain constant, sequence numbers and timestamps advance, paired-shadow records chain cleanly, and Forward Observation receipts chain in lockstep. Different candidates, baselines, and forward windows must never share a chain.

Persistent platforms must use conditional appends: store the current chain head per `(candidate_id, baseline_id)` and enforce a unique constraint on `forward_observation_receipt_sha256`. Pure contracts cannot substitute for atomic database/object-store writes or prevent concurrent writers from forking the same chain head.

## Relationship to legacy `ShadowValidator`

Legacy `ShadowValidator` reads recent production performance snapshots and explicitly returns:

```json
{
  "evidence_kind": "recent_performance_proxy",
  "paired_shadow_evidence": false,
  "no_order": true,
  "live_authority_granted": false
}
```

These proxy summaries remain useful for diagnostics, but because they lack simultaneous candidate/baseline outputs on the same timestamped input snapshot, they never qualify as `paired_shadow_evidence.v1` or proof of P2 completion.

## Platform integration boundaries

After generating each Forward Observation receipt, non-live adapters freeze the input snapshot digest, run candidate and baseline side by side, build this artifact, and persist it via conditional append. Neither Forward Observation schedulers nor live adapters may infer order or live authority from this artifact; completing the window still requires independent human approval.

`quant_platform_kit.common.runtime_reports` exposes a shared `artifacts` extension map across all platforms. Upgraded platforms can call the pure function `build_paired_shadow_evidence_report_artifacts(...)` and pass its return value to `build_runtime_report_base(..., artifacts=...)` or `finalize_runtime_report(..., artifacts=...)`:

```python
artifacts = build_paired_shadow_evidence_report_artifacts(
    evidence,
    policy=policy,
    forward_observation_receipt=receipt,
)
report = build_runtime_report_base(..., artifacts=artifacts, dry_run=True)
```

This helper validates policy/receipt bindings and writes `paired_shadow_evidence_json` (canonical JSON string) and its digest into `artifacts`, along with `paired_shadow_evidence_no_order=true` and `paired_shadow_evidence_live_authority_granted=false`. It never receives, mutates, or deploys runtime targets, writes cloud storage, submits orders, or alters execution modes. Because `PlatformRunner` does not own report schema internals, no per-platform branching is needed. Storing a JSON string rather than a nested mapping prevents report serializers from stripping `previous_paired_shadow_evidence_sha256: null` on the first record, keeping the receipt digest verifiable.
