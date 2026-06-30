# ADR 0002: Merge Combo Strategy Repos Into Domain Strategy Packages

**Date**: 2026-06-30
**Status**: Accepted

## Context

The organization had 4 standalone "combo" repositories (QuantUsComboStrategies, QuantHkComboStrategies, QuantCnComboStrategies, QuantCryptoComboStrategies) each containing 1-2 strategy files that were thin wrappers combining sub-strategies from the main domain packages (UsEquityStrategies, HkEquityStrategies, CnEquityStrategies, CryptoStrategies). Version 0.1.0, 2-3 commits each.

This created:
- 4 near-empty repos requiring separate CI, testing, and dependency management
- Duplicated catalog/manifest/entrypoint boilerplate
- `crypto_equity_combo` duplicated in both CryptoStrategies and QuantCryptoComboStrategies
- Platform repos importing from two packages for the same domain

## Decision

Merge all combo strategies into their parent domain strategy packages:

| Combo Repo | Merged Into |
|-----------|------------|
| QuantUsComboStrategies | UsEquityStrategies |
| QuantHkComboStrategies | HkEquityStrategies |
| QuantCnComboStrategies | CnEquityStrategies |
| QuantCryptoComboStrategies | CryptoStrategies |

The original combo repos were converted to backward-compatible re-export wrappers that import from the parent domain package.

## Consequences

- **Positive**: 4 fewer repos to maintain (CI, deps, tests)
- **Positive**: `crypto_equity_combo` now has a single source of truth
- **Positive**: Catalog entries for combo profiles live alongside their sub-strategies
- **Negative**: Platform repos had pre-existing tests that imported from the old combo locations — required updates to `runtime_adapters.py`, `combo_entrypoints.py`, and test expectations
- **Negative**: Re-export wrappers create a transitional dependency that will be removed once platform repos update their imports
