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
