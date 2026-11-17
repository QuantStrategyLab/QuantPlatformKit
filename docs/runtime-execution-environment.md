# Runtime Execution Environment Contract

[简体中文](runtime-execution-environment.zh-CN.md)

Previously, `dry_run_only` overloaded both local previews and broker PAPER accounts, blurring side-effect-free simulation with broker PAPER execution. Runtime targets now use `execution_environment` to declare exact side-effect boundaries:

| Value | `dry_run_only` | Permitted side effects |
|---|---|---|
| `dry_run` | `true` | Local preview or internal simulation only; must never call a broker |
| `paper` | `false` | Broker-dedicated PAPER accounts only; still requires release, risk, account-identity, and command gates |
| `live` | `false` | May access live accounts; not live authorization on its own and still requires the independent live command gate |

Compatibility: when a legacy target omits `execution_environment`, `dry_run_only=true` resolves to `dry_run` and `false` resolves to `live`. Legacy `execution_mode` retains its existing serialization semantics and cannot declare broker PAPER accounts; new configuration must specify `execution_environment`.

This is a configuration contract only and never enables targets, broker connections, PAPER trading, or Live orders.
