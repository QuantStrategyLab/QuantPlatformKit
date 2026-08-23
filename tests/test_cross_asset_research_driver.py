from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from quant_platform_kit.strategy_lifecycle.research_driver import (
    InvalidResearchDriverArtifact,
    RESEARCH_DRIVER_DOMAINS,
    build_nonready_research_stage,
    build_ready_research_stage,
    build_research_driver_terminal_artifact,
    canonical_research_driver_terminal_bytes,
    research_driver_terminal_sha256,
    validate_research_driver_terminal_artifact,
)


ROOT = Path(__file__).parents[1]
SCHEMA_PATH = (
    ROOT
    / "src/quant_platform_kit/schemas/research-driver-terminal.v1.schema.json"
)


def _ready_stages() -> dict[str, dict[str, object]]:
    return {
        "p1_input": build_ready_research_stage(
            "p1_input", artifact_id="manifest-001", artifact_sha256="a" * 64
        ),
        "p2_freeze": build_ready_research_stage(
            "p2_freeze", artifact_id="freeze-001", artifact_sha256="b" * 64
        ),
        "p3_evidence": build_ready_research_stage(
            "p3_evidence", artifact_id="evidence-001", artifact_sha256="c" * 64
        ),
    }


def _build(domain: str = "us_equity", **overrides):
    stages = _ready_stages()
    stages.update(overrides)
    return build_research_driver_terminal_artifact(
        run_id="daily-20260824",
        generated_at="2026-08-24T22:00:00+08:00",
        strategy_id="strategy-001",
        candidate_id="candidate-001",
        domain=domain,
        **stages,
    )


@pytest.mark.parametrize("domain", sorted(RESEARCH_DRIVER_DOMAINS))
def test_all_supported_asset_domains_share_one_ready_contract(domain):
    artifact = _build(domain)
    assert artifact["terminal"] is True
    assert artifact["terminal_status"] == "READY"
    assert artifact["domain"] == domain
    assert artifact["no_order"] is True
    assert artifact["permission_effect"] == "none"
    assert artifact["catalog_status_used_as_evidence"] is False


def test_missing_stage_still_emits_truthful_deferred_terminal_artifact():
    artifact = _build(p3_evidence=None)
    assert artifact["terminal_status"] == "DEFERRED"
    assert artifact["stages"]["p3_evidence"] == {
        "stage": "P3",
        "status": "DEFERRED",
        "artifact": None,
        "reason_codes": ["p3_evidence_not_produced"],
    }


def test_malformed_evidence_is_parked_instead_of_crashing_or_claiming_ready():
    malformed = _ready_stages()["p1_input"]
    malformed["artifact"]["sha256"] = "not-a-digest"
    artifact = _build(p1_input=malformed)
    assert artifact["terminal_status"] == "PARKED"
    assert artifact["stages"]["p1_input"]["reason_codes"] == [
        "p1_input_invalid"
    ]
    assert artifact["stages"]["p2_freeze"]["status"] == "PARKED"
    assert artifact["stages"]["p3_evidence"]["status"] == "PARKED"


def test_ready_downstream_stage_cannot_bypass_a_deferred_dependency():
    deferred = build_nonready_research_stage(
        "p1_input", status="DEFERRED", reason_codes=("input_not_available",)
    )
    artifact = _build(p1_input=deferred)
    assert artifact["terminal_status"] == "PARKED"
    assert artifact["stages"]["p2_freeze"]["reason_codes"] == [
        "p1_input_not_ready"
    ]
    assert artifact["stages"]["p3_evidence"]["reason_codes"] == [
        "p2_freeze_not_ready"
    ]


def test_catalog_metadata_cannot_be_smuggled_in_as_stage_evidence():
    catalog_record = _ready_stages()["p1_input"]
    catalog_record["catalog_status"] = "live_enabled"
    artifact = _build(p1_input=catalog_record)
    assert artifact["terminal_status"] == "PARKED"
    assert artifact["stages"]["p1_input"]["artifact"] is None


def test_python_output_matches_closed_json_schema():
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    assert list(validator.iter_errors(_build("hk_equity"))) == []


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("no_order", False),
        ("permission_effect", "live"),
        ("catalog_status_used_as_evidence", True),
        ("terminal", False),
    ],
)
def test_authority_and_terminal_guards_fail_closed(field, value):
    artifact = _build()
    artifact[field] = value
    with pytest.raises(InvalidResearchDriverArtifact):
        validate_research_driver_terminal_artifact(artifact)


def test_validator_rejects_tampered_terminal_status_and_dependency_chain():
    artifact = _build()
    artifact["terminal_status"] = "DEFERRED"
    with pytest.raises(InvalidResearchDriverArtifact, match="terminal_status"):
        validate_research_driver_terminal_artifact(artifact)

    artifact = _build()
    artifact["stages"]["p1_input"] = build_nonready_research_stage(
        "p1_input", status="DEFERRED", reason_codes=("input_not_available",)
    )
    artifact["terminal_status"] = "DEFERRED"
    with pytest.raises(InvalidResearchDriverArtifact, match="bypass"):
        validate_research_driver_terminal_artifact(artifact)


def test_canonical_bytes_digest_and_copy_isolation_are_deterministic():
    artifact = _build("crypto")
    reordered = json.loads(json.dumps(artifact))
    assert canonical_research_driver_terminal_bytes(reordered) == (
        canonical_research_driver_terminal_bytes(artifact)
    )
    assert research_driver_terminal_sha256(reordered) == (
        research_driver_terminal_sha256(artifact)
    )
    validated = validate_research_driver_terminal_artifact(artifact)
    validated["stages"]["p1_input"]["artifact"]["artifact_id"] = "changed"
    assert artifact["stages"]["p1_input"]["artifact"]["artifact_id"] == (
        "manifest-001"
    )


def test_unknown_domain_and_invalid_generated_at_are_rejected():
    with pytest.raises(InvalidResearchDriverArtifact, match="unsupported"):
        _build("forex")
    stages = _ready_stages()
    with pytest.raises(InvalidResearchDriverArtifact, match="timezone"):
        build_research_driver_terminal_artifact(
            run_id="run",
            generated_at="2026-08-24T22:00:00",
            strategy_id="strategy",
            candidate_id="candidate",
            domain="crypto",
            **stages,
        )
