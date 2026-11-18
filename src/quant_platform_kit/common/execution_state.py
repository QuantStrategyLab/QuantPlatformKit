"""Execution marker storage for duplicate-run suppression across trading platforms."""

from __future__ import annotations

import os
import tempfile
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from ._execution_state_helpers import (
    DEFAULT_EXECUTION_LEDGER_DIGEST_RECORD_LIMIT,
    DEFAULT_EXECUTION_OUTCOME_NAMESPACE,
    DEFAULT_EXECUTION_STATE_DIR,
    DEFAULT_EXECUTION_STATE_NAMESPACE,
    EXECUTION_LEDGER_DIGEST_SCHEMA_VERSION,
    _clean_key_part,
    _clean_relative_key,
    _date_key,
    _date_keys,
    _env_bool,
    _first_non_empty,
    _is_paper_account_scope,
    _is_successful_no_action_report,
    _month_segment,
    _optional_str,
    _parse_cloud_uri,
    _parse_gcs_uri,
    _read_cloud_env,
    _report_effective_date_keys,
    _report_matches_execution,
    _report_signal_date_keys,
    _report_signal_snapshot,
    _runtime_report_segment,
    build_account_owner_marker_key,
    build_execution_marker_key,
)
from ._execution_state_session import AccountSubmissionSession
from ._execution_state_store import AccountOwnerClaimResult, ExecutionMarkerStore
from ._execution_state_submission_models import (
    _ACCOUNT_SUBMISSION_LOCKS,
    _ACCOUNT_SUBMISSION_LOCKS_MUTEX,
    _ACCOUNT_SUBMISSION_NAMESPACE,
    _SUBMISSION_ACK,
    _SUBMISSION_PARTIAL,
    _SUBMISSION_TERMINAL,
    ACCOUNT_SUBMISSION_CONTRACT,
    AccountDomainObservation,
    AccountSubmissionError,
    AccountSubmissionGrant,
    RiskReservationSpec,
    _default_utc_clock,
    _resolve_observation,
    _resolve_risk_reservation_spec,
    _submission_account,
    _submission_digest,
    _submission_number,
    _submission_text,
    submission_binding_digest,
    submission_intent_digest,
    submission_release_digest,
)


def _get_object_store(*, project_id: str | None = None):
    try:
        from quant_platform_kit.cloud import get_object_store
    except ImportError as exc:
        raise RuntimeError(
            "quant_platform_kit.cloud is required for GCS execution markers"
        ) from exc
    return get_object_store(project_id=project_id)


def claim_account_owner(
    store: ExecutionMarkerStore,
    *,
    broker: str,
    account_id: str,
    owner_id: str,
    metadata: Mapping[str, Any] | None = None,
) -> AccountOwnerClaimResult:
    """Claim exclusive ownership of one physical broker account.

    Semantics:
    - create-only success => this caller becomes owner (allowed/created)
    - existing claim with the same owner_id => allow without rewrite
    - existing claim with a different owner_id => contested/denied
    - claim lost the race but payload is unreadable => fail closed
    """
    owner = _first_non_empty(owner_id)
    if not owner:
        raise ValueError("account owner claim requires owner_id")
    marker_key = build_account_owner_marker_key(broker=broker, account_id=account_id)
    claim_metadata = dict(metadata or {})
    claim_metadata["owner_id"] = owner
    if store.claim_marker(marker_key, metadata=claim_metadata):
        return AccountOwnerClaimResult(
            allowed=True,
            contested=False,
            created=True,
            owner_id=owner,
            marker_key=marker_key,
        )
    existing = store.read_marker(marker_key)
    if existing is None:
        raise RuntimeError(
            f"account owner claim lost the create race but marker is unreadable: {marker_key}"
        )
    existing_metadata = existing.get("metadata") if isinstance(existing.get("metadata"), Mapping) else {}
    existing_owner = _first_non_empty(existing_metadata.get("owner_id"))
    if existing_owner == owner:
        return AccountOwnerClaimResult(
            allowed=True,
            contested=False,
            created=False,
            owner_id=owner,
            marker_key=marker_key,
        )
    return AccountOwnerClaimResult(
        allowed=False,
        contested=True,
        created=False,
        owner_id=existing_owner or "unknown",
        marker_key=marker_key,
    )


def build_execution_marker_store_from_env(
    *,
    platform_env_prefix: str,
    env_reader: Callable[[str, str | None], str | None],
    project_id: str | None = None,
    client_factory: Any = None,
    default_local_dir: str | Path | None = None,
    execution_mode: str | None = None,
) -> ExecutionMarkerStore:
    prefix = str(platform_env_prefix or "").strip().upper()
    mode = _first_non_empty(
        execution_mode, env_reader(f"{prefix}_EXECUTION_MODE", None),
    ).lower() or None
    explicit_cloud_uri = _read_cloud_env(
        env_reader, new_key=f"{prefix}_EXECUTION_STATE_CLOUD_URI",
        old_key=f"{prefix}_EXECUTION_STATE_GCS_URI",
    )
    report_cloud_uri = (
        env_reader("QSL_EXECUTION_REPORT_CLOUD_URI", None)
        or env_reader("QSL_EXECUTION_REPORT_GCS_URI", None)
        or _read_cloud_env(
            env_reader, new_key="EXECUTION_REPORT_CLOUD_URI",
            old_key="EXECUTION_REPORT_GCS_URI",
        )
    )
    local_dir: str | Path | None = env_reader(f"{prefix}_EXECUTION_STATE_DIR", None)
    if not str(local_dir or "").strip():
        local_dir = default_local_dir
    if not str(local_dir or "").strip():
        local_dir = None
    cloud_uri = explicit_cloud_uri or report_cloud_uri
    if mode in {"live", "real", "production"} and not _first_non_empty(
        explicit_cloud_uri, report_cloud_uri,
    ):
        ephemeral_roots = (Path("/tmp").resolve(), Path(tempfile.gettempdir()).resolve())
        # The store expands "~" when it reads and writes; validate the same path.
        resolved_dir = Path(local_dir).expanduser().resolve() if local_dir is not None else None
        if resolved_dir is None or any(
            resolved_dir.is_relative_to(root) for root in ephemeral_roots
        ):
            raise ValueError("EXECUTION_STATE_DURABLE_PATH_REQUIRED")
    return ExecutionMarkerStore(
        local_dir=local_dir or DEFAULT_EXECUTION_STATE_DIR,
        cloud_prefix_uri=cloud_uri,
        project_id=project_id,
        client_factory=client_factory,
    )


def resolve_execution_dedup_enabled(
    *,
    platform_env_prefix: str,
    env_reader: Callable[[str, str | None], str | None],
    dry_run_only: bool,
    account_scope: object = None,
) -> bool:
    prefix = str(platform_env_prefix or "").strip().upper()
    raw_value = env_reader(f"{prefix}_EXECUTION_DEDUP_ENABLED", None)
    if raw_value is not None and str(raw_value).strip():
        return _env_bool(raw_value, default=bool(dry_run_only))
    return bool(dry_run_only) or _is_paper_account_scope(account_scope)

