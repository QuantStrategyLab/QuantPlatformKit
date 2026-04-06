# Strategy contract migration notes

## What changed in PR1

QuantPlatformKit now provides a shared strategy contract for the platform/strategy split:

- `quant_platform_kit.strategy_contracts.StrategyManifest`
- `quant_platform_kit.strategy_contracts.StrategyContext`
- `quant_platform_kit.strategy_contracts.StrategyDecision`
- `quant_platform_kit.strategy_contracts.StrategyEntrypoint`
- `quant_platform_kit.strategy_contracts.StrategyRuntimeAdapter`
- `quant_platform_kit.common.strategies.load_strategy_entrypoint(...)`
- `quant_platform_kit.common.strategies.validate_strategy_manifest(...)`
- `quant_platform_kit.common.strategies.validate_strategy_decision(...)`
- `quant_platform_kit.common.strategy_contracts.validate_strategy_runtime_adapter(...)`

PR1 kept the old global compatibility helpers for one compatibility window.
They have now been removed in the next-window cleanup batch; platforms should use
`resolve_platform_strategy_definition(...)` and `get_enabled_profiles_for_platform(...)`.

## How strategy repos should migrate next

### 1. Add manifest + evaluate entrypoint per live profile

Each profile should expose either:

- an explicit `entrypoint` object, or
- a module-level `manifest` + `evaluate(ctx)` pair.

Recommended import target for downstream platforms:

```python
from quant_platform_kit.common.strategies import load_strategy_entrypoint
```

### 2. Keep legacy component modules during the migration window

`load_strategy_entrypoint(...)` resolves candidates in this order:

1. `StrategyDefinition.entrypoint`
2. a catalog component named `entrypoint`
3. existing legacy component modules that now expose `entrypoint`, or `manifest` + `evaluate`

That means strategy repos can add the new contract without deleting legacy `signal_logic`, `allocation`, `core`, or `rotation` modules in the same PR.

### 3. Move platform-only fields out of strategy returns

The new `StrategyDecision` only keeps:

- `positions`
- `budgets`
- `risk_flags`
- `diagnostics`

Fields such as `sell_order_symbols`, `buy_order_symbols`, `portfolio_rows`, `cash_sweep_symbol`, and other broker/UI ordering hints should move to platform-side decision mappers in later PRs.

### 4. Move platform-side runtime metadata behind a typed adapter when needed

Some platforms still need strategy-owned runtime metadata during the migration window.

For IBKR feature-snapshot profiles, that metadata now moves behind:

- `StrategyRuntimeAdapter`
- strategy-repo getter functions such as `get_platform_runtime_adapter(profile, platform_id=...)`

Use this adapter for strategy-owned runtime metadata such as:

- status icon defaults
- required feature snapshot columns
- snapshot contract / manifest expectations
- managed-symbol extraction helpers
- temporary runtime-config loaders kept during the migration window

Do not move broker execution fields back into `StrategyDecision`.

## Platform migration expectations

Platform repos should gradually switch from:

- `resolve_strategy_definition(...)`
- `load_strategy_component_module(...)`

to:

- `resolve_platform_strategy_definition(...)`
- `load_strategy_entrypoint(...)`
- platform-local decision mappers

During the compatibility window, old component loaders may stay in place behind feature flags or rollback paths.

## Cross-repo follow-up

- `UsEquityStrategies`: add per-profile manifest + entrypoint adapters for every live profile.
- `CryptoStrategies`: add `crypto_leader_rotation` entrypoint and artifact/input manifest declarations.
- `InteractiveBrokersPlatform`: stop reading strategy private constants in `main.py`, consume unified decisions via a mapper.
- `LongBridgePlatform` / `CharlesSchwabPlatform`: remove allocation shims and hard-coded strategy asset lists.
- `BinancePlatform`: replace `core` / `rotation` shims with a unified entrypoint and explicit artifact contract.

## PR6 cleanup status

### Mainline status by repository

| Repository | Mainline execution path | Compatibility window still kept |
| --- | --- | --- |
| `InteractiveBrokersPlatform` | `main.py` -> `strategy_runtime.load_strategy_runtime(...)` -> unified entrypoint -> `decision_mapper.map_strategy_decision(...)` | no legacy signal-module bridge remains. |
| `LongBridgePlatform` | `main.py` -> `strategy_runtime.load_strategy_runtime(...)` -> unified entrypoint -> `decision_mapper.map_strategy_decision_to_plan(...)` | no platform-local allocation loader remains. |
| `CharlesSchwabPlatform` | `main.py` -> `strategy_runtime.load_strategy_runtime(...)` -> unified entrypoint -> `decision_mapper.map_strategy_decision_to_plan(...)` | no platform-local allocation loader remains. |
| `BinancePlatform` | `main.py` / cycle services -> `strategy_runtime.load_strategy_runtime(...)` -> unified entrypoint -> decision mappers | no direct component loader or main/runtime compatibility wrapper remains. |

### Cleanup completed in the current window

- Strategy repositories now expose manifest + entrypoint adapters for live profiles without changing trading formulas.
- `UsEquityStrategies` now also exposes a typed IBKR runtime adapter for migration-window snapshot/runtime metadata.
- Platform-only output fields remain outside `StrategyDecision`; platforms now derive orders and notifications through local mappers.
- `BinancePlatform` removed repo-local `strategy_core.py` and `strategy/rotation.py`; live-pool loading now follows an explicit artifact contract instead of assuming a sibling checkout is the only source.
- `LongBridgePlatform` and `CharlesSchwabPlatform` mainline flows no longer pass long chains of strategy-specific allocation arguments through `main.py`.
- `QuantPlatformKit` removed the deprecated global resolver helpers after one full compatibility window.
- `LongBridgePlatform` and `CharlesSchwabPlatform` removed `load_allocation_module(...)`; loaders now expose unified entrypoints only.
- `InteractiveBrokersPlatform` removed `load_signal_logic_module(...)`, `STRATEGY_LOGIC`, and the legacy snapshot/runtime fallback path; runtime metadata now comes from `UsEquityStrategies.get_platform_runtime_adapter(...)` only.
- `BinancePlatform` removed `load_strategy_component(...)`, direct `core` / `rotation` loading, and the temporary main/runtime wrapper helpers; runtime and execution now stay on unified entrypoints plus decision mappers only.

### Compatibility APIs intentionally kept for one more window

No platform-local compatibility API from PR1-PR6 is intentionally kept after the current cleanup batches.

### Next-window removals

Remove these only after the next platform release has shipped on the unified entrypoint path and rollback is no longer needed:

No remaining platform-runtime cleanup item is pending from this migration track.

Detailed repo-by-repo split: [`next_window_cleanup_split.md`](./next_window_cleanup_split.md)

### Cross-repo dependency notes

- Platform repos depend on `QuantPlatformKit` for contract types, loader validation, and shared broker helpers.
- `InteractiveBrokersPlatform`, `LongBridgePlatform`, and `CharlesSchwabPlatform` depend on `UsEquityStrategies` entrypoints staying API-compatible for at least one window.
- `BinancePlatform` depends on `CryptoStrategies` entrypoints plus the explicit live-pool artifact contract; sibling repo checkout is only an optional fallback now.
- `InteractiveBrokersPlatform` now depends on `UsEquityStrategies.get_platform_runtime_adapter(...)` for runtime metadata on the unified path.
