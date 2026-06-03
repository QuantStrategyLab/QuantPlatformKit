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

## Useful docs

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
