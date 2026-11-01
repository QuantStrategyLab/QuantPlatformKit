# Offline risk gate replay

The dedicated `quant_platform_kit.risk.gate.replay` module provides
`replay_apply_risk_gate` and `replay_assess_with_evidence`. Each requires a UTC
whole-second `evaluation_time` and accepts the corresponding live gate's
inputs. The replay invokes the same risk engine and static checks using that
time. The evidence path applies the usual candidate, mandate, snapshot and
risk-state validations at the supplied time; the live evidence API retains its
wall-clock freshness restriction. Runtime observers are not invoked.

Both functions return `ReplayRiskGateResult`, a record with fixed
`executable=false`, `scope=research_only` and `provenance_status=unverified`,
rather than a `StrategyDecision` or live `RiskGateResult`.
It is for offline analysis and does not authorize an order or establish that an
order or fill occurred. A replay caller must independently freeze and bind the
actual input bytes, candidate, configuration, engine revision and availability
times; supplying a historical clock alone does not establish point-in-time
provenance or production parity. The replay wrapper does not compute or verify
an input-manifest digest.
