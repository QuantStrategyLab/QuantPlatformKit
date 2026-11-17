# Forward Observation Runtime Contract

[简体中文](forward-observation-runtime-contract.zh-CN.md)

`quant_platform_kit.strategy_lifecycle.forward_observation` is a pure decision layer shared across strategies, plugins, and platforms. It never connects to brokers, mutates runtime targets, deploys services, or places orders.

`shadow` is the mandatory non-live channel for every forward-observation candidate; `paper` is an **optional target-platform capability**, not a prerequisite for shadow or forward observation. When a target lacks paper support, its policy may list `shadow` only, and `paper_status=unsupported` in snapshots is a valid capability fact rather than a shadow failure.

Every frozen candidate must declare an explicit `ForwardObservationPolicy`: candidate ID, strategy profile, unlevered benchmark, forward trading-day count, review milestones, consecutive healthy cycles required to resume, market calendar, fixed/rolling window, window start, window rationale ref, and exact non-live evidence mode. The controller defines no implicit defaults ("252 days", "20/60 days", or per-strategy presets); candidates missing these fields are rejected rather than inheriting SOXL parameters. Without verified P3 historical evidence and refs, status stays `PARKED`.

Once P3 passes, the controller emits `start_shadow`, `continue_shadow`, and post-recovery `resume_shadow` intents, adding matching `*_paper` intents only when the policy explicitly declares a Paper channel. Shadow-only policies allow only `shadow_decision` evidence; paper-enabled policies require `shadow_decision + simulated_replay` or `shadow_decision + broker_paper`, never conflating simulated replay, order previews, and broker paper. Stale data or inconsistencies in a **configured** Shadow/Paper channel enter auto-recoverable `PAUSED`; risk blocks, human holds, identity mismatches, revocation, or superseding candidates enter non-auto-recoverable terminal states.

Genuine candidate shadow must record candidate and baseline signals, hypothetical orders, positions, costs, and returns on the identical timestamped input snapshot, isolated by `candidate_id`. Recent production strategy performance snapshots serve monitoring only and never substitute for parallel candidate shadow evidence.

Upon completing the candidate's full forward window (for example, 252 trading days for SOXL V7 backed by its backtest and risk validation), the controller stops configured non-live channels and enters `FORWARD_COMPLETE_HUMAN_REVIEW`. Windows vary by strategy when backed by frozen candidate evidence and cannot mutate mid-run. Every returned payload fixes:

- `no_order=true`
- `live_authority_granted=false`
- `live_action=human_approval_required`

Schedulers can automate non-live observation, persistence, and safe pause/resume, while every platform adapter treats outputs strictly as non-live intents. Initial live enablement, re-enablement, capital increases, and parameter edits still require independent human approval and re-validation.

Each valid observation cycle should emit `forward_observation_receipt.v1`, containing candidate ID, full policy digest, observation trading day/sequence, previous receipt digest, P1/P2/P3/risk/release/plugin digests, and exact evidence mode—never raw prices, accounts, orders, or secrets. Validators enforce strictly sequential append, candidate/policy consistency, and adherence to the frozen window.
