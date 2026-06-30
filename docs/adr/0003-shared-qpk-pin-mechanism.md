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
2. **Auto-update workflow** (`update-qpk-pin.yml`) — runs on every push to QPK main, writes the current HEAD SHA to QPK_PIN
3. **Consistency check script** (`check_qpk_pin_consistency.py`) — validates all git-based QPK references in a repo match QPK_PIN, with optional `--fix` mode for automatic updates

Dependent repos add a CI step that curls the QPK_PIN file and runs the check script.

## Consequences

- **Positive**: Single source of truth prevents SHA drift
- **Positive**: CI catches mismatches before they reach deployment
- **Positive**: `--fix` mode enables automated dependency updates
- **Negative**: Requires QPK GitHub Actions to have push permission to main
- **Negative**: Dependent repos must add the consistency check to their CI
- **Neutral**: The pin file itself is a simple text file; no new infrastructure required
