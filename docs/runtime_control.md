# Runtime control contract (`qsl.runtime_control.v1`)

Status: library + schema only. No platform reads it yet; existing variables
(`RUNTIME_TARGET_ENABLED`, `<BROKER>_DRY_RUN_ONLY`, `<BROKER>_CASH_ONLY_EXECUTION`,
`<BROKER>_RESERVED_CASH_RATIO`, ...) keep their current meaning until each
platform migrates in its own reviewed PR.

## Why

The same control is currently spelled differently per broker and can live in a
repository variable, an environment variable, a secret and a Cloud Run env var
at the same time. `RuntimeControl` gives every broker one typed shape and one
resolver.

## Shape

See `schemas/runtime-control.v1.schema.json`. Example:

```json
{
  "schema_version": "qsl.runtime_control.v1",
  "target_id": "example/live",
  "platform_id": "example",
  "strategy_profile": "example_profile",
  "enabled": false,
  "mode": "dry_run",
  "cash_policy": {"cash_only": true, "reserved_cash_ratio": 0.03, "reserved_cash_floor_usd": 0},
  "risk_limits_ref": "example_profile/2026-01-01",
  "options_enabled": false
}
```

## Precedence

1. Safe defaults: disabled, `dry_run`, cash-only.
2. The reviewed target document (`RUNTIME_CONTROL_JSON`), which must match the
   expected target, platform and strategy profile.
3. Emergency overrides, which may only tighten: `RUNTIME_TARGET_ENABLED=false`
   disables, `RUNTIME_CONTROL_MODE_OVERRIDE` may move towards `dry_run`.
   An override that would loosen a control raises `RuntimeControlError`.

Booleans and enums are parsed strictly; empty strings and typos raise instead of
falling back to live trading. Reserved cash combines with the strategy default
using `max`, so configuration can raise but never lower it.
