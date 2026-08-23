from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from quant_platform_kit.strategy_lifecycle.forward_risk_driver import (
    InvalidForwardRiskArtifact,
    build_forward_risk_terminal_artifact,
    build_nonready_forward_risk_stage,
    build_ready_forward_observation_stage,
    build_ready_portfolio_risk_stage,
    canonical_forward_risk_terminal_bytes,
    forward_risk_terminal_sha256,
    validate_forward_risk_terminal_artifact,
)
from quant_platform_kit.strategy_lifecycle.research_driver import (
    RESEARCH_DRIVER_DOMAINS,
    build_nonready_research_stage,
    build_ready_research_stage,
    build_research_driver_terminal_artifact,
)


ROOT = Path(__file__).parents[1]
SCHEMA_PATH = ROOT / "src/quant_platform_kit/schemas/forward-risk-terminal.v1.schema.json"


def _research_terminal(domain: str = "us_equity", *, ready: bool = True):
    p3 = (
        build_ready_research_stage(
            "p3_evidence", artifact_id="evidence-001", artifact_sha256="c" * 64
        )
        if ready
        else build_nonready_research_stage(
            "p3_evidence", status="DEFERRED", reason_codes=("evidence_pending",)
        )
    )
    return build_research_driver_terminal_artifact(
        run_id="daily-20260824",
        generated_at="2026-08-24T20:00:00+08:00",
        strategy_id="strategy-001",
        candidate_id="candidate-001",
        domain=domain,
        p1_input=build_ready_research_stage(
            "p1_input", artifact_id="manifest-001", artifact_sha256="a" * 64
        ),
        p2_freeze=build_ready_research_stage(
            "p2_freeze", artifact_id="freeze-001", artifact_sha256="b" * 64
        ),
        p3_evidence=p3,
    )


def _p4(mode: str = "shadow"):
    return build_ready_forward_observation_stage(
        mode=mode,
        artifact_id="forward-001",
        artifact_sha256="d" * 64,
        candidate_id="candidate-001",
        observed_at="2026-08-24T20:30:00+08:00",
        expires_at="2026-08-26T20:30:00+08:00",
    )


def _p5():
    return build_ready_portfolio_risk_stage(
        artifact_id="risk-001",
        artifact_sha256="e" * 64,
        candidate_id="candidate-001",
        observed_at="2026-08-24T20:40:00+08:00",
        expires_at="2026-08-25T20:40:00+08:00",
    )


def _build(domain: str = "us_equity", **overrides):
    values = {"p4_forward": _p4(), "p5_risk": _p5()}
    values.update(overrides)
    return build_forward_risk_terminal_artifact(
        research_terminal=_research_terminal(domain),
        generated_at="2026-08-24T21:00:00+08:00",
        **values,
    )


@pytest.mark.parametrize("domain", sorted(RESEARCH_DRIVER_DOMAINS))
def test_all_asset_domains_share_one_ready_p4_p5_contract(domain):
    artifact = _build(domain)
    assert artifact["terminal_status"] == "READY"
    assert artifact["domain"] == domain
    assert artifact["no_order"] is True
    assert artifact["permission_effect"] == "none"
    assert artifact["broker_dependency"] is False


@pytest.mark.parametrize("mode", ["shadow", "paper"])
def test_p4_can_describe_shadow_or_existing_paper_evidence_without_broker_access(mode):
    artifact = _build(p4_forward=_p4(mode))
    assert artifact["stages"]["p4_forward"]["mode"] == mode
    assert artifact["broker_dependency"] is False


def test_missing_observations_still_emit_a_deferred_terminal_artifact():
    artifact = _build(p4_forward=None, p5_risk=None)
    assert artifact["terminal_status"] == "DEFERRED"
    assert artifact["stages"]["p4_forward"]["status"] == "DEFERRED"
    assert artifact["stages"]["p5_risk"]["status"] == "DEFERRED"


def test_p5_cannot_bypass_missing_p4():
    artifact = _build(p4_forward=None)
    assert artifact["terminal_status"] == "PARKED"
    assert artifact["stages"]["p5_risk"] == {
        "stage": "P5",
        "status": "PARKED",
        "mode": "portfolio_risk",
        "artifact": None,
        "reason_codes": ["p4_forward_not_ready"],
    }


def test_ready_p4_p5_cannot_bypass_nonready_p1_p3_terminal():
    artifact = build_forward_risk_terminal_artifact(
        research_terminal=_research_terminal(ready=False),
        generated_at="2026-08-24T21:00:00+08:00",
        p4_forward=_p4(),
        p5_risk=_p5(),
    )
    assert artifact["terminal_status"] == "PARKED"
    assert artifact["research_terminal_status"] == "DEFERRED"
    assert artifact["stages"]["p4_forward"]["reason_codes"] == [
        "research_terminal_not_ready"
    ]


def test_stale_or_wrong_candidate_observation_is_parked():
    stale = _p4()
    stale["artifact"]["expires_at"] = "2026-08-24T20:59:59+08:00"
    artifact = _build(p4_forward=stale)
    assert artifact["terminal_status"] == "PARKED"
    assert artifact["stages"]["p4_forward"]["reason_codes"] == [
        "p4_observation_invalid"
    ]

    wrong_candidate = _p4()
    wrong_candidate["artifact"]["candidate_id"] = "candidate-002"
    artifact = _build(p4_forward=wrong_candidate)
    assert artifact["stages"]["p4_forward"]["status"] == "PARKED"


def test_python_output_matches_closed_json_schema():
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    assert list(validator.iter_errors(_build("crypto"))) == []


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("no_order", False),
        ("permission_effect", "live"),
        ("broker_dependency", True),
        ("terminal", False),
    ],
)
def test_authority_guards_fail_closed(field, value):
    artifact = _build()
    artifact[field] = value
    with pytest.raises(InvalidForwardRiskArtifact):
        validate_forward_risk_terminal_artifact(artifact)


def test_validator_rejects_tampered_status_and_dependency_chain():
    artifact = _build()
    artifact["terminal_status"] = "DEFERRED"
    with pytest.raises(InvalidForwardRiskArtifact, match="terminal_status"):
        validate_forward_risk_terminal_artifact(artifact)

    artifact = _build()
    artifact["stages"]["p4_forward"] = build_nonready_forward_risk_stage(
        "P4", status="DEFERRED", reason_codes=("forward_pending",)
    )
    artifact["terminal_status"] = "DEFERRED"
    with pytest.raises(InvalidForwardRiskArtifact, match="P5 READY"):
        validate_forward_risk_terminal_artifact(artifact)


def test_canonical_digest_and_copy_isolation_are_deterministic():
    artifact = _build("hk_equity")
    reordered = json.loads(json.dumps(artifact))
    assert canonical_forward_risk_terminal_bytes(reordered) == (
        canonical_forward_risk_terminal_bytes(artifact)
    )
    assert forward_risk_terminal_sha256(reordered) == (
        forward_risk_terminal_sha256(artifact)
    )
    validated = validate_forward_risk_terminal_artifact(artifact)
    validated["stages"]["p4_forward"]["artifact"]["artifact_id"] = "changed"
    assert artifact["stages"]["p4_forward"]["artifact"]["artifact_id"] == "forward-001"


def test_research_terminal_digest_is_bound_and_rejects_bad_format():
    artifact = _build()
    assert len(artifact["research_terminal_sha256"]) == 64
    tampered = copy.deepcopy(artifact)
    tampered["research_terminal_sha256"] = "sha256:not-valid"
    with pytest.raises(InvalidForwardRiskArtifact, match="SHA-256"):
        validate_forward_risk_terminal_artifact(tampered)

