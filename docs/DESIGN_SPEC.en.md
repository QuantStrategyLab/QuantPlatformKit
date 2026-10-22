# Platform, strategy and plugin development standard — English overview

[完整中文规范](DESIGN_SPEC.md) · [Specification index](README.md)

This summarizes v1.0 dated 2026-06-30. The complete Chinese standard retains its exact examples and checklists. Treat legacy plugin mounting/config-sync examples as historical compatibility material under the [historical plugin contract](strategy_plugin_runtime_contract.md); they are not current mounting or trading authority.

## Platform and strategy interfaces

Platforms own broker integration, runtime settings/policies, decision mapping, adapters and execution. A registry imports strategy catalogs, declares `PlatformCapabilityMatrix`, derives enabled profiles and routes runtime adapters. Required dataclass fields precede defaulted fields. The standard lists `/run`, `/dry-run`, `/probe`, `/health` and `/monitor-dispatch`; health includes module-import checks and dry-run must not submit orders.

Pure strategy logic stays in its strategy package. Catalog metadata declares compatibility, profile/domain, cadence and status; adapters declare required inputs and execution timing. `signal_effective_after_trading_days=1` means next-day effectiveness; `0` means same-day. Snapshot-backed strategies retain their feature inputs and cadence. Visibility or compatibility does not alone establish live eligibility.

## Configuration and scheduling

`RUNTIME_TARGET_JSON` is the documented strategy/settings source; do not independently set deprecated `STRATEGY_PROFILE`. Maintain required/optional environment templates. Preserve the complete standard's field definitions and the [configuration specification](STRATEGY_PLATFORM_SPEC.md), subject to the historical plugin boundary above.

Scheduler timezones follow the market, not the service region: US `America/New_York`, HK `Asia/Hong_Kong`, crypto `UTC`. The v1.0 standard describes main/precheck/backup/monitor tasks, artifact persistence and deduplication. Its cron examples and versioned integration examples are not proof of a configured or deployed schedule.

## Security and verification

The standard requires credentials/tokens in Secret Manager or GitHub Secrets, none in Git; least-privilege service accounts; restricted Cloud Run invocation by scheduler/runtime identities; no `allUsers` invoker; and SYSTEM_MANAGED service-account keys. It requires environment completeness and strategy/platform consistency checks before deployment and health/dry-run verification afterward.

Environment additions use `--update-env-vars`; the standard prohibits `--set-env-vars` because it replaces unspecified values. JSON values must be passed safely. These are documentation requirements, not permission to change a cloud resource. Consult the full [platform, strategy and plugin checklists](DESIGN_SPEC.md#7-检查清单) for all v1.0 requirements and the [index](README.md) for scope and compatibility.

This overview changes no public API, risk rule or provider right. The repository [license](../LICENSE) applies; neither a checklist nor CI authorizes strategy selection, live trading or credential access.
