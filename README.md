# QuantPlatformKit

<!-- qsl-doc-overview:start -->

> ⚠️ 投资有风险，不构成投资建议，仅供学习交流用途。
> ⚠️ Investing involves risk. This project does not provide investment advice and is for educational and research purposes only.

## Open-source overview / 开源项目入口

| Item | Description |
| --- | --- |
| Project type | shared runtime kit |
| What it does | Shared broker adapters, strategy contracts, runtime interfaces and notification utilities used across QuantStrategyLab platforms. |
| 中文说明 | 共享运行时工具包，提供券商适配、策略契约、组件加载和通知工具。 |
| Current status | Library/infrastructure. It does not own strategy alpha or backtest performance. |

### Quick start

- `python -m pip install -e '.[test]'`
- `python -m pytest -q`

### Deploy / operate safely

Publish through package/version pins consumed by downstream repos; verify compatibility before bumping platform dependencies.

### Strategy performance / evidence boundary

No standalone strategy performance. Validate behavior through downstream strategy and platform tests.

> Detailed runbooks, migration notes, workflow internals, and historical decisions are kept below. Start with this overview before using the lower-level operational sections.

<!-- qsl-doc-overview:end -->

> ⚠️ 投资有风险，不构成投资建议，仅供学习交流用途。


## 中文摘要

- 完整中文版见 [`README.zh-CN.md`](README.zh-CN.md)；本节保留在英文文件顶部，方便从当前文件直接找到中文入口。
- 用途：本文档围绕 `QuantPlatformKit`，用于理解 `QuantPlatformKit` 的配置、运行、部署、研究或验收边界。
- 主要覆盖：`What This Repository Is`、`Repository Workflow`、`Strategy Plugins`、`Package Layout`、`Development`。
- 阅读顺序：先确认边界、输入输出和权限要求，再执行文档里的命令、CI、dry-run、发布或切换步骤。
- 风险提示：涉及实盘、密钥、权限、Cloud Run、交易所或券商 API 的变更，必须先在测试环境或 dry-run 验证；不要只凭示例直接修改生产。
- 英文正文保留更完整的命令、字段名和配置键；如果摘要和正文不一致，以正文中的实际命令和配置为准。
Shared platform contracts, broker adapters, strategy-plugin helpers, and notification primitives for QuantStrategyLab repositories.

[中文](./README.zh-CN.md)

## What This Repository Is

`QuantPlatformKit` is the public shared platform layer. It keeps cross-repository interfaces stable so strategy repositories and broker platform repositories can evolve without copying runtime glue.

It contains:

- common domain models and runtime target helpers
- narrow ports for market data, portfolio snapshots, order execution, notifications, and state
- reusable broker adapter utilities
- QuantConnect Cloud deployment helpers for hybrid hosted/self-hosted runtimes
- strategy loading, strategy-plugin, and alert-message contracts
- optional strategy-plugin alert channels for email, SMS, push, and Telegram providers
- synthetic-data tests for public behavior

It does not contain private runtime wiring or generated strategy outputs.

## Repository Workflow

QuantStrategyLab repositories are split by responsibility:

- Strategy repositories own strategy metadata, input requirements, and `manifest + evaluate(ctx)` entrypoints.
- Platform repositories own broker sessions, runtime config loading, runtime entrypoints, decision mapping, and order submission.
- Snapshot or data pipeline repositories own generated artifacts and their publication process.
- `QuantPlatformKit` owns the shared contracts and helper APIs used by those repositories.

The normal flow is:

```text
Platform repository
  builds StrategyContext from broker/runtime inputs
  loads a strategy entrypoint from a strategy repository
  receives a StrategyDecision
  maps that decision into broker-specific execution and notifications

QuantPlatformKit
  provides shared contracts, loaders, adapters, and plugin alert helpers
```

Strategy code should not branch on a broker platform, and platform code should not duplicate strategy rules.

## Strategy Plugins

Strategy plugins are sidecar artifacts that platform repositories may read when a strategy profile opts in. This repository defines the public plugin contract, compatibility checks, alert-message building, optional alert delivery helpers, and duplicate-suppression helpers.

Generated plugin artifacts and platform-specific notification routing stay with the producing pipeline or consuming platform repository. Tests in this repository use synthetic price history and synthetic payloads only.

Plugin artifacts may carry display-only `strategy_plugin_messages.v1` and
`strategy_plugin_log.v1` localized notification/log text. Platform renderers can
use those strings, while strategy and platform logic should continue to depend
on machine fields such as `canonical_route`, `suggested_action`,
`reason_codes`, and `position_control`.
General notification artifacts are loaded through `notification_targets`, not
through synthetic strategy mounts; they can trigger alerts but never attach
position controls to a strategy runtime.

Plugin alert delivery is provider-neutral at the platform boundary. Platform repositories pass runtime settings into `publish_strategy_plugin_alerts`; this repository handles configured `email`, `sms`, `push`, and `telegram` channels without coupling plugin logic to a broker platform.

## Package Layout

```text
src/quant_platform_kit/
  common/
  ibkr/
  binance/
  schwab/
  longbridge/
  quantconnect/
  notifications/
tests/
```

See [docs/quantconnect.md](./docs/quantconnect.md) for the public QuantConnect connector contract and placeholder-only examples.
See [docs/strategy_plugin_runtime_contract.md](./docs/strategy_plugin_runtime_contract.md)
for the strategy-plugin runtime contract and
[docs/strategy_plugin_runtime_contract.zh-CN.md](./docs/strategy_plugin_runtime_contract.zh-CN.md)
for the Chinese version.

## Development

Run the public test suite:

```bash
PYTHONPATH=src pytest
```

Run linting:

```bash
PYTHONPATH=src ruff check .
```

## License

MIT License. See [LICENSE](./LICENSE).
