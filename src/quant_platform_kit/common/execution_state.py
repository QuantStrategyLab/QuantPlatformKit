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
        for namespace in (self.namespace, self.outcome_namespace):
            entries = self._recent_ledger_entries(
                namespace=namespace,
                relative_prefix=relative_prefix,
                record_limit=normalized_limit,
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
        return hashlib.sha256(payload.encode("utf-8")).hexdigest(), len(records)

    def _recent_ledger_entries(
        self,
        *,
        namespace: str,
        relative_prefix: str,
        record_limit: int,
    ) -> list[tuple[str, str]]:
        if self.cloud_prefix_uri:
            object_store = self._object_store()
            prefix_uri = self._cloud_prefix_for_namespace(relative_prefix, namespace)
            uris = sorted(str(uri) for uri in object_store.list(prefix_uri))
            selected_uris = uris[-record_limit:]
            return [(uri, object_store.read_text(uri)) for uri in selected_uris]
        if self.local_dir:
            root = Path(self.local_dir).expanduser() / namespace / _clean_relative_key(relative_prefix)
            paths = sorted(path for path in root.rglob("*.json") if path.is_file())
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
) -> ExecutionMarkerStore:
    prefix = str(platform_env_prefix or "").strip().upper()
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
    local_dir = env_reader(f"{prefix}_EXECUTION_STATE_DIR", None)
    return ExecutionMarkerStore(
        local_dir=local_dir or default_local_dir or DEFAULT_EXECUTION_STATE_DIR,
        cloud_prefix_uri=explicit_cloud_uri or report_cloud_uri,
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
                 owner_id: str, profile: str, intent_id: str, release_id: str):
        if not isinstance(store, ExecutionMarkerStore) or not (store.cloud_prefix_uri or store.local_dir):
            raise AccountSubmissionError("existing durable execution store required")
        broker, account = _submission_account(broker, account_id)
        values = {
            "store": store, "broker": broker, "account_id": account,
            "owner_id": _submission_text(owner_id), "profile": _submission_text(profile),
            "intent_id": _submission_digest(intent_id), "release_id": _submission_digest(release_id),
            "account_root": "v1/" + submission_binding_digest({"broker": broker, "account_id": account}),
            "_issued": {}, "_used": set(), "_mutex": threading.RLock(), "_failed": False,
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
        if status in _SUBMISSION_ACK:
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
        state: dict[str, Any] = {"generation": 0, "head_sha256": "0" * 64, "attempts": {}}
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
            if event["kind"] == "PREPARED":
                keys = {"attempt_id", "fence", "intent_id", "order_sha256", "release_id", "owner_id", "profile", "quantity"}
                if set(data) != keys:
                    raise AccountSubmissionError("invalid prepared fields")
                for key in ["attempt_id", "fence", "intent_id", "order_sha256", "release_id"]:
                    _submission_digest(data[key])
                for key in ["owner_id", "profile"]:
                    _submission_text(data[key])
                quantity = _submission_number(data["quantity"])
                if quantity <= 0 or any(a["certainty"] in {"PREPARED", "UNKNOWN"} for a in state["attempts"].values()):
                    raise AccountSubmissionError("prepared event bypasses unresolved account")
                if data["attempt_id"] in state["attempts"] or any(
                    (a["intent_id"], a["order_sha256"]) == (data["intent_id"], data["order_sha256"])
                    for a in state["attempts"].values()
                ):
                    raise AccountSubmissionError("duplicate submission identity")
                state["attempts"][data["attempt_id"]] = {
                    **data, "generation": sequence, "event_sha256": event["event_sha256"],
                    "certainty": "PREPARED", "observation": None, "filled_quantity": 0.0,
                }
            elif event["kind"] == "OBSERVED":
                if set(data) != {"attempt_id", "observation"} or data["attempt_id"] not in state["attempts"]:
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
                attempt.update(certainty=certainty, observation=observation, filled_quantity=filled)
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

    def reserve(self, order) -> AccountSubmissionGrant:
        """Only a fresh acknowledged create can return a grant; never reclaim it."""
        with self._mutex:
            if self._failed:
                raise AccountSubmissionError("session persistence uncertain; no grant")
            digest, quantity = self._order(order)
            state = self.read_state()
            if any(a["certainty"] in {"PREPARED", "UNKNOWN"} for a in state["attempts"].values()):
                raise AccountSubmissionError("unresolved UNKNOWN/account submission")
            if any((a["intent_id"], a["order_sha256"]) == (self.intent_id, digest) for a in state["attempts"].values()):
                raise AccountSubmissionError("same intent/order already reserved; no retry grant")
            data = {
                "attempt_id": uuid.uuid4().hex + uuid.uuid4().hex,
                "fence": uuid.uuid4().hex + uuid.uuid4().hex,
                "intent_id": self.intent_id, "order_sha256": digest, "release_id": self.release_id,
                "owner_id": self.owner_id, "profile": self.profile, "quantity": quantity,
            }
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
        return state

    def dispatch(self, grant: AccountSubmissionGrant, order, submit: Callable[[], Any]):
        """Consume exactly once at the final platform submit wrapper, then observe."""
        with self._mutex:
            if self._failed:
                raise AccountSubmissionError("session persistence uncertain")
            state = self._owned_grant(grant)
            digest, _ = self._order(order)
            if digest != grant.order_sha256 or grant.attempt_id in self._used:
                raise AccountSubmissionError("wrong order or already-used grant")
            if state["attempts"][grant.attempt_id]["certainty"] != "PREPARED":
                raise AccountSubmissionError("grant no longer prepared")
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
        self.record_observation(grant, report)
        attempt = self.read_state()["attempts"][grant.attempt_id]
        if attempt["certainty"] == "UNKNOWN" and str(getattr(report, "status", "")).strip() in (
            _SUBMISSION_ACK | _SUBMISSION_PARTIAL | _SUBMISSION_TERMINAL
        ):
            raise AccountSubmissionError("broker result facts are uncertain; original attempt retained")
        return report

    def record_observation(self, grant: AccountSubmissionGrant, report) -> bool:
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
            self._append(state, "OBSERVED", {"attempt_id": grant.attempt_id, "observation": observation})
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
