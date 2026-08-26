from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from quant_platform_kit.risk.contracts import CandidateRiskIdentity
from quant_platform_kit.strategy_lifecycle.candidate_control import (
    PROMOTION_DECISION_SCHEMA_VERSION,
    SOURCE_RECEIPT_SCHEMA_VERSION,
    STRATEGY_CANDIDATE_SCHEMA_VERSION,
    CandidateIdentityBinding,
    CandidateKind,
    PromotionDecision,
    PromotionOutcome,
    PromotionScope,
    ResearchCandidateStatus,
    SourceReceipt,
    StrategyCandidate,
    validate_promotion_decision,
    validate_source_receipt,
    validate_strategy_candidate,
)


ROOT = Path(__file__).resolve().parents[1]
_REVISION = "a" * 40
_DIGEST = "b" * 64
_OTHER_DIGEST = "c" * 64


def _risk_identity() -> CandidateRiskIdentity:
    return CandidateRiskIdentity(
        strategy_profile="soxl_soxx_trend_income",
        account_mode="shadow",
        strategy_revision=_REVISION,
        runner_revision=_REVISION,
        config_sha256=_DIGEST,
        input_manifest_sha256=_OTHER_DIGEST,
        authority_receipt_sha256="d" * 64,
    )


def _receipt(receipt_id: str, content_sha256: str) -> SourceReceipt:
    return SourceReceipt(
        receipt_id=receipt_id,
        source_uri=f"https://example.test/{receipt_id}",
        retrieved_at="2026-08-27T10:00:00Z",
        content_sha256=content_sha256,
        license="CC-BY-4.0",
    )


def _candidate() -> StrategyCandidate:
    receipts = tuple(sorted(
        (_receipt("paper", "e" * 64), _receipt("market-note", "f" * 64)),
        key=lambda receipt: receipt.receipt_sha256,
    ))
    return StrategyCandidate(
        candidate_id="candidate.soxl.parameter-risk-budget.2026-08-27",
        candidate_kind=CandidateKind.PARAMETER_CHANGE,
        research_status=ResearchCandidateStatus.SHADOW_READY,
        strategy_profile="soxl_soxx_trend_income",
        domain="us_equity",
        created_at="2026-08-27T10:30:00Z",
        identity_binding=CandidateIdentityBinding(
            candidate_risk_identity_sha256=_risk_identity().candidate_sha256,
            research_spec_sha256="1" * 64,
            optimization_spec_sha256="2" * 64,
            source_receipt_sha256s=tuple(receipt.receipt_sha256 for receipt in receipts),
        ),
        source_receipts=receipts,
    )


def test_candidate_binds_existing_risk_identity_and_untrusted_source_receipts() -> None:
    candidate = _candidate()
    payload = candidate.to_dict()

    assert payload["schema_version"] == STRATEGY_CANDIDATE_SCHEMA_VERSION
    assert payload["identity_binding"]["candidate_risk_identity_sha256"] == _risk_identity().candidate_sha256
    assert payload["grants_execution_authority"] is False
    assert candidate.grants_execution_authority is False
    assert [receipt["content_trust"] for receipt in payload["source_receipts"]] == ["untrusted", "untrusted"]
    assert validate_strategy_candidate(payload) == []


def test_parameter_change_requires_optimization_spec_but_other_candidate_kinds_do_not() -> None:
    binding = CandidateIdentityBinding(
        candidate_risk_identity_sha256=_risk_identity().candidate_sha256,
        research_spec_sha256="1" * 64,
    )
    with pytest.raises(ValueError, match="require optimization_spec_sha256"):
        StrategyCandidate(
            candidate_id="candidate.invalid.parameter",
            candidate_kind=CandidateKind.PARAMETER_CHANGE,
            research_status=ResearchCandidateStatus.DRAFT,
            strategy_profile="soxl_soxx_trend_income",
            domain="us_equity",
            created_at="2026-08-27T10:30:00Z",
            identity_binding=binding,
        )

    plugin_candidate = StrategyCandidate(
        candidate_id="candidate.plugin-revision",
        candidate_kind=CandidateKind.PLUGIN_REVISION,
        research_status=ResearchCandidateStatus.RESEARCHING,
        strategy_profile="risk-plugin",
        domain="us_equity",
        created_at="2026-08-27T10:30:00Z",
        identity_binding=binding,
    )
    assert validate_strategy_candidate(plugin_candidate.to_dict()) == []


def test_candidate_validator_rejects_tampering_and_unbound_source_receipts() -> None:
    payload = _candidate().to_dict()
    payload["source_receipts"][0]["content_trust"] = "trusted"

    issues = validate_strategy_candidate(payload)

    assert "source_receipts[0].content_trust must be 'untrusted'" in issues
    assert "candidate_sha256 does not match canonical artifact content" in issues


def test_source_receipt_validator_requires_license_hash_and_no_authority() -> None:
    payload = _receipt("paper", "e" * 64).to_dict()
    payload["license"] = ""
    payload["grants_execution_authority"] = True

    issues = validate_source_receipt(payload)

    assert "license must be a non-empty canonical string" in issues
    assert "grants_execution_authority must be False" in issues
    assert "receipt_sha256 does not match canonical artifact content" in issues


def test_human_promotion_decision_is_expiring_and_never_grants_live() -> None:
    candidate = _candidate()
    decision = PromotionDecision(
        decision_id="decision.soxl.shadow.2026-08-27",
        candidate_sha256=candidate.candidate_sha256,
        outcome=PromotionOutcome.APPROVED,
        scope=PromotionScope.SHADOW,
        reviewed_by="ops-reviewer-17",
        reviewed_at="2026-08-27T11:00:00Z",
        expires_at="2026-09-03T11:00:00Z",
    )
    payload = decision.to_dict()

    assert payload["schema_version"] == PROMOTION_DECISION_SCHEMA_VERSION
    assert payload["approval_actor_type"] == "human"
    assert decision.grants_live is False
    assert decision.grants_execution_authority is False
    assert decision.is_current(at=datetime(2026, 8, 28, tzinfo=timezone.utc)) is True
    assert decision.is_current(at=datetime(2026, 9, 3, 11, tzinfo=timezone.utc)) is False
    assert validate_promotion_decision(payload) == []


def test_promotion_decision_rejects_live_scope_and_expired_window() -> None:
    with pytest.raises(ValueError):
        PromotionScope("live")

    payload = PromotionDecision(
        decision_id="decision.expired",
        candidate_sha256=_candidate().candidate_sha256,
        outcome=PromotionOutcome.APPROVED,
        scope=PromotionScope.PAPER,
        reviewed_by="ops-reviewer-17",
        reviewed_at="2026-08-27T11:00:00Z",
        expires_at="2026-09-03T11:00:00Z",
    ).to_dict()
    payload["scope"] = "live"
    payload["expires_at"] = "2026-08-27T10:00:00Z"

    issues = validate_promotion_decision(payload)

    assert "scope must be research, shadow, or paper; live is never allowed" in issues
    assert "expires_at must be after reviewed_at" in issues
    assert "decision_sha256 does not match canonical artifact content" in issues


def test_serialized_contract_schemas_match_public_versions() -> None:
    expected = {
        "source-receipt.v1.schema.json": SOURCE_RECEIPT_SCHEMA_VERSION,
        "strategy-candidate.v1.schema.json": STRATEGY_CANDIDATE_SCHEMA_VERSION,
        "promotion-decision.v1.schema.json": PROMOTION_DECISION_SCHEMA_VERSION,
    }
    for filename, version in expected.items():
        payload = json.loads((ROOT / "src" / "quant_platform_kit" / "schemas" / filename).read_text())
        assert payload["properties"]["schema_version"]["const"] == version


def test_serialized_contracts_validate_against_their_json_schemas() -> None:
    candidate = _candidate()
    decision = PromotionDecision(
        decision_id="decision.soxl.shadow.2026-08-27",
        candidate_sha256=candidate.candidate_sha256,
        outcome=PromotionOutcome.APPROVED,
        scope=PromotionScope.SHADOW,
        reviewed_by="ops-reviewer-17",
        reviewed_at="2026-08-27T11:00:00Z",
        expires_at="2026-09-03T11:00:00Z",
    )
    artifacts = {
        "source-receipt.v1.schema.json": candidate.source_receipts[0].to_dict(),
        "strategy-candidate.v1.schema.json": candidate.to_dict(),
        "promotion-decision.v1.schema.json": decision.to_dict(),
    }
    for filename, artifact in artifacts.items():
        schema = json.loads((ROOT / "src" / "quant_platform_kit" / "schemas" / filename).read_text())
        assert list(Draft202012Validator(schema).iter_errors(artifact)) == []
