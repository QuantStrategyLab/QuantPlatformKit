# Non-Live Execution Evidence Binding

[简体中文](non-live-execution-evidence-binding.zh-CN.md)

`quant_platform_kit.strategy_lifecycle.non_live_execution_evidence` defines `non_live_execution_evidence_binding.v1`. It freezes three previously separate facts into one verifiable record:

- A frozen candidate and its immutable candidate revision digest.
- A target platform, an account-redacted `runtime_scope_sha256`, a platform adapter digest, and a non-live channel.
- An exact strategy release identity together with digests of the matching P4 forward receipt and non-live evidence artifact.

This contract applies uniformly to single strategies, combo strategies, and `plugin_composite` candidates without hardcoding SOXL, TQQQ, or any platform. `plugin_composite` is the only valid candidate shape for runtime plugin participation; a single plugin must never masquerade as a standalone strategy.

## Frozen bindings

The builder verifies that receipt digests for `p2_config`, `p3_evidence`, `risk_policy`, `strategy_release`, and `plugin_bundle` match the config, evidence, risk, manifest, and plugin digests of `StrategyReleaseIdentity` exactly. A candidate therefore cannot mix another strategy version, risk policy, or plugin bundle into forward observation.

`execution_channel` must be `shadow` or `paper` and enabled by the candidate's policy. Shadow requires `shadow_decision` in the receipt; Paper also requires `simulated_replay` or `broker_paper` declared in the policy. Every path fixes:

```json
{
  "no_order": true,
  "live_authority_granted": false
}
```

It is never an order permit, account permit, scheduler, or live promoter, and it never reads or writes object storage, Cloud Run, GitHub, market data, or brokers.

## Account and runtime scope

Records persist `runtime_scope_sha256` only—never account numbers, account selectors, service names, deployment URLs, credentials, or raw broker responses. Platforms call `non_live_runtime_scope_sha256(runtime_target=..., execution_channel=...)` inside their controlled environment: it hashes only platform, deployment/account/service scope, and execution environment, returning no raw fields. It rejects live targets, requires `dry_run` targets for Shadow, and requires an explicit non-live scope selector on all targets. Audit and storage layers match by digest only, while actual account identity checks, paper command scopes, and order admission remain with the existing runtime-target, account-identity, paper-command, and risk-gate contracts.

## Current Shadow and future Paper

The generic builder accepts caller-verified `schema_version + sha256` evidence references so future Paper adapters can use their own strictly validated schemas. For current `paired_shadow_evidence.v1`, platforms should use `build_paired_shadow_execution_evidence_binding(...)`, which additionally verifies consistency across the paired-shadow artifact, policy, and forward receipt.

Platforms may call `build_non_live_execution_evidence_report_artifacts(...)` to place canonical JSON and digests into `runtime_reports.artifacts`. Persistent services must isolate/query by `(candidate_id, platform_id, runtime_scope_sha256, execution_channel)` and persist receipts, evidence, and bindings via create-only or conditional-append writes; pure functions cannot replace object-store atomicity and access control.
