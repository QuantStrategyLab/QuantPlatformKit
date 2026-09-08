# Research Promotion HITL Cycle Implementation Plan

> **For agentic workers:** Implement task-by-task. No live authority.

**Goal:** Wire drift → bounded re-optimization → non-live shadow evidence → human notify/decide, without granting live trading authority.

**Architecture:** Thin driver in QuantPlatformKit `strategy_lifecycle` that freezes a durable ticket, reuses existing drift/optimize/shadow/notify primitives, and stops at `awaiting_human`. Human accept only records operator intent; it never enables live.

**Tech Stack:** Python 3.12, existing QPK strategy_lifecycle contracts, pytest.

2026-09-08 quota routing follow-up (local, not deployed): optimization decisions
send `research_stage=optimization` through both the SDK and direct HTTP path.
The gateway selects the model/effort against its Codex roster and account reserve.
Research bypasses any configured API fallback. A quota deferral preserves
`research_promotion_state=deferred` and `retry_at`, without running the optimizer.
Clients check gateway research-routing capability before submission and verify
the completed route metadata. An old SDK/service cannot silently drop this policy.
Publish/deploy the gateway and matching SDK before adopting the QPK consumer.
This is admission/routing, not a new schedule or the missing real-candidate job.

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

2026-09-08 local wiring: `run_auto_pilot_cycle` now uses Codex-only diagnosis (no paid analyze/review fallback or simulated success on failure) and passes candidate-bound callbacks to `run_actionable_research_promotion`. This replaces the direct ticket/proxy shortcut while retaining deterministic proposal risk checks. Missing backtest/shadow bindings park before AI or optimization; the bound path caps search at 25 combinations/4 parameter keys, requires strict WFA/OOS and paired shadow, persists the existing ticket, and syncs only awaiting tickets. `console_synced` is true only for confirmed delivery, false for skipped/failed delivery, and null when unattempted. Human accept remains intent only.

The user explicitly authorizes automatic isolated drift-triggered research; manual approval is at the candidate gate, not before each research phase. The scheduled AAB watcher diagnosis is switched to the existing Codex execute channel with the frozen strategy revision. That watcher still emits a diagnosis comment, not an experiment dispatch. The remaining production binding is one real candidate execution job with authorized inputs, the real optimizer/BacktestOrchestrator WFA/OOS callbacks and paired-shadow collector, and the existing QRT sync URL/token. Current verification is offline/synthetic; no real provider, Codex job, shadow collection, Git publication, or deployment was executed. Do not treat a placeholder US-equity runner or a mock passed flag as production validation.

Local verification (2026-09-08): 133 QPK tests and 83 subtests passed with outbound sockets blocked, covering the autopilot/CLI/reviewer/actionable runner/strict cycle/paired adapter/drift paths. The AAB watcher/diagnosis suites passed 36 tests; its real gateway client was exercised through mocked submit/poll HTTP responses, with no model call. Targeted ruff, workflow actionlint, and diff checks passed. Independent read-only review found no new P1/P2 in this patch; this does not validate deployed behavior. The chosen candidate and authorized real input/shadow bindings are still required for a first real end-to-end run.

## 2026-09-08 F02 日期与研究准入修复接续

此前本页 133/83 等测试数字仅对应前批 HITL/Codex 接线，不代表验证了本轮新增的日期与风险语义。本轮最终验证为 **219 个测试 + 14 subtests**；其中独立 freshness 文件 **32 个测试**，包括过期/未来/缺失日期、观察来源配对、旧 critical/review 禁令延续、null 健康展示、Issue/Codex 调用前拒绝，以及日期/有效期溢出。

`DriftResult`、`StrategyPerformanceSnapshot` 的 `as_of` 缺失/非法时保留 `None`，不替换成今天或哨兵。研究状态可以 unavailable，而已知的 REVIEW/CRITICAL 通过严格 `risk_status` 保持风险禁令。**必须成套发布/安装 probe 与 risk mapper，不能把新 probe 单文件复制给旧 mapper。** 默认 7 个自然日是按日期预算，不声称交易日或精确168小时时效；历史回放必须显式提供 `evaluation_date`，不能覆盖来源 `as_of`。

精确解释器、命令和实际日志：
[本轮完整验证配置](/Users/lisiyi/Projects/.worktrees/aab-hitl-codex-only-20260908/docs/validation/2026-09-08-monitor-drift/qpk-final.json)、
[实际测试输出](/Users/lisiyi/Projects/.worktrees/aab-hitl-codex-only-20260908/docs/validation/2026-09-08-monitor-drift/qpk-final.log)。
完整修改/consumer 清单、RED/GREEN、AAB源码镜像修复及真实恢复前最小步骤见
[本轮交接](/Users/lisiyi/Projects/.worktrees/aab-hitl-codex-only-20260908/docs/monitor-drift-repair-2026-09-08.md)。
本轮未发布 Git、部署、重启、触发模型或券商任务，线上采用和业务恢复仍须分别取证。
