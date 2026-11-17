# Capital Envelope Target Scaling and Attention Budget

[简体中文](capital-envelope-target-scale-v1.zh-CN.md)

## API

1. `apply_combined_scale_to_targets(targets, combined_scale)`
   - `None` or invalid scale -> **omit** (returns finite non-negative targets unchanged)
   - Valid scale in `[0, 1]` -> scales down only, never scales up
2. `resolve_mandate_dd_budget(profile)`
   - Defaults to `0.35` for SOXL/TQQQ (not 10%)
   - Overridable via explicit `override` or `QSL_MANDATE_DD_BUDGET[_PROFILE]`
3. `publish_attention_telegram_transition` — sends Telegram alerts only on `ACTION`/`HALT` transitions

## Platform consumption

- Scale either buy-side quantities or target weights in one place; applying `combined_scale` twice along one path causes double scaling.
- Deduplicate attention notifications on state transitions and record the marker only after delivery succeeds.
- Daily-loss checks require account-scoped daily-loss facts; missing facts must never be inferred as passing from notification outcomes.

Library APIs and dependency pins do not prove a platform consumes this path. Verify actual adoption by inspecting deployed versions, configuration, and cycle execution evidence.
