from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import json
from pathlib import Path

from jsonschema import Draft202012Validator

from quant_platform_kit.research_factory import (
    ResearchPublicationIntent,
    ResearchWorkerManifest,
    ResearchWorkerRole,
    build_source_receipt,
    validate_publication_intent,
    validate_source_receipt,
    validate_worker_manifest,
)


ROOT = Path(__file__).resolve().parents[1]


def _receipt(*, licence: str | None = "CC-BY-4.0", usage: str = "candidate_copy"):
    return build_source_receipt(
        source_id="source-1",
        source_url="https://example.test/research",
        publisher="Example publisher",
        retrieved_at=datetime(2026, 8, 27, tzinfo=timezone.utc),
        content=b"untrusted source material",
        declared_license=licence,
        requested_usage_scope=usage,
    )


def test_expected_worker_manifests_are_least_privilege() -> None:
    for role in ResearchWorkerRole:
        assert validate_worker_manifest(
            ResearchWorkerManifest.expected(worker_id=f"{role.value}-1", role=role)
        ) == []


def test_worker_manifest_rejects_extra_privilege() -> None:
    manifest = ResearchWorkerManifest.expected(
        worker_id="fetcher-1", role=ResearchWorkerRole.FETCHER
    )
    elevated = ResearchWorkerManifest(
        **{
            **manifest.__dict__,
            "capabilities": manifest.capabilities | {"broker_order_submit"},
            "broker_access": True,
        }
    )

    issues = validate_worker_manifest(elevated)

    assert "worker capabilities must exactly match the role allowlist" in issues
    assert "broker_access must be false for research workers" in issues


def test_unknown_licence_is_forced_to_citation_only() -> None:
    receipt = _receipt(licence=None, usage="candidate_copy")

    assert receipt.usage_scope == "citation_or_summary"
    assert receipt.untrusted is True
    assert receipt.to_dict()["receipt_sha256"] == receipt.receipt_sha256
    assert validate_source_receipt(receipt) == []


def test_copying_requires_a_separate_licence_review_receipt() -> None:
    unreviewed = _receipt()
    reviewed = build_source_receipt(
        source_id="source-2",
        source_url="https://example.test/compatible-research",
        publisher="Example publisher",
        retrieved_at=datetime(2026, 8, 27, tzinfo=timezone.utc),
        content=b"reviewed material",
        declared_license="MIT",
        requested_usage_scope="candidate_copy",
        license_review_id="licence-review-2026-08-27",
    )

    assert unreviewed.usage_scope == "citation_or_summary"
    assert reviewed.usage_scope == "candidate_copy"
    assert validate_source_receipt(reviewed) == []


def test_receipt_digest_binds_licence_review_and_source_metadata() -> None:
    first = build_source_receipt(
        source_id="source-3",
        source_url="https://example.test/research",
        publisher="Example publisher",
        retrieved_at=datetime(2026, 8, 27, tzinfo=timezone.utc),
        content=b"same material",
        declared_license="MIT",
        requested_usage_scope="candidate_copy",
        license_review_id="review-1",
    )
    changed_review = build_source_receipt(
        source_id="source-3",
        source_url="https://example.test/research",
        publisher="Example publisher",
        retrieved_at=datetime(2026, 8, 27, tzinfo=timezone.utc),
        content=b"same material",
        declared_license="MIT",
        requested_usage_scope="candidate_copy",
        license_review_id="review-2",
    )

    assert first.receipt_sha256 != changed_review.receipt_sha256


def test_source_receipt_serialization_matches_the_public_schema() -> None:
    receipt = build_source_receipt(
        source_id="source-schema",
        source_url="https://example.test/research",
        publisher="Example publisher",
        retrieved_at=datetime(2026, 8, 27, tzinfo=timezone.utc),
        content=b"source material",
        declared_license="MIT",
        requested_usage_scope="candidate_copy",
        license_review_id="license-review-1",
    )
    schema = json.loads(
        (ROOT / "src" / "quant_platform_kit" / "schemas" / "research-source-receipt.v1.schema.json").read_text()
    )

    assert list(Draft202012Validator(schema).iter_errors(receipt.to_dict())) == []


def test_source_receipt_rejects_non_https_and_trusted_content() -> None:
    receipt = _receipt()
    invalid = replace(receipt, source_url="http://example.test", untrusted=False)

    issues = validate_source_receipt(invalid)

    assert "source_url must be an absolute https URL" in issues
    assert "untrusted must be true for network source receipts" in issues


def test_publication_intent_cannot_grant_live_authority() -> None:
    intent = ResearchPublicationIntent(
        schema_version="research_factory.v1",
        candidate_id="candidate-1",
        repository="QuantStrategyLab/UsEquityStrategies",
        branch="research/candidate-1",
        pull_request_title="research: candidate-1",
        evidence_core_sha256="a" * 64,
        source_receipt_ids=("source-1",),
        research_only=False,
        no_order=False,
        live_authority_granted=True,
    )

    assert validate_publication_intent(intent) == [
        "research_only must be true",
        "no_order must be true",
        "live_authority_granted must be false",
    ]
