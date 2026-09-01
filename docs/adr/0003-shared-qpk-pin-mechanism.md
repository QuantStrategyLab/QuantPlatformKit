# ADR 0003: QPK_PIN Dependency Consistency Mechanism

**Date**: 2026-06-30
**Status**: Accepted

## Context

The organization uses git-based dependencies (`quant-platform-kit @ git+https://...@<sha>`) across 15+ repos. When QPK changes, every dependent repo must manually update its pin. This has caused repeated deployment failures:

- Pip `ResolutionImpossible` errors when strategy repos declare QPK@SHA_A but platforms pin QPK@SHA_B
- Cloud Run `ImportError` when Docker images are built with mismatched QPK versions
- Manual cascading updates across strategy → platform repos

Three separate incidents occurred during a single day of development due to SHA drift.

## Decision

Introduce `QPK_PIN` as the single source of truth for which QPK commit all dependent repos should reference:

1. **QPK_PIN file** in QPK repo root — contains only the canonical QPK commit SHA
2. **Auto-update workflow** (`update-qpk-pin.yml`) — runs on every non-documentation push to QPK main, verifies that QPK commit in isolation, and advances only `QPK_PIN`
3. **Consistency check script** (`check_qpk_pin_consistency.py`) — validates all git-based QPK references in a repo match QPK_PIN, with optional `--fix` mode for automatic updates
4. **Staged propagation** (`open-downstream-qpk-pin-prs.yml`) — first updates the four strategy packages; only after their `main` branches all pin `QPK_PIN` does it reconcile the aggregate bundle and open dependency PRs for all direct execution-platform and P1-pipeline consumers with those exact strategy commits

The aggregate manifests are intentionally not rewritten in the first stage. A
QPK-only aggregate update is not installable while strategy packages still
declare the previous direct-URL QPK requirement; pip correctly reports
`ResolutionImpossible`. Keeping the previous bundle coherent until the
strategy stage lands removes that propagation deadlock without weakening
dependency resolution.

Dependent repos add a CI step that curls the QPK_PIN file and runs the check script.

## Consequences

- **Positive**: Single source of truth prevents SHA drift
- **Positive**: CI catches mismatches before they reach deployment
- **Positive**: `--fix` mode enables automated dependency updates
- **Positive**: Execution-platform and P1-pipeline PRs are opened only for a coherent QPK plus strategy commit bundle
- **Negative**: Requires QPK GitHub Actions to have push permission to main
- **Negative**: Dependent repos must add the consistency check to their CI
- **Neutral**: The pin file itself is a simple text file; no new infrastructure required
- **Neutral**: `qsl-pins.txt` may temporarily describe the previous coherent bundle while `QPK_PIN` stages the next QPK commit
