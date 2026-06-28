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

## 云服务抽象层

`quant_platform_kit.cloud` 包为常用云服务定义了协议接口——密钥管理、对象存储、文档数据库、计算发现和部署上下文。平台代码可以通过这些接口编写，无需硬编码到特定云厂商。

**支持的 Provider：**

| Provider | 环境变量 | 说明 |
|----------|---------|------|
| **Google Cloud**（默认） | `QSL_CLOUD_PROVIDER=gcp` | 使用 GCP Secret Manager、Cloud Storage、Firestore—— 保持原有行为，无需修改配置。 |
| **本地文件系统** | `QSL_CLOUD_PROVIDER=local` | 密钥和数据库存储在 `~/.qsl/` 目录下。无需任何云凭证——适合开发、测试和离线环境。 |
| **环境变量** | `QSL_CLOUD_PROVIDER=env` | 密钥从环境变量读取；其余操作使用本地文件系统。适合 CI 场景。 |

**用法：**

```python
from quant_platform_kit.cloud import (
    get_secret_store,       # SecretStore（只读）
    get_secret_store_rw,    # SecretStoreReadWrite（令牌刷新等写场景）
    get_object_store,       # ObjectStore（GCS / S3 / 本地文件）
    get_document_store,     # DocumentStore（Firestore / JSON 文件）
    get_compute_discovery,  # ComputeDiscovery（GCE / 环境变量）
    get_deployment_context, # DeploymentContext（Cloud Run / 本地 mock）
)

# 读取密钥——无论后端是 GCP、环境变量还是 ~/.qsl/secrets/ 都可以
secret = get_secret_store().get_secret("my-api-key")

# 读写对象——URI 格式与 provider 无关
data = get_object_store().read_text("gs://bucket/path/to/data.json")
get_object_store().write_text("gs://bucket/path/to/output.json", '{"key": "value"}')
```

切换 Provider 只需设置 `QSL_CLOUD_PROVIDER` 环境变量：

```bash
export QSL_CLOUD_PROVIDER=local  # 所有云操作走 ~/.qsl/ 本地目录
python your_script.py
```

令牌刷新场景（如 LongPort 或 Schwab OAuth 自动续期）使用读写版接口：

```python
from quant_platform_kit.cloud import get_secret_store_rw
rw = get_secret_store_rw()
rw.update_secret("my-token", "new-token-value")
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

## 社区和安全

- 贡献前请阅读 [CONTRIBUTING.md](CONTRIBUTING.md)，确认 PR 范围、本地校验和文档要求。
- 讨论、issue 和 review 请遵守 [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)。
- 涉及密钥、自动化、券商/交易所或云资源的漏洞请按 [SECURITY.md](SECURITY.md) 私密报告；不要为 secret 或实盘风险开公开 issue。

## 许可证

详见 [LICENSE](LICENSE)。
