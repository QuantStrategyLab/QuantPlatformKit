# Runtime-Selectable Allowlist v1

[简体中文](runtime-selectable-allowlist-v1.zh-CN.md)

`runtime-selectable allowlist` defines which strategy profiles a platform may select in a given deployment; it is not a strategy lifecycle state and never grants live authority.

## Boundaries

- The catalog describes strategy lifecycle and evidence states.
- The allowlist specifies which profiles a runtime may select.
- Authority policy, the Risk Gate, and broker permissions decide whether execution is allowed.
- When allowlist, evidence, or authority is missing, profiles must stay `PARKED` / `live_candidate` and never execute automatically.

```json
{
  "schema": "qsl.runtime_selectable_allowlist.v1",
  "platform": "example",
  "domain": "us_equity",
  "profiles": ["example_profile"],
  "source_digest": "<sha256>",
  "generated_at": "<utc>",
  "permission_effect": "none"
}
```

During migration, legacy `get_runtime_enabled_profiles()` serves strictly as a one-time read adapter; new code must not write legacy status fields. Once migrated, brokers and runtimes must consume only this allowlist and independently verify authority, Risk Gate, rollback references, and broker permissions.
