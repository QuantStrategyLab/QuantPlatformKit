# Runtime-selectable allowlist v1

`runtime-selectable allowlist` 描述某个平台在当前部署中可以选择的策略 profile；它不等于策略生命周期状态，也不授予 live 权限。

## 边界

- catalog 负责描述策略生命周期和证据状态；
- allowlist 负责描述 runtime 可选择的 profile；
- authority policy、Risk Gate 和 broker permission 负责决定是否可以执行；
- 缺少 allowlist、证据或 authority 时，profile 必须保持 `PARKED`/`live_candidate`，不能自动执行。

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

迁移期间，旧 `get_runtime_enabled_profiles()` 只能作为一次性读取适配器；新代码不得继续写入旧 status 字段。迁移完成后，各 broker/runtime 应只消费本 allowlist，并独立校验 authority、Risk Gate、回滚引用和 broker 权限。
