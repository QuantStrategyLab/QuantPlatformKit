# QuantPlatformKit


## QSL 架构角色

- **层级**：`核心共享库`。
- **职责**：共享 runtime contracts 和平台 adapters。
- **事实源/归属**：稳定 contracts、broker adapters、runtime helpers、notifications、risk utilities。
- **消费对象**：platforms、strategies、pipelines、lifecycle tooling。
- **禁止事项**：决定哪个策略 live 或保存环境 secrets。

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

## 策略生命周期 CLI

`quant-lifecycle` 是策略监控、漂移检测、优化、更新和 dashboard 的共享生命周期入口。
生产定时任务应放在各 domain 仓库，并调用这个 CLI 或底层
`quant_platform_kit.strategy_lifecycle` 模块。

```bash
quant-lifecycle monitor --domain us_equity
quant-lifecycle drift --domain us_equity
quant-lifecycle autopilot --domain us_equity --dry-run
quant-lifecycle evidence --file path/to/evidence.json
quant-lifecycle dashboard --format all
```

## 延伸文档

- [`docs/strategy_lifecycle_policy.zh-CN.md`](docs/strategy_lifecycle_policy.zh-CN.md)
- [`docs/strategy_portfolio_action_matrix.zh-CN.md`](docs/strategy_portfolio_action_matrix.zh-CN.md)
- [`docs/evidence_package_template.zh-CN.md`](docs/evidence_package_template.zh-CN.md)
- [`docs/cross_asset_research_driver.zh-CN.md`](docs/cross_asset_research_driver.zh-CN.md)
- [`docs/cross_asset_forward_risk_driver.zh-CN.md`](docs/cross_asset_forward_risk_driver.zh-CN.md)

## 云服务抽象层

`quant_platform_kit.cloud` 包为常用云服务定义了协议接口——密钥管理、对象存储、文档数据库、计算发现和部署上下文。平台代码可以通过这些接口编写，无需硬编码到特定云厂商。

**支持的 Provider：**

| Provider | 环境变量 | 说明 |
|----------|---------|------|
| **Google Cloud**（默认） | `QSL_CLOUD_PROVIDER=gcp` | 使用 GCP Secret Manager、Cloud Storage、Firestore—— 保持原有行为，无需修改配置。 |
| **AWS** | `QSL_CLOUD_PROVIDER=aws` | 使用 AWS Secrets Manager、S3、DynamoDB—— 需要 boto3 和有效的 AWS 凭证。 |
| **Azure** | `QSL_CLOUD_PROVIDER=azure` | 使用 Azure Key Vault、Blob Storage、Cosmos DB—— 需要 azure-identity 和 Azure SDK。 |
| **本地文件系统** | `QSL_CLOUD_PROVIDER=local` | 密钥和数据库存储在 `~/.qsl/` 目录下。无需任何云凭证——适合开发、测试和离线环境。 |
| **环境变量** | `QSL_CLOUD_PROVIDER=env` | 密钥从环境变量读取；其余操作使用本地文件系统。适合 CI 场景。 |

## v1 迁移

v1 已删除 `quant_platform_kit.strategy_contracts`。策略 contract 请改从 `quant_platform_kit.common.strategy_contracts` 导入；执行转换和 runtime input 分别从其对应的 `common` 模块导入。不会提供兼容 facade。
