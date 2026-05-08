# US equity strategy switch and rollback runbook

This document is the operational runbook for switching US equity strategy profiles on the current broker platforms.

Use this after the shared package and platform code is already deployed.

Do **not** use it to justify switching a profile that is not already supported by the platform status matrix.

The current control plane carries `RuntimeTarget` / `RUNTIME_TARGET_JSON` for service identity, while `STRATEGY_PROFILE` remains the compatibility selector for strategy routing.

## Scope

Configurable US equity profiles:

- `global_etf_rotation`
- `mega_cap_leader_rotation_top50_balanced`
- `russell_1000_multi_factor_defensive`
- `soxl_soxx_trend_income`
- `tqqq_growth_income`
- `tech_communication_pullback_enhancement`

Note: older deployments may still accept `qqq_tech_enhancement` as a legacy alias for `tech_communication_pullback_enhancement`, but runbooks should use the canonical profile name.

Runtime platforms:

- `ibkr`
- `schwab`
- `longbridge`

For the current six-profile scope, all three broker platforms report the runtime-enabled matrix as `eligible=true` and `enabled=true`. That means switching among these supported profiles is an operational change, not a strategy-contract migration.

## Operational profile groups

Treat the profiles as two operational groups:

- **Direct-runtime profiles**
  - `global_etf_rotation`
  - `tqqq_growth_income`
  - `soxl_soxx_trend_income`
- **Snapshot-backed profiles**
  - `mega_cap_leader_rotation_top50_balanced`
  - `russell_1000_multi_factor_defensive`
  - `tech_communication_pullback_enhancement`

The platform scripts now expose this view directly:

- `input_mode`
- `requires_snapshot_artifacts`
- `requires_snapshot_manifest_path`
- `requires_strategy_config_path`
- `config_source_policy`
- `reconciliation_output_policy`
- `runtime_execution_window_trading_days`

So the operator does not need to remember the distinction from profile names alone.

## Standard switch path

Use the same path every time:

1. verify the target profile is `eligible=true` and `enabled=true`
2. update the GitHub-managed runtime variables for the target service
3. rerun or wait for `Sync Cloud Run Env`
4. verify the Cloud Run env on the service
5. verify the first heartbeat or execution notification

Do not change service names as part of a strategy switch.

## Service inventory

| Platform | Service | Identity split |
| --- | --- | --- |
| IBKR | `interactive-brokers-quant-service` | `ACCOUNT_GROUP` |
| Schwab | `charles-schwab-quant-service` | single service |
| LongBridge HK | `longbridge-quant-hk-service` | `ACCOUNT_REGION=HK` |
| LongBridge SG | `longbridge-quant-sg-service` | `ACCOUNT_REGION=SG` |

## Step 1: verify the target profile before touching env

Run the platform status script inside the platform repo.

### IBKR

```bash
cd /Users/lisiyi/Projects/InteractiveBrokersPlatform
PYTHONPATH=/Users/lisiyi/Projects/QuantPlatformKit/src:/Users/lisiyi/Projects/UsEquityStrategies/src:. \
  .venv/bin/python scripts/print_strategy_profile_status.py --json
```

### Schwab

```bash
cd /Users/lisiyi/Projects/CharlesSchwabPlatform
PYTHONPATH=/Users/lisiyi/Projects/QuantPlatformKit/src:/Users/lisiyi/Projects/UsEquityStrategies/src:. \
  /Users/lisiyi/Projects/LongBridgePlatform/.venv/bin/python scripts/print_strategy_profile_status.py --json
```

### LongBridge

```bash
cd /Users/lisiyi/Projects/LongBridgePlatform
PYTHONPATH=/Users/lisiyi/Projects/QuantPlatformKit/src:/Users/lisiyi/Projects/UsEquityStrategies/src:. \
  .venv/bin/python scripts/print_strategy_profile_status.py --json
```

Required result:

- the target `canonical_profile` exists
- `eligible` is `true`
- `enabled` is `true`

If any of those checks fail, stop. That is a code or rollout problem, not a live switch problem.

## Step 2: know which extra envs the selected runtime still needs

| Profile | Extra runtime inputs beyond `RUNTIME_TARGET_JSON` / `STRATEGY_PROFILE` |
| --- | --- |
| `global_etf_rotation` | none |
| `mega_cap_leader_rotation_top50_balanced` | feature snapshot path + snapshot manifest path |
| `russell_1000_multi_factor_defensive` | feature snapshot path |
| `soxl_soxx_trend_income` | none |
| `tqqq_growth_income` | none |
| `tech_communication_pullback_enhancement` | feature snapshot path + snapshot manifest path; strategy config path is optional unless the rollout overrides the packaged config |

Notes:

- `tech_communication_pullback_enhancement` on IBKR may also keep a reconciliation output path when the deployment wants that artifact.
- `tech_communication_pullback_enhancement` now has `config_source_policy=bundled_or_env`, so the packaged canonical config is used unless an env path is deliberately set.
- `russell_1000_multi_factor_defensive` currently requires the snapshot path but not a manifest path.
- When switching away from a feature-snapshot profile, remove stale snapshot/config envs from the service instead of leaving them behind.

## Step 3: update GitHub-managed runtime variables

Preferred operational path:

- update GitHub repository variables or environment variables
- let `.github/workflows/sync-cloud-run-env.yml` apply the change
- keep `RUNTIME_TARGET_JSON` aligned with the selected service, region, and account identity

### IBKR

Required:

- `RUNTIME_TARGET_JSON`
- `STRATEGY_PROFILE`
- `ACCOUNT_GROUP`
- `IB_ACCOUNT_GROUP_CONFIG_SECRET_NAME`

Optional:

- `IBKR_DRY_RUN_ONLY`

Feature-snapshot profiles additionally need:

- `IBKR_FEATURE_SNAPSHOT_PATH`
- `IBKR_FEATURE_SNAPSHOT_MANIFEST_PATH` when the selected profile requires a manifest
- `IBKR_STRATEGY_CONFIG_PATH` only when `config_source_policy=env_only`, or as an explicit override for `bundled_or_env`

Remove when not needed:

- `IBKR_FEATURE_SNAPSHOT_PATH`
- `IBKR_FEATURE_SNAPSHOT_MANIFEST_PATH`
- `IBKR_STRATEGY_CONFIG_PATH`
- `IBKR_RECONCILIATION_OUTPUT_PATH`

### Schwab

Required:

- `RUNTIME_TARGET_JSON`
- `STRATEGY_PROFILE`

Optional:

- `SCHWAB_DRY_RUN_ONLY`

Feature-snapshot profiles additionally need:

- `SCHWAB_FEATURE_SNAPSHOT_PATH`
- `SCHWAB_FEATURE_SNAPSHOT_MANIFEST_PATH` when the selected profile requires a manifest
- `SCHWAB_STRATEGY_CONFIG_PATH` only when `config_source_policy=env_only`, or as an explicit override for `bundled_or_env`

Remove when not needed:

- `SCHWAB_FEATURE_SNAPSHOT_PATH`
- `SCHWAB_FEATURE_SNAPSHOT_MANIFEST_PATH`
- `SCHWAB_STRATEGY_CONFIG_PATH`

### LongBridge

Required:

- `RUNTIME_TARGET_JSON`
- `STRATEGY_PROFILE`
- `ACCOUNT_PREFIX`
- `ACCOUNT_REGION`
- `LONGPORT_SECRET_NAME`
- `LONGPORT_APP_KEY_SECRET_NAME`
- `LONGPORT_APP_SECRET_SECRET_NAME`

Optional:

- `LONGBRIDGE_DRY_RUN_ONLY`

Feature-snapshot profiles additionally need:

- `LONGBRIDGE_FEATURE_SNAPSHOT_PATH`
- `LONGBRIDGE_FEATURE_SNAPSHOT_MANIFEST_PATH` when the selected profile requires a manifest
- `LONGBRIDGE_STRATEGY_CONFIG_PATH` only when `config_source_policy=env_only`, or as an explicit override for `bundled_or_env`

Remove when not needed:

- `LONGBRIDGE_FEATURE_SNAPSHOT_PATH`
- `LONGBRIDGE_FEATURE_SNAPSHOT_MANIFEST_PATH`
- `LONGBRIDGE_STRATEGY_CONFIG_PATH`

## Step 4: rerun env sync and verify Cloud Run

Wait for the platform workflow to finish:

- `Sync Cloud Run Env`

Then verify the service directly.

### Example checks

```bash
gcloud run services describe interactive-brokers-quant-service \
  --project interactivebrokersquant \
  --region us-central1 \
  --format='flattened(spec.template.spec.containers[0].env[])'
```

```bash
gcloud run services describe charles-schwab-quant-service \
  --project charlesschwabquant \
  --region us-central1 \
  --format='flattened(spec.template.spec.containers[0].env[])'
```

```bash
gcloud run services describe longbridge-quant-hk-service \
  --project longbridgequant \
  --region asia-east2 \
  --format='flattened(spec.template.spec.containers[0].env[])'
```

```bash
gcloud run services describe longbridge-quant-sg-service \
  --project longbridgequant \
  --region asia-southeast1 \
  --format='flattened(spec.template.spec.containers[0].env[])'
```

Verify:

- `STRATEGY_PROFILE` matches the intended target
- feature-snapshot envs exist only for feature-snapshot profiles
- stale dry-run or artifact envs were removed when the new profile does not need them

## Step 5: verify the first runtime output

Do not stop at Cloud Run env.

Verify the first heartbeat or execution notification shows:

- the expected display name
- the expected account prefix (`[HK]` / `[SG]` for LongBridge)
- no stale strategy-specific service-name suffix in the LongBridge notification prefix

If the profile uses feature snapshots, also verify:

- the snapshot file exists at the configured path
- the manifest matches the expected contract version
- the managed symbols in the first notification match the intended strategy

## Common switch examples

Use these as concrete templates. They are not the only valid switches, but they cover the most common operational paths.

### Example A: switch IBKR to `tqqq_growth_income`

Set:

- `STRATEGY_PROFILE=<runtime_enabled us_equity profile>`
- keep `ACCOUNT_GROUP`
- keep `IB_ACCOUNT_GROUP_CONFIG_SECRET_NAME`

Remove if present:

- `IBKR_FEATURE_SNAPSHOT_PATH`
- `IBKR_FEATURE_SNAPSHOT_MANIFEST_PATH`
- `IBKR_STRATEGY_CONFIG_PATH`
- `IBKR_RECONCILIATION_OUTPUT_PATH`

Why:

- `tqqq_growth_income` only needs `benchmark_history + portfolio_snapshot`
- it does not use the feature-snapshot artifact chain

### Example B: switch Schwab to `tech_communication_pullback_enhancement`

Set:

- `STRATEGY_PROFILE=<runtime_enabled us_equity profile>`
- `SCHWAB_FEATURE_SNAPSHOT_PATH`
- `SCHWAB_FEATURE_SNAPSHOT_MANIFEST_PATH`

Optional override:

- `SCHWAB_STRATEGY_CONFIG_PATH`

Keep or remove separately depending on the rollout choice:

- `SCHWAB_DRY_RUN_ONLY`

Why:

- `tech_communication_pullback_enhancement` is a feature-snapshot profile
- the strategy has a packaged canonical config; set the env path only when overriding it

### Example C: switch LongBridge HK to `russell_1000_multi_factor_defensive`

Keep:

- `ACCOUNT_PREFIX=HK`
- `ACCOUNT_REGION=HK`
- `LONGPORT_SECRET_NAME`
- `LONGPORT_APP_KEY_SECRET_NAME`
- `LONGPORT_APP_SECRET_SECRET_NAME`

Set:

- `STRATEGY_PROFILE=russell_1000_multi_factor_defensive`
- `LONGBRIDGE_FEATURE_SNAPSHOT_PATH`

Remove if present:

- `LONGBRIDGE_FEATURE_SNAPSHOT_MANIFEST_PATH`
- `LONGBRIDGE_STRATEGY_CONFIG_PATH`

Why:

- Russell uses the feature snapshot contract
- it currently requires the snapshot path but not the manifest or strategy config path

### Example D: switch LongBridge SG back to a non-snapshot profile

Keep:

- `ACCOUNT_PREFIX=SG`
- `ACCOUNT_REGION=SG`

Set one of:

- `STRATEGY_PROFILE=<runtime_enabled us_equity profile>`
- `STRATEGY_PROFILE=<runtime_enabled us_equity profile>`
- `STRATEGY_PROFILE=global_etf_rotation`

Remove if present:

- `LONGBRIDGE_FEATURE_SNAPSHOT_PATH`
- `LONGBRIDGE_FEATURE_SNAPSHOT_MANIFEST_PATH`
- `LONGBRIDGE_STRATEGY_CONFIG_PATH`

Decide separately:

- whether `LONGBRIDGE_DRY_RUN_ONLY` should stay or be removed

Why:

- non-snapshot profiles do not need the feature-snapshot artifact chain
- SG often carries dry-run as an operational choice, not as a profile requirement

## Rollback rules

Rollback is simple if you keep it operational:

1. restore the last known good `STRATEGY_PROFILE`
2. restore or remove the companion snapshot/config envs so they match that profile
3. rerun `Sync Cloud Run Env`
4. verify Cloud Run env again
5. verify the next heartbeat or execution notification

Do not use any of these as rollback mechanisms:

- old service names
- ad hoc local edits on Cloud Run
- partially reverting only one feature-snapshot env

If the service cannot start after a switch:

1. revert the service env first
2. only then investigate code or dependency issues

## Recommended operator checklist

For every live switch, record these five items in the change note or operator log:

1. service name
2. old profile
3. new profile
4. extra envs added or removed
5. first successful heartbeat or execution timestamp
