from __future__ import annotations

from quant_platform_kit.risk import (
    consume_research_risk,
    consume_research_risk_batch,
)


def _ready(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "lifecycle_status": "ACCEPTED",
        "account_equity": 10_000.0,
        "risk_budget": 0.01,
        "effective_exposure": 0.25,
        "max_loss_estimate": 0.008,
        "drawdown_scalar": 1.0,
        "kelly_fraction": 0.2,
        "applied_fraction": 0.1,
        "circuit_state": "ACTIVE",
        "evidence_package_id": "sha256:research",
        "expires_at": "2099-08-24T00:00:00Z",
    }
    values.update(overrides)
    return values


def test_missing_real_evidence_is_deferred_without_snapshot() -> None:
    result = consume_research_risk("tecl", None)
    assert result.status == "DEFERRED"
    assert result.snapshot is None


def test_ready_record_consumes_canonical_snapshot() -> None:
    result = consume_research_risk("soxl", _ready())
    assert result.status == "READY"
    assert result.snapshot is not None
    assert result.snapshot.to_dict()["evidence_package_id"] == "sha256:research"


def test_batch_keeps_strategy_boundaries_and_fail_closed() -> None:
    results = consume_research_risk_batch({"soxl": _ready(), "smart_dca": {"lifecycle_status": "PARKED"}})
    assert [item.strategy_id for item in results] == ["soxl", "smart_dca"]
    assert [item.status for item in results] == ["READY", "PARKED"]
    assert results[1].snapshot is None
