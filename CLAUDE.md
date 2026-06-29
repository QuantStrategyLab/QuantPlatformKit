# QuantPlatformKit - Shared Infrastructure

Shared broker adapters, runtime contracts, strategy loading interfaces, and notification utilities for QuantStrategyLab trading platforms.

## Key Files

- `src/quant_platform_kit/common/strategies.py` — StrategyCatalog, PlatformCapabilityMatrix, PlatformStrategyPolicy
- `src/quant_platform_kit/common/runtime_target.py` — RUNTIME_TARGET_JSON parsing
- `src/quant_platform_kit/strategy_contracts.py` — StrategyRuntimeAdapter, execution contracts
- `scripts/validate_platform_consistency.py` — Cross-platform strategy validation
- `scripts/check_required_env.py` — Environment variable validation
- `docs/ARCHITECTURE.md` — Full architecture documentation
- `docs/STRATEGY_PLATFORM_SPEC.md` — Adding strategies/platforms/plugins spec

## Design Rules

1. **Single Source of Truth**: RUNTIME_TARGET_JSON is the canonical config entry-point
2. **Strategy Registry Pattern**: strategy_registry.py imports catalogs, merges, filters through capability matrix
3. **Auto-Sync**: Plugin mounts and monitor targets auto-align to RUNTIME_TARGET_JSON on startup
4. **Scheduler TZ = Market TZ**: Not service region
5. **Dataclass field order**: Required fields before default fields

## CI / Validation Scripts

- `python scripts/check_required_env.py --platform=schwab` — pre-deploy env check
- `python scripts/validate_platform_consistency.py` — catalog vs registry consistency
- `python scripts/sync_strategy_config.py` — auto-generate Scheduler jobs from config
