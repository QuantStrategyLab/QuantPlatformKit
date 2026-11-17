# Actionable Attention Thresholds v1 (`AttentionLevel`)

[简体中文](operational-attention-v1.zh-CN.md)

Scope: notification severity grading and human recovery routing only; grants no live authority, raises no RRL, and performs no Kelly calculations.

## Principles

1. **Never** send Telegram alerts on TQQQ/SOXL using a global absolute drawdown cutoff (such as 10%).
2. Evaluate drawdown strictly relative to explicit `mandate_dd_budget`; omit the axis if no budget is provided.
3. Notify only on `ACTION` or `HALT`, keyed by state transitions, and record markers only after delivery succeeds.
4. Automatic brakes remain in `NEW_RISK` and `RiskEngine`; this module classifies attention and renders short messages only.

## API

- `evaluate_attention(AttentionAxes | mapping) -> AttentionDecision`
- `resolve_mandate_dd_budget(profile)` — defaults to `0.35` for SOXL/TQQQ (not 10%)
- `attention_transition_key(...)` deduplication key
- `render_attention_compact(locale=...)` (`zh-CN` -> `zh`)
- `publish_attention_telegram_transition` — sends Telegram alerts only on `ACTION`/`HALT` transitions
- `build_drift_alert` / `publish_drift_alerts`: `WATCH` opens no page; Telegram calls `send_telegram_message`; missing config logs and returns `skipped` rather than swallowing exceptions

When Telegram delivery raises or returns `False`, logged keys mask the account segment as `redacted`. Sending, marker persistence, and deduplication continue using the raw transition key; failed or skipped sends never write a success marker. Consumers adopt log redaction only upon updating their pinned QPK revision.

## Severity levels

| Level | Examples | Telegram |
|---|---|---|
| `OK` | Path drawdown within budget | No |
| `WATCH` | Drift `watch`; `dd_ratio` in `[0.7, 1)` | No |
| `ACTION` | `NEW_RISK` prohibits buys; drift `review`; drawdown breaches mandate | Yes (transition) |
| `HALT` | Drift `critical`; reconciliation uncertain; hard `PARK` | Yes (transition) |

## Operational acceptance

Attention messages describe notification classification and delivery outcomes only. Verifying order rejection, buy blocks, or buy-side scaling requires inspecting each platform's deployed revision, risk inputs, and actual cycle evidence rather than library API availability alone. Missing daily-loss facts or unconfirmed `assess_with_evidence` calls retain their unknown states.
