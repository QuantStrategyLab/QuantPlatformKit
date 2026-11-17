# Specification index

[English README](../README.md) · [中文 README](../README.zh-CN.md)

Read documents at the library revision used by your consumer. These are source-level specifications and design references, not evidence of deployed versions or permission to trade.

## Architecture and implementation

- [Architecture](ARCHITECTURE.md) ([中文](ARCHITECTURE.zh-CN.md)): [layers](ARCHITECTURE.md#2-layer-descriptions), [data flow](ARCHITECTURE.md#3-data-flow), [design patterns](ARCHITECTURE.md#4-design-patterns), [naming](ARCHITECTURE.md#5-naming-conventions), [dependencies](ARCHITECTURE.md#6-dependency-graph) and [cross-cutting concerns](ARCHITECTURE.md#7-cross-cutting-concerns).
- [Development standard: English overview](design-spec-overview.md) · [complete Chinese v1.0 standard](design-spec.md): platform/strategy development, configuration, monitoring, security and checklists. The v1.0 plugin examples are historical; see the compatibility section below before reading mount examples.
- [Strategy-platform configuration](strategy-platform-spec.md): [source of truth](strategy-platform-spec.md#single-source-of-truth), [strategies](strategy-platform-spec.md#adding-a-new-strategy), [platforms](strategy-platform-spec.md#adding-a-new-platform), [validation](strategy-platform-spec.md#configuration-validation) and [scheduler timezones](strategy-platform-spec.md#scheduler-timezone-rules). Legacy plugin/config-sync examples must be read with the historical boundary below.
- [Lifecycle AI task service migration (V2)](ai-service/task-service-v2.md) ([中文](ai-service/task-service-v2.zh-CN.md)): `TaskClient` V2 routing, idempotency, pending recovery and drift-review inputs.
- [QPK downstream pin automation token configuration](qpk-repo-sync-auth.md) ([中文](qpk-repo-sync-auth.zh-CN.md)): GitHub App installation tokens, failover, secret inventory and Binance separation.
- [Strategy–M0 research coverage catalog](strategy-context-coverage-catalog.md) ([中文](strategy-context-coverage-catalog.zh-CN.md)): explicit profile mapping to M0 research subject types and `not_mapped` defaults.

## Runtime contracts

- [Cloud Run revision tags](cloud-run-tags.md): pinned offline allocation, exact-target warmup policy and caller restore requirements.
- [Strategy release and runtime receipt contract (v1)](strategy-release-runtime-contract.md) ([中文](strategy-release-runtime-contract.zh-CN.md)) and [one-time setup intent](strategy-release-runtime-contract.md#one-time-setup-intent): release identity receipts and immutable, non-executing owner setup scope without runtime activation authority.
- [Strategy release readiness gate](strategy-release-readiness.md) ([中文](strategy-release-readiness.zh-CN.md)): pre-release checks, content-hashed plugin bundles and findings.
- [Runtime execution environment contract](runtime-execution-environment.md) ([中文](runtime-execution-environment.zh-CN.md)): `dry_run`, `paper` and `live` side-effect boundaries.
- [Runtime-selectable allowlist v1](runtime-selectable-allowlist-v1.md) ([中文](runtime-selectable-allowlist-v1.zh-CN.md)): platform-selectable profiles without lifecycle or live authority.
- [Account identity gate](account-identity-gate.md) ([中文](account-identity-gate.zh-CN.md)): read-only account metadata verification and `observe`/`enforce` boundaries.
- [Account new-risk gate](account-new-risk-gate.md) ([中文](account-new-risk-gate.zh-CN.md)): reconciliation health axes, capital envelope, Policy A drift gate and persistent `CIRCUIT_BREAKER_OPEN` log.
- [Account owner fence operations](account-owner-fence-ops.md) ([中文](account-owner-fence-ops.zh-CN.md)): `claim_account_owner` exclusive fence and manual handoff steps.
- [Immutable execution outcomes](execution-outcomes.md) ([中文](execution-outcomes.zh-CN.md)): create-only `execution_markers/` and `execution_outcomes/` separation.
- [Execution receipt contract v1](execution-receipt-contract.md) ([中文](execution-receipt-contract.zh-CN.md)): redacted `qsl_execution_receipt.v1` outcomes attached to runtime reports.
- [Broker reconciliation continuity contract](broker-reconciliation-continuity.md) ([中文](broker-reconciliation-continuity.zh-CN.md)): `RECONCILE_ONLY` recovery, v2 baseline enrollment and CAS activation plan.
- [Decision data binding (v1)](decision-data-binding.md) ([中文](decision-data-binding.zh-CN.md)): separation of verified historical data artifacts, live quotes and order entry.
- [Multisource daily bar data assurance gate](multisource-data-assurance.md) ([中文](multisource-data-assurance.zh-CN.md)): independent market-data consistency checks (`VERIFIED` / `DEGRADED` / `PARKED`).
- [Capital envelope target scaling and attention budget](capital-envelope-target-scale-v1.md) ([中文](capital-envelope-target-scale-v1.zh-CN.md)): single-path `combined_scale` and drawdown budget resolution.
- [Actionable attention thresholds v1](operational-attention-v1.md) ([中文](operational-attention-v1.zh-CN.md)): `AttentionLevel` grading and transition-deduplicated Telegram alerts.
- [Platform notification outcomes](platform-notification-outcomes.md): credential-free intents, receipts and log redaction.
- [Unified operator format](unified-operator-format.md): five sections, count semantics and display-only rollout.
- [Notification routing policy](notification-routing-policy.md): durable daily facts and urgent incidents.
- [Alpaca public market data collection](alpaca-public-market-data.md): manual, read-only workflow and its secrets.
- [Platform repository boundaries](platform-repo-boundaries.md) ([中文](platform-repo-boundaries.zh-CN.md)).
- [Lifecycle policy](strategy-lifecycle-policy.md) ([中文](strategy-lifecycle-policy.zh-CN.md)).
- [Strategy lifecycle terminology](strategy-lifecycle-terminology.md) ([中文](strategy-lifecycle-terminology.zh-CN.md)): canonical lifecycle states and legacy status compatibility.
- [Pending order evidence v1](pending-order-evidence-v1.md): optional journal evidence without budget release.
- [Paper execution consumer](paper-execution-command-consumer.md), [portfolio action matrix](strategy-portfolio-action-matrix.md) and [evidence package](evidence-package-template.md).
- [IBKR read-only order outcomes](ibkr-order-outcomes.md): identity-bound terminal observations without execution authority.

## Research, backtesting, and promotion

- [Strategy promotion and risk standard](strategy-promotion-risk-standard.md) ([中文](strategy-promotion-risk-standard.zh-CN.md)): `live_ready` vs. `kelly_ready`, Paper observation period, risk metrics and `v2`/`v3` evidence packages.
- [QSL backtest standard v1](backtest-standard-v1.md) ([中文](backtest-standard-v1.zh-CN.md)): required research metrics, cost scenarios, causal timing and walk-forward rules.
- [`research_stats` reference](research-stats.md) ([中文](research-stats.zh-CN.md)): PSR, DSR, PBO, stationary bootstrap and cost-stress primitives.
- [Research execution and cost models v1](research-execution-models-v1.md) ([中文](research-execution-models-v1.zh-CN.md)): `FillModel` and `CostModel` pure helpers.
- [Kelly contract v2](kelly-contract-v2.md) ([中文](kelly-contract-v2.zh-CN.md)): `bet_loss_risk_share` vs. `capital_exposure` units and fail-closed gates.
- [Window metrics semantics](window-metrics-semantics.md) ([中文](window-metrics-semantics.zh-CN.md)): `qpk.window_metrics.v2` `ddof`, daily win-rate semantics, benchmark alignment and `qpk.net_compounding.v1`.
- [Forward observation runtime contract](forward-observation-runtime-contract.md) ([中文](forward-observation-runtime-contract.zh-CN.md)): `ForwardObservationPolicy`, shadow/paper channels and `forward_observation_receipt.v1`.
- [P2 real paired shadow evidence contract](paired-shadow-evidence.md) ([中文](paired-shadow-evidence.zh-CN.md)): `paired_shadow_evidence.v1` chained receipts and report artifacts.
- [Non-live execution evidence binding](non-live-execution-evidence-binding.md) ([中文](non-live-execution-evidence-binding.zh-CN.md)): `non_live_execution_evidence_binding.v1` across shadow and paper channels.
- [Adaptive allocation control plane](adaptive-allocation-control-plane.md) ([中文](adaptive-allocation-control-plane.zh-CN.md)): shadow-only `qsl.selection_decision.v1` and boundary with advisor research.
- [Cross-asset research driver contract](cross-asset-research-driver.md) ([中文](cross-asset-research-driver.zh-CN.md)): P1–P3 `research_driver_terminal.v1` across US, CN, HK and Crypto.
- [Cross-asset P4/P5 forward-risk observation contract](cross-asset-forward-risk-driver.md) ([中文](cross-asset-forward-risk-driver.zh-CN.md)): `forward_risk_terminal.v1` pure observation adapter.
- [Synthetic combo evidence](synthetic-combo-evidence.md) ([中文](synthetic-combo-evidence.zh-CN.md)): `learning_only` correlated-group haircut evidence.
- [Unified net return research report (中文)](unified-net-report.md): B3 `build_unified_net_report` specification.
- [Same-frequency net return path diagnostics (中文)](net-path-diagnostics.md): `qsl.net_path_diagnostics.v1` underwater and loss-run metrics.
- [B1/B2 continuous volatility and drawdown scaling preregistration proposal (中文)](b1-b2-preregistration-proposal.md): offline study proposal.
- [Operational shadow and statistical edge dual-gate proposal (中文)](promotion-dual-gate-proposal.md): proposed O/S review gates.
- [Cross-asset integration plan (中文)](cross-asset-integration-plan.md): CN, HK and Crypto inventory onboarding sequence.

## Historical compatibility

- [Legacy plugin runtime contract](strategy-plugin-runtime-contract.md) ([中文](strategy-plugin-runtime-contract.zh-CN.md)): **HISTORICAL / no authority effect**. Retained for replay and migration troubleshooting; not the current platform-mount specification.
- Automatic name-based `latest_signal.json` mounts are retired. V2 observation/notification evidence does not enable Paper/Live or establish P4–P6 eligibility. A runnable composite candidate needs its own bound revisions, inputs, portfolio rules and P1–P3/target-channel evidence, as stated in the linked contract.

Provider rights, credential restrictions, risk controls and the repository [license](../LICENSE) remain applicable.
