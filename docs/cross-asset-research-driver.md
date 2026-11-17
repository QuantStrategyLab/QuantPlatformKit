# Cross-Asset Research Driver Contract

[简体中文](cross-asset-research-driver.zh-CN.md)

## Goals and boundaries

`research_driver_terminal.v1` provides a uniform P1-P3 research terminal format across US, CN, HK, and Crypto domains. It aggregates identities of previously generated and validated artifacts without fetching data, running backtests, reading strategy catalogs, or connecting to brokers.

Fixed pipeline boundary:

```text
P1 research input manifest
-> P2 strategy config freeze
-> P3 strategy evidence package
-> READY / DEFERRED / PARKED terminal artifact
```

Every invocation with a valid run/strategy/candidate identity must emit a terminal artifact:

- Valid artifacts across all three stages: `READY`.
- Artifact not yet produced or awaiting normal upstream completion: `DEFERRED`.
- Malformed artifact, digest mismatch, or skipped upstream dependency: `PARKED`.
- Every outcome preserves `no_order=true` and `permission_effect=none`.

## Evidence requirements

| Stage | Required artifact for READY | Notes |
|---|---|---|
| P1 | `research_input_manifest.v1` | Identity and SHA-256 produced after existing P1 validator checks |
| P2 | `strategy_config_freeze.v1` | Identity and SHA-256 of frozen candidate configuration |
| P3 | `strategy_evidence_package.v2` | Identity and SHA-256 produced after existing P3 validator checks |

`catalog_status`, `runtime_enabled`, inventory rows, and web display flags are never evidence. The contract rejects those fields and fixes `catalog_status_used_as_evidence=false`.

## Producer usage

```python
from quant_platform_kit.strategy_lifecycle import (
    build_ready_research_stage,
    build_research_driver_terminal_artifact,
)

terminal = build_research_driver_terminal_artifact(
    run_id="daily-2026-08-24",
    generated_at="2026-08-24T22:00:00+08:00",
    strategy_id="example_strategy",
    candidate_id="candidate-001",
    domain="cn_equity",
    p1_input=build_ready_research_stage(
        "p1_input", artifact_id="manifest-001", artifact_sha256="a" * 64
    ),
    p2_freeze=build_ready_research_stage(
        "p2_freeze", artifact_id="freeze-001", artifact_sha256="b" * 64
    ),
    p3_evidence=None,
)
assert terminal["terminal_status"] == "DEFERRED"
assert terminal["no_order"] is True
```

Production workflows should emit this JSON in a `finally`/`always` step across success, skipped, missing-dependency, and failure branches. This contract never promotes `READY` into shadow, paper, or live; downstream lifecycle consumers still verify artifacts and authority independently.

## Migration guardrails

- Legacy strategies may emit `DEFERRED` initially rather than fabricating P1/P2/P3 completion.
- Allowed `domain` values are strictly `us_equity`, `cn_equity`, `hk_equity`, and `crypto`.
- This module binds validated immutable identities only and does not replace P1/P3 validators.
- Never populate `READY` from catalog/inventory state or infer trading authority from this artifact.
