# ADR 0004: Unify Platform Strategy Loader via QPK Shared Module

**Date**: 2026-06-30
**Status**: Accepted

## Context

Four Cloud Run-based platform repos (InteractiveBrokersPlatform, LongBridgePlatform, CharlesSchwabPlatform, FirstradePlatform) each contained an identical `strategy_loader.py` implementing a 3-function pattern:

```python
def load_strategy_definition(raw_profile)
def load_strategy_entrypoint_for_profile(raw_profile)
def load_strategy_runtime_adapter_for_profile(raw_profile)
```

This created a Shotgun Surgery anti-pattern: any change to the strategy loading contract required updating 4 repos with identical code.

## Decision

Extract the shared strategy loading logic into `quant_platform_kit.common.platform_runner.loader`:

- `load_strategy_definition()` — resolves a profile string to a `StrategyDefinition`
- `load_strategy_entrypoint_for_profile()` — loads the entrypoint with runtime adapter
- `load_strategy_runtime_adapter_for_profile()` — loads the runtime adapter

Each platform repo retains a thin `strategy_loader.py` wrapper that delegates to the QPK module, customizing only the `platform_id` constant.

## Consequences

- **Positive**: Single implementation to maintain and test
- **Positive**: Adding a new platform requires only a one-line platform_id constant change
- **Negative**: Required updating all 4 platform repos simultaneously
- **Negative**: Initially caused `ModuleNotFoundError` on Cloud Run because Docker images had older QPK without the `platform_runner.loader` module — resolved by rebuilding images after QPK SHA sync
- **Neutral**: The 3-function API remains unchanged; existing callers are unaffected
