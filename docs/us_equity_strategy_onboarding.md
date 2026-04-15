# US Equity Strategy Onboarding Checklist

_Verified snapshot: 2026-04-15_

This checklist describes how a new `us_equity` strategy becomes available on the three US equity broker platforms without adding a manual allowlist entry in each platform repository.

It applies to:

- `InteractiveBrokersPlatform`
- `CharlesSchwabPlatform`
- `LongBridgePlatform`
- `UsEquityStrategies`
- `QuantPlatformKit`

## Target operating model

`UsEquityStrategies` is the source of truth for live strategy profiles. The three platform repositories derive their runtime allowlists from `get_runtime_enabled_profiles()`.

A new strategy should become selectable on a platform only after these are true:

1. The strategy is registered in the `UsEquityStrategies` catalog.
2. The strategy declares `status="runtime_enabled"` only when it is ready for live runtime.
3. The strategy lists the exact platforms it supports in `supported_platforms`.
4. The strategy exposes a unified entrypoint returning `StrategyDecision`.
5. The strategy has one platform-neutral runtime adapter spec.
6. Platform runtime adapters are derived from that spec plus platform native target mode.
7. The platform capability matrix says the platform can supply the declared `required_inputs`.
8. The relevant platform status script reports `eligible=true` and `enabled=true`.

Do not add a second per-platform rollout allowlist for live US equity profiles.

## Strategy repository requirements

In `UsEquityStrategies`, a new live profile needs:

- a canonical profile id in `catalog.py`
- a `StrategyDefinition` with `domain="us_equity"`
- explicit `required_inputs`
- explicit `target_mode`
- `status="runtime_enabled"` only after platform coverage is complete
- `supported_platforms` set to the intended platforms
- a manifest and unified entrypoint
- focused strategy tests
- one platform-neutral runtime adapter spec

The current standard input names are:

- `market_history`
- `benchmark_history`
- `derived_indicators`
- `portfolio_snapshot`
- `feature_snapshot`

Do not introduce a new input name unless the cross-platform contract docs are updated first.

## Runtime adapter requirements

Each strategy needs one base `StrategyRuntimeAdapter` spec in `UsEquityStrategies`.

The base adapter should declare strategy-owned metadata:

- required feature snapshot columns when the strategy uses `feature_snapshot`
- snapshot date/freshness rules when the artifact has date-sensitive content
- manifest requirements and contract version when a manifest is required
- runtime config loader only when the strategy genuinely needs an external config file

Platform-specific adapters are generated from:

- the strategy's `required_inputs`
- the strategy's `target_mode`
- the platform's native target mode
- the platform's declared capabilities

When a weight-mode strategy runs on a value-native platform, the generated adapter adds `portfolio_snapshot` so the platform can translate weights into dollar orders. When the strategy already requires `portfolio_snapshot`, the generated adapter maps it as the portfolio input automatically.

The adapter generator is the bridge between strategy contract and platform runtime. Strategy code should not branch on broker platform ids.

## Platform repository requirements

The three US equity platform repositories should stay thin:

- resolve the selected `STRATEGY_PROFILE`
- ask the shared strategy registry whether the profile is supported
- assemble `StrategyContext`
- load the unified entrypoint
- map `StrategyDecision` to broker-specific orders and notifications

The platform registry should derive live profiles from `UsEquityStrategies.get_runtime_enabled_profiles()`.

Platform repositories should not hard-code strategy symbol pools, private strategy constants, or manual live profile allowlists.

## Artifact-backed profiles

If a strategy uses `feature_snapshot`, the platform env sync workflow must enforce the artifact env vars before Cloud Run is updated. The workflow should derive this from `scripts/print_strategy_profile_status.py --json`, not from a hard-coded profile-name list.

Current env mapping:

| Platform | Snapshot path env | Manifest path env | Strategy config env |
| --- | --- | --- | --- |
| IBKR | `IBKR_FEATURE_SNAPSHOT_PATH` | `IBKR_FEATURE_SNAPSHOT_MANIFEST_PATH` | `IBKR_STRATEGY_CONFIG_PATH` |
| Schwab | `SCHWAB_FEATURE_SNAPSHOT_PATH` | `SCHWAB_FEATURE_SNAPSHOT_MANIFEST_PATH` | `SCHWAB_STRATEGY_CONFIG_PATH` |
| LongBridge | `LONGBRIDGE_FEATURE_SNAPSHOT_PATH` | `LONGBRIDGE_FEATURE_SNAPSHOT_MANIFEST_PATH` | `LONGBRIDGE_STRATEGY_CONFIG_PATH` |

Only profiles whose adapter requires a manifest should require the manifest path. Only profiles with a runtime config loader should require the strategy config path.

## Test gates

Before marking a new profile `runtime_enabled`, run:

- `QuantPlatformKit` strategy contract tests
- `UsEquityStrategies` contract governance and entrypoint tests
- IBKR runtime config, loader, runtime, and workflow tests
- LongBridge runtime config, loader, runtime, and workflow tests
- Schwab runtime config, loader, runtime, and workflow tests
- each platform's `scripts/print_strategy_profile_status.py --json`

`UsEquityStrategies` governance tests should fail if a `runtime_enabled` strategy does not have the expected generated platform adapter coverage.

## Release order

Use this order for a live rollout:

1. Merge and tag `QuantPlatformKit` if shared contracts changed.
2. Merge and tag `UsEquityStrategies`.
3. Update platform repository dependency pins to the released tags.
4. Merge the platform repositories.
5. Let Cloud Run source deployments build the platform repositories.
6. Enable or update GitHub-managed env sync values.
7. Verify Cloud Run env and the first runtime heartbeat.

Current pending tags for this change set:

- `QuantPlatformKit` -> `v0.7.16`
- `UsEquityStrategies` -> `v0.7.23`

## Permission-dependent steps

Local code, tests, and docs do not require GitHub or Google Cloud login.

These steps require credentials:

- pushing commits and tags with `gh` or `git`
- creating pull requests or releases
- updating GitHub repository variables, secrets, or environments
- creating or updating Workload Identity Federation bindings
- creating or updating Secret Manager secrets
- deploying or inspecting Cloud Run services
- creating or updating Cloud Scheduler jobs
- reading or writing GCS strategy artifacts
