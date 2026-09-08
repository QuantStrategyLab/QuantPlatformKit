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

## 2026-09-08 候选读回与人工决定回收

本次接续仅补齐 QRT 候选送达确认和已保存票据的人工决定回收。沿用
`research_promotion_cycle` 的 ticket、保存/加载和决定校验，不新增票据系统。

`make_console_research_promotion_sync(..., pull_console=None)` 保留返回布尔值的接口。
它先 GET 同一 ticket；只有确认 404 才允许一次 POST，写后再 GET。HTTP 2xx
本身不代表送达，只有候选身份、参数、预算、回测与 shadow 证据、通知材料及
awaiting 状态完整一致才返回 `True`。QRT 添加的展示字段不作为权限输入。
Python `1.0` 与 JavaScript JSON 写回的 `1` 视为同一数值，布尔值仍与数字区分。
未知 POST 结果只读对账；同一个同步回调对已尝试的 ticket 不再 POST。
该回调内的限制不是跨进程持久化去重，调用方须串行处理同一 ticket。

同步使用 `make_console_research_promotion_pull(..., raise_on_unavailable=True)`：
此模式下 `None` 仅表示已确认 404；权限失败、超时、非法响应和错 ticket 都抛固定
脱敏错误。默认模式保留 `None` 表示不可用的旧接口。注入同步 `pull_console`
的调用者必须遵守严格模式语义，不能把网络错误转换成 404。

正常周期和原有 `research-promotion-pull` CLI 共享以下入口：

```python
reconcile_saved_research_promotion_ticket(
    ticket_path, *, pull_console=None, output_path=None, domain=None,
) -> dict
```

返回 `ticket_id`、`strategy_profile`、`state`、`status`、固定 `reason` 和恒为
`False` 的 `live_authority_granted`。状态语义如下：

| status | 含义 |
|---|---|
| `updated` | 完整校验远端决定后，已保存接受/拒绝意图 |
| `awaiting_human` | 一致票据仍等待人工决定，原文件不变 |
| `already_terminal` | 本地已结束；不 GET、不重新处理决定 |
| `unavailable` | 远端不可读/不存在或保存失败；原文件不变 |
| `rejected` | 本地文件或远端候选、证据、决定、权限不符合约定 |
| `skipped` | 不属于请求 domain，或不是 awaiting 票据 |

`run_auto_pilot_cycle(..., pull_console=None)` 在新研究阶段前扫描
`store.local_root/research_promotion_tickets/*.json`，结果写入 `research_decisions`。
坏文件单独返回状态，不阻断其他票据；跨 domain 不访问远端。没有 awaiting
票据或处于 dry-run 时，回收阶段不发 HTTP 请求。本周期仍等待决定、决定不可验证、
或刚完成回收的同 profile 暂停新研究。历史终态不永久禁止新观察对应的研究；
旧 ticket 没有事件/来源 revision，跨 run 与新证据的去重仍未实现。

接受和拒绝都只保存意图，接受所选的 `live` 模式不是 live 授权。完整候选材料、
证据 notes、决定状态与时间必须对应；读回的 live 授权必须显式为 `False`。
保存通过同目录临时文件和原子替换完成；失败保留原票据。重复回收同一本地终态
文件不写入也不重新研究。`--output` 继续表示另存结果；要以该结果继续回收时须把它
作为后续输入文件。CLI 在 `updated`、`already_terminal`、`awaiting_human` 返回 0，
其余受控状态返回 1，不输出底层异常。

本轮新增 46 项离线回归。实际先后复现：初次 24 项失败（缺读回与回收接口）；
扩展后 8 项失败（重复写、原子保存、周期与 CLI）；数值往返 1 项失败，以及后续
tuple/list 往返和缺决定时间 2 项失败，修复后均通过。最终相关 9 文件为
**171 passed、97 subtests passed**，定向 ruff 通过。全部远端交互使用注入替身，
未运行生产 POST、模型、通知、交易或部署。主助手另行报告真实 QRT Worker 的
localhost HTTP / 内存 KV 往返通过：accept/reject 各一次 POST、重复同步只 GET、
匿名与错候选拒绝、接受保持无 live 授权、终态重复回收不改文件。该检查仍使用
合成数据，不是线上业务验证。本轮未新增实验 dispatcher、跨进程并发控制、额度恢复排班，也未接入
`promotion_review` / `research_summary` 模型阶段。
