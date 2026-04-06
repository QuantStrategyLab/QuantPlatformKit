# Next-window cleanup split plan

_Verified snapshot: 2026-04-07_

This document pre-splits the **next compatibility-window cleanup** into small PR-sized batches.

It is a planning document only.
Do **not** merge these removals early.
The current window still intentionally keeps rollback hooks.

## Scope

Remove only migration-window compatibility layers that were kept during PR1-PR6.

Do **not** use this cleanup window to:

- change any strategy formulas
- change thresholds or risk semantics
- refactor broker integrations beyond the boundary-removal work
- mix feature work into cleanup PRs

## Common release gates

Every removal PR below should wait until all of these are true:

1. the unified-entrypoint mainline has shipped for at least one stable release window
2. rollback to the previous release tag is still possible during the cutover
3. regression tests for the affected repo are green on the unified path
4. `rg` shows the legacy symbol is only referenced in the files being deleted or updated in that PR
5. any research or test-only imports have been moved off the compatibility shim first

## Recommended PR order

1. `NW1` QuantPlatformKit deprecated helper removal - done
2. `NW2` LongBridgePlatform allocation-loader removal - done
3. `NW3` CharlesSchwabPlatform allocation-loader removal - done
4. `NW4` UsEquityStrategies metadata lift for IB cleanup - done
5. `NW5` InteractiveBrokersPlatform legacy-module bridge removal - done
6. `NW6` BinancePlatform direct component-loader and main-wrapper removal - done

This order keeps the easy and low-coupling deletions first, and leaves the IB / Binance boundary cleanup for after their remaining test and adapter dependencies are gone.

## Execution status

- Completed on the current branch: `NW1`, `NW2`, `NW3`, `NW4`, `NW5`, `NW6`
- Remaining planned batch after that: none

---

## NW1 - QuantPlatformKit: remove deprecated global compatibility helpers

**Status:** completed on the current branch.

### Goal

Delete the migration-window helpers that were superseded by `StrategyCatalog` + `PlatformStrategyPolicy`.

### Repositories

- `QuantPlatformKit`

### Delete

- `src/quant_platform_kit/common/strategies.py`
  - `get_supported_profiles_for_platform(...)`
  - `resolve_strategy_definition(...)`
  - the deprecation warning strings and legacy call path that support them
- `src/quant_platform_kit/__init__.py`
  - legacy exports for the two deprecated helpers
- tests and docs that still assert the deprecated flow

### Keep

- `resolve_platform_strategy_definition(...)`
- `get_enabled_profiles_for_platform(...)`
- `build_platform_profile_matrix(...)`
- platform-local `strategy_registry.py` wrappers that already sit on top of the new policy/catalog API

### Current references to clean up

- `src/quant_platform_kit/common/strategies.py`
- `src/quant_platform_kit/__init__.py`
- `tests/test_strategies.py`
- `tests/test_strategy_contracts.py`
- `docs/strategy_contract_migration.md`

### Done when

- `rg -n "resolve_strategy_definition\(|get_supported_profiles_for_platform\(" .` in `QuantPlatformKit` only finds historical notes that were intentionally rewritten, or finds no runtime code at all
- tests cover only the catalog/policy path

### Suggested validation

```bash
cd /Users/lisiyi/Projects/QuantPlatformKit
python3 -m ruff check src tests
PYTHONPATH=src python3 -m unittest tests.test_strategy_contracts tests.test_strategies tests.test_models -v
```

---

## NW2 - LongBridgePlatform: remove allocation compatibility loader

**Status:** completed on the current branch.

### Goal

Delete the last platform-local allocation shim API now that `main.py` already runs through `strategy_runtime` + unified entrypoint.

### Repositories

- `LongBridgePlatform`

### Delete

- `strategy_loader.py`
  - `load_allocation_module(...)`
- tests that still verify allocation-module loading

### Current references to clean up

- `strategy_loader.py`
- `tests/test_strategy_loader.py`

### Preconditions

None beyond the common release gates.
The mainline path is already on `load_strategy_entrypoint_for_profile(...)`.

### Done when

- `rg -n "load_allocation_module\(" .` in `LongBridgePlatform` returns no matches
- loader tests only assert unified entrypoint loading

### Suggested validation

```bash
cd /Users/lisiyi/Projects/LongBridgePlatform
python3 -m ruff check strategy_loader.py tests/test_strategy_loader.py tests/test_strategy_runtime.py
PYTHONPATH=.:/Users/lisiyi/Projects/QuantPlatformKit/src:/Users/lisiyi/Projects/UsEquityStrategies/src python -m unittest \
  tests.test_strategy_loader tests.test_strategy_runtime tests.test_rebalance_service tests.test_request_handling -v
```

---

## NW3 - CharlesSchwabPlatform: remove allocation compatibility loader

**Status:** completed on the current branch.

### Goal

Do the same cleanup as LongBridge, but in the Schwab runtime.

### Repositories

- `CharlesSchwabPlatform`

### Delete

- `strategy_loader.py`
  - `load_allocation_module(...)`
- tests that still verify allocation-module loading

### Current references to clean up

- `strategy_loader.py`
- `tests/test_strategy_loader.py`

### Preconditions

None beyond the common release gates.
The mainline path is already on `load_strategy_entrypoint_for_profile(...)`.

### Done when

- `rg -n "load_allocation_module\(" .` in `CharlesSchwabPlatform` returns no matches
- loader tests only assert unified entrypoint loading

### Suggested validation

```bash
cd /Users/lisiyi/Projects/CharlesSchwabPlatform
python3 -m ruff check strategy_loader.py tests/test_strategy_loader.py tests/test_strategy_runtime.py
PYTHONPATH=.:/Users/lisiyi/Projects/QuantPlatformKit/src:/Users/lisiyi/Projects/UsEquityStrategies/src python -m unittest \
  tests.test_strategy_loader tests.test_strategy_runtime tests.test_rebalance_service tests.test_request_handling -v
```

---

## NW4 - UsEquityStrategies: lift the remaining IB-facing legacy metadata

**Status:** completed on the current branch. A typed runtime adapter now exists in `UsEquityStrategies`, and `InteractiveBrokersPlatform` now consumes it without the legacy signal-module fallback.

### Goal

Move the last **strategy-side** metadata that IB still reads through the legacy signal module into the unified side, so the platform can delete the legacy bridge in the next PR.

### Repositories

- `UsEquityStrategies`
- possibly `QuantPlatformKit` only if the existing manifest/default-config shape proves insufficient

### Strategy-side data still consumed through the IB legacy module today

`InteractiveBrokersPlatform/strategy_runtime.py` still reads these through `legacy_module`:

- `STATUS_ICON`
- `load_runtime_parameters(...)`
- `REQUIRED_FEATURE_COLUMNS`
- `SNAPSHOT_DATE_COLUMNS`
- `MAX_SNAPSHOT_MONTH_LAG`
- `REQUIRE_SNAPSHOT_MANIFEST`
- `SNAPSHOT_CONTRACT_VERSION`
- `extract_managed_symbols(...)`

### Recommended direction

Prefer one of these, in this order:

1. move the data into `manifest.default_config` when it is declarative
2. expose a strategy-side adapter object next to the unified entrypoint for IB-only snapshot/runtime metadata
3. only extend QuantPlatformKit contract types if the first two options are clearly not enough

Do **not** reintroduce platform-shaped return payloads into `StrategyDecision`.

### Done when

- IB runtime can build snapshot guards and managed-symbol metadata without importing the legacy signal module
- the strategy-side contract remains formula-neutral
- there is a regression test in `UsEquityStrategies` for the new metadata path

### Suggested validation

```bash
cd /Users/lisiyi/Projects/UsEquityStrategies
python3 -m ruff check src tests
PYTHONPATH=src:/Users/lisiyi/Projects/QuantPlatformKit/src python -m unittest tests.test_entrypoints tests.test_catalog -v
```

---

## NW5 - InteractiveBrokersPlatform: remove the legacy signal-module bridge

### Goal

Delete the remaining platform-side bridge to legacy signal modules after NW4 has moved the required metadata to the unified side.

### Repositories

- `InteractiveBrokersPlatform`
- depends on `UsEquityStrategies` work from `NW4`

### Delete

- `strategy_loader.py`
  - `load_signal_logic_module(...)`
- `strategy_runtime.py`
  - `legacy_module` field on `LoadedStrategyRuntime`
  - all `getattr(..., legacy_module, ...)` snapshot/runtime fallbacks
  - direct `load_runtime_parameters(...)` call through the legacy module
- `main.py`
  - `STRATEGY_LOGIC`
  - `strategy_check_sma`
  - `strategy_compute_13612w_momentum`
  - `strategy_compute_signals` (currently dead)
  - any wrapper logic that only exists to proxy legacy module helpers
- tests that still exercise `load_signal_logic_module(...)`

### Current references to clean up

- `strategy_loader.py`
- `strategy_runtime.py`
- `main.py`
- `tests/test_strategy_loader.py`

### Additional notes

`compute_signals(...)` stays.
It is the platform mainline entry into `STRATEGY_RUNTIME.evaluate(...)` and `decision_mapper.map_strategy_decision(...)`.
Only the legacy module bridge should go away.

### Done when

- `rg -n "load_signal_logic_module\(|\bSTRATEGY_LOGIC\b" .` in `InteractiveBrokersPlatform` returns no runtime matches
- snapshot guard configuration comes from the unified side only
- IB smoke/regression tests still pass with no behavior drift

### Suggested validation

```bash
cd /Users/lisiyi/Projects/InteractiveBrokersPlatform
python3 -m ruff check main.py strategy_loader.py strategy_runtime.py tests/test_strategy_loader.py tests/test_strategy_runtime.py
PYTHONPATH=.:/Users/lisiyi/Projects/QuantPlatformKit/src:/Users/lisiyi/Projects/UsEquityStrategies/src ./.venv/bin/python -m pytest \
  tests/test_strategy_loader.py \
  tests/test_strategy_runtime.py \
  tests/test_decision_mapper.py \
  tests/test_rebalance_service.py \
  tests/test_request_handling.py \
  tests/test_runtime_config_support.py -q
```

---

## NW6 - BinancePlatform: remove direct core/rotation component loading and main-level compatibility wrappers

**Status:** completed on the current branch.

### Goal

Finish the platform-side cleanup so Binance only loads the unified entrypoint and decision mappers, while research/tests use either unified runtime outputs or explicit upstream strategy imports.

### Repositories

- `BinancePlatform`
- optional follow-up in `CryptoStrategies` only if an extra typed helper is still missing

### Delete from platform runtime code

- `strategy_loader.py`
  - `load_strategy_component(...)`
- `strategy_runtime.py`
  - `core_module`
  - `rotation_module`
  - temporary helper methods:
    - `compute_allocation_budgets(...)`
    - `get_dynamic_btc_base_order(...)`
    - `allocate_trend_buy_budget(...)`
    - `refresh_rotation_pool(...)`
- `main.py`
  - `get_dynamic_btc_target_ratio(...)`
  - `get_dynamic_btc_base_order(...)`
  - `rank_normalize(...)`
  - `build_stable_quality_pool(...)`
  - `refresh_rotation_pool(...)`
  - `select_rotation_weights(...)`
  - `allocate_trend_buy_budget(...)`

### Current references that must move first

- `tests/test_strategy_loader.py`
  - currently still asserts `load_strategy_component(...)`
- `tests/test_trend_pool_loading.py`
  - currently patches `main.build_stable_quality_pool(...)` and calls `main.refresh_rotation_pool(...)`
- `research/backtest.py`
  - still calls `get_dynamic_btc_base_order(...)`
- any remaining tests that import main-level compatibility wrappers instead of using unified runtime output or explicit `crypto_strategies` imports

### Preferred migration targets

- use `StrategyDecision.diagnostics` for runtime-facing BTC / trend-rotation facts
- import explicit upstream modules from `CryptoStrategies` in research-only code when a helper is intentionally research-only
- keep platform runtime code on `load_strategy_entrypoint_for_profile(...)` only

### Done when

- `rg -n "load_strategy_component\(|get_dynamic_btc_target_ratio\(|get_dynamic_btc_base_order\(|build_stable_quality_pool\(|refresh_rotation_pool\(|select_rotation_weights\(|allocate_trend_buy_budget\(" .` in `BinancePlatform` only finds intended research-side upstream imports or returns no matches for platform runtime code
- `strategy_runtime.py` loads the unified entrypoint only
- loader tests no longer assert direct `core` / `rotation` module resolution

### Suggested validation

```bash
cd /Users/lisiyi/Projects/BinancePlatform
python3 -m ruff check main.py strategy_loader.py strategy_runtime.py research/backtest.py tests
PYTHONPATH=.:/Users/lisiyi/Projects/QuantPlatformKit/src:/Users/lisiyi/Projects/CryptoStrategies/src python -m unittest discover -s tests -p 'test_*.py' -v
```

---

## Cross-repo grep checklist before opening removal PRs

Use these quick checks before starting each deletion batch:

```bash
for repo in QuantPlatformKit InteractiveBrokersPlatform LongBridgePlatform CharlesSchwabPlatform BinancePlatform; do
  echo "===== $repo ====="
  cd /Users/lisiyi/Projects/$repo || exit 1
  rg -n "resolve_strategy_definition\(|get_supported_profiles_for_platform\(|load_signal_logic_module\(|STRATEGY_LOGIC\b|load_allocation_module\(|load_strategy_component\(|get_dynamic_btc_target_ratio\(|get_dynamic_btc_base_order\(|build_stable_quality_pool\(|refresh_rotation_pool\(|select_rotation_weights\(|allocate_trend_buy_budget\(" . --glob '!**/__pycache__/**'
  echo
 done
```

If that output still shows runtime or test references outside the PR scope, split again before deleting.
