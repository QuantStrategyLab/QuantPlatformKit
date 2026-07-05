# QuantPlatformKit

[Chinese README](README.zh-CN.md)

> Investing involves risk. This project does not provide investment advice and is for education, research, and engineering review only.

## What this repository is

QuantPlatformKit is a QuantStrategyLab shared runtime library. It provides shared contracts, broker adapters, strategy loaders, notification utilities, and runtime helpers used by platform repositories.

It supports the system but does not decide which strategy should be live. Strategy eligibility remains in the strategy and snapshot repositories; broker execution remains in the platform repositories.

## Design boundary

- Keep contracts stable and versioned where downstream repositories depend on them.
- Prefer backward-compatible changes unless a coordinated migration is planned.
- Keep secrets and environment-specific settings outside the shared library code.
- Document changes that affect multiple platforms or strategy packages.

## Repository layout

- `src/`: library and runtime code.
- `tests/`: unit, contract, and regression tests.
- `docs/`: runbooks, design notes, evidence, and integration contracts.
- `.github/workflows/`: CI, scheduled jobs, release, or deployment workflows.

## Quick start

```bash
python -m pip install -e .
python -m pytest -q
```

## Strategy lifecycle CLI

`quant-lifecycle` provides the shared lifecycle entrypoint for strategy monitoring, drift detection, optimization, updates, and dashboards.
Production schedules should live in domain repositories and call this CLI or the underlying
`quant_platform_kit.strategy_lifecycle` modules directly.

```bash
quant-lifecycle monitor --domain us_equity
quant-lifecycle drift --domain us_equity
quant-lifecycle autopilot --domain us_equity --dry-run
quant-lifecycle evidence --file path/to/evidence.json
quant-lifecycle dashboard --format all
```

## Cloud provider abstraction

QuantPlatformKit includes a cloud provider abstraction layer at `quant_platform_kit.cloud`. It defines protocol interfaces for common cloud services — secret management, object storage, document databases, compute discovery, and deployment context — so that platform code can be written without hard-wiring to a specific cloud provider.

**Supported providers:**

| Provider | Env var | Description |
|----------|---------|-------------|
| **Google Cloud** (default) | `QSL_CLOUD_PROVIDER=gcp` | Uses GCP Secret Manager, Cloud Storage, Firestore — original behavior, no config change needed. |
| **AWS** | `QSL_CLOUD_PROVIDER=aws` | Uses AWS Secrets Manager, S3, DynamoDB — requires boto3 and valid AWS credentials. |
| **Azure** | `QSL_CLOUD_PROVIDER=azure` | Uses Azure Key Vault, Blob Storage, Cosmos DB — requires azure-identity and Azure SDK packages. |
| **Local filesystem** | `QSL_CLOUD_PROVIDER=local` | Reads secrets and stores data under `~/.qsl/`. No cloud credentials required — ideal for development and testing. |
| **Environment variables** | `QSL_CLOUD_PROVIDER=env` | Reads secrets from environment variables; uses local filesystem for object/document storage. Suitable for CI. |

**Usage:**

```python
from quant_platform_kit.cloud import (
    get_secret_store,      # SecretStore (read-only)
    get_secret_store_rw,   # SecretStoreReadWrite (for token rotation)
    get_object_store,      # ObjectStore (GCS, S3, or local)
    get_document_store,    # DocumentStore (Firestore or JSON files)
    get_compute_discovery, # ComputeDiscovery (GCE or env var)
    get_deployment_context,# DeploymentContext (Cloud Run or local mock)
)

# Read a secret — works identically with GCP, env var, or ~/.qsl/secrets/
secret = get_secret_store().get_secret("my-api-key")

# Read/write objects — URI format is provider-neutral
data = get_object_store().read_text("gs://bucket/path/to/data.json")
get_object_store().write_text("gs://bucket/path/to/output.json", '{"key": "value"}')
```

To switch provider, set `QSL_CLOUD_PROVIDER` before importing the library:

```bash
export QSL_CLOUD_PROVIDER=local  # use ~/.qsl/ for all cloud operations
python your_script.py
```

For token-rotation scenarios (e.g. LongPort or Schwab OAuth refresh), use the read-write store:

```python
from quant_platform_kit.cloud import get_secret_store_rw
rw = get_secret_store_rw()
rw.update_secret("my-token", "new-token-value")
```

## Useful docs
- [`docs/strategy_lifecycle_policy.md`](docs/strategy_lifecycle_policy.md)
- [`docs/strategy_portfolio_action_matrix.md`](docs/strategy_portfolio_action_matrix.md)
- [`docs/evidence_package_template.md`](docs/evidence_package_template.md)

- [`docs/platform_notification_outcomes.md`](docs/platform_notification_outcomes.md)
- [`docs/platform_notification_outcomes.zh-CN.md`](docs/platform_notification_outcomes.zh-CN.md)
- [`docs/platform_repo_boundaries.md`](docs/platform_repo_boundaries.md)
- [`docs/platform_repo_boundaries.zh-CN.md`](docs/platform_repo_boundaries.zh-CN.md)
- [`docs/quantconnect.md`](docs/quantconnect.md)
- [`docs/strategy_plugin_runtime_contract.md`](docs/strategy_plugin_runtime_contract.md)
- [`docs/strategy_plugin_runtime_contract.zh-CN.md`](docs/strategy_plugin_runtime_contract.zh-CN.md)
- [`docs/us_equity_cross_platform_strategy_spec.md`](docs/us_equity_cross_platform_strategy_spec.md)

## Community and security

- See [CONTRIBUTING.md](CONTRIBUTING.md) for pull request scope, local verification, and documentation expectations.
- Follow [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) for maintainer and contributor conduct.
- Report credential, automation, broker, exchange, or cloud-resource vulnerabilities through [SECURITY.md](SECURITY.md); do not open public issues for secrets or live-execution risk.

## License

See [LICENSE](LICENSE).
