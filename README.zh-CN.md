# QuantPlatformKit

[English README](README.md)

> 投资有风险。本项目不构成投资建议，仅用于学习、研究和工程审阅。

## 这个仓库是什么

QuantPlatformKit 是 QuantStrategyLab 的共享运行时库。平台仓库共用的契约、券商适配器、策略加载器、通知工具和运行辅助代码。

它支撑系统运行，但不决定哪个策略应该 live。策略资格由策略仓和 snapshot 仓负责；券商执行由平台仓负责。

## 设计边界

- 下游仓库依赖的契约要保持稳定，必要时做版本化。
- 除非有协同迁移计划，否则优先保持向后兼容。
- 密钥和环境专属配置不要写进共享库代码。
- 会影响多个平台或策略包的改动，需要在文档中说明。

## 仓库结构

- `src/`：库代码和运行时代码。
- `tests/`：单元测试、契约测试和回归测试。
- `docs/`：运行手册、设计说明、证据和集成契约。
- `.github/workflows/`：CI、定时任务、发布或部署 workflow。

## 快速开始

```bash
python -m pip install -e .
python -m pytest -q
```

## 延伸文档

- [`docs/platform_notification_outcomes.md`](docs/platform_notification_outcomes.md)
- [`docs/platform_notification_outcomes.zh-CN.md`](docs/platform_notification_outcomes.zh-CN.md)
- [`docs/platform_repo_boundaries.md`](docs/platform_repo_boundaries.md)
- [`docs/platform_repo_boundaries.zh-CN.md`](docs/platform_repo_boundaries.zh-CN.md)
- [`docs/quantconnect.md`](docs/quantconnect.md)
- [`docs/strategy_plugin_runtime_contract.md`](docs/strategy_plugin_runtime_contract.md)
- [`docs/strategy_plugin_runtime_contract.zh-CN.md`](docs/strategy_plugin_runtime_contract.zh-CN.md)
- [`docs/us_equity_cross_platform_strategy_spec.md`](docs/us_equity_cross_platform_strategy_spec.md)

## 许可证

详见 [LICENSE](LICENSE)。
