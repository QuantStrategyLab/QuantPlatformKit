# US Equity release and cutover plan

This document is the operational follow-up to:

- `docs/us_equity_cross_platform_strategy_spec.md`
- `docs/us_equity_execution_translation_spec.md`

It focuses on one thing only:

- how to release the shared packages safely
- how to move the live platform services to the intended strategy profiles

It does **not** redefine strategy formulas.

## Why this plan exists

The local refactor now spans three repositories and two shared packages:

- `QuantPlatformKit`
- `UsEquityStrategies`
- `InteractiveBrokersPlatform`
- `CharlesSchwabPlatform`
- `LongBridgePlatform`

The platform services do not install local sibling checkouts directly. They install fixed Git tags from:

- `quant-platform-kit`
- `us-equity-strategies`

That means Cloud Run cutover must happen in this order:

1. release shared packages
2. update platform dependency pins
3. deploy platform repos
4. change live strategy profiles only after the new code is actually live

## Current baseline

### Shared package versions

- `QuantPlatformKit`: `0.7.8`
- `UsEquityStrategies`: `0.7.11`

### Current platform requirements pins

| Repository | `quant-platform-kit` | `us-equity-strategies` |
| --- | --- | --- |
| `InteractiveBrokersPlatform` | `v0.7.7` | `v0.7.7` |
| `CharlesSchwabPlatform` | `v0.7.8` | `v0.7.10` |
| `LongBridgePlatform` | `v0.7.8` | `v0.7.11` |

This mismatch is the main release risk. The local runtime refactor is already ahead of the deployed tags.

## Proposed next release bundle

Recommended target tags for the next bundle:

- `QuantPlatformKit` -> `v0.7.10`
- `UsEquityStrategies` -> `v0.7.13`

Reason:

- `UsEquityStrategies` depends on `QuantPlatformKit`
- the new runtime and execution helpers live in `QuantPlatformKit`
- `UsEquityStrategies` should only move after the new QPK tag exists

## Release order

### Step 1: release `QuantPlatformKit`

Expected contents:

- execution translation helpers
- feature snapshot shared loader
- cross-platform runtime input helpers
- IBKR runtime input helpers

Output:

- tag `v0.7.10`

### Step 2: update and release `UsEquityStrategies`

Change:

- bump its QPK dependency to `quant-platform-kit @ ...@v0.7.10`

Output:

- tag `v0.7.13`

### Step 3: bump platform repo requirements

After both tags exist, update all three platform repos to:

| Repository | `quant-platform-kit` | `us-equity-strategies` |
| --- | --- | --- |
| `InteractiveBrokersPlatform` | `v0.7.10` | `v0.7.13` |
| `CharlesSchwabPlatform` | `v0.7.10` | `v0.7.13` |
| `LongBridgePlatform` | `v0.7.10` | `v0.7.13` |

Important:

- do **not** point requirements at tags that do not exist yet
- do **not** cut live env first and hope deployment catches up later

### Step 4: deploy platform repos

Deploy each platform repo after its requirements are updated and merged.

Minimum deployment rule:

- the deployed commit must contain the new requirement pins
- the deployed image must be confirmed before changing live strategy env

## Command checklist

Use this sequence as-is, with commits reviewed before tagging.

### 1) Release `QuantPlatformKit` as `v0.7.10`

```bash
cd /Users/lisiyi/Projects/QuantPlatformKit
git diff --check
./.venv/bin/python -m unittest tests.test_strategy_contracts
PYTHONPATH=src /Users/lisiyi/Projects/LongBridgePlatform/.venv/bin/python -m unittest \
  tests.test_strategy_contracts \
  tests.test_ibkr_runtime_inputs \
  tests.test_longbridge_portfolio

git add README.md README.zh-CN.md pyproject.toml src tests docs
git commit -m "Prepare v0.7.10 release"
git tag v0.7.10
git push origin HEAD
git push origin v0.7.10
```

### 2) Release `UsEquityStrategies` as `v0.7.13`

```bash
cd /Users/lisiyi/Projects/UsEquityStrategies
git diff --check
PYTHONPATH=/Users/lisiyi/Projects/QuantPlatformKit/src:src \
  /Users/lisiyi/Projects/LongBridgePlatform/.venv/bin/python -m unittest \
  tests.test_catalog \
  tests.test_entrypoints \
  tests.test_platform_registry_support

git add README.md pyproject.toml src tests docs
git commit -m "Prepare v0.7.13 release"
git tag v0.7.13
git push origin HEAD
git push origin v0.7.13
```

### 3) Update platform repos after both tags exist

```bash
cd /Users/lisiyi/Projects/InteractiveBrokersPlatform
git diff --check
git add requirements.txt
git commit -m "Bump shared strategy package pins"
git push origin HEAD

cd /Users/lisiyi/Projects/CharlesSchwabPlatform
git diff --check
git add requirements.txt
git commit -m "Bump shared strategy package pins"
git push origin HEAD

cd /Users/lisiyi/Projects/LongBridgePlatform
git diff --check
git add requirements.txt
git commit -m "Bump shared strategy package pins"
git push origin HEAD
```

If any repo still has unrelated local edits, split or stash them before creating the release commit.

## Strategy selector cutover pattern

| Platform service | Intended strategy profile | Notes |
| --- | --- | --- |
***REMOVED***
| `longbridge-quant-hk-service` | `qqq_tech_enhancement` | HK should move to QQQ Tech Enhancement |
***REMOVED***
***REMOVED***

## Cutover env changes

### CharlesSchwabPlatform

Service:

- `charles-schwab-quant-service`

Set:

- `STRATEGY_PROFILE=<runtime_enabled us_equity profile>`

Remove:

- `SCHWAB_DRY_RUN_ONLY` unless a dry-run rollback is explicitly wanted

### LongBridgePlatform HK

Service:

- `longbridge-quant-hk-service`

Set:

- `ACCOUNT_PREFIX=HK`
- `ACCOUNT_REGION=HK`
- `STRATEGY_PROFILE=qqq_tech_enhancement`
- `LONGBRIDGE_FEATURE_SNAPSHOT_PATH`
- `LONGBRIDGE_FEATURE_SNAPSHOT_MANIFEST_PATH`
- `LONGBRIDGE_STRATEGY_CONFIG_PATH`

Keep unset unless explicitly needed:

- `LONGBRIDGE_DRY_RUN_ONLY`

Reason:

- `qqq_tech_enhancement` is a feature snapshot strategy
- HK cutover is not only a profile switch; it also needs snapshot/config inputs

### LongBridgePlatform SG

Service:

- `longbridge-quant-sg-service`

Set:

- `ACCOUNT_PREFIX=SG`
- `ACCOUNT_REGION=SG`
- `STRATEGY_PROFILE=<runtime_enabled us_equity profile>`

Keep current dry-run choice unless separately changed:

- `LONGBRIDGE_DRY_RUN_ONLY`

Remove if present:

- `LONGBRIDGE_FEATURE_SNAPSHOT_PATH`
- `LONGBRIDGE_FEATURE_SNAPSHOT_MANIFEST_PATH`
- `LONGBRIDGE_STRATEGY_CONFIG_PATH`

### InteractiveBrokersPlatform

Service:

- `interactive-brokers-quant-service`

Set:

- `STRATEGY_PROFILE=<runtime_enabled us_equity profile>`

Keep as-is unless the live rollout decision changes:

- `IBKR_DRY_RUN_ONLY`
- `ACCOUNT_GROUP`

Remove the tech-specific feature snapshot envs after switching away from `qqq_tech_enhancement`:

- `IBKR_FEATURE_SNAPSHOT_PATH`
- `IBKR_FEATURE_SNAPSHOT_MANIFEST_PATH`
- `IBKR_STRATEGY_CONFIG_PATH`
- `IBKR_RECONCILIATION_OUTPUT_PATH`

Reason:

- `soxl_soxx_trend_income` now uses canonical `derived_indicators + portfolio_snapshot`
- it does not need the tech feature snapshot artifact chain

## Verification checklist

### Before changing live env

For each platform repo:

1. verify `requirements.txt` pins the intended QPK / UES tags
2. run the platform test subset most relevant to strategy runtime
3. deploy
4. verify the new commit SHA is actually on Cloud Run

### After changing live env

Verify with `gcloud run services describe ...`:

- `CLOUD_RUN_SERVICE` points to the intended service
- `STRATEGY_PROFILE` matches the intended profile
- feature snapshot envs exist only where needed
- stale feature snapshot envs are removed from services that no longer use them

Then verify the first heartbeat / execution notification:

***REMOVED***
- LongBridge HK -> `QQQ Tech Enhancement`
- LongBridge SG -> `TQQQ Growth Income`
***REMOVED***

## Rollback rules

Rollback should happen in the reverse order:

1. revert live env if the deployed runtime is wrong
2. revert platform repo requirements if the package bundle is bad
3. only then consider rolling back shared package tags by releasing a newer fix tag

Do not reuse old service names or old strategy-coded service naming as a rollback mechanism.
