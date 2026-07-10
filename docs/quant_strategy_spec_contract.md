# Quant Strategy Specification Contracts

This document defines the first versioned artifacts introduced by the Quant
Strategy Review and Optimization Standard.  They are research evidence inputs;
they do not change existing lifecycle stages, evidence-package fields, or
runtime interfaces.

## Artifacts

| Artifact | Schema version | Purpose |
| --- | --- | --- |
| `ResearchSpec` | `research_spec.v1` | Freeze a falsifiable hypothesis, PIT data revision, four-layer benchmarks, net cost model, OOS plan, and complete trial ledger before evaluation. |
| `OptimizationSpec` | `optimization_spec.v1` | Freeze optimization inputs, permitted parameter ranges, constrained objective, nested WFA, locked holdout, multiple-testing control, cost stress, stop rules, and human-only promotion. |

Schemas are stored in `schemas/`.  Python validation is deliberately dependency
free so an evidence gate can consume the same artifact without installing a
JSON Schema runtime.

```bash
python scripts/validate_strategy_spec.py path/to/spec.json
```

The command is silent on success, prints field-level contract violations to
stderr on failure, and returns a non-zero exit code.  Code integrations may
use `validate_research_spec`, `validate_optimization_spec`, or
`validate_strategy_spec_file` from `quant_platform_kit.strategy_lifecycle`.

## v1 safety rules

- Research evaluation requires a locked OOS interval, at least three
  walk-forward folds, PIT and survivorship checks,
  net-of-cost accounting, all-trial recording, and capital/passive/risk-matched/
  simple-rule benchmarks.
- Optimization can only vary declared parameters.  It requires frozen data,
  universe, benchmark, cost-model, and code references; nested walk-forward;
  a non-reused locked holdout; complete trial recording; and 1x/2x/3x cost
  stress.
- v1 rejects full Kelly and automatic risk increases.  Kelly is retained only
  as a bounded fractional-cap input and human approval remains mandatory.

`StrategyReviewReport` and `PositionBudgetReport` are intentionally deferred.
They will consume these immutable inputs rather than duplicate them.
