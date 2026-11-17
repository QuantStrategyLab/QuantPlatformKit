# Strategy–M0 Research Coverage Catalog

[简体中文](strategy-context-coverage-catalog.zh-CN.md)

`qsl.strategy-context-coverage-catalog.v1` is a versioned, read-only research coverage catalog. It links an **explicitly specified** `strategy_profile` to its strategy kind, instrument classes, exposure buckets, capital role, benchmark identifiers, and permitted M0 research subject types.

It is not a runtime configuration: it must contain no positions, orders, accounts, brokers, platforms, schedulers, or enable flags, and fixes `authority={"research_only": true, "no_order": true}`. Loaders never infer classification from profile names, display names, or tickers; profiles lacking an explicit owner entry stay `not_mapped` and cannot consume M0 research outputs.

An example resides at [`registry/strategy_context_coverage_catalog.example.json`](registry/strategy_context_coverage_catalog.example.json). Example files are not production catalogs; adopting repositories must create owner-reviewed instances explicitly bound to their profiles.

## Required fields per entry

- `strategy_kind`: e.g., `equity_selection`, `diversified_etf_rotation`, `dca`, `crypto_pool_rotation`, `multi_strategy_combo`, or `risk_overlay`; unknown values fail closed.
- `instrument_classes`: e.g., `single_equity`, `etf`, `leveraged_etf`, `crypto_asset`, `multi_asset`, or `plugin`.
- `exposure_buckets`: owner-maintained comparable risk-exposure tags (sector, region, factor, or underlying index) used as inputs to correlation/overlap checks, never guessed from names.
- `capital_role`: `core`, `satellite`, `defensive`, `reserve`, or `overlay`.
- `benchmark_ids`: identifiers for research and monitoring lookup only; authoritative passive or unlevered benchmarks remain bound via `strategy-benchmark-catalog.v1`.
- `allowed_m0_research_subject_types`: explicit subset of `asset_idea`, `theme_context`, `strategy_hypothesis`, and `risk_context`.

## Boundaries with advisor research and strategy lifecycle

Advisor outputs are adapted into M0 research subjects and checked against this catalog for explicit profile coverage. Passing coverage may only create quota-limited, traceable `P1`-`P3` research tasks; it cannot alter `base_score`, risk multipliers, candidate weights, platform routing, or runtime switches.

```text
M0 research subject -> explicit coverage catalog -> P1-P3 research/backtest/evidence
                    -> immutable candidate -> P0 Shadow (zero weight) -> M1 display
```

Single-stock ideas therefore cannot switch sector or leveraged ETFs, and theme views cannot bypass DCA cadence, benchmarks, or risk constraints. P0 `selection_input.v1` continues accepting only verifiable market data, platform health, and admitted immutable candidates—never this catalog or advisor prose directly.

## Migration sequence

1. Strategy/plugin owners author explicit entries for their profiles with benchmark and exposure rationale in PRs.
2. Once catalog validation passes, the M0 adapter may emit `research task` items; unmapped profiles display `not_mapped`.
3. Bind passing `P1`-`P3` results to immutable candidates before entering the P0 Shadow flow.
4. Authoritative benchmarks, risk gates, reconciliation, lifecycle state, and platform approvals remain independent fail-closed controls.
