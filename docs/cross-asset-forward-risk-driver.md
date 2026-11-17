# Cross-Asset P4/P5 Forward-Risk Observation Adapter Contract

[简体中文](cross-asset-forward-risk-driver.zh-CN.md)

## Architecture overview

The P1-P3 research driver binds inputs, frozen configuration, and historical/OOS evidence. Because P4/P5 carry distinct temporal and account/portfolio properties, they remain separate in `forward_risk_terminal.v1` as a second pure-observation envelope:

```text
P1-P3 terminal digest
-> P4 shadow/forward (or existing paper) identity
-> P5 portfolio RiskSnapshot identity
-> READY / DEFERRED / PARKED terminal artifact
```

## Authority boundaries

This adapter fixes:

- `no_order=true`
- `permission_effect=none`
- `broker_dependency=false`
- No paper, shadow, or live runtime startup
- No market-data fetching, strategy execution, sizing calculation, or broker connection
- `READY` indicates evidence completeness only and grants no shadow, paper, or live authority

In P4, `mode=paper` only denotes consuming simulated results already produced and verified by another platform; the QPK adapter itself never connects to a paper broker. Platforms without paper support use `mode=shadow` without being blocked.

## P4/P5 READY criteria

| Stage | Artifact schema | Additional constraints |
|---|---|---|
| P4 | `forward_observation.v1` | P1-P3 terminal must be `READY`; `candidate` must match; artifact must be unexpired when terminal is built |
| P5 | `portfolio_risk_snapshot.v1` | P4 must be `READY`; `candidate` must match; `RiskSnapshot` identity must be unexpired |

Missing normal upstream inputs yield `DEFERRED`; malformed, expired, candidate-mismatched, or out-of-order artifacts yield `PARKED`. Every valid P1-P3 terminal can emit one P4/P5 terminal artifact; a green workflow run never substitutes for the terminal file.

## Existing producer fit

- `ShadowValidator` reads recent performance snapshots for comparison but does not define cross-asset immutable P4 artifacts; strategy producers must emit `forward_observation.v1`.
- `RiskSnapshot` already enforces fail-closed expiry, Kelly fraction, risk budget, and circuit-breaker checks, making it suitable as the P5 producer; this contract binds its immutable identity without duplicating risk logic.
- `lifecycle_matrix_runtime` already aggregates P4/P5 terminal state read-only and continues consuming these artifacts once producers are wired.
- Paper is not a universal prerequisite: paper-capable platforms emit P4 paper observations, while others satisfy P4 via no-order shadow/forward observations.

## Incremental rollout

1. Emit P1-P3 terminals across all asset domains, reporting `DEFERRED` or `PARKED` honestly when evidence is absent.
2. Adapt daily strategy shadow reports to `forward_observation.v1` without altering strategy math.
3. Serialize and hash existing `RiskSnapshot` outputs as `portfolio_risk_snapshot.v1`.
4. Emit the P4/P5 envelope from an `always()` workflow terminal step.
5. Read artifacts from the read-only matrix while live/runtime paths continue relying on independent authority and the Risk Gate.

Avoid adding a second scheduler, general event bus, or direct paper/broker execution inside this adapter; doing so re-couples the evidence layer to execution.
