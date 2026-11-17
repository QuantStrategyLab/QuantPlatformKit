# Lifecycle AI Task Service Migration (V2)

[简体中文](task-service-v2.zh-CN.md)

Note: This baseline describes local migration behavior in `QuantPlatformKit`; downstream pinned consumer versions do not include it until those pins are explicitly updated.

`strategy_lifecycle/ai_provider.py` now uses `ai_service.client.TaskClient` and calls only the V2 submit and query endpoints. The legacy HTTP client, CLI/VPS routing, built-in model mappings, provider chains, and paid fallbacks have been removed. `AiProviderConfig` takes `label`, `mode`, `model`, and `profile`; the legacy `codex_vps()`, `claude()`, and `gpt()` factories are removed.

The reusable drift workflow downloads pinned `QuantAIService` (`2.0.13`) and `QuantPlatformKit` (`1.0.0`) wheels from GitHub Releases into a temporary runner directory under HTTPS, timeout, and size limits, verifying each wheel's configured SHA-256 without falling back to public package indexes. Core `QuantPlatformKit` features do not eagerly import the AI client; enabling AI paths requires the client wheel, `AI_SERVICE_URL`, `AI_SERVICE_AUDIENCE`, and an approved token client or GitHub Actions OIDC. Legacy `CODEX_AUDIT_SERVICE_*` and `AI_GATEWAY_RESEARCH_PROVIDERS` variables are no longer used by this module.

## Routing and results

Standard execution reads `AI_SERVICE_MODE` (default `agent`), `AI_SERVICE_MODEL` (must be set explicitly), and `AI_SERVICE_PROFILE` (default `default`). Reviewers read an explicit routing list from `AI_SERVICE_REVIEWERS_JSON`, with an optional verifier specified via `AI_SERVICE_VERIFIER_JSON` (none by default). Example:

```json
[
  {"label": "reviewer-primary", "mode": "agent", "model": "configured-dot", "profile": "default"},
  {"label": "reviewer-secondary", "mode": "agent", "model": "configured-grok", "profile": "second-opinion"}
]
```

The server resolves the actual provider and project permissions; `label` names a review role rather than proving vendor or model identity. Duplicate `(mode, profile)` pairs cannot act as two distinct review paths, and distinct profiles alone do not prove host, account, or tool isolation—formal independent review requires separate endpoints and permission boundaries on the service side.

Task requests carry only the objective, materials, output schema, timeout, mode, and profile. Lifecycle outputs return inside a `report` string whose domain JSON is validated by the lifecycle caller. Responses must match the original task ID and request binding and carry completion plus advisory status before parsing. API routes verify the reported model; persistent assistants must set `model_verification=unavailable` rather than fabricating legacy Codex model or reasoning-effort proof.

## Retries and research authority

Callers supply an operation idempotency key (or reuse the GitHub Actions run ID) with role, materials, model, and route included in the digest. Research promotion decisions hash the full prompt constructed from frozen inputs as the operation identity. Client timeouts and read failures on a known task retain the task ID and stay `outcome_unknown` with no automatic fallback or re-trigger.

Research flows store `ai_task_pending` as `deferred` rather than a negative research opinion. Subsequent runs query the original task through a dedicated pending reader; the `resume_task_id` path never submits a new task and re-verifies the original request binding. Without a pending reader, the ticket stays pending; mismatched configuration or materials block adopting the old result. Parsing for legacy Codex capacity-deferral records stays intact to avoid rewriting historical research evidence, without restoring legacy service compatibility.

AI completion and recommendations never grant numerical research, trading, capital, or release authority. Existing source freshness, frozen inputs, Python numerical checks, backtests, paired shadow validation, risk conditions, and human candidate decisions remain mandatory. Historical `codex_integration.py` filenames and existing evidence logs remain unchanged.

## Local verification

Tests use synthetic inputs and fake task clients only, without calling live models or reading real market or account data. Coverage spans task result binding, API model mismatch, unverifiable persistent-assistant models, idempotency keys, unknown outcomes, timeouts, original-task recovery, dual reviewer roles, research recovery, and risk admission. Offline tests do not prove live Dot/Grok connectivity or production research readiness.

## Shared material and review helpers

`ai_patch.py` permits bounded replacements only on caller-whitelisted existing files matching a baseline digest and unique anchor; syntax and domain validation remain caller responsibilities before writing candidates, with no hardcoded platform or strategy allowlist.

`research_task.py` preserves the watcher wire schema and validates source completeness and strictly typed research bounds without hardcoded SOXL defaults; non-empty parameter-bound digests require caller-supplied allowlists validated against business provenance by strategy repositories.

`research_summary.py` defaults to API mode with explicit model and profile configuration and returns `unavailable` when unconfigured. `task_review.py` checks task identity, unique roles, unique task IDs, and schema completeness across requested reviewer roles. Every role must finish to form an advisory quorum, and disagreements require human judgment. It sends no external messages and grants no trading, deployment, or release authority.

## Drift review inputs

The reusable workflow passes complete `DriftResult` dimensions, observed values, baseline values, thresholds, observation date, baseline source, and drift score algorithm metadata to review without fabricating missing evidence; incomplete materials remain `PARKED`. Pinned client and QPK wheel digests remain unchanged.

Manual dispatch supports `verification_only` to run detection and AI review while skipping GitHub Issue creation. Scheduled runs keep default behavior where all outputs remain advisory. Manual verification succeeds only when all advisory tasks complete (including valid negative or human-check recommendations); pending, unknown, or technical failures still fail verification. Scheduled runs treat completed negative or split AI opinions as normal workflow completion while preserving `PARKED` status and `ok=false` adoption gates, failing only on pending, unknown, or technical errors.
