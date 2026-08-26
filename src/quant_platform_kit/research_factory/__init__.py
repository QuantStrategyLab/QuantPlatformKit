"""Pure contracts for isolated, research-only automation workers.

This package intentionally contains no HTTP client, GitHub client, cloud client,
credential loader, platform runtime setting, or broker adapter.  Deployment
must enforce its capability manifests with separate identities; these contracts
make the intended boundary testable before any such deployment exists.
"""

from quant_platform_kit.research_factory.contracts import (
    RESEARCH_SOURCE_RECEIPT_SCHEMA_VERSION,
    ResearchPublicationIntent,
    ResearchSourceReceipt,
    ResearchWorkerManifest,
    ResearchWorkerRole,
    build_source_receipt,
)
from quant_platform_kit.research_factory.validation import (
    RESEARCH_FACTORY_SCHEMA_VERSION,
    validate_publication_intent,
    validate_source_receipt,
    validate_worker_manifest,
)

__all__ = [
    "RESEARCH_FACTORY_SCHEMA_VERSION",
    "RESEARCH_SOURCE_RECEIPT_SCHEMA_VERSION",
    "ResearchPublicationIntent",
    "ResearchSourceReceipt",
    "ResearchWorkerManifest",
    "ResearchWorkerRole",
    "build_source_receipt",
    "validate_publication_intent",
    "validate_source_receipt",
    "validate_worker_manifest",
]
