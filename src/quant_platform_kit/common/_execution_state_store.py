"""Durable execution marker store (local filesystem and cloud object store)."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
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
    _first_non_empty,
    _is_successful_no_action_report,
    _month_segment,
    _optional_str,
    _parse_cloud_uri,
    _report_effective_date_keys,
    _report_matches_execution,
    _report_signal_date_keys,
    _report_signal_snapshot,
    _runtime_report_segment,
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
        from . import execution_state

        return execution_state._get_object_store(project_id=self.project_id)

    def _gcs_client(self):
        """Deprecated: use _object_store() instead."""
        return self._object_store()
