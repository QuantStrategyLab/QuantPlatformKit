# Strategy Release Readiness Gate

[简体中文](strategy-release-readiness.zh-CN.md)

`assess_strategy_release_readiness` is a pre-release pure function shared across strategies, platforms, and plugins. It never connects to brokers, mutates parameters, deploys services, or places orders.

`StrategyReleaseReadiness.build_manifest()` generates a loadable `StrategyReleaseManifest` only when all of the following pass:

- Strategy configuration, risk rules, and at least one plugin bundle are readable regular files.
- The evidence package validates cleanly and explicitly permits promotion.
- Strategy profile and source revision inside the evidence match the release target exactly.
- Release ID, effective trading date, and target set satisfy the immutable release contract.

On failure, it returns `ready: false` with stable, path-free, content-free `findings` such as `evidence_package_missing`, `evidence_not_promotion_eligible`, or `evidence_revision_mismatch`. Monitoring tools may aggregate this output, but it must never be treated as a release identity or trading authorization.

Plugin bundle digests hash approved file contents only, producing identical identities across working directories and platforms without embedding local absolute paths.

For leveraged strategies such as SOXL, missing formal backtest and acceptance evidence must stop at this gate: diagnostics and evidence completion are permitted, whereas paper overrides or `ACTIVE` promotion are forbidden.
