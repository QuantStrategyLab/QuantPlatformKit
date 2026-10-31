"""Execution marker storage for duplicate-run suppression across trading platforms."""

from __future__ import annotations

import json
import math
import threading
import uuid
import hashlib
import os
import re
import tempfile
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path
from typing import Any


DEFAULT_EXECUTION_STATE_DIR = "/tmp/quant_execution_state"
DEFAULT_EXECUTION_STATE_NAMESPACE = "execution_markers"
DEFAULT_EXECUTION_OUTCOME_NAMESPACE = "execution_outcomes"
EXECUTION_LEDGER_DIGEST_SCHEMA_VERSION = "execution_ledger_digest.v1"
DEFAULT_EXECUTION_LEDGER_DIGEST_RECORD_LIMIT = 256


def _first_non_empty(*values: object) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _env_bool(value: object, *, default: bool) -> bool:
    text = str(value or "").strip().lower()
    if not text:
        return default
    if text in {"1", "true", "t", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "f", "no", "n", "off"}:
        return False
    return default


def _parse_cloud_uri(uri: str) -> tuple[str, str]:
    text = str(uri or "").strip()
    if not text.startswith("gs://") and not text.startswith("s3://"):
        raise ValueError(f"cloud uri must start with gs:// or s3://, got: {uri!r}")
    remainder = text[5:]
    bucket, _, prefix = remainder.partition("/")
    if not bucket:
        raise ValueError(f"cloud uri must include a bucket, got: {uri!r}")
    return bucket, prefix.strip("/")


# Backward-compatible alias
_parse_gcs_uri = _parse_cloud_uri


def _read_cloud_env(
    env_reader: Callable[[str, str | None], str | None],
    *,
    new_key: str,
    old_key: str,
) -> str | None:
    """Read new env var name first, fall back to old name with deprecation warning."""
    val = env_reader(new_key, None)
    if val is not None:
        return val
    val = env_reader(old_key, None)
    if val is not None:
        import warnings
        warnings.warn(
            f"Env var '{old_key}' is deprecated, use '{new_key}'",
            DeprecationWarning,
            stacklevel=3,
        )
    return val


def _clean_key_part(value: object, *, fallback: str) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[^a-z0-9._=-]+", "-", text)
    text = re.sub(r"-{2,}", "-", text).strip("-.")
    return text or fallback


def _clean_relative_key(key: str) -> str:
    parts = [
        _clean_key_part(part, fallback="unknown")
        for part in str(key or "").replace("\\", "/").split("/")
        if str(part or "").strip()
    ]
    return "/".join(parts) or "unknown"


def build_execution_marker_key(
    *,
    platform: str,
    strategy_profile: str,
    account_scope: str,
    execution_mode: str,
    signal_date: object,
    effective_date: object,
    execution_timing_contract: object = None,
) -> str:
    """Build a stable marker key for one strategy signal execution."""
    signal = _first_non_empty(signal_date)
    effective = _first_non_empty(effective_date)
    if not signal and not effective:
        return ""
    return "/".join(
        (
            "v1",
            _clean_key_part(platform, fallback="platform"),
            _clean_key_part(account_scope, fallback="account"),
            _clean_key_part(strategy_profile, fallback="strategy"),
            _clean_key_part(execution_mode, fallback="mode"),
            _clean_key_part(signal or "no-signal-date", fallback="signal"),
            _clean_key_part(effective or "no-effective-date", fallback="effective"),
            _clean_key_part(execution_timing_contract or "no-contract", fallback="contract"),
        )
    )


def build_account_owner_marker_key(*, broker: str, account_id: str) -> str:
    """Build a durable account-owner fence key (strategy profile intentionally omitted)."""
    broker_part = _first_non_empty(broker)
    account_part = _first_non_empty(account_id)
    if not broker_part or not account_part:
        raise ValueError("account owner marker requires broker and account_id")
    return "/".join(
        (
            "v1",
            "account-owner",
            _clean_key_part(broker_part, fallback="broker"),
            _clean_key_part(account_part, fallback="account"),
        )
    )


@dataclass(frozen=True)
class AccountOwnerClaimResult:
    """Result of attempting to claim exclusive ownership of one physical account."""

    allowed: bool
    contested: bool
    created: bool
    owner_id: str
    marker_key: str


@dataclass(frozen=True)
class ExecutionMarkerStore:
    local_dir: str | Path | None = DEFAULT_EXECUTION_STATE_DIR
    cloud_prefix_uri: str | None = None
    project_id: str | None = None
    namespace: str = DEFAULT_EXECUTION_STATE_NAMESPACE
    outcome_namespace: str = DEFAULT_EXECUTION_OUTCOME_NAMESPACE
    client_factory: Any = None
    prior_report_scan_limit: int = 100

    def has_marker(self, marker_key: str) -> bool:
        if not str(marker_key or "").strip():
            return False
        if self.cloud_prefix_uri and self._object_store().exists(self._cloud_uri(marker_key)):
            return True
        if self.local_dir and self._local_path(marker_key).exists():
            return True
        return False

    def record_marker(
        self,
        marker_key: str,
        *,
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        if not str(marker_key or "").strip():
            return
        payload = {
            "schema_version": "execution_marker.v1",
            "marker_key": str(marker_key),
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "metadata": dict(metadata or {}),
        }
        encoded = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
        if self.cloud_prefix_uri:
            self._object_store().write_text(
                self._cloud_uri(marker_key),
                encoded,
                content_type="application/json",
            )
            return
        if self.local_dir:
            path = self._local_path(marker_key)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(encoded, encoding="utf-8")

    def record_outcome(
        self,
        marker_key: str,
        *,
        metadata: Mapping[str, Any] | None = None,
    ) -> bool:
        """Append one terminal execution outcome without replacing its claim.

        The durable claim at ``execution_markers`` is the deduplication
        authority and must remain immutable.  A post-execution outcome is
        therefore written under a separate stable namespace with create-only
        semantics.  It requires only object create/read permissions on cloud
        storage and is idempotent: an already-recorded outcome returns
        ``False`` without any overwrite attempt.
        """

        if not str(marker_key or "").strip():
            return False
        payload = json.dumps(
            {
                "schema_version": "execution_outcome.v1",
                "marker_key": str(marker_key),
                "recorded_at": datetime.now(timezone.utc).isoformat(),
                "metadata": dict(metadata or {}),
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        if self.cloud_prefix_uri:
            create = getattr(self._object_store(), "create_text", None)
            if not callable(create):
                raise RuntimeError("cloud execution store lacks atomic create-only support")
            return bool(create(self._outcome_cloud_uri(marker_key), payload, "application/json"))
        if self.local_dir:
            path = self._outcome_local_path(marker_key)
            path.parent.mkdir(parents=True, exist_ok=True)
            try:
                descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            except FileExistsError:
                return False
            try:
                with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                    handle.write(payload)
                    handle.flush()
                    os.fsync(handle.fileno())
            except Exception:
                path.unlink(missing_ok=True)
                raise
            return True
        raise RuntimeError("execution state store has no durable outcome backend")

    def claim_marker(self, marker_key: str, *, metadata: Mapping[str, Any] | None = None) -> bool:
        """Atomically reserve an execution identity before broker submission."""
        if not str(marker_key or "").strip():
            raise ValueError("execution claim requires a marker key")
        payload = json.dumps({
            "schema_version": "execution_claim.v1",
            "marker_key": str(marker_key),
            "claimed_at": datetime.now(timezone.utc).isoformat(),
            "state": "claimed",
            "metadata": dict(metadata or {}),
        }, ensure_ascii=False, indent=2, sort_keys=True)
        if self.cloud_prefix_uri:
            create = getattr(self._object_store(), "create_text", None)
            if not callable(create):
                raise RuntimeError("cloud execution store lacks atomic create-only support")
            return bool(create(self._cloud_uri(marker_key), payload, "application/json"))
        if self.local_dir:
            path = self._local_path(marker_key)
            path.parent.mkdir(parents=True, exist_ok=True)
            try:
                fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            except FileExistsError:
                return False
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            return True
        raise RuntimeError("execution state store has no durable claim backend")

    def read_marker(self, marker_key: str) -> dict[str, Any] | None:
        """Read one durable claim/marker payload, or ``None`` when absent."""
        if not str(marker_key or "").strip():
            return None
        raw = ""
        if self.cloud_prefix_uri:
            store = self._object_store()
            uri = self._cloud_uri(marker_key)
            exists = getattr(store, "exists", None)
            if callable(exists) and not bool(exists(uri)):
                return None
            read_text = getattr(store, "read_text", None)
            if not callable(read_text):
                raise RuntimeError("cloud execution store lacks read_text support")
            try:
                raw = str(read_text(uri) or "")
            except FileNotFoundError:
                return None
            except Exception as exc:
                # Some providers raise provider-specific not-found errors.
                if "NotFound" in type(exc).__name__ or "404" in str(exc):
                    return None
                raise
        elif self.local_dir:
            path = self._local_path(marker_key)
            if not path.exists():
                return None
            raw = path.read_text(encoding="utf-8")
        else:
            raise RuntimeError("execution state store has no durable claim backend")
        if not raw.strip():
            return None
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise RuntimeError(f"execution marker payload is not an object: {marker_key}")
        return payload

    def has_prior_execution_report(
        self,
        *,
        platform: str,
        strategy_profile: str,
        account_scope: str,
        signal_date: object,
        effective_date: object,
        dry_run_only: bool,
    ) -> bool:
        if not self.cloud_prefix_uri:
            return False
        signal = _first_non_empty(signal_date)
        effective = _first_non_empty(effective_date)
        if not signal and not effective:
            return False
        month_segment = _month_segment(signal, effective)
        bucket_name, prefix = _parse_cloud_uri(str(self.cloud_prefix_uri or ""))
        object_prefix = "/".join(
            part.strip("/")
            for part in (
                prefix,
                _runtime_report_segment(platform),
                _runtime_report_segment(strategy_profile),
                _runtime_report_segment(account_scope),
                month_segment,
            )
            if part and part.strip("/")
        )
        store = self._object_store()
        prefix_uri = f"gs://{bucket_name}/{object_prefix}"
        scanned = 0
        for uri in store.list(prefix_uri):
            if not uri.endswith(".json"):
                continue
            scanned += 1
            if scanned > max(1, int(self.prior_report_scan_limit or 1)):
                break
            try:
                payload = json.loads(store.read_text(uri))
            except Exception:
                continue
            if _report_matches_execution(
                payload,
                platform=platform,
                strategy_profile=strategy_profile,
                account_scope=account_scope,
                signal_date=signal,
                effective_date=effective,
                dry_run_only=dry_run_only,
            ):
                return True
        return False

    def calculate_recent_ledger_digest(
        self,
        *,
        platform: str,
        strategy_profile: str,
        account_scope: str,
        execution_mode: str,
        record_limit: int = DEFAULT_EXECUTION_LEDGER_DIGEST_RECORD_LIMIT,
    ) -> tuple[str, int]:
        """Hash recent durable claims/outcomes without exposing their contents.

        A continuity reconciler needs a repeatable representation of the local
        idempotency ledger, but may not put marker names, accounts, order
        metadata, or execution reports in a public receipt.  This method reads
        the durable ledger scoped to one platform/profile/account/mode and
        returns only ``(sha256, record_count)``.  It uses the newest bounded
        records because the recovery contract reconciles the current operating
        window, not an unbounded historical archive.

        Read failures are intentionally propagated.  A caller must treat them
        as an unmatched local ledger and keep a live baseline frozen.
        """

        digest, count, _truncated = self.calculate_recent_ledger_digest_with_coverage(
            platform=platform, strategy_profile=strategy_profile, account_scope=account_scope,
            execution_mode=execution_mode, record_limit=record_limit,
        )
        return digest, count

    def calculate_recent_ledger_digest_with_coverage(
        self, *, platform: str, strategy_profile: str, account_scope: str, execution_mode: str,
        record_limit: int = DEFAULT_EXECUTION_LEDGER_DIGEST_RECORD_LIMIT,
    ) -> tuple[str, int, bool]:
        """Return the existing digest plus whether either bounded namespace was truncated."""
        try:
            normalized_limit = int(record_limit)
        except (TypeError, ValueError) as exc:
            raise ValueError("record_limit must be a positive integer") from exc
        if normalized_limit <= 0:
            raise ValueError("record_limit must be a positive integer")

        relative_prefix = "/".join(
            (
                "v1",
                _clean_key_part(platform, fallback="platform"),
                _clean_key_part(account_scope, fallback="account"),
                _clean_key_part(strategy_profile, fallback="strategy"),
                _clean_key_part(execution_mode, fallback="mode"),
            )
        )
        records: list[dict[str, str]] = []
        truncation: list[bool] = []
        for namespace in (self.namespace, self.outcome_namespace):
            entries = self._recent_ledger_entries(
                namespace=namespace,
                relative_prefix=relative_prefix,
                record_limit=normalized_limit,
                truncation_out=truncation,
            )
            records.extend(
                {
                    "namespace": namespace,
                    "object_sha256": hashlib.sha256(uri.encode("utf-8")).hexdigest(),
                    "content_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
                }
                for uri, content in entries
            )
        payload = json.dumps(
            {
                "schema_version": EXECUTION_LEDGER_DIGEST_SCHEMA_VERSION,
                "records": sorted(
                    records,
                    key=lambda item: (
                        item["namespace"],
                        item["object_sha256"],
                        item["content_sha256"],
                    ),
                ),
            },
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest(), len(records), any(truncation)

    def _recent_ledger_entries(
        self,
        *,
        namespace: str,
        relative_prefix: str,
        record_limit: int,
        truncation_out: list[bool] | None = None,
    ) -> list[tuple[str, str]]:
        if self.cloud_prefix_uri:
            object_store = self._object_store()
            prefix_uri = self._cloud_prefix_for_namespace(relative_prefix, namespace)
            uris = sorted(str(uri) for uri in object_store.list(prefix_uri))
            if truncation_out is not None:
                truncation_out.append(len(uris) > record_limit)
            selected_uris = uris[-record_limit:]
            return [(uri, object_store.read_text(uri)) for uri in selected_uris]
        if self.local_dir:
            root = Path(self.local_dir).expanduser() / namespace / _clean_relative_key(relative_prefix)
            paths = sorted(path for path in root.rglob("*.json") if path.is_file())
            if truncation_out is not None:
                truncation_out.append(len(paths) > record_limit)
            selected_paths = paths[-record_limit:]
            return [(str(path), path.read_text(encoding="utf-8")) for path in selected_paths]
        raise RuntimeError("execution state store has no durable ledger backend")

    def _local_path(self, marker_key: str) -> Path:
        root = Path(self.local_dir or tempfile.gettempdir()).expanduser()
        return root / self.namespace / f"{_clean_relative_key(marker_key)}.json"

    def _outcome_local_path(self, marker_key: str) -> Path:
        root = Path(self.local_dir or tempfile.gettempdir()).expanduser()
        return root / self.outcome_namespace / f"{_clean_relative_key(marker_key)}.json"

    def _cloud_uri(self, marker_key: str) -> str:
        return self._cloud_uri_for_namespace(marker_key, self.namespace)

    def _outcome_cloud_uri(self, marker_key: str) -> str:
        return self._cloud_uri_for_namespace(marker_key, self.outcome_namespace)

    def _cloud_uri_for_namespace(self, marker_key: str, namespace: str) -> str:
        bucket_name, prefix = _parse_cloud_uri(str(self.cloud_prefix_uri or ""))
        object_name = "/".join(
            part.strip("/")
            for part in (
                prefix,
                namespace,
                f"{_clean_relative_key(marker_key)}.json",
            )
            if part and part.strip("/")
        )
        return f"gs://{bucket_name}/{object_name}"

    def _cloud_prefix_for_namespace(self, marker_key: str, namespace: str) -> str:
        bucket_name, prefix = _parse_cloud_uri(str(self.cloud_prefix_uri or ""))
        object_name = "/".join(
            part.strip("/")
            for part in (
                prefix,
                namespace,
                _clean_relative_key(marker_key),
            )
            if part and part.strip("/")
        )
        return f"gs://{bucket_name}/{object_name}/"

    def _object_store(self):
        try:
            from quant_platform_kit.cloud import get_object_store
        except ImportError as exc:
            raise RuntimeError(
                "quant_platform_kit.cloud is required for GCS execution markers"
            ) from exc
        return get_object_store(project_id=self.project_id)

    def _gcs_client(self):
        """Deprecated: use _object_store() instead."""
        return self._object_store()



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


def _is_paper_account_scope(value: object) -> bool:
    return str(value or "").strip().upper() == "PAPER"


def _runtime_report_segment(value: object) -> str:
    text = str(value or "").strip()
    safe = "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "_" for ch in text)
    return safe or "unknown"


def _month_segment(*values: object) -> str:
    for value in values:
        text = _optional_str(value)
        if len(text) >= 7 and text[4] == "-" and text[:4].isdigit() and text[5:7].isdigit():
            return text[:7]
    return ""


def _optional_str(value: object) -> str:
    return str(value or "").strip()


def _report_matches_execution(
    payload: Mapping[str, Any],
    *,
    platform: str,
    strategy_profile: str,
    account_scope: str,
    signal_date: str,
    effective_date: str,
    dry_run_only: bool,
) -> bool:
    report = dict(payload or {})
    if _optional_str(report.get("platform")).lower() != _optional_str(platform).lower():
        return False
    if _optional_str(report.get("strategy_profile")).lower() != _optional_str(strategy_profile).lower():
        return False
    if _optional_str(report.get("account_scope")).lower() != _optional_str(account_scope).lower():
        return False
    if bool(report.get("dry_run")) != bool(dry_run_only):
        return False
    summary = dict(report.get("summary") or {})
    if signal_date and _date_key(signal_date) not in _report_signal_date_keys(report, summary):
        return False
    if effective_date and _date_key(effective_date) not in _report_effective_date_keys(report, summary):
        return False
    return (
        bool(summary.get("action_done"))
        or int(float(summary.get("orders_previewed_count") or 0)) > 0
        or int(float(summary.get("order_events_count") or 0)) > 0
        or _is_successful_no_action_report(report, summary)
    )


def _is_successful_no_action_report(report: Mapping[str, Any], summary: Mapping[str, Any]) -> bool:
    if _optional_str(report.get("status")).lower() != "ok":
        return False
    if int(float(summary.get("orders_skipped_count") or 0)) > 0:
        return False
    return bool("action_done" in summary and not summary.get("action_done"))


def _report_signal_date_keys(report: Mapping[str, Any], summary: Mapping[str, Any]) -> set[str]:
    signal_snapshot = _report_signal_snapshot(report)
    return _date_keys(
        summary.get("signal_date"),
        signal_snapshot.get("signal_as_of"),
        signal_snapshot.get("market_date"),
        signal_snapshot.get("price_as_of"),
        signal_snapshot.get("snapshot_as_of"),
    )


def _report_effective_date_keys(report: Mapping[str, Any], summary: Mapping[str, Any]) -> set[str]:
    signal_snapshot = _report_signal_snapshot(report)
    return _date_keys(
        summary.get("effective_date"),
        signal_snapshot.get("effective_date"),
    )


def _report_signal_snapshot(report: Mapping[str, Any]) -> dict[str, Any]:
    diagnostics = report.get("diagnostics")
    if not isinstance(diagnostics, Mapping):
        return {}
    signal_snapshot = diagnostics.get("signal_snapshot")
    return dict(signal_snapshot) if isinstance(signal_snapshot, Mapping) else {}


def _date_keys(*values: object) -> set[str]:
    return {key for value in values if (key := _date_key(value))}


def _date_key(value: object) -> str:
    text = _optional_str(value)
    if len(text) >= 10 and text[4] == "-" and text[7] == "-":
        return text[:10]
    return text


ACCOUNT_SUBMISSION_CONTRACT = "account_submission.v1"
_ACCOUNT_SUBMISSION_NAMESPACE = "account_submissions"
_SUBMISSION_ACK = frozenset({"PendingSubmit", "ApiPending", "ApiPendingSubmit", "Submitted", "PreSubmitted"})
_SUBMISSION_PARTIAL = frozenset({"Partial", "PartiallyFilled"})
_SUBMISSION_TERMINAL = frozenset({"Filled", "Rejected", "rejected", "Cancelled", "ApiCancelled"})


class AccountSubmissionError(RuntimeError):
    """No new submission permission was obtained; reconciliation may be required."""


def submission_binding_digest(value: Mapping[str, Any]) -> str:
    """Content identity; never use lossy path cleaning for account/order identity."""
    if not isinstance(value, Mapping) or not value:
        raise AccountSubmissionError("nonempty submission binding required")
    try:
        encoded = json.dumps(dict(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise AccountSubmissionError("invalid submission binding") from exc
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _submission_text(value: object) -> str:
    if not isinstance(value, str) or not value or value != value.strip() or len(value) > 256:
        raise AccountSubmissionError("invalid submission identity")
    if any(ord(char) < 32 or ord(char) > 126 for char in value):
        raise AccountSubmissionError("invalid submission identity")
    return value


def _submission_digest(value: object) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise AccountSubmissionError("invalid submission digest")
    return value


def _submission_account(broker: str, account_id: str) -> tuple[str, str]:
    broker = _submission_text(broker).lower()
    if re.fullmatch(r"[a-z][a-z0-9_-]*", broker) is None:
        raise AccountSubmissionError("invalid broker identity")
    account = _submission_text(account_id)
    if broker == "ibkr":
        account = account.upper()
        if re.fullmatch(r"(?:DU|U|F|I)[0-9]+", account) is None:
            raise AccountSubmissionError("physical IBKR account identity required")
    return broker, account


def _submission_number(value: object) -> float:
    if isinstance(value, bool):
        raise AccountSubmissionError("invalid submission quantity/price")
    try:
        result = float(value)
    except (ValueError, TypeError) as exc:
        raise AccountSubmissionError("invalid submission quantity/price") from exc
    if not math.isfinite(result) or result < 0:
        raise AccountSubmissionError("invalid submission quantity/price")
    return result


@dataclass(frozen=True)
class AccountSubmissionGrant:
    account_root: str
    attempt_id: str
    fence: str
    generation: int
    event_sha256: str
    intent_id: str
    order_sha256: str
    release_id: str


@dataclass(frozen=True, eq=False)
class ConditionalPlanningHandle:
    """Process-local reference for a conditional, non-executable candidate."""
    strategy_state_sha256: str
    strategy_intent_sha256: str
    strategy_session: str
    input_sha256: str


def _joint_strategy_transition(value):
    from quant_platform_kit.common.strategy_risk_state import StrategyRiskStateTransition
    try:
        return StrategyRiskStateTransition.from_dict(value)
    except (TypeError, ValueError) as exc:
        raise AccountSubmissionError("invalid joint strategy state") from exc


def _joint_strategy_binding(state, profile, owner_id, release_id, state_sha, intent_sha, strategy_session):
    enrollment = state["strategy_enrollment"]
    if enrollment is None:
        if state_sha is not None or intent_sha is not None or strategy_session is not None:
            raise AccountSubmissionError("strategy state binding requires enrollment")
        return None
    transition = _joint_strategy_transition(state["strategy_state"])
    payload = transition.state
    intent = payload.get("pending_intent")
    if (profile != enrollment["profile"] or owner_id != enrollment["owner_id"] or release_id != enrollment["release_id"]
            or state_sha != transition.transition_sha256 or not isinstance(intent, dict)
            or strategy_session != transition.effective_session
            or set(intent) != {"id", "alpha_epoch", "signal_session"}
            or type(intent["id"]) is not str or not intent["id"]
            or type(intent["alpha_epoch"]) is not int or intent["alpha_epoch"] <= 0
            or intent["alpha_epoch"] != payload.get("alpha_epoch")
            or intent["signal_session"] != transition.effective_session
            or payload.get("schema_version") != "tqqq_daily_state.v1"
            or payload.get("session") != transition.effective_session
            or payload.get("alpha_trend_active") is not True
            or payload.get("volatility_latch_active") is not False
            or payload.get("intent_invalidation_reason") not in (None, "new_session")
            or intent_sha != submission_binding_digest(intent)):
        raise AccountSubmissionError("strategy state binding mismatch or intent unavailable")
    return {"strategy_state_sha256": state_sha, "strategy_intent_sha256": intent_sha,
            "strategy_session": strategy_session}


@dataclass(frozen=True, init=False, eq=False)
class AccountSubmissionSession:
    """Stage B: immutable account arbitration, with no UNKNOWN resolution API.

    Every writer uses one broker/physical-account sequence on the existing
    ObjectStore. A fresh, confirmed create is the only source of a grant. A
    stale listing cannot acquire the occupied next sequence. PREPARED remains
    blocking after crashes; only the original in-memory grant owner can dispatch
    it once. There is no TTL, takeover, delete, reset, or automatic reconciliation.
    """

    contract_version = ACCOUNT_SUBMISSION_CONTRACT

    def __init__(self, store: ExecutionMarkerStore, *, broker: str, account_id: str,
                 owner_id: str, profile: str, intent_id: str, release_id: str,
                 account_domain=None, observed_account_id=None, broker_identity=None, observed_at=None, decision_at=None,
                 observed_environment=None, observed_server=None, observed_currency=None, observed_lifecycle_id=None, clock=None):
        if not isinstance(store, ExecutionMarkerStore) or not (store.cloud_prefix_uri or store.local_dir):
            raise AccountSubmissionError("existing durable execution store required")
        broker, account = _submission_account(broker, account_id)
        values = {
            "store": store, "broker": broker, "account_id": account,
            "owner_id": _submission_text(owner_id), "profile": _submission_text(profile),
            "intent_id": _submission_digest(intent_id), "release_id": _submission_digest(release_id),
            "account_root": "v1/" + submission_binding_digest({"broker": broker, "account_id": account}),
            "_issued": {}, "_used": set(), "_planning_handles": {}, "_mutex": threading.RLock(), "_failed": False,
            "account_domain": account_domain, "observed_account_id": observed_account_id,
            "broker_identity": broker_identity, "observed_at": observed_at, "decision_at": decision_at,
            "observed_environment": observed_environment, "observed_server": observed_server,
            "observed_currency": observed_currency, "observed_lifecycle_id": observed_lifecycle_id,
            "clock": clock if clock is not None else lambda: datetime.now(timezone.utc),
        }
        for name, value in values.items():
            object.__setattr__(self, name, value)

    def _location(self, sequence: int | None = None):
        suffix = self.account_root + "/" + (f"{sequence:020d}.json" if sequence is not None else "")
        if self.store.cloud_prefix_uri:
            if sequence is None:
                return self.store._cloud_prefix_for_namespace(self.account_root, _ACCOUNT_SUBMISSION_NAMESPACE)
            return self.store._cloud_uri_for_namespace(suffix.removesuffix(".json"), _ACCOUNT_SUBMISSION_NAMESPACE)
        return Path(self.store.local_dir).expanduser() / _ACCOUNT_SUBMISSION_NAMESPACE / suffix

    def for_intent(self, intent_id):
        """Create a new session bound to the actual post-risk intent digest."""
        return AccountSubmissionSession(self.store, broker=self.broker, account_id=self.account_id,
            owner_id=self.owner_id, profile=self.profile, intent_id=intent_id, release_id=self.release_id,
            account_domain=self.account_domain, observed_account_id=self.observed_account_id,
            broker_identity=self.broker_identity, observed_at=self.observed_at, decision_at=self.decision_at,
            observed_environment=self.observed_environment, observed_server=self.observed_server,
            observed_currency=self.observed_currency, observed_lifecycle_id=self.observed_lifecycle_id, clock=self.clock)

    def _order(self, order) -> tuple[str, float]:
        _, account = _submission_account(self.broker, getattr(order, "account_id", None))
        if account != self.account_id:
            raise AccountSubmissionError("submission account differs from session")
        quantity = _submission_number(getattr(order, "quantity", None))
        if quantity <= 0:
            raise AccountSubmissionError("positive submission quantity required")
        limit = getattr(order, "limit_price", None)
        if limit is not None:
            limit = _submission_number(limit)
        descriptor = {
            "account_id": account, "symbol": _submission_text(getattr(order, "symbol", "")).upper(),
            "side": _submission_text(getattr(order, "side", "")).lower(), "quantity": quantity,
            "order_type": _submission_text(getattr(order, "order_type", "market")).lower(),
            "limit_price": limit, "time_in_force": str(getattr(order, "time_in_force", None) or "DAY").upper(),
            "metadata": dict(getattr(order, "metadata", None) or {}),
        }
        if descriptor["side"] not in {"buy", "sell"}:
            raise AccountSubmissionError("unsupported submission side")
        return submission_binding_digest(descriptor), quantity

    def order_binding_digest(self, order) -> str:
        """Return the canonical digest used to bind this account's order."""
        return self._order(order)[0]

    @staticmethod
    def _event_hash(event: Mapping[str, Any]) -> str:
        return submission_binding_digest({k: v for k, v in event.items() if k != "event_sha256"})

    @staticmethod
    def _certainty(observation: Mapping[str, Any], quantity: float) -> str:
        status, order_id = observation["status"], observation["broker_order_id"]
        filled, price = observation["filled_quantity"], observation["average_fill_price"]
        if filled > quantity or (filled > 0 and (price is None or price <= 0)):
            return "UNKNOWN"
        if status in {"Rejected", "rejected", "Cancelled", "ApiCancelled"}:
            return "TERMINAL"
        if not order_id:
            return "UNKNOWN"
        if status == "Filled":
            return "TERMINAL" if filled == quantity else "UNKNOWN"
        if status in _SUBMISSION_PARTIAL:
            return "KNOWN_PENDING" if 0 < filled < quantity else "UNKNOWN"
        if status in _SUBMISSION_ACK or status == "accepted":
            return "KNOWN_PENDING"
        return "UNKNOWN"

    def read_state(self) -> dict[str, Any]:
        """Validate and reduce all account events; absence alone grants nothing."""
        prefix = self._location()
        if self.store.cloud_prefix_uri:
            objects = self.store._object_store()
            locations = list(objects.list(str(prefix)))
            read = objects.read_text
        else:
            locations = list(prefix.glob("*.json")) if prefix.exists() else []
            def read(path):
                return path.read_text(encoding="utf-8")
        if len(locations) != len(set(map(str, locations))):
            raise AccountSubmissionError("duplicate account journal sequence")
        state: dict[str, Any] = {"generation": 0, "head_sha256": "0" * 64, "attempts": {}, "domain_binding": None, "risk_reservations": {}, "equity_observation": None, "snapshot_position_risk": 0.0, "strategy_enrollment": None, "strategy_state": None}
        for location in sorted(locations, key=str):
            sequence = state["generation"] + 1
            if str(location) != str(self._location(sequence)):
                raise AccountSubmissionError("incomplete or wrong account journal sequence")
            try:
                event = json.loads(read(location))
            except (ValueError, TypeError) as exc:
                raise AccountSubmissionError("invalid account journal JSON") from exc
            required = {"schema_version", "account_root", "sequence", "previous_sha256", "kind", "data", "event_sha256"}
            if not isinstance(event, dict) or set(event) != required:
                raise AccountSubmissionError("invalid account journal event fields")
            if (event["schema_version"] != ACCOUNT_SUBMISSION_CONTRACT or event["account_root"] != self.account_root
                    or type(event["sequence"]) is not int or event["sequence"] != sequence
                    or event["previous_sha256"] != state["head_sha256"]
                    or event["event_sha256"] != self._event_hash(event)):
                raise AccountSubmissionError("account journal schema/root/hash/sequence mismatch")
            data = event["data"]
            if not isinstance(data, dict):
                raise AccountSubmissionError("invalid account event data")
            if event["kind"] == "DOMAIN_BOUND":
                if set(data) != {"domain_key", "account_type", "currency"} or state["domain_binding"] is not None:
                    raise AccountSubmissionError("invalid or duplicate domain binding")
                _submission_digest(data["domain_key"])
                _submission_text(data["account_type"])
                _submission_text(data["currency"])
                state["domain_binding"] = data
            elif event["kind"] == "STRATEGY_STATE_ENROLLED":
                keys = {"profile", "owner_id", "release_id", "account_domain_key", "legacy_head_sha256",
                        "authority_receipt_sha256", "transition"}
                if set(data) != keys or state["strategy_enrollment"] is not None or state["domain_binding"] is None:
                    raise AccountSubmissionError("invalid strategy state enrollment")
                transition = _joint_strategy_transition(data["transition"])
                if (data["account_domain_key"] != state["domain_binding"]["domain_key"]
                        or data["profile"] != transition.identity.strategy_profile
                        or data["legacy_head_sha256"] != transition.transition_sha256
                        or any(a["certainty"] in {"PREPARED", "UNKNOWN", "KNOWN_PENDING"} for a in state["attempts"].values())):
                    raise AccountSubmissionError("strategy state enrollment mismatch")
                _submission_text(data["owner_id"])
                _submission_digest(data["release_id"])
                _submission_digest(data["authority_receipt_sha256"])
                state["strategy_enrollment"] = {key: data[key] for key in ("profile", "owner_id", "release_id", "account_domain_key")}
                state["strategy_state"] = transition.to_dict()
            elif event["kind"] == "STRATEGY_STATE_ADVANCED":
                if set(data) != {"profile", "owner_id", "release_id", "transition"} or state["strategy_enrollment"] is None:
                    raise AccountSubmissionError("invalid strategy state advance")
                enrolled = state["strategy_enrollment"]
                if any(data[k] != enrolled[k] for k in ("profile", "owner_id", "release_id")):
                    raise AccountSubmissionError("strategy state actor mismatch")
                prior = _joint_strategy_transition(state["strategy_state"])
                transition = _joint_strategy_transition(data["transition"])
                if (transition.identity != prior.identity or transition.previous_transition_sha256 != prior.transition_sha256
                        or transition.effective_session <= prior.effective_session
                        or any(a["certainty"] in {"PREPARED", "UNKNOWN", "KNOWN_PENDING"} for a in state["attempts"].values())):
                    raise AccountSubmissionError("strategy state advance conflict")
                state["strategy_state"] = transition.to_dict()
            elif event["kind"] == "EQUITY_OBSERVED":
                equity_fields = {"equity", "cash_flow", "peak", "currency", "valuation_at", "source_digest", "covered_fills", "covered_fees", "position_risk", "position_3x_exposure", "protected_equity", "balance", "cash", "account_domain_key", "account_binding", "valid_until", "pending_3x_exposure", "open_orders_complete", "positions", "open_orders_empty"}
                if set(data) not in (equity_fields, equity_fields | {"pending_order_evidence"}) or state["domain_binding"] is None:
                    raise AccountSubmissionError("invalid equity observation")
                equity = _submission_number(data["equity"])
                _submission_number(data["balance"])
                _submission_number(data["cash"])
                if state["domain_binding"] is None or data["account_domain_key"] != state["domain_binding"]["domain_key"] or data["account_binding"] != submission_binding_digest({"broker": self.broker, "account_id": self.account_id}) or data["open_orders_complete"] is not True or _submission_number(data["pending_3x_exposure"]) < 0:
                    raise AccountSubmissionError("invalid snapshot account or pending observation")
                if not isinstance(data["positions"], dict) or any(not isinstance(symbol, str) or not symbol or not math.isfinite(_submission_number(qty)) for symbol, qty in data["positions"].items()) or type(data["open_orders_empty"]) is not bool:
                    raise AccountSubmissionError("invalid position or pending observation")
                from quant_platform_kit.common.account_domain import _time
                if _time(data["valid_until"]) <= _time(data["valuation_at"]):
                    raise AccountSubmissionError("invalid snapshot validity interval")
                cash_flow = _submission_number(data["cash_flow"])
                peak = _submission_number(data["peak"])
                if not isinstance(data["covered_fills"], dict) or any(not isinstance(key, str) or _submission_number(value) < 0 for key, value in data["covered_fills"].items()):
                    raise AccountSubmissionError("invalid covered attempt ids")
                if not isinstance(data["covered_fees"], dict) or any(not isinstance(key, str) or _submission_number(value) < 0 for key, value in data["covered_fees"].items()):
                    raise AccountSubmissionError("invalid covered fees")
                if _submission_number(data["position_3x_exposure"]) < 0:
                    raise AccountSubmissionError("invalid 3x position exposure")
                if _submission_number(data["position_risk"]) < 0:
                    raise AccountSubmissionError("invalid position risk")
                previous = state["equity_observation"]
                expected_peak = equity if previous is None else max(equity, previous["peak"] + cash_flow)
                expected_protected = equity if previous is None else max(equity, previous["protected_equity"])
                if data["protected_equity"] != expected_protected:
                    raise AccountSubmissionError("invalid protected equity transition")
                if equity < 0 or peak < 0 or not math.isclose(peak, expected_peak, rel_tol=1e-12, abs_tol=1e-9) or data["currency"] != state["domain_binding"]["currency"]:
                    raise AccountSubmissionError("invalid equity peak transition")
                from quant_platform_kit.common.account_domain import _time
                if previous is not None and _time(data["valuation_at"]) <= _time(previous["valuation_at"]):
                    raise AccountSubmissionError("non-monotonic equity observation")
                if "pending_order_evidence" in data:
                    from quant_platform_kit.common.pending_order_evidence import validate_pending_order_evidence
                    try:
                        validate_pending_order_evidence(data["pending_order_evidence"], observation=data,
                                                        attempts=state["attempts"], reservations=state["risk_reservations"])
                    except (ValueError, TypeError, KeyError) as exc:
                        raise AccountSubmissionError("invalid pending order evidence") from exc
                state["equity_observation"] = data
                state["snapshot_position_risk"] = _submission_number(data["position_risk"])
            elif event["kind"] == "RISK_RESERVED":
                if set(data) != {"order_sha256", "amount", "currency", "valuation_at", "source_digest", "reserved_3x_exposure", "quantity", "estimated_fee", "loss_per_unit", "quantity_step", "risk_fraction", "product_leverage_factor", "unit_price", "existing_3x_exposure", "pending_3x_exposure", "floor", "cost_buffer", "leverage_hitl_approved", "account_budget_policy"}:
                    raise AccountSubmissionError("invalid risk reservation")
                order_digest = _submission_digest(data["order_sha256"])
                amount = _submission_number(data["amount"])
                exposure = _submission_number(data["reserved_3x_exposure"])
                if amount <= 0 or exposure < 0 or order_digest in state["risk_reservations"] or state["domain_binding"] is None:
                    raise AccountSubmissionError("invalid or duplicate risk reservation")
                if data["currency"] != state["domain_binding"]["currency"]:
                    raise AccountSubmissionError("risk reservation currency mismatch")
                _submission_text(data["valuation_at"])
                _submission_text(data["source_digest"])
                quantity = _submission_number(data["quantity"])
                fee = _submission_number(data["estimated_fee"])
                for field in ("loss_per_unit", "quantity_step", "risk_fraction", "product_leverage_factor", "unit_price", "existing_3x_exposure", "pending_3x_exposure", "floor", "cost_buffer"):
                    _submission_number(data[field])
                if not isinstance(data["account_budget_policy"], dict):
                    raise AccountSubmissionError("invalid account budget policy")
                if type(data["leverage_hitl_approved"]) is not bool:
                    raise AccountSubmissionError("invalid leverage approval fact")
                if quantity <= 0 or fee < 0 or fee > amount:
                    raise AccountSubmissionError("invalid reserved quantity or fee")
                state["risk_reservations"][order_digest] = {**data, "remaining_amount": amount, "reconciled_filled": 0.0, "actual_fee": 0.0, "remaining_3x_exposure": exposure}
            elif event["kind"] == "RISK_RECONCILED":
                from quant_platform_kit.common.account_domain import _time
                if set(data) != {"attempt_id", "filled_quantity", "actual_fee", "snapshot_position_risk", "source_digest"}:
                    raise AccountSubmissionError("invalid risk reconciliation")
                attempt = state["attempts"].get(data["attempt_id"])
                observation = state["equity_observation"]
                if attempt is None or observation is None or data["source_digest"] != observation["source_digest"]:
                    raise AccountSubmissionError("risk reconciliation snapshot mismatch")
                reservation = state["risk_reservations"].get(attempt["order_sha256"])
                filled = _submission_number(data["filled_quantity"])
                fee = _submission_number(data["actual_fee"])
                position_risk = _submission_number(data["snapshot_position_risk"])
                if (reservation is None or attempt["certainty"] not in {"TERMINAL", "KNOWN_PENDING"}
                        or observation["covered_fills"].get(data["attempt_id"]) != filled
                        or observation["covered_fees"].get(data["attempt_id"]) != fee
                        or observation["position_risk"] != position_risk
                        or observation["source_digest"] == reservation["source_digest"]
                        or _time(observation["valuation_at"]) <= _time(reservation["valuation_at"])
                        or filled != attempt["filled_quantity"] or filled < reservation["reconciled_filled"]
                        or fee < reservation["actual_fee"] or position_risk < 0):
                    raise AccountSubmissionError("risk reconciliation facts mismatch")
                if attempt["certainty"] == "TERMINAL":
                    remaining = 0.0
                else:
                    remaining = (reservation["amount"] - reservation["estimated_fee"]) * (1.0 - filled / reservation["quantity"]) + max(0.0, reservation["estimated_fee"] - fee)
                remaining_3x = 0.0 if attempt["certainty"] == "TERMINAL" else reservation["reserved_3x_exposure"] * (1.0 - filled / reservation["quantity"])
                reservation.update(remaining_amount=remaining, remaining_3x_exposure=remaining_3x, reconciled_filled=filled, actual_fee=fee)
                state["snapshot_position_risk"] = position_risk
            elif event["kind"] == "PREPARED":
                keys = {"attempt_id", "fence", "intent_id", "order_sha256", "release_id", "owner_id", "profile", "quantity"}
                if set(data) not in (keys, keys | {"reduction", "reduction_source_digest"}, keys | {"reduction", "reduction_source_digest", "reduction_kind"}, keys | {"strategy_binding"}) or ("reduction" in data and data["reduction"] is not True) or ("reduction_kind" in data and data["reduction_kind"] != "strategy_position"):
                    raise AccountSubmissionError("invalid prepared fields")
                for key in ["attempt_id", "fence", "intent_id", "order_sha256", "release_id"]:
                    _submission_digest(data[key])
                for key in ["owner_id", "profile"]:
                    _submission_text(data[key])
                if not data.get("reduction"):
                    supplied = data.get("strategy_binding") or {}
                    binding = _joint_strategy_binding(state, data["profile"], data["owner_id"], data["release_id"],
                        supplied.get("strategy_state_sha256"), supplied.get("strategy_intent_sha256"), supplied.get("strategy_session"))
                    if binding != data.get("strategy_binding"):
                        raise AccountSubmissionError("strategy state binding mismatch")
                elif state["strategy_enrollment"] is not None and any(
                        data[key] != state["strategy_enrollment"][key] for key in ("profile", "owner_id", "release_id")):
                    raise AccountSubmissionError("strategy reduction actor mismatch")
                quantity = _submission_number(data["quantity"])
                if quantity <= 0 or any(a["certainty"] in {"PREPARED", "UNKNOWN"} for a in state["attempts"].values()):
                    raise AccountSubmissionError("prepared event bypasses unresolved account")
                if data["attempt_id"] in state["attempts"] or any(
                    (a["intent_id"], a["order_sha256"]) == (data["intent_id"], data["order_sha256"])
                    for a in state["attempts"].values()
                ):
                    raise AccountSubmissionError("duplicate submission identity")
                if state["domain_binding"] is not None and not data.get("reduction"):
                    if (data["order_sha256"] not in state["risk_reservations"] or any(
                            a["order_sha256"] == data["order_sha256"] and not a.get("reduction")
                            for a in state["attempts"].values())):
                        raise AccountSubmissionError("account risk reservation already used or missing")
                state["attempts"][data["attempt_id"]] = {
                    **data, "generation": sequence, "event_sha256": event["event_sha256"],
                    "certainty": "PREPARED", "observation": None, "filled_quantity": 0.0,
                    "prepared_snapshot": state["equity_observation"],
                }
            elif event["kind"] == "OBSERVED":
                if set(data) not in ({"attempt_id", "observation"}, {"attempt_id", "observation", "recorded_at"}) or data["attempt_id"] not in state["attempts"]:
                    raise AccountSubmissionError("observation references unknown attempt")
                attempt = state["attempts"][data["attempt_id"]]
                observation = data["observation"]
                if not isinstance(observation, dict) or set(observation) != {
                    "status", "broker_order_id", "filled_quantity", "average_fill_price", "certainty",
                }:
                    raise AccountSubmissionError("invalid observation fields")
                if not isinstance(observation["status"], str):
                    raise AccountSubmissionError("invalid broker status")
                if observation["broker_order_id"] is not None:
                    _submission_text(observation["broker_order_id"])
                filled = _submission_number(observation["filled_quantity"])
                if observation["average_fill_price"] is not None:
                    _submission_number(observation["average_fill_price"])
                certainty = self._certainty(observation, attempt["quantity"])
                prior = attempt["observation"]
                if (certainty != observation["certainty"] or filled < attempt["filled_quantity"]
                        or filled > attempt["quantity"] or attempt["certainty"] in {"UNKNOWN", "TERMINAL"}
                        or (prior and prior["broker_order_id"] and prior["broker_order_id"] != observation["broker_order_id"])):
                    raise AccountSubmissionError("illegal or non-monotonic observation; UNKNOWN cannot be resolved")
                recorded_at = data.get("recorded_at")
                if recorded_at is not None:
                    from quant_platform_kit.common.account_domain import _time
                    try:
                        instant = _time(recorded_at)
                        previous_watermark = attempt.get("last_observation_recorded_at")
                        if previous_watermark is not None and instant < _time(previous_watermark):
                            raise ValueError("reception time moved backwards")
                    except (ValueError, TypeError) as exc:
                        raise AccountSubmissionError("invalid journal observation watermark") from exc
                    attempt["last_observation_recorded_at"] = recorded_at
                attempt.update(certainty=certainty, observation=observation, filled_quantity=filled,
                               observation_event_sha256=event["event_sha256"], observation_recorded_at=recorded_at)
            else:
                raise AccountSubmissionError("unsupported account event; no resolution API")
            state.update(generation=sequence, head_sha256=event["event_sha256"])
        return state

    def _append(self, state: Mapping[str, Any], kind: str, data: dict) -> dict:
        event = {
            "schema_version": ACCOUNT_SUBMISSION_CONTRACT, "account_root": self.account_root,
            "sequence": state["generation"] + 1, "previous_sha256": state["head_sha256"],
            "kind": kind, "data": data,
        }
        event["event_sha256"] = self._event_hash(event)
        encoded = json.dumps(event, sort_keys=True, allow_nan=False)
        location = self._location(event["sequence"])
        try:
            if self.store.cloud_prefix_uri:
                created = self.store._object_store().create_text(str(location), encoded, "application/json")
            else:
                location.parent.mkdir(parents=True, exist_ok=True)
                try:
                    fd = os.open(location, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                except FileExistsError:
                    created = False
                else:
                    with os.fdopen(fd, "w", encoding="utf-8") as handle:
                        handle.write(encoded)
                        handle.flush()
                        os.fsync(handle.fileno())
                    created = True
            if created is not True:
                raise AccountSubmissionError("account event create conflict; no submission grant")
            confirmed = self.read_state()
            if confirmed["generation"] != event["sequence"] or confirmed["head_sha256"] != event["event_sha256"]:
                raise AccountSubmissionError("account event confirmation failed")
        except Exception:
            object.__setattr__(self, "_failed", True)
            raise
        return event

    def record_account_equity(self, *, snapshot, cash_flow, baseline_confirmed=False):
        """Record a complete account equity observation with cash-flow-adjusted peak."""
        from quant_platform_kit.common.account_risk_budget import available_new_risk_budget
        from quant_platform_kit.common.account_domain import (
            account_domain_key, account_domain_matches_broker_identity,
            account_domain_policy_active, validate_account_domain,
        )
        with self._mutex:
            if self._failed:
                raise AccountSubmissionError("session persistence uncertain")
            state = self.read_state()
            binding = state["domain_binding"]
            if binding is None or self.account_domain is None:
                raise AccountSubmissionError("bound domain required")
            domain = validate_account_domain(self.account_domain, platform_id=self.broker)
            if (binding != {"domain_key": account_domain_key(domain), "account_type": domain["policy"]["account_type"], "currency": domain["policy"]["currency"]}
                    or not account_domain_matches_broker_identity(domain, self.broker_identity, observed_environment=self.observed_environment, observed_server=self.observed_server, observed_currency=self.observed_currency, observed_lifecycle_id=self.observed_lifecycle_id)
                    or not account_domain_policy_active(domain, as_of=self.decision_at)):
                raise AccountSubmissionError("verified domain required")
            _, observed_account = _submission_account(self.broker, self.observed_account_id)
            if observed_account != self.account_id:
                raise AccountSubmissionError("account domain observation mismatch")
            # Validate completeness, identity, pending exposure, and source validity.
            if (snapshot.get("account_domain_key") != account_domain_key(domain)
                    or snapshot.get("account_id") != self.account_id
                    or snapshot.get("open_orders_complete") is not True
                    or _submission_number(snapshot.get("pending_3x_exposure")) < 0):
                raise AccountSubmissionError("snapshot account or pending observation mismatch")
            # Validate completeness, currency, time, provenance and numeric facts.
            available_new_risk_budget(snapshot, currency=binding["currency"], floor=0,
                                      reserved=0, cost_buffer=0, risk_fraction=0.005)
            from quant_platform_kit.common.account_domain import _time
            if not _time(snapshot["valuation_at"]) <= _time(self.observed_at) <= _time(self.decision_at) < _time(snapshot.get("valid_until")):
                raise AccountSubmissionError("equity snapshot is not current at decision time")
            equity = _submission_number(snapshot["equity"])
            flow = _submission_number(cash_flow)
            previous = state["equity_observation"]
            if previous is None and baseline_confirmed is not True:
                raise AccountSubmissionError("trusted initial equity baseline required")
            if equity < 0 or (previous is not None and _time(snapshot["valuation_at"]) <= _time(previous["valuation_at"])):
                raise AccountSubmissionError("invalid or non-monotonic equity observation")
            peak = equity if previous is None else max(equity, previous["peak"] + flow)
            positions = snapshot.get("positions")
            open_orders_empty = snapshot.get("open_orders_empty")
            if not isinstance(positions, dict) or any(not isinstance(symbol, str) or not symbol or not math.isfinite(_submission_number(qty)) for symbol, qty in positions.items()) or type(open_orders_empty) is not bool:
                raise AccountSubmissionError("complete positions and pending observation required")
            covered = snapshot.get("covered_fills", {})
            covered_fees = snapshot.get("covered_fees", {})
            position_risk = snapshot.get("position_risk")
            position_3x = snapshot.get("position_3x_exposure")
            if not isinstance(covered, dict) or any(not isinstance(key, str) or _submission_number(value) < 0 for key, value in covered.items()):
                raise AccountSubmissionError("invalid covered attempt ids")
            if not isinstance(covered_fees, dict) or any(not isinstance(key, str) or _submission_number(value) < 0 for key, value in covered_fees.items()):
                raise AccountSubmissionError("invalid covered fees")
            if _submission_number(position_3x) < 0:
                raise AccountSubmissionError("invalid 3x position exposure")
            if _submission_number(position_risk) < 0:
                raise AccountSubmissionError("invalid position risk")
            evidence = snapshot.get("pending_order_evidence")
            evidence_fields = {}
            if "pending_order_evidence" in snapshot:
                from quant_platform_kit.common.pending_order_evidence import validate_pending_order_evidence
                observation = {**snapshot, "account_binding": submission_binding_digest({"broker": self.broker, "account_id": self.account_id})}
                try:
                    validate_pending_order_evidence(evidence, observation=observation,
                                                    attempts=state["attempts"], reservations=state["risk_reservations"])
                except (ValueError, TypeError, KeyError) as exc:
                    raise AccountSubmissionError("invalid pending order evidence") from exc
                evidence_fields["pending_order_evidence"] = evidence
            return self._append(state, "EQUITY_OBSERVED", {
                **evidence_fields, "equity": equity, "cash_flow": flow, "peak": peak,
                "currency": binding["currency"], "valuation_at": snapshot["valuation_at"],
                "source_digest": snapshot["source_digest"], "covered_fills": covered,
                "covered_fees": covered_fees, "position_risk": position_risk, "position_3x_exposure": position_3x,
                "protected_equity": equity if previous is None else max(equity, previous["protected_equity"]),
                "balance": float(snapshot["balance"]), "cash": float(snapshot["cash"]),
                "account_domain_key": snapshot["account_domain_key"],
                "account_binding": submission_binding_digest({"broker": self.broker, "account_id": self.account_id}),
                "valid_until": snapshot["valid_until"], "pending_3x_exposure": float(snapshot["pending_3x_exposure"]),
                "open_orders_complete": True, "positions": positions, "open_orders_empty": open_orders_empty,
            })

    def reserve_account_risk(self, order, *, snapshot, floor, cost_buffer, amount, risk_fraction,
                             loss_per_unit, estimated_fee, quantity_step, product_leverage_factor,
                             unit_price, existing_3x_exposure, pending_3x_exposure, leverage_hitl_approved,
                             account_budget_policy):
        """Atomically reserve account-currency risk; reservations are never auto-released."""
        from quant_platform_kit.common.account_risk_budget import (
            available_new_risk_budget, maximum_risk_quantity,
        )
        from quant_platform_kit.common.account_domain import (
            account_domain_key, account_domain_matches_broker_identity,
            account_domain_policy_active, validate_account_domain,
        )

        with self._mutex:
            if self._failed or self.account_domain is None:
                raise AccountSubmissionError("bound domain and healthy journal required")
            state = self.read_state()
            if any(item["certainty"] in {"PREPARED", "UNKNOWN"} for item in state["attempts"].values()):
                raise AccountSubmissionError("unresolved account submission")
            domain = validate_account_domain(self.account_domain, platform_id=self.broker)
            binding = state["domain_binding"]
            if (binding is None or binding != {"domain_key": account_domain_key(domain),
                    "account_type": domain["policy"]["account_type"], "currency": domain["policy"]["currency"]}
                    or not account_domain_matches_broker_identity(domain, self.broker_identity, observed_environment=self.observed_environment, observed_server=self.observed_server, observed_currency=self.observed_currency, observed_lifecycle_id=self.observed_lifecycle_id)
                    or not account_domain_policy_active(domain, as_of=self.decision_at)):
                raise AccountSubmissionError("verified domain must be bound before risk reservation")
            _, observed_account = _submission_account(self.broker, self.observed_account_id)
            if observed_account != self.account_id:
                raise AccountSubmissionError("account domain observation mismatch")
            observed = state["equity_observation"]
            if observed is None or any(observed[key] != snapshot.get(key) for key in ("equity", "balance", "cash", "currency", "valuation_at", "source_digest", "account_domain_key", "valid_until", "pending_3x_exposure", "open_orders_complete")):
                raise AccountSubmissionError("matching recorded equity snapshot required")
            from quant_platform_kit.risk.capital_risk_envelope import evaluate_capital_risk_envelope
            peak = observed["peak"]
            if peak <= 0:
                raise AccountSubmissionError("positive protected peak required")
            protected_envelope = evaluate_capital_risk_envelope(
                observed["protected_equity"], drawdown_from_peak=max(0.0, 1.0 - observed["equity"] / peak),
            )
            if not protected_envelope.new_risk_allowed:
                raise AccountSubmissionError("protected drawdown brake prohibits new risk")
            order_digest, quantity = self._order(order)
            if type(leverage_hitl_approved) is not bool:
                raise AccountSubmissionError("invalid leverage approval fact")
            from quant_platform_kit.common.account_domain import _time
            if not _time(observed["valuation_at"]) <= _time(self.observed_at) <= _time(self.decision_at) < _time(observed["valid_until"]):
                raise AccountSubmissionError("account valuation is stale")
            if snapshot.get("account_id") != self.account_id or pending_3x_exposure != observed["pending_3x_exposure"]:
                raise AccountSubmissionError("snapshot account or pending exposure mismatch")
            factor = _submission_number(product_leverage_factor)
            price = _submission_number(unit_price)
            existing_3x = _submission_number(existing_3x_exposure)
            pending_3x = _submission_number(pending_3x_exposure)
            if factor not in (1.0, 3.0) or price <= 0 or existing_3x < 0 or pending_3x < 0 or existing_3x != observed["position_3x_exposure"]:
                raise AccountSubmissionError("known product exposure and pending exposure required")
            if factor == 3.0:
                if protected_envelope.leverage_product_cap.new_leverage_requires_hitl and leverage_hitl_approved is not True:
                    raise AccountSubmissionError("leverage approval required")
                cap = protected_envelope.leverage_product_cap.max_3x_etf_weight * observed["equity"]
                reserved_3x = sum(item["remaining_3x_exposure"] for item in state["risk_reservations"].values())
                if existing_3x + pending_3x + reserved_3x + quantity * price > cap:
                    raise AccountSubmissionError("product leverage cap exceeded")
            amount = _submission_number(amount)
            max_quantity = maximum_risk_quantity(budget=amount, loss_per_unit=loss_per_unit,
                                                 estimated_fee=estimated_fee, quantity_step=quantity_step)
            quantity_steps = Fraction(str(quantity)) / Fraction(str(quantity_step))
            if quantity > max_quantity or abs(quantity_steps - round(quantity_steps)) > Fraction(1, 10**9):
                raise AccountSubmissionError("quantity exceeds reserved risk or step")
            if amount <= 0 or order_digest in state["risk_reservations"]:
                raise AccountSubmissionError("invalid or duplicate account risk reservation")
            expected_fields = {"preference", "version", "source", "per_trade_fraction", "total_future_risk_limit", "floor", "cost_buffer", "contract_floor"}
            if not isinstance(account_budget_policy, Mapping) or set(account_budget_policy) != expected_fields:
                raise AccountSubmissionError("explicit account budget policy required")
            if any(account_budget_policy[key] != domain["policy"][key] for key in ("preference", "version", "source")):
                raise AccountSubmissionError("account budget policy binding mismatch")
            policy_fraction = _submission_number(account_budget_policy["per_trade_fraction"])
            total_limit = _submission_number(account_budget_policy["total_future_risk_limit"])
            if (policy_fraction != _submission_number(risk_fraction) or total_limit < 0
                    or _submission_number(account_budget_policy["floor"]) != _submission_number(floor)
                    or _submission_number(account_budget_policy["cost_buffer"]) != _submission_number(cost_buffer)):
                raise AccountSubmissionError("account budget policy values mismatch")
            if domain["policy"]["capital_kind"] == "FTMO_SIMULATED":
                contract_floor = _submission_number(account_budget_policy["contract_floor"])
                if contract_floor <= 0 or _submission_number(floor) < contract_floor:
                    raise AccountSubmissionError("FTMO confirmed contract floor required")
                if _submission_number(risk_fraction) > 0.005:
                    raise AccountSubmissionError("FTMO risk fraction exceeds offline cap")
            elif account_budget_policy["contract_floor"] is not None:
                raise AccountSubmissionError("unexpected contract floor for own account")
            existing = state["snapshot_position_risk"] + sum(item["remaining_amount"] for item in state["risk_reservations"].values())
            budget = available_new_risk_budget(snapshot, currency=binding["currency"], floor=floor,
                                               reserved=existing, cost_buffer=cost_buffer, risk_fraction=risk_fraction)
            if amount > budget or existing + amount > total_limit:
                raise AccountSubmissionError("account risk budget exceeded")
            return self._append(state, "RISK_RESERVED", {
                "order_sha256": order_digest, "amount": amount, "currency": binding["currency"],
                "valuation_at": snapshot["valuation_at"], "source_digest": snapshot["source_digest"],
                "reserved_3x_exposure": quantity * price if factor == 3.0 else 0.0,
                "quantity": quantity, "estimated_fee": float(estimated_fee),
                "loss_per_unit": float(loss_per_unit), "quantity_step": float(quantity_step),
                "risk_fraction": float(risk_fraction), "product_leverage_factor": factor,
                "unit_price": price, "existing_3x_exposure": existing_3x,
                "pending_3x_exposure": pending_3x, "floor": float(floor),
                "cost_buffer": float(cost_buffer), "leverage_hitl_approved": leverage_hitl_approved,
                "account_budget_policy": dict(account_budget_policy),
            })

    def reconcile_account_risk(self, *, attempt_id, filled_quantity, actual_fee, snapshot_position_risk, source_digest):
        """Transfer observed fills into a complete recorded snapshot; UNKNOWN stays reserved."""
        from quant_platform_kit.common.account_domain import (
            account_domain_key, account_domain_matches_broker_identity,
            account_domain_policy_active, validate_account_domain,
        )
        with self._mutex:
            if self._failed:
                raise AccountSubmissionError("session persistence uncertain")
            state = self.read_state()
            if self.account_domain is None:
                raise AccountSubmissionError("verified domain required")
            domain = validate_account_domain(self.account_domain, platform_id=self.broker)
            binding = {"domain_key": account_domain_key(domain), "account_type": domain["policy"]["account_type"], "currency": domain["policy"]["currency"]}
            _, observed_account = _submission_account(self.broker, self.observed_account_id)
            if (state["domain_binding"] != binding or observed_account != self.account_id
                    or not account_domain_matches_broker_identity(domain, self.broker_identity, observed_environment=self.observed_environment, observed_server=self.observed_server, observed_currency=self.observed_currency, observed_lifecycle_id=self.observed_lifecycle_id)
                    or not account_domain_policy_active(domain, as_of=self.decision_at)):
                raise AccountSubmissionError("verified domain required")
            attempt = state["attempts"].get(attempt_id)
            if attempt is None or attempt["certainty"] not in {"TERMINAL", "KNOWN_PENDING"}:
                raise AccountSubmissionError("known broker observation required")
            reservation = state["risk_reservations"].get(attempt["order_sha256"])
            observation = state["equity_observation"]
            filled = _submission_number(filled_quantity)
            fee = _submission_number(actual_fee)
            position_risk = _submission_number(snapshot_position_risk)
            from quant_platform_kit.common.account_domain import _time
            if (reservation is None or observation is None or source_digest != observation["source_digest"]
                    or observation["covered_fills"].get(attempt_id) != filled
                    or observation["covered_fees"].get(attempt_id) != fee
                    or observation["position_risk"] != position_risk
                    or observation["source_digest"] == reservation["source_digest"]
                    or _time(observation["valuation_at"]) <= _time(reservation["valuation_at"])
                    or filled != attempt["filled_quantity"] or filled < reservation["reconciled_filled"]
                    or fee < reservation["actual_fee"] or position_risk < 0):
                raise AccountSubmissionError("risk reconciliation facts mismatch")
            return self._append(state, "RISK_RECONCILED", {
                "attempt_id": attempt_id, "filled_quantity": filled_quantity,
                "actual_fee": actual_fee, "snapshot_position_risk": snapshot_position_risk,
                "source_digest": source_digest,
            })

    def reserve_reduction(self, order, *, admission) -> AccountSubmissionGrant:
        """Reserve an account-brake reduction from a complete bound snapshot."""
        return self._reserve_verified_reduction(order, admission=admission, strategy_position=False)

    def reserve_strategy_reduction(self, order) -> AccountSubmissionGrant:
        """Reserve an independently proven position reduction, without a flip."""
        return self._reserve_verified_reduction(order, admission=None, strategy_position=True)

    def _reserve_verified_reduction(self, order, *, admission, strategy_position):
        from quant_platform_kit.common.account_domain import (
            _time, account_domain_key, account_domain_matches_broker_identity,
            account_domain_policy_active, validate_account_domain,
        )
        from quant_platform_kit.risk.account_new_risk_gate import NewRiskAdmissionResult, is_proven_risk_reducing_order
        with self._mutex:
            if self._failed or self.account_domain is None or (not strategy_position and (not isinstance(admission, NewRiskAdmissionResult) or not admission.hard_brake_triggered)):
                raise AccountSubmissionError("verified account brake required")
            state = self.read_state()
            enrollment = state["strategy_enrollment"]
            if strategy_position and enrollment is None:
                raise AccountSubmissionError("strategy state enrollment required")
            if enrollment is not None and any(enrollment[k] != getattr(self, k) for k in ("profile", "owner_id", "release_id")):
                raise AccountSubmissionError("strategy state enrollment mismatch")
            domain = validate_account_domain(self.account_domain, platform_id=self.broker)
            binding = {"domain_key": account_domain_key(domain), "account_type": domain["policy"]["account_type"], "currency": domain["policy"]["currency"]}
            _, account = _submission_account(self.broker, self.observed_account_id)
            observed = state["equity_observation"]
            if (state["domain_binding"] != binding or account != self.account_id or observed is None
                    or not observed["open_orders_complete"] or not observed["open_orders_empty"]
                    or not account_domain_matches_broker_identity(domain, self.broker_identity, observed_environment=self.observed_environment, observed_server=self.observed_server, observed_currency=self.observed_currency, observed_lifecycle_id=self.observed_lifecycle_id)
                    or not account_domain_policy_active(domain, as_of=self.decision_at)
                    or not _time(observed["valuation_at"]) <= _time(self.decision_at) < _time(observed["valid_until"])):
                raise AccountSubmissionError("complete verified reduction observation required")
            from quant_platform_kit.risk.capital_risk_envelope import evaluate_capital_risk_envelope
            if not strategy_position and (observed["peak"] <= 0 or "DRAWDOWN_BRAKE_TRIPPED" not in evaluate_capital_risk_envelope(
                    observed["protected_equity"], drawdown_from_peak=max(0.0, 1.0 - observed["equity"] / observed["peak"])).reasons):
                raise AccountSubmissionError("independent drawdown brake not verified")
            digest, quantity = self._order(order)
            symbol = str(getattr(order, "symbol", "")).strip().upper()
            side = str(getattr(order, "side", "")).strip().lower()
            if not is_proven_risk_reducing_order(observed["positions"].get(symbol), side, quantity, pending_quantity=0):
                raise AccountSubmissionError("order reduction not proven")
            if any(a["certainty"] in {"PREPARED", "UNKNOWN", "KNOWN_PENDING"} for a in state["attempts"].values()):
                raise AccountSubmissionError("unresolved account submission")
            for attempt_id, attempt in state["attempts"].items():
                if attempt["filled_quantity"] <= 0:
                    continue
                source = attempt["prepared_snapshot"]
                if (source is None or observed["covered_fills"].get(attempt_id) != attempt["filled_quantity"]
                        or attempt_id not in observed["covered_fees"]
                        or observed["source_digest"] == source["source_digest"]
                        or _time(observed["valuation_at"]) <= _time(source["valuation_at"])):
                    raise AccountSubmissionError("filled submission requires a newer covering snapshot")
            if any((a["intent_id"], a["order_sha256"]) == (self.intent_id, digest) for a in state["attempts"].values()):
                raise AccountSubmissionError("same intent/order already reserved")
            data = {"attempt_id": uuid.uuid4().hex + uuid.uuid4().hex, "fence": uuid.uuid4().hex + uuid.uuid4().hex,
                    "intent_id": self.intent_id, "order_sha256": digest, "release_id": self.release_id,
                    "owner_id": self.owner_id, "profile": self.profile, "quantity": quantity, "reduction": True,
                    "reduction_source_digest": observed["source_digest"]}
            if strategy_position:
                data["reduction_kind"] = "strategy_position"
            event = self._append(state, "PREPARED", data)
            grant = AccountSubmissionGrant(self.account_root, data["attempt_id"], data["fence"], event["sequence"], event["event_sha256"], self.intent_id, digest, self.release_id)
            self._issued[grant.attempt_id] = grant
            return grant

    def _joint_domain(self, state):
        from quant_platform_kit.common.account_domain import (
            account_domain_key, account_domain_matches_broker_identity, account_domain_policy_active, validate_account_domain,
        )
        if self.account_domain is None:
            raise AccountSubmissionError("verified account domain required")
        domain = validate_account_domain(self.account_domain, platform_id=self.broker)
        _, account = _submission_account(self.broker, self.observed_account_id)
        if (account != self.account_id or not account_domain_matches_broker_identity(
                domain, self.broker_identity, observed_environment=self.observed_environment,
                observed_server=self.observed_server, observed_currency=self.observed_currency,
                observed_lifecycle_id=self.observed_lifecycle_id)
                or not account_domain_policy_active(domain, as_of=self.decision_at)):
            raise AccountSubmissionError("account domain observation mismatch")
        binding = {"domain_key": account_domain_key(domain), "account_type": domain["policy"]["account_type"],
                   "currency": domain["policy"]["currency"]}
        if state["domain_binding"] is None:
            self._append(state, "DOMAIN_BOUND", binding)
            state = self.read_state()
        if state["domain_binding"] != binding:
            raise AccountSubmissionError("account domain binding mismatch")
        return state, binding

    def enroll_strategy_state(self, transition, *, legacy_store, migration_authorization):
        """Migrate an externally authorized legacy head into this account journal.

        The binding is not authentication. The caller must independently
        verify its authority and the exact legacy head before invoking this.
        """
        from quant_platform_kit.common.strategy_risk_state import StrategyRiskStateStore, StrategyRiskStateTransition
        if (not isinstance(transition, StrategyRiskStateTransition) or not isinstance(legacy_store, StrategyRiskStateStore)
                or not isinstance(migration_authorization, Mapping)):
            raise AccountSubmissionError("invalid strategy state migration")
        if set(migration_authorization) != {"account_domain_key", "account_binding_sha256", "owner_id", "release_id", "legacy_head_sha256", "strategy_identity", "authority_receipt_sha256"}:
            raise AccountSubmissionError("invalid strategy state migration fields")
        if (transition.identity.strategy_profile != self.profile
                or migration_authorization["account_binding_sha256"] != submission_binding_digest({"broker": self.broker, "account_id": self.account_id})
                or migration_authorization["owner_id"] != self.owner_id
                or migration_authorization["release_id"] != self.release_id
                or migration_authorization["strategy_identity"] != transition.identity.to_dict()
                or migration_authorization["legacy_head_sha256"] != transition.transition_sha256):
            raise AccountSubmissionError("strategy state migration mismatch")
        _submission_digest(migration_authorization["authority_receipt_sha256"])
        from quant_platform_kit.common.account_domain import account_domain_key
        if self.account_domain is None or migration_authorization["account_domain_key"] != account_domain_key(self.account_domain):
            raise AccountSubmissionError("strategy state migration domain mismatch")
        try:
            legacy_chain = legacy_store.load_chain(transition.identity)
        except Exception as exc:
            raise AccountSubmissionError("legacy strategy state unavailable") from exc
        if not legacy_chain or legacy_chain[-1] != transition:
            raise AccountSubmissionError("legacy strategy state head mismatch")
        with self._mutex:
            if self._failed:
                raise AccountSubmissionError("session persistence uncertain")
            state, domain = self._joint_domain(self.read_state())
            if migration_authorization["account_domain_key"] != domain["domain_key"]:
                raise AccountSubmissionError("strategy state migration domain mismatch")
            if state["strategy_enrollment"] is not None or any(
                    a["certainty"] in {"PREPARED", "UNKNOWN", "KNOWN_PENDING"} for a in state["attempts"].values()):
                raise AccountSubmissionError("strategy state enrollment conflict")
            return self._append(state, "STRATEGY_STATE_ENROLLED", {
                "profile": self.profile, "owner_id": self.owner_id, "release_id": self.release_id,
                "account_domain_key": domain["domain_key"], "legacy_head_sha256": transition.transition_sha256,
                "authority_receipt_sha256": migration_authorization["authority_receipt_sha256"],
                "transition": transition.to_dict()})

    def advance_strategy_state(self, transition):
        """Append one state transition under the account's dispatch fence."""
        from quant_platform_kit.common.strategy_risk_state import StrategyRiskStateTransition
        if not isinstance(transition, StrategyRiskStateTransition):
            raise AccountSubmissionError("invalid strategy state")
        with self._mutex:
            if self._failed:
                raise AccountSubmissionError("session persistence uncertain")
            state = self.read_state()
            if state["strategy_enrollment"] is None:
                raise AccountSubmissionError("strategy state enrollment mismatch")
            state, _ = self._joint_domain(state)
            enrollment = state["strategy_enrollment"]
            if enrollment is None or any(enrollment[k] != getattr(self, k) for k in ("profile", "owner_id", "release_id")):
                raise AccountSubmissionError("strategy state enrollment mismatch")
            prior = _joint_strategy_transition(state["strategy_state"])
            if (transition.identity != prior.identity or transition.previous_transition_sha256 != prior.transition_sha256
                    or transition.effective_session <= prior.effective_session
                    or any(a["certainty"] in {"PREPARED", "UNKNOWN", "KNOWN_PENDING"} for a in state["attempts"].values())):
                raise AccountSubmissionError("strategy state advance conflict")
            return self._append(state, "STRATEGY_STATE_ADVANCED", {"profile": self.profile, "owner_id": self.owner_id,
                "release_id": self.release_id, "transition": transition.to_dict()})

    def conditional_planning_handle(self, *, strategy_state_sha256, strategy_intent_sha256, strategy_session, input_sha256):
        """Issue a non-executable candidate handle for a confirmed current head."""
        with self._mutex:
            if self._failed:
                raise AccountSubmissionError("session persistence uncertain")
            state = self.read_state()
            if state["strategy_enrollment"] is None:
                raise AccountSubmissionError("strategy state enrollment required")
            _joint_strategy_binding(state, self.profile, self.owner_id, self.release_id,
                                    strategy_state_sha256, strategy_intent_sha256, strategy_session)
            if _joint_strategy_transition(state["strategy_state"]).input_sha256 != _submission_digest(input_sha256):
                raise AccountSubmissionError("strategy input mismatch")
            if any(a["certainty"] in {"PREPARED", "UNKNOWN", "KNOWN_PENDING"} for a in state["attempts"].values()):
                raise AccountSubmissionError("unresolved account submission")
            handle = ConditionalPlanningHandle(strategy_state_sha256, strategy_intent_sha256, strategy_session, input_sha256)
            self._planning_handles[id(handle)] = handle
            return handle

    def validate_conditional_planning_handle(self, handle, *, input_sha256):
        """Recheck a handle; this never reserves or authorizes an order."""
        with self._mutex:
            if self._planning_handles.get(id(handle)) is not handle or handle.input_sha256 != input_sha256:
                raise AccountSubmissionError("invalid conditional planning handle")
            state = self.read_state()
            _joint_strategy_binding(state, self.profile, self.owner_id, self.release_id,
                                    handle.strategy_state_sha256, handle.strategy_intent_sha256, handle.strategy_session)
            if self._failed or _joint_strategy_transition(state["strategy_state"]).input_sha256 != input_sha256 or any(
                    a["certainty"] in {"PREPARED", "UNKNOWN", "KNOWN_PENDING"} for a in state["attempts"].values()):
                raise AccountSubmissionError("conditional planning handle no longer current")
            return True

    def reserve(self, order, *, strategy_state_sha256=None, strategy_intent_sha256=None, strategy_session=None) -> AccountSubmissionGrant:
        """Only a fresh acknowledged create can return a grant; never reclaim it."""
        with self._mutex:
            if self._failed:
                raise AccountSubmissionError("session persistence uncertain; no grant")
            digest, quantity = self._order(order)
            state = self.read_state()
            strategy_binding = _joint_strategy_binding(state, self.profile, self.owner_id, self.release_id,
                                                       strategy_state_sha256, strategy_intent_sha256, strategy_session)
            if self.account_domain is not None:
                from quant_platform_kit.common.account_domain import (
                    account_domain_key, account_domain_matches_broker_identity, account_domain_policy_active, validate_account_domain,
                )
                domain = validate_account_domain(self.account_domain, platform_id=self.broker)
                if not account_domain_policy_active(domain, as_of=self.decision_at):
                    raise AccountSubmissionError("account domain policy not active")
                try:
                    _, observed_account = _submission_account(self.broker, self.observed_account_id)
                except (ValueError, TypeError) as exc:
                    raise AccountSubmissionError("observed account identity required") from exc
                if observed_account != self.account_id or not account_domain_matches_broker_identity(domain, self.broker_identity, observed_environment=self.observed_environment, observed_server=self.observed_server, observed_currency=self.observed_currency, observed_lifecycle_id=self.observed_lifecycle_id):
                    raise AccountSubmissionError("account domain observation mismatch")
                binding = {"domain_key": account_domain_key(domain),
                           "account_type": domain["policy"]["account_type"],
                           "currency": domain["policy"]["currency"]}
                if state["domain_binding"] is None:
                    self._append(state, "DOMAIN_BOUND", binding)
                    state = self.read_state()
                if state["domain_binding"] != binding:
                    raise AccountSubmissionError("account domain binding mismatch")
            elif state["domain_binding"] is not None:
                raise AccountSubmissionError("bound account domain required")
            if self.account_domain is not None:
                reservation = state["risk_reservations"].get(digest)
                observation = state["equity_observation"]
                if reservation is None:
                    raise AccountSubmissionError("account risk reservation required")
                if observation is None or any(reservation[key] != observation[key] for key in ("valuation_at", "source_digest")):
                    raise AccountSubmissionError("account risk reservation is stale")
            if any(a["certainty"] in {"PREPARED", "UNKNOWN"} for a in state["attempts"].values()):
                raise AccountSubmissionError("unresolved UNKNOWN/account submission")
            if self.account_domain is not None and any(
                a["order_sha256"] == digest and not a.get("reduction") for a in state["attempts"].values()
            ):
                raise AccountSubmissionError("account risk reservation already used")
            if any((a["intent_id"], a["order_sha256"]) == (self.intent_id, digest) for a in state["attempts"].values()):
                raise AccountSubmissionError("same intent/order already reserved; no retry grant")
            data = {
                "attempt_id": uuid.uuid4().hex + uuid.uuid4().hex,
                "fence": uuid.uuid4().hex + uuid.uuid4().hex,
                "intent_id": self.intent_id, "order_sha256": digest, "release_id": self.release_id,
                "owner_id": self.owner_id, "profile": self.profile, "quantity": quantity,
            }
            if strategy_binding is not None:
                data["strategy_binding"] = strategy_binding
            event = self._append(state, "PREPARED", data)
            grant = AccountSubmissionGrant(self.account_root, data["attempt_id"], data["fence"],
                                           event["sequence"], event["event_sha256"], self.intent_id, digest, self.release_id)
            self._issued[grant.attempt_id] = grant
            return grant

    def _owned_grant(self, grant: AccountSubmissionGrant) -> dict:
        if (not isinstance(grant, AccountSubmissionGrant) or self._issued.get(grant.attempt_id) is not grant
                or grant.account_root != self.account_root or grant.intent_id != self.intent_id
                or grant.release_id != self.release_id):
            raise AccountSubmissionError("wrong/stale/session grant")
        state = self.read_state()
        attempt = state["attempts"].get(grant.attempt_id)
        if (not attempt or attempt["fence"] != grant.fence or attempt["generation"] != grant.generation
                or attempt["event_sha256"] != grant.event_sha256 or attempt["order_sha256"] != grant.order_sha256):
            raise AccountSubmissionError("grant fence/binding mismatch")
        if state["strategy_enrollment"] is not None and not attempt.get("reduction"):
            binding = attempt.get("strategy_binding") or {}
            _joint_strategy_binding(state, self.profile, self.owner_id, self.release_id,
                                    binding.get("strategy_state_sha256"), binding.get("strategy_intent_sha256"),
                                    binding.get("strategy_session"))
        return state

    def dispatch(self, grant: AccountSubmissionGrant, order, submit: Callable[[], Any], *, record_observation_watermark=False):
        """Consume exactly once at the final platform submit wrapper, then observe."""
        with self._mutex:
            if type(record_observation_watermark) is not bool:
                raise AccountSubmissionError("invalid observation watermark option")
            if self._failed:
                raise AccountSubmissionError("session persistence uncertain")
            state = self._owned_grant(grant)
            digest, _ = self._order(order)
            if digest != grant.order_sha256 or grant.attempt_id in self._used:
                raise AccountSubmissionError("wrong order or already-used grant")
            if state["attempts"][grant.attempt_id]["certainty"] != "PREPARED":
                raise AccountSubmissionError("grant no longer prepared")
            if self.account_domain is not None:
                from quant_platform_kit.common.account_domain import (
                    _time, account_domain_key, account_domain_matches_broker_identity,
                    account_domain_policy_active, validate_account_domain,
                )
                domain = validate_account_domain(self.account_domain, platform_id=self.broker)
                now = self.clock()
                now_text = now.isoformat() if isinstance(now, datetime) else now
                observed = state["equity_observation"]
                reservation = state["risk_reservations"].get(digest)
                binding = {"domain_key": account_domain_key(domain), "account_type": domain["policy"]["account_type"], "currency": domain["policy"]["currency"]}
                _, account = _submission_account(self.broker, self.observed_account_id)
                is_reduction = state["attempts"][grant.attempt_id].get("reduction") is True
                if (state["domain_binding"] != binding or account != self.account_id
                        or not account_domain_matches_broker_identity(domain, self.broker_identity, observed_environment=self.observed_environment, observed_server=self.observed_server, observed_currency=self.observed_currency, observed_lifecycle_id=self.observed_lifecycle_id)
                        or not account_domain_policy_active(domain, as_of=now_text)
                        or observed is None or (reservation is None and not is_reduction)
                        or (not is_reduction and any(observed[key] != reservation[key] for key in ("valuation_at", "source_digest")))
                        or (is_reduction and (not observed["open_orders_complete"] or not observed["open_orders_empty"]
                            or observed["source_digest"] != state["attempts"][grant.attempt_id]["reduction_source_digest"]))
                        or not _time(observed["valuation_at"]) <= _time(now_text) < _time(observed["valid_until"])):
                    raise AccountSubmissionError("expired or mismatched domain observation")
            self._used.add(grant.attempt_id)
        try:
            report = submit()
        except Exception as exc:
            try:
                self.record_observation(grant, None)
            except Exception as persist_exc:
                exc.add_note("account outcome persistence also failed: " + type(persist_exc).__name__)
                object.__setattr__(self, "_failed", True)
            raise
        if record_observation_watermark:
            try:
                now = self.clock()
                recorded_at = now.isoformat() if isinstance(now, datetime) else now
                from quant_platform_kit.common.account_domain import _time
                _time(recorded_at)
            except Exception:
                recorded_at = None
            if recorded_at is not None:
                self.record_observation(grant, report, recorded_at=recorded_at)
            else:
                self.record_observation(grant, report)
        else:
            self.record_observation(grant, report)
        attempt = self.read_state()["attempts"][grant.attempt_id]
        if attempt["certainty"] == "UNKNOWN" and str(getattr(report, "status", "")).strip() in (
            _SUBMISSION_ACK | _SUBMISSION_PARTIAL | _SUBMISSION_TERMINAL | {"accepted"}
        ):
            raise AccountSubmissionError("broker result facts are uncertain; original attempt retained")
        return report

    def record_observation(self, grant: AccountSubmissionGrant, report, *, recorded_at=None) -> bool:
        """Persist original facts. Exact replay is idempotent, never a new grant."""
        with self._mutex:
            if self._failed:
                raise AccountSubmissionError("session persistence uncertain")
            state = self._owned_grant(grant)
            if grant.attempt_id not in self._used:
                raise AccountSubmissionError("grant not dispatched")
            attempt = state["attempts"][grant.attempt_id]
            prior = attempt["observation"]
            status = str(getattr(report, "status", "") or "").strip()
            order_id = str(getattr(report, "broker_order_id", "") or "").strip() or None
            invalid = False
            try:
                filled = _submission_number(getattr(report, "filled_quantity", None) or 0.0)
                price_value = getattr(report, "average_fill_price", None)
                price = _submission_number(price_value) if price_value is not None else None
                if filled < attempt["filled_quantity"] or filled > attempt["quantity"]:
                    raise AccountSubmissionError("non-monotonic fill")
                if order_id is not None:
                    _submission_text(order_id)
                if prior and prior["broker_order_id"] and order_id != prior["broker_order_id"]:
                    raise AccountSubmissionError("broker order identity changed")
            except AccountSubmissionError:
                invalid = True
                status = "Unknown"
                order_id = prior["broker_order_id"] if prior else None
                filled = attempt["filled_quantity"]
                price = prior["average_fill_price"] if prior else None
            observation = {"status": status, "broker_order_id": order_id,
                           "filled_quantity": filled, "average_fill_price": price}
            observation["certainty"] = self._certainty(observation, attempt["quantity"])
            if prior == observation:
                if invalid:
                    raise AccountSubmissionError("historical/non-monotonic observation rejected")
                return False
            if attempt["certainty"] in {"UNKNOWN", "TERMINAL"}:
                raise AccountSubmissionError("historical UNKNOWN/terminal cannot be changed")
            event_data = {"attempt_id": grant.attempt_id, "observation": observation}
            if recorded_at is not None:
                from quant_platform_kit.common.account_domain import _time
                try:
                    instant = _time(recorded_at)
                    previous_watermark = attempt.get("last_observation_recorded_at")
                    if previous_watermark is None or instant >= _time(previous_watermark):
                        event_data["recorded_at"] = recorded_at
                except (ValueError, TypeError):
                    # Optional metadata must never discard a broker observation.
                    pass
            self._append(state, "OBSERVED", event_data)
            if invalid:
                raise AccountSubmissionError("invalid/non-monotonic broker observation; UNKNOWN persisted")
            return True


def submission_release_digest(receipt: Mapping[str, Any]) -> str:
    """Bind the loaded release identity; observation timestamps are not identity."""
    if (not isinstance(receipt, Mapping) or receipt.get("attestation_state") != "self_attested"
            or not receipt.get("release_id") or not isinstance(receipt.get("strategy_release"), Mapping)
            or not receipt["strategy_release"]):
        raise AccountSubmissionError("attested release binding required for submission")
    return submission_binding_digest({k: v for k, v in receipt.items() if k != "loaded_at"})


def submission_intent_digest(metadata: Mapping[str, Any], profile: str) -> str:
    allocation = metadata.get("allocation")
    if not isinstance(allocation, Mapping) or not allocation:
        raise AccountSubmissionError("approved allocation identity required")
    return submission_binding_digest({
        "profile": _submission_text(profile), "allocation": dict(allocation),
        **{key: metadata.get(key) for key in (
            "trade_date", "signal_date", "effective_date", "snapshot_as_of", "execution_timing_contract",
        )},
    })

