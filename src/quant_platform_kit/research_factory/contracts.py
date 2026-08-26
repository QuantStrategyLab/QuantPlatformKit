"""Data-only contracts for a least-privilege research factory.

External material is represented only by a receipt and digest.  It remains
untrusted and cannot acquire repository, deployment, cloud, broker, or secret
authority through this module.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
import json


RESEARCH_SOURCE_RECEIPT_SCHEMA_VERSION = "research_source_receipt.v1"


class ResearchWorkerRole(str, Enum):
    """The only roles allowed in the research-factory boundary."""

    FETCHER = "fetcher"
    PLANNER_BUILDER = "planner_builder"
    PUBLISHER = "publisher"


_EXPECTED_CAPABILITIES: dict[ResearchWorkerRole, frozenset[str]] = {
    ResearchWorkerRole.FETCHER: frozenset({"public_network_read", "quarantine_write"}),
    ResearchWorkerRole.PLANNER_BUILDER: frozenset({"quarantine_read", "sandbox_write"}),
    ResearchWorkerRole.PUBLISHER: frozenset({"research_pull_request_write"}),
}


@dataclass(frozen=True)
class ResearchWorkerManifest:
    """One worker's complete capability set.

    A deployment should grant exactly the listed set with a dedicated identity.
    ``validate_worker_manifest`` rejects a superset because an extra capability
    is a privilege-escalation risk, not a harmless implementation detail.
    """

    schema_version: str
    worker_id: str
    role: ResearchWorkerRole
    capabilities: frozenset[str]
    secret_access: bool = False
    broker_access: bool = False
    cloud_runtime_access: bool = False
    deployment_write_access: bool = False

    @classmethod
    def expected(cls, *, worker_id: str, role: ResearchWorkerRole) -> "ResearchWorkerManifest":
        """Build the least-privilege manifest for ``role``."""

        return cls(
            schema_version="research_factory.v1",
            worker_id=worker_id,
            role=role,
            capabilities=_EXPECTED_CAPABILITIES[role],
        )


@dataclass(frozen=True)
class ResearchSourceReceipt:
    """Digest-only receipt for quarantined public material.

    ``usage_scope`` is deliberately conservative.  A source without a known
    compatible licence may inform a factual citation or summary, but its code
    and data must not be copied into a generated candidate.
    """

    schema_version: str
    source_id: str
    source_url: str
    publisher: str
    retrieved_at: datetime
    content_sha256: str
    declared_license: str | None
    usage_scope: str
    license_review_id: str | None = None
    untrusted: bool = True
    receipt_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        """Bind all source, licence, and usage fields to one canonical digest."""

        object.__setattr__(self, "receipt_sha256", sha256(self.canonical_json).hexdigest())

    @property
    def canonical_payload(self) -> dict[str, object]:
        """Return the raw-content-free, identity-bearing receipt payload."""

        retrieved_at = self.retrieved_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        return {
            "schema_version": RESEARCH_SOURCE_RECEIPT_SCHEMA_VERSION,
            "source_id": self.source_id,
            "source_url": self.source_url,
            "publisher": self.publisher,
            "retrieved_at": retrieved_at,
            "content_sha256": self.content_sha256,
            "declared_license": self.declared_license,
            "usage_scope": self.usage_scope,
            "license_review_id": self.license_review_id,
            "untrusted": self.untrusted,
            "grants_execution_authority": False,
        }

    @property
    def canonical_json(self) -> bytes:
        """Canonical bytes whose digest binds this receipt into a candidate."""

        return json.dumps(
            self.canonical_payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")

    def to_dict(self) -> dict[str, object]:
        """Return a digest-bearing receipt without exposing fetched bytes."""

        return {**self.canonical_payload, "receipt_sha256": self.receipt_sha256}


@dataclass(frozen=True)
class ResearchPublicationIntent:
    """A research-only repository publication request.

    The intent can create a reviewable pull request but has no field that can
    select a runtime target, merge a branch, deploy a service, or place an
    order.  A publisher implementation must treat this as a request, not proof
    of approval.
    """

    schema_version: str
    candidate_id: str
    repository: str
    branch: str
    pull_request_title: str
    evidence_core_sha256: str
    source_receipt_ids: tuple[str, ...]
    research_only: bool = True
    no_order: bool = True
    live_authority_granted: bool = False


def build_source_receipt(
    *,
    source_id: str,
    source_url: str,
    publisher: str,
    retrieved_at: datetime,
    content: bytes,
    declared_license: str | None,
    requested_usage_scope: str,
    license_review_id: str | None = None,
) -> ResearchSourceReceipt:
    """Create an immutable receipt without retaining the untrusted content.

    Licence absence, ambiguity, or lack of a review receipt is fail-closed to
    ``citation_or_summary``.  A declared SPDX expression alone does not prove
    that a particular code/data use is permitted.
    The caller must separately place raw material in a quarantined store that
    is not mounted into a planner, publisher, platform, or broker runtime.
    """

    normalized_license = (declared_license or "").strip() or None
    normalized_review_id = (license_review_id or "").strip() or None
    usage_scope = requested_usage_scope
    if normalized_license is None or normalized_review_id is None:
        usage_scope = "citation_or_summary"
    return ResearchSourceReceipt(
        schema_version=RESEARCH_SOURCE_RECEIPT_SCHEMA_VERSION,
        source_id=source_id,
        source_url=source_url,
        publisher=publisher,
        retrieved_at=retrieved_at,
        content_sha256=sha256(content).hexdigest(),
        declared_license=normalized_license,
        usage_scope=usage_scope,
        license_review_id=normalized_review_id,
        untrusted=True,
    )
