# Strategy-Platform Configuration Specification

## Single Source of Truth

Every platform service has **one** canonical config entry-point:

```
RUNTIME_TARGET_JSON = {"platform_id": "...", "strategy_profile": "...", ...}
```

All other config values that reference the strategy name MUST derive from
`RUNTIME_TARGET_JSON.strategy_profile` — either at code level or through the
auto-sync layer described below.

### Derived values (auto-synced on startup)

| Config location | Field | Auto-sync |
|---|---|---|
| `SCHWAB_STRATEGY_PLUGIN_MOUNTS_JSON` | `.strategy_plugins[].strategy` | ✅ corrected on startup |
| `STRATEGY_PLUGIN_MOUNTS_JSON` (IBKR, LB) | `.strategy_plugins[].strategy` | ✅ corrected on startup |
| `MONITOR_DISPATCH_TARGETS_JSON` | `.targets[].strategy_profile` | ✅ corrected on startup (Schwab) |
| `SCHWAB_MONITOR_DISPATCH_TARGETS_JSON` | `.targets[].strategy_profile` | ✅ corrected on startup (Schwab) |

### Deprecated (do NOT set)

- `STRATEGY_PROFILE` — was a standalone env var that duplicated `RUNTIME_TARGET_JSON.strategy_profile`. Removed in Schwab `runtime_config_support.py`. IBKR and LongBridge never had this fallback.

---

## Adding a New Strategy

See also: [`strategy_lifecycle_policy.md`](./strategy_lifecycle_policy.md) for the
promotion ladder and live-enable gate model.

Before requesting live enablement, attach an evidence package that covers:

- backtest summary
- drift / regime notes
- platform compatibility evidence
- plugin gate status, if applicable

1. Add strategy definition to the shared catalog (`us_equity_strategies` or `hk_equity_strategies`)
2. Set `compatible_platforms` to list which platforms support it
3. Add to `runtime_enabled_profiles` for the rollout
4. Each platform repo picks it up via `derive_enabled_profiles_for_platform()` — no per-platform code change needed unless the strategy requires special exclusions
5. To deploy: update `RUNTIME_TARGET_JSON.strategy_profile` on the target service, and optionally add plugin mounts

**Checklist:**
```
[ ] strategy definition in shared catalog
[ ] compatible_platforms includes target platform(s)
[ ] runtime_enabled_profiles includes profile name
[ ] platform's capability matrix supports required inputs/domain
[ ] RUNTIME_TARGET_JSON.strategy_profile updated on target service
[ ] plugin mounts JSON (if any) updated — or rely on auto-sync
[ ] Scheduler jobs exist for the service (already there if service exists)
```

---

## Adding a New Platform

1. Create platform repo from template (copy an existing one)
2. Implement `strategy_registry.py`:
   - Define `PLATFORM_CAPABILITY_MATRIX` (domains, inputs, capabilities)
   - Define `*_EXCLUDED_LIVE_PROFILES` (strategies not yet ready)
   - Derive `ELIGIBLE_STRATEGY_PROFILES` and `*_ENABLED_PROFILES`
3. Implement `runtime_config_support.py`:
   - Define `PlatformRuntimeSettings` dataclass with all platform-specific fields
   - All non-default fields MUST appear BEFORE any field with a default value
   - Implement `load_platform_runtime_settings()` reading from env vars
4. Implement broker adapters, market data ports, execution ports
5. Add Cloud Scheduler jobs:
   - `{platform}-{strategy}-main`: `45 15 * * *` → `/run`
   - `{platform}-{strategy}-precheck`: `45 9 * * *` → `/dry-run`
   - `{platform}-{strategy}-backup`: `52 15 * * 1-5` → `/run`
6. Set `RUNTIME_TARGET_JSON` on the Cloud Run service
7. Wire into `MONITOR_DISPATCH_TARGETS_JSON` for cross-platform health checks

**Platform dataclass rule:**
```python
@dataclass(frozen=True)
class PlatformRuntimeSettings:
    # Required fields FIRST (no defaults)
    project_id: str | None
    secret_name: str
    strategy_profile: str
    # ... more required fields ...

    # Fields with defaults AFTER all required fields
    notification_channel: str = "telegram"
    dry_run_only: bool = False  # ← note: False IS a valid default here
    # ...
```

---

## Adding a New Plugin

1. Add plugin definition with `signal_path`, `enabled`, `expected_mode`
2. Add to `{PLATFORM}_STRATEGY_PLUGIN_MOUNTS_JSON` env var:
   ```json
   {
     "strategy_plugins": [{
       "strategy": "<strategy_profile>",
       "plugin": "<plugin_name>",
       "signal_path": "gs://your-bucket/path/to/signal.json",
       "enabled": true,
       "expected_mode": "shadow"
     }]
   }
   ```
3. The `strategy` field is auto-synced to match `RUNTIME_TARGET_JSON.strategy_profile` — you can set it to anything and it will be corrected on startup. Setting it correctly is still recommended for documentation.

---

## Configuration Validation

Before deploying, run:
```bash
# Check required env vars
python scripts/check_required_env.py --platform=schwab --json

# Check strategy-platform consistency
python scripts/validate_platform_consistency.py
```

These should be integrated into CI pipelines for all platform repos.

---

## Deployment Checklist

When changing a strategy's configuration:

```
[ ] RUNTIME_TARGET_JSON updated (ONLY this is required)
[ ] Deploy the service (Cloud Run picks up new env var)
[ ] Verify: check Cloud Logging for "[config-sync]" messages
[ ] Verify: trigger /dry-run via Scheduler or manual POST
[ ] Verify: check execution report in GCS for expected strategy name
```

The auto-sync layer handles everything else (plugin mounts, monitor targets).

---

## Scheduler Timezone Rules

| Market | Calendar | Timezone | Example Scheduler |
|---|---|---|---|
| US Equity | NASDAQ | `America/New_York` | `45 15 * * *` = 3:45 PM ET (15 min before 4 PM close) |
| HK Equity | XHKG | `Asia/Hong_Kong` | `45 15 * * *` = 3:45 PM HKT (15 min before 4 PM close) |

**Rule**: The Scheduler timezone MUST match the **market's** timezone, NOT the Cloud Run service region.

### Execution frequency by strategy type

| Type | Cron | Explanation |
|---|---|---|
| Daily | `45 15 * * *` | Every trading day, 15 min before close |
| Monthly DCA/Snapshot | `45 15 1-7 * *` | Days 1-7 each month, 7-day retry window for data readiness |
| Month-end | `45 15 28-31 * *` | Last days of month (cron handles 28/29/30/31 automatically) |

The `execution_dedup_enabled` flag prevents duplicate execution within the month window.

## Version History

| Version | Date | Changes |
|---|---|---|
| 1.0 | 2026-06-30 | Initial spec: single source of truth, auto-sync, validation scripts |
| 1.1 | 2026-06-30 | Add scheduler timezone rules, strategy frequency types |
