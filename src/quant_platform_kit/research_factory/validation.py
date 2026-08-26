"""Dependency-free validation for research-factory boundary contracts."""

from __future__ import annotations

from datetime import datetime
import re
from typing import Any
from urllib.parse import urlparse

from quant_platform_kit.research_factory.contracts import (
    _EXPECTED_CAPABILITIES,
    RESEARCH_SOURCE_RECEIPT_SCHEMA_VERSION,
    ResearchPublicationIntent,
    ResearchSourceReceipt,
    ResearchWorkerManifest,
    ResearchWorkerRole,
)


RESEARCH_FACTORY_SCHEMA_VERSION = "research_factory.v1"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SOURCE_USAGE_SCOPES = {"citation_or_summary", "candidate_copy"}


def validate_worker_manifest(manifest: Any) -> list[str]:
    """Validate a complete least-privilege worker manifest."""

    if type(manifest) is not ResearchWorkerManifest:
        return ["worker manifest must be ResearchWorkerManifest"]

    issues = _common_contract_issues(manifest.schema_version, manifest.worker_id, "worker")
    if type(manifest.role) is not ResearchWorkerRole:
        issues.append("worker role must be ResearchWorkerRole")
        return issues
    if manifest.capabilities != _EXPECTED_CAPABILITIES[manifest.role]:
        issues.append("worker capabilities must exactly match the role allowlist")
    for field in (
        "secret_access",
        "broker_access",
        "cloud_runtime_access",
        "deployment_write_access",
    ):
        if getattr(manifest, field) is not False:
            issues.append(f"{field} must be false for research workers")
    return issues


def validate_source_receipt(receipt: Any) -> list[str]:
    """Validate a quarantined, untrusted public-source receipt."""

    if type(receipt) is not ResearchSourceReceipt:
        return ["source receipt must be ResearchSourceReceipt"]

    issues = _common_contract_issues(
        receipt.schema_version,
        receipt.source_id,
        "source",
        expected_schema_version=RESEARCH_SOURCE_RECEIPT_SCHEMA_VERSION,
    )
    parsed = urlparse(receipt.source_url)
    if parsed.scheme != "https" or not parsed.netloc:
        issues.append("source_url must be an absolute https URL")
    if not isinstance(receipt.publisher, str) or not receipt.publisher.strip():
        issues.append("publisher must be a non-empty string")
    if not isinstance(receipt.retrieved_at, datetime) or receipt.retrieved_at.tzinfo is None:
        issues.append("retrieved_at must be timezone-aware datetime")
    if not isinstance(receipt.content_sha256, str) or not _SHA256.fullmatch(receipt.content_sha256):
        issues.append("content_sha256 must be a lowercase SHA-256 digest")
    if receipt.declared_license is not None and (
        not isinstance(receipt.declared_license, str) or not receipt.declared_license.strip()
    ):
        issues.append("declared_license must be a non-empty string or None")
    if receipt.license_review_id is not None and (
        not isinstance(receipt.license_review_id, str) or not receipt.license_review_id.strip()
    ):
        issues.append("license_review_id must be a non-empty string or None")
    if receipt.usage_scope not in _SOURCE_USAGE_SCOPES:
        issues.append("usage_scope must be citation_or_summary or candidate_copy")
    if (
        receipt.declared_license is None or receipt.license_review_id is None
    ) and receipt.usage_scope != "citation_or_summary":
        issues.append(
            "unknown/unreviewed licence must restrict usage_scope to citation_or_summary"
        )
    if receipt.untrusted is not True:
        issues.append("untrusted must be true for network source receipts")
    if (
        isinstance(receipt.retrieved_at, datetime)
        and receipt.retrieved_at.tzinfo is not None
        and receipt.receipt_sha256 != _canonical_source_receipt_digest(receipt)
    ):
        issues.append("receipt_sha256 must match canonical source receipt content")
    return issues


def validate_publication_intent(intent: Any) -> list[str]:
    """Validate a publication request that cannot carry live authority."""

    if type(intent) is not ResearchPublicationIntent:
        return ["publication intent must be ResearchPublicationIntent"]

    issues = _common_contract_issues(intent.schema_version, intent.candidate_id, "candidate")
    for field in ("repository", "branch", "pull_request_title"):
        value = getattr(intent, field)
        if not isinstance(value, str) or not value.strip():
            issues.append(f"{field} must be a non-empty string")
    if not isinstance(intent.evidence_core_sha256, str) or not _SHA256.fullmatch(intent.evidence_core_sha256):
        issues.append("evidence_core_sha256 must be a lowercase SHA-256 digest")
    if not intent.source_receipt_ids or any(
        not isinstance(value, str) or not value.strip() for value in intent.source_receipt_ids
    ):
        issues.append("source_receipt_ids must contain non-empty IDs")
    if intent.research_only is not True:
        issues.append("research_only must be true")
    if intent.no_order is not True:
        issues.append("no_order must be true")
    if intent.live_authority_granted is not False:
        issues.append("live_authority_granted must be false")
    return issues


def _common_contract_issues(
    schema_version: Any,
    identifier: Any,
    label: str,
    *,
    expected_schema_version: str = RESEARCH_FACTORY_SCHEMA_VERSION,
) -> list[str]:
    issues: list[str] = []
    if schema_version != expected_schema_version:
        issues.append(f"schema_version must be {expected_schema_version!r}")
    if not isinstance(identifier, str) or not identifier.strip():
        issues.append(f"{label} ID must be a non-empty string")
    return issues


def _canonical_source_receipt_digest(receipt: ResearchSourceReceipt) -> str:
    """Recalculate a receipt digest without retaining network content."""

    from hashlib import sha256

    return sha256(receipt.canonical_json).hexdigest()
