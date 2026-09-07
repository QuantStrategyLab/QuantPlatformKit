# Research Promotion HITL Cycle Implementation Plan

> **For agentic workers:** Implement task-by-task. No live authority.

**Goal:** Wire drift → bounded re-optimization → non-live shadow evidence → human notify/decide, without granting live trading authority.

**Architecture:** Thin driver in QuantPlatformKit `strategy_lifecycle` that freezes a durable ticket, reuses existing drift/optimize/shadow/notify primitives, and stops at `awaiting_human`. Human accept only records operator intent; it never enables live.

**Tech Stack:** Python 3.12, existing QPK strategy_lifecycle contracts, pytest.

---

### Task 1: Ticket + budget + driver (TDD)

- Create: `src/quant_platform_kit/strategy_lifecycle/research_promotion_cycle.py`
- Test: `tests/test_research_promotion_cycle.py`

### Task 2: CLI decide/notify hooks

- Modify: `src/quant_platform_kit/strategy_lifecycle/cli.py`
- Modify: `src/quant_platform_kit/strategy_lifecycle/__init__.py` exports

### Task 3: Autopilot handoff note

- Modify: `codex_integration._process_optimization_decision` to attach a promotion ticket id when human approval is required (still `execution_authorized=False`).


### Task 4: Telegram notify + paired-shadow record helper

- Add: `make_telegram_research_promotion_notifier` (soft-skip when unconfigured)
- Add: `shadow_record_from_paired_evidence` + `require_paired_shadow` budget flag
- Wire Codex autopilot ticket open to Telegram notify hook
- Still no live enablement after accept

### Task 5: Non-live paired-shadow adapter feed

- Add: `paired_shadow_adapter.py` (`collect_paired_shadow_for_promotion`, `resolve_promotion_shadow_record`)
- Codex autopilot prefers `store.collect_paired_shadow_observation` when present; else explicit proxy marker
- Still no live enablement after accept

### Task 6: Human confirmation contract (platform / mode / risk)

- Accept requires `PromotionConfirmation`: target_platform, execution_mode (`live`|`paper`), risk_profile
- Default suggested risk profile: `CAPITAL_PRESERVATION`
- `paper` only when broker truly supports paper/sim; **no synthetic matching**
- Accept still never sets `live_authority_granted`

### Task 7: Soft-sync awaiting tickets to QuantRuntimeSettings console

- Add: `make_console_research_promotion_sync` (soft-skip when URL/token unset)
- Wire Codex autopilot `open_awaiting_human_ticket(..., sync_console=...)`
- Env on research runner:
  - `RESEARCH_PROMOTION_SYNC_URL=https://<console-host>/api/internal/sync-research-promotion-ticket`
  - `RESEARCH_PROMOTION_SYNC_TOKEN` must equal QRT Worker secret `RESEARCH_PROMOTION_SYNC_TOKEN`
- Failures soft-skip; never grant live authority
- Console accept/reject is an **intent ledger** in QRT KV
- Local follow-up: `quant-lifecycle research-promotion-pull --ticket <path>` reads
  `GET /api/internal/research-promotion-ticket?ticket_id=...` (same sync token) and
  applies the console decision onto the local awaiting ticket without granting live
