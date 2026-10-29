# 运行执行环境契约

`dry_run_only` 过去同时表达本地预览和 PAPER 的含义，容易把无副作用模拟与真实券商 PAPER 账户混淆。运行目标现用 `execution_environment` 明确表达能力边界：

| 值 | `dry_run_only` | 允许的副作用 |
| --- | --- | --- |
| `dry_run` | `true` | 仅本地预览或内部模拟；不得调用券商。 |
| `paper` | `false` | 仅券商专用 PAPER 账户；仍必须通过 release、风险准入、账户身份和命令门。 |
| `live` | `false` | 可能访问实盘账户；本字段不是 Live 授权，仍需要独立的 Live 命令门。 |

兼容性规则：旧目标未提供 `execution_environment` 时，`dry_run_only=true` 自动解析为 `dry_run`，`false` 自动解析为 `live`。旧 `execution_mode` 保持既有序列化含义，不能用来声明券商 PAPER 账户；新增配置应以 `execution_environment` 为准。

这只是纯配置契约，不会启用运行目标、券商连接、PAPER 或 Live 下单。
