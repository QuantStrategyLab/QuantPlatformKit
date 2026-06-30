# ADR 0001: Record Architecture Decisions

**Date**: 2026-06-30
**Status**: Accepted

## Context

QuantStrategyLab operates 28 repositories across 5 layers (shared libs → strategies → pipelines → platforms → ops). Architectural choices have been made incrementally without formal documentation. This ADR establishes the practice of recording architecture decisions and serves as the template for all future ADRs.

## Decision

All significant architectural decisions will be recorded as Architecture Decision Records (ADRs) in this directory (`docs/adr/`). Each ADR follows the format: Context → Decision → Consequences.

## Template

```markdown
# ADR NNNN: <title>

**Date**: YYYY-MM-DD
**Status**: Proposed | Accepted | Deprecated | Superseded

## Context
What is the issue that we're seeing that is motivating this decision or change?

## Decision
What is the change that we're proposing and/or doing?

## Consequences
What becomes easier or more difficult to do because of this change?
```

## Consequences

- **Positive**: Future contributors can understand *why* the system is structured as it is
- **Positive**: New team members can onboard by reading ADRs chronologically
- **Negative**: Maintaining ADRs requires discipline; stale ADRs must be marked as deprecated
- **Neutral**: ADRs are immutable once accepted; changes require a new ADR with "Supersedes" reference
