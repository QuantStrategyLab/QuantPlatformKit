# QuantStrategyLab Architecture

> Investing involves risk. This document describes system architecture only, not investment advice.

## Layer Model

```
┌─────────────────────────────────────────────────────────┐
│                   EXECUTION LAYER                        │
│  SchwabPlatform  │ IBKRPlatform │ LongBridgePlatform    │
│  BinancePlatform │ FirstradePlatform                    │
│  (Cloud Run)     │ (Cloud Run)  │ (GitHub Actions+VPS)  │
├─────────────────────────────────────────────────────────┤
│                   STRATEGY LAYER                         │
│  UsEquityStrategies │ HkEquityStrategies                │
│  CnEquityStrategies │ CryptoStrategies                  │
│  QuantUsComboStrategies │ QuantHkComboStrategies        │
│  (pip wheels, version-pinned in requirements.txt)       │
├─────────────────────────────────────────────────────────┤
│                   SNAPSHOT LAYER                         │
│  UsEquitySnapshotPipelines │ HkEquitySnapshotPipelines  │
│  CnEquitySnapshotPipelines │ CryptoLivePoolPipelines    │
│  (GCS artifacts, consumed by execution layer)           │
├─────────────────────────────────────────────────────────┤
│                INFRASTRUCTURE LAYER                      │
│  QuantPlatformKit │ QuantRuntimeSettings                │
│  QuantStrategyPlugins │ MarketSignalSources             │
│  (shared contracts, adapters, runtime tooling)          │
└─────────────────────────────────────────────────────────┘
```

## Data Flow

```
Strategy Definition (pip package)
  → Strategy Catalog (STRATEGY_CATALOG)
    → Platform Capability Matrix (can this platform run it?)
      → Snapshot Pipeline (generates artifacts → GCS)
        → Runtime Adapter (loads strategy entrypoint)
          → Platform Execution (fetch data → compute → submit orders)
            → Execution Report (GCS + structured log)
              → Monitor Dispatch (probe + dry-run checks)
```

## Configuration Single Source of Truth

Every platform service has ONE canonical config entry-point:

```
RUNTIME_TARGET_JSON = {
  "platform_id": "...",
  "strategy_profile": "...",
  "execution_mode": "live" | "paper",
  "dry_run_only": true | false,
  "account_scope": "...",
  "scheduler": {
    "main_time": "45 15 * * *",
    "precheck_time": "45 9 * * *",
    "probe_time": "35 9,15 * * *",
    "timezone": "America/New_York"
  }
}
```

**All other config values that reference strategy/platform names derive from this.** The auto-sync layer (config-sync) corrects stale references on startup.

## Design Patterns

### 1. Strategy Registry Pattern

Each platform has a `strategy_registry.py` that:
- Imports shared strategy catalogs from pip packages
- Merges multiple catalogs (US + HK + Combo)
- Filters strategies through a capability matrix
- Routes to the correct runtime adapter

```
profile → domain check → adapter lookup → StrategyRuntimeAdapter
```

### 2. Runtime Adapter Pattern

Every strategy exposes a `StrategyRuntimeAdapter` via `get_platform_runtime_adapter(profile, platform_id)`. The adapter declares:
- `available_inputs` — what data the strategy needs
- `managed_symbols_extractor` — symbols to monitor
- `runtime_policy` — execution timing contract

### 3. Config Auto-Sync Pattern

At module load time, the `config-sync` layer:
1. Reads `STRATEGY_PROFILE` from `RUNTIME_TARGET_JSON`
2. Scans plugin mount JSON → corrects stale `strategy` fields
3. Scans monitor target JSON → corrects stale `strategy_profile` fields
4. Logs `[config-sync]` messages for each correction

**Result**: User only changes `RUNTIME_TARGET_JSON`. Everything else auto-aligns.

### 4. Single Source of Truth Pattern

- `RUNTIME_TARGET_JSON` = canonical strategy+platform assignment
- `STRATEGY_PROFILE` env var = DEPRECATED (removed)
- Plugin mount `strategy` field = auto-synced to match
- Monitor target `strategy_profile` = auto-synced to match

### 5. Execution Timing Pattern

Strategies declare `signal_effective_after_trading_days` and `execution_timing_contract` in their runtime policy. The platform:
- Checks market calendar before execution
- Respects the timing contract (next_trading_day, etc.)
- Uses `execution_dedup_enabled` for multi-day windows (monthly DCA)

## Naming Conventions

| Type | Convention | Example |
|---|---|---|
| Platform ID | lowercase, underscores | `schwab`, `interactive_brokers`, `longbridge` |
| Strategy Profile | lowercase, underscores | `soxl_soxx_trend_income` |
| Domain | lowercase, underscores | `us_equity`, `hk_equity`, `quant_combo` |
| Repo Name | PascalCase for platforms, camelCase for packages | `CharlesSchwabPlatform`, `us-equity-strategies` |
| Pip Package | lowercase-hyphenated | `us-equity-strategies`, `quant-us-combo-strategies` |
| Python Package | lowercase_underscores | `us_equity_strategies`, `quant_us_combo_strategies` |
| GCP Service | lowercase-hyphenated | `charles-schwab-quant-service` |
| Scheduler Job | `{platform}-{strategy}-{type}` | `schwab-soxl-main`, `ibkr-u16608560-precheck` |

## Scheduler Rules

| Market | Calendar | Timezone | Execution Window | Cron |
|---|---|---|---|---|
| US Equity | NASDAQ | `America/New_York` | 3:45 PM ET | `45 15 * * *` |
| HK Equity | XHKG | `Asia/Hong_Kong` | 3:45 PM HKT | `45 15 * * *` |
| A-Share | XSHG | `Asia/Shanghai` | 2:45 PM CST | `45 14 * * *` |
| Crypto | 24/7 | UTC | N/A | GitHub Actions `schedule` |

**Rule**: Scheduler timezone = **market** timezone, not service region.

## Adding a New Platform

1. Create platform repo from the closest existing template
2. Implement `strategy_registry.py`:
   - Import shared catalogs, merge them
   - Define `PLATFORM_CAPABILITY_MATRIX`
   - Define `*_EXCLUDED_LIVE_PROFILES`
   - Implement `get_platform_runtime_adapter(profile, platform_id)`
3. Implement `runtime_config_support.py`:
   - Define `PlatformRuntimeSettings` dataclass
   - REQUIRED fields FIRST, default fields AFTER (Python dataclass rule)
   - Implement `load_platform_runtime_settings()`
4. Implement broker adapters, market data ports, execution ports
5. Add `main.py` with Flask routes (`/run`, `/dry-run`, `/probe`, `/health`, `/monitor-dispatch`)
6. Add Cloud Scheduler jobs (or GitHub Actions for self-hosted)
7. Add `.env.example` with all required env vars
8. Add to `MONITOR_DISPATCH_TARGETS_JSON` for cross-platform monitoring

## Adding a New Strategy

1. Add strategy definition to the appropriate shared catalog pip package
2. Set `compatible_platforms` in the catalog
3. Set `runtime_enabled_profiles` for rollout
4. Implement `get_platform_runtime_adapter(profile, platform_id)` in the runtime_adapters module
5. Each platform auto-discovers it via `derive_enabled_profiles_for_platform()`
6. To deploy: update `RUNTIME_TARGET_JSON.strategy_profile` on the target service

## Adding a New Plugin

1. Add plugin definition to `STRATEGY_PLUGIN_MOUNTS_JSON`
2. The `strategy` field auto-syncs to match `RUNTIME_TARGET_JSON.strategy_profile`
3. Plugin signals are consumed by the strategy entrypoint

## Deployment Safety

1. `python scripts/check_required_env.py --platform=<id>` — validate env vars
2. `python scripts/validate_platform_consistency.py` — validate catalog vs registry
3. Deploy to Cloud Run with `--clear-base-image`
4. Verify `/health` returns 200 with no module errors
5. Trigger `/dry-run` via Scheduler — verify execution report
6. Enable live execution only after dry-run passes

## Version History

| Version | Date | Changes |
|---|---|---|
| 1.0 | 2026-06-30 | Initial architecture document |
