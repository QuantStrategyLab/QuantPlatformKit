"""Unified persistence layer for strategy lifecycle data.

Follows the same local+cloud pattern as alert_marker.py.
Data is organized under partitioned GCS paths:

    gs://{bucket}/daily/{domain}/{strategy}/{date}.json
    gs://{bucket}/backtest/{domain}/{strategy}/backtest_v{n}_{stamp}.json
    gs://{bucket}/backtest/{domain}/{strategy}/runs/{run_digest}/backtest_v{n}.json
    gs://{bucket}/research_trial/{identity_digest}/started.json
    gs://{bucket}/research_trial/{identity_digest}/terminal.json
    gs://{bucket}/research_trial/{identity_digest}/ledger.json
    gs://{bucket}/drift/{domain}/{strategy}/drift_{date}.json
    gs://{bucket}/optimization/{domain}/{strategy}/proposal_v{n}_{stamp}.json
    gs://{bucket}/dashboard/aggregated_health.json
    gs://{bucket}/audit/updates/{strategy}/{entry_id}.json

Research objects use one digest of the original domain, profile, and trial id.
When cloud_bucket is set, that bucket is the only research authority.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from quant_platform_kit.cloud import get_object_store
from quant_platform_kit.strategy_lifecycle.contracts import (
    BacktestResult,
    BacktestValidationIdentity,
    DriftResult,
    OptimizationProposal,
    ResearchDailyLedger,
    ResearchLedgerDay,
    ResearchPositionMark,
    ResearchTrialRecord,
    ResearchTrialStatus,
    StrategyHealthScore,
    StrategyPerformanceSnapshot,
    UpdateLogEntry,
)

SCHEMA_VERSION = "strategy_lifecycle.v1"
DEFAULT_BUCKET_ENV = "LIFECYCLE_PERFORMANCE_BUCKET"
DEFAULT_LOCAL_ROOT = Path(tempfile.gettempdir()) / "quant_platform_lifecycle"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean_key(value: str) -> str:
    parts = []
    for raw_part in str(value or "").replace("\\", "/").split("/"):
        cleaned = "".join(
            char if char.isalnum() or char in {"-", "_", "."} else "-"
            for char in raw_part.strip()
        ).strip("-._")
        if cleaned:
            parts.append(cleaned[:100])
    return "/".join(parts) or "unknown"


@dataclass(frozen=True)
class PerformanceStore:
    """Read/write strategy lifecycle data to local filesystem and/or cloud storage."""

    cloud_bucket: str = ""
    cloud_prefix: str = ""
    local_root: Path | None = None
    project_id: str | None = None
    client_factory: Any = None

    # ── factory ──────────────────────────────────────────────────

    @classmethod
    def from_env(cls, *, bucket_env: str = DEFAULT_BUCKET_ENV) -> "PerformanceStore":
        import os

        raw_bucket = (os.environ.get(bucket_env) or "").strip()
        cloud_bucket = ""
        cloud_prefix = ""
        if raw_bucket:
            if raw_bucket.startswith("gs://"):
                remainder = raw_bucket[5:]
                cloud_bucket, _, cloud_prefix = remainder.partition("/")
            else:
                cloud_bucket = raw_bucket

        local_root = None
        local_env = os.environ.get("LIFECYCLE_LOCAL_ROOT")
        if local_env:
            local_root = Path(local_env)
        else:
            local_root = DEFAULT_LOCAL_ROOT

        return cls(
            cloud_bucket=cloud_bucket,
            cloud_prefix=cloud_prefix.strip("/"),
            local_root=local_root,
            project_id=os.environ.get("GOOGLE_CLOUD_PROJECT"),
        )

    # ── cloud helpers ────────────────────────────────────────────

    def _object_store(self):
        return get_object_store(project_id=self.project_id)

    def _cloud_path(self, key: str) -> str:
        prefix = self.cloud_prefix
        clean = _clean_key(key)
        return f"{prefix}/{clean}" if prefix else clean

    def _cloud_uri(self, key: str) -> str:
        return f"gs://{self.cloud_bucket}/{self._cloud_path(key)}"

    def _cloud_key(self, uri: str) -> str:
        bucket_prefix = f"gs://{self.cloud_bucket}/"
        path = uri[len(bucket_prefix) :] if uri.startswith(bucket_prefix) else uri
        prefix = self.cloud_prefix.strip("/")
        return path[len(prefix) + 1 :] if prefix and path.startswith(f"{prefix}/") else path

    def _read_cloud_json(self, key: str) -> dict[str, Any] | None:
        if not self.cloud_bucket:
            return None
        try:
            store = self._object_store()
            raw = store.read_bytes(self._cloud_uri(key))
            data = json.loads(raw.decode("utf-8"))
            return data if isinstance(data, Mapping) else None
        except Exception:
            return None

    def _write_cloud_json(self, key: str, payload: Mapping[str, Any]) -> None:
        if not self.cloud_bucket:
            return
        store = self._object_store()
        store.write_bytes(
            self._cloud_uri(key),
            json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"),
        )

    def _list_cloud_keys(self, prefix: str) -> list[str]:
        if not self.cloud_bucket:
            return []
        try:
            store = self._object_store()
            return [self._cloud_key(uri) for uri in store.list(self._cloud_uri(prefix))]
        except Exception:
            return []

    # ── local helpers ────────────────────────────────────────────

    def _local_path(self, key: str) -> Path:
        root = self.local_root or DEFAULT_LOCAL_ROOT
        return root / _clean_key(key)

    def _read_local_json(self, key: str) -> dict[str, Any] | None:
        path = self._local_path(key)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, Mapping) else None
        except Exception:
            return None

    def _write_local_json(self, key: str, payload: Mapping[str, Any]) -> None:
        path = self._local_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # ── generic read/write ───────────────────────────────────────

    def _read(self, key: str) -> dict[str, Any] | None:
        return self._read_local_json(key) or self._read_cloud_json(key)

    def _write(self, key: str, payload: Mapping[str, Any]) -> None:
        self._write_local_json(key, payload)
        self._write_cloud_json(key, payload)

    def _list_local_json_keys(self, prefix: str) -> list[str]:
        base_root = (self.local_root or DEFAULT_LOCAL_ROOT).resolve()
        local_dir = self._local_path(prefix)
        keys: list[str] = []
        if local_dir.exists():
            paths = sorted(local_dir.rglob("*.json"))
        else:
            parent = local_dir.parent
            if not parent.exists():
                return []
            stem = local_dir.name
            paths = sorted(path for path in parent.glob(f"{stem}*.json") if path.is_file())
        for path in paths:
            try:
                keys.append(path.resolve().relative_to(base_root).as_posix())
            except ValueError:
                continue
        return keys

    # ── snapshots ────────────────────────────────────────────────

    def _snapshot_key(self, snapshot: StrategyPerformanceSnapshot) -> str:
        if snapshot.as_of is None:
            raise ValueError("observation_date_unavailable")
        return f"daily/{_clean_key(snapshot.domain)}/{_clean_key(snapshot.strategy_profile)}/{snapshot.as_of.isoformat()}.json"

    def save_snapshot(self, snapshot: StrategyPerformanceSnapshot) -> None:
        self._write(self._snapshot_key(snapshot), {**snapshot.to_dict(), "schema_version": SCHEMA_VERSION})

    def load_snapshot(self, domain: str, strategy_profile: str, as_of: date) -> StrategyPerformanceSnapshot | None:
        key = f"daily/{_clean_key(domain)}/{_clean_key(strategy_profile)}/{as_of.isoformat()}.json"
        data = self._read(key)
        if not data:
            return None
        return _snapshot_from_dict(data)

    def load_latest_snapshot(self, domain: str, strategy_profile: str) -> StrategyPerformanceSnapshot | None:
        prefix = f"daily/{_clean_key(domain)}/{_clean_key(strategy_profile)}/"
        keys = self._list_cloud_keys(prefix)
        if not keys:
            # fall back to local
            keys = self._list_local_json_keys(prefix)
        if not keys:
            return None
        latest_key = sorted(keys)[-1]
        data = self._read(latest_key)
        return _snapshot_from_dict(data) if data else None

    def load_snapshots_batch(
        self, domain: str, strategy_profiles: Sequence[str], as_of: date | None = None
    ) -> Mapping[str, StrategyPerformanceSnapshot]:
        result: dict[str, StrategyPerformanceSnapshot] = {}
        for profile in strategy_profiles:
            if as_of:
                snapshot = self.load_snapshot(domain, profile, as_of)
            else:
                snapshot = self.load_latest_snapshot(domain, profile)
            if snapshot:
                result[profile] = snapshot
        return result

    # ── drift ────────────────────────────────────────────────────

    def _drift_key(self, domain: str, strategy_profile: str, as_of: date) -> str:
        return f"drift/{_clean_key(domain)}/{_clean_key(strategy_profile)}/drift_{as_of.isoformat()}.json"

    def save_drift_result(self, result: DriftResult) -> None:
        if result.as_of is None:
            raise ValueError("observation_date_unavailable")
        self._write(
            self._drift_key(result.domain, result.strategy_profile, result.as_of),
            {**result.to_dict(), "schema_version": SCHEMA_VERSION},
        )

    def load_latest_drift(self, domain: str, strategy_profile: str) -> DriftResult | None:
        prefix = f"drift/{_clean_key(domain)}/{_clean_key(strategy_profile)}/"
        keys = self._list_cloud_keys(prefix)
        if not keys:
            keys = self._list_local_json_keys(prefix)
        if not keys:
            return None
        data = self._read(sorted(keys)[-1])
        return _drift_from_dict(data) if data else None

    # ── backtest ─────────────────────────────────────────────────

    def _backtest_key(self, result: BacktestResult) -> str:
        raw_run_id = result.run_id if isinstance(result.run_id, str) else ""
        directory = f"backtest/{_clean_key(result.domain)}/{_clean_key(result.strategy_profile)}"
        if raw_run_id.strip():
            digest = hashlib.sha256(raw_run_id.encode("utf-8")).hexdigest()
            return f"{directory}/runs/{digest}/backtest_v{result.param_version}.json"
        stamp = _clean_key(result.computed_at or result.run_id or result.param_set_id or _now_iso()).replace("/", "_")
        return f"{directory}/backtest_v{result.param_version}_{stamp}.json"

    def save_backtest_result(self, result: BacktestResult) -> None:
        self._write(
            self._backtest_key(result),
            {**result.to_dict(), "schema_version": SCHEMA_VERSION},
        )

    def load_backtest_by_run_id(
        self,
        domain: str,
        strategy_profile: str,
        run_id: str,
        *,
        param_version: int | None = None,
    ) -> BacktestResult | None:
        raw_run_id = run_id if isinstance(run_id, str) else ""
        if not raw_run_id.strip():
            return None
        prefix = f"backtest/{_clean_key(domain)}/{_clean_key(strategy_profile)}/"
        keys = list(dict.fromkeys([*self._list_cloud_keys(prefix), *self._list_local_json_keys(prefix)]))
        matches = self._exact_backtest_matches(
            keys,
            domain=domain,
            strategy_profile=strategy_profile,
            run_id=raw_run_id,
            param_version=param_version,
        )
        if not matches:
            return None
        matches.sort(key=lambda item: item[0])
        return matches[-1][1]

    def _exact_backtest_matches(
        self,
        keys: list[str],
        *,
        domain: str,
        strategy_profile: str,
        run_id: str,
        param_version: int | None,
    ) -> list[tuple[tuple[str, int, str], BacktestResult]]:
        matches: list[tuple[tuple[str, int, str], BacktestResult]] = []
        for key in keys:
            item = self._exact_backtest_match(
                key,
                domain=domain,
                strategy_profile=strategy_profile,
                run_id=run_id,
                param_version=param_version,
            )
            if item is not None:
                matches.append(item)
        return matches

    def _exact_backtest_match(
        self,
        key: str,
        *,
        domain: str,
        strategy_profile: str,
        run_id: str,
        param_version: int | None,
    ) -> tuple[tuple[str, int, str], BacktestResult] | None:
        data = self._read(key)
        if not isinstance(data, Mapping) or data.get("run_id") != run_id:
            return None
        result = _backtest_from_dict(data)
        if (
            result is None
            or result.run_id != run_id
            or result.domain != domain
            or result.strategy_profile != strategy_profile
        ):
            return None
        if param_version is not None and int(result.param_version) != int(param_version):
            return None
        return (_backtest_sort_key(result, key), result)

    def load_latest_backtest(self, domain: str, strategy_profile: str) -> BacktestResult | None:
        prefix = f"backtest/{_clean_key(domain)}/{_clean_key(strategy_profile)}/"
        keys = list(dict.fromkeys([*self._list_cloud_keys(prefix), *self._list_local_json_keys(prefix)]))
        if not keys:
            return None
        candidates: list[tuple[tuple[str, int, str], BacktestResult]] = []
        for key in keys:
            data = self._read(key)
            result = _backtest_from_dict(data) if data else None
            if result is None:
                continue
            candidates.append((_backtest_sort_key(result, key), result))
        if not candidates:
            return None
        baseline_candidates = [item for item in candidates if _is_baseline_backtest(item[1])]
        selected = baseline_candidates or candidates
        selected.sort(key=lambda item: item[0])
        return selected[-1][1]

    # ── research trials ──────────────────────────────────────────
    # One backend: cloud when cloud_bucket is set, otherwise local exclusive
    # create. A cloud or local readback is not proof of the other backend.

    def _research_key(self, domain: str, strategy_profile: str, trial_id: str, name: str) -> str:
        material = f"{domain}\0{strategy_profile}\0{trial_id}".encode()
        digest = hashlib.sha256(material).hexdigest()
        return f"research_trial/{digest}/{name}.json"

    def save_research_ledger(self, ledger: ResearchDailyLedger) -> None:
        """Create the one ledger for this trial. An existing identical object is kept."""

        if type(ledger) is not ResearchDailyLedger:
            raise ValueError("research_ledger_malformed")
        self._create_same(
            self._research_key(ledger.domain, ledger.strategy_profile, ledger.trial_id, "ledger"),
            _research_payload(ledger),
        )

    def load_research_ledger(
        self,
        domain: str,
        strategy_profile: str,
        trial_id: str,
        run_id: str,
        param_version: int,
    ) -> ResearchDailyLedger | None:
        if type(param_version) is not int or param_version <= 0:
            return None
        ledger = _research_ledger_from_dict(
            self._read_research_json(self._research_key(domain, strategy_profile, trial_id, "ledger"))
        )
        if (
            ledger is None
            or ledger.domain != domain
            or ledger.strategy_profile != strategy_profile
            or ledger.trial_id != trial_id
            or ledger.run_id != run_id
            or ledger.param_version != param_version
        ):
            return None
        return ledger

    def save_research_trial(self, trial: ResearchTrialRecord) -> None:
        """Create started or one terminal. Succeeded is stored only after result and ledger."""

        if type(trial) is not ResearchTrialRecord:
            raise ValueError("research_trial_malformed")
        name = "started" if trial.status is ResearchTrialStatus.STARTED else "terminal"
        other = "terminal" if name == "started" else "started"
        self._require_research_pair(trial, other)
        if trial.status is ResearchTrialStatus.SUCCEEDED:
            problem = self._research_success_problem(trial)
            if problem is not None:
                raise ValueError(problem)
        self._create_same(
            self._research_key(trial.domain, trial.strategy_profile, trial.trial_id, name),
            _research_payload(trial),
        )

    def load_research_trial(
        self,
        domain: str,
        strategy_profile: str,
        trial_id: str,
        *,
        run_id: str | None = None,
        param_version: int | None = None,
    ) -> ResearchTrialRecord | None:
        started_text = self._research_text(self._research_key(domain, strategy_profile, trial_id, "started"))
        terminal_text = self._research_text(self._research_key(domain, strategy_profile, trial_id, "terminal"))
        started = _research_trial_from_dict(_research_object(started_text)) if started_text is not None else None
        terminal = _research_trial_from_dict(_research_object(terminal_text)) if terminal_text is not None else None
        if terminal_text is not None:
            if (
                terminal is None
                or terminal.domain != domain
                or terminal.strategy_profile != strategy_profile
                or terminal.trial_id != trial_id
                or (
                    started_text is not None
                    and (started is None or not _research_trial_continues(started, terminal))
                )
            ):
                return None
            record = terminal
        else:
            record = started
        if record is None or record.domain != domain or record.strategy_profile != strategy_profile or record.trial_id != trial_id:
            return None
        if record.status is ResearchTrialStatus.SUCCEEDED and self._research_success_problem(record) is not None:
            return None
        if run_id is not None and record.run_id != run_id:
            return None
        if param_version is not None and (type(param_version) is not int or record.param_version != param_version):
            return None
        return record

    def _research_success_problem(self, trial: ResearchTrialRecord) -> str | None:
        if not isinstance(trial.run_id, str) or type(trial.param_version) is not int:
            return "research_trial_result_missing"
        result = self._read_saved_backtest(trial.domain, trial.strategy_profile, trial.run_id, trial.param_version)
        if result is None:
            return "research_trial_result_missing"
        ledger = self.load_research_ledger(
            trial.domain, trial.strategy_profile, trial.trial_id, trial.run_id, trial.param_version
        )
        if ledger is None:
            if self._research_text(self._research_key(trial.domain, trial.strategy_profile, trial.trial_id, "ledger")) is None:
                return "research_trial_ledger_missing"
            return "research_trial_result_mismatch"
        if not _research_result_matches(result, trial, ledger):
            return "research_trial_result_mismatch"
        return None

    def _require_research_pair(self, trial: ResearchTrialRecord, other_name: str) -> None:
        text = self._research_text(self._research_key(trial.domain, trial.strategy_profile, trial.trial_id, other_name))
        if text is None:
            return
        other = _research_trial_from_dict(_research_object(text))
        if other is None:
            raise ValueError("research_trial_malformed")
        started, terminal = (trial, other) if other_name == "terminal" else (other, trial)
        if not _research_trial_continues(started, terminal):
            raise ValueError("research_trial_conflict")

    def _read_saved_backtest(self, domain: str, strategy_profile: str, run_id: str, param_version: int) -> BacktestResult | None:
        key = self._backtest_key(
            BacktestResult(
                strategy_profile=strategy_profile,
                domain=domain,
                param_set_id="stored",
                params={},
                run_id=run_id,
                param_version=param_version,
            )
        )
        data = self._read_research_json(key)
        if data is None:
            return None
        return _backtest_from_dict(data)

    def _read_research_json(self, key: str) -> dict[str, Any] | None:
        return _research_object(self._research_text(key))

    def _research_text(self, key: str) -> str | None:
        if self.cloud_bucket:
            store = self._object_store()
            uri = self._cloud_uri(key)
            try:
                present = bool(store.exists(uri))
            except Exception as exc:
                raise ValueError("research_store_unavailable") from exc
            if not present:
                return None
            try:
                return str(store.read_text(uri))
            except Exception as exc:
                raise ValueError("research_store_unavailable") from exc
        path = self._local_path(key)
        if not path.exists():
            return None
        try:
            return path.read_text(encoding="utf-8")
        except OSError as exc:
            raise ValueError("research_store_unavailable") from exc

    def _create_same(self, key: str, payload: Mapping[str, Any]) -> None:
        text = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        if self.cloud_bucket:
            self._cloud_create_same(self._cloud_uri(key), text)
            return
        path = self._local_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            self._require_same_local(path, text)
            return
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())

    def _cloud_create_same(self, uri: str, text: str) -> None:
        store = self._object_store()
        try:
            present = bool(store.exists(uri))
        except Exception as exc:
            raise ValueError("research_store_unavailable") from exc
        if not present:
            try:
                created = bool(store.create_text(uri, text, content_type="application/json"))
            except Exception as exc:
                raise ValueError("research_store_unavailable") from exc
            if created:
                return
        try:
            current = str(store.read_text(uri))
        except Exception as exc:
            raise ValueError("research_store_unavailable") from exc
        _research_same_text(current, text, ledger=uri.endswith("/ledger.json"))

    def _require_same_local(self, path: Path, text: str) -> None:
        try:
            current = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise ValueError("research_store_unavailable") from exc
        _research_same_text(current, text, ledger=path.name == "ledger.json")

    # ── optimization ─────────────────────────────────────────────

    def _proposal_key(self, proposal: OptimizationProposal) -> str:
        version = proposal.proposed_metrics.param_version if proposal.proposed_metrics else 1
        stamp = _clean_key(proposal.computed_at or _now_iso()).replace("/", "_")
        return (
            f"optimization/{_clean_key(proposal.domain)}/{_clean_key(proposal.strategy_profile)}/"
            f"proposal_v{version}_{stamp}.json"
        )

    def save_proposal(self, proposal: OptimizationProposal) -> None:
        self._write(
            self._proposal_key(proposal),
            {**proposal.to_dict(), "schema_version": SCHEMA_VERSION},
        )

    def load_proposal(self, domain: str, strategy_profile: str, version: int) -> OptimizationProposal | None:
        directory_prefix = f"optimization/{_clean_key(domain)}/{_clean_key(strategy_profile)}/"
        proposal_stem = f"proposal_v{version}"
        exact_key = f"{directory_prefix}{proposal_stem}.json"
        stamped_prefix = f"{proposal_stem}_"
        cloud_keys = [key for key in self._list_cloud_keys(directory_prefix) if Path(key).name.startswith(stamped_prefix)]
        local_keys = [key for key in self._list_local_json_keys(directory_prefix) if Path(key).name.startswith(stamped_prefix)]
        keys = list(
            dict.fromkeys(
                [exact_key, *cloud_keys, *local_keys]
            )
        )
        candidates: list[tuple[str, OptimizationProposal]] = []
        for key in keys:
            data = self._read(key)
            proposal = _proposal_from_dict(data) if data else None
            if proposal is not None:
                result_version = proposal.proposed_metrics.param_version if proposal.proposed_metrics else 1
                if int(result_version) != int(version):
                    continue
                candidates.append((str(proposal.computed_at or ""), proposal))
        if not candidates:
            return None
        candidates.sort(key=lambda item: item[0])
        return candidates[-1][1]

    # ── audit ────────────────────────────────────────────────────

    def _audit_key(self, strategy_profile: str, entry_id: str) -> str:
        return f"audit/updates/{_clean_key(strategy_profile)}/{_clean_key(entry_id)}.json"

    def save_audit_entry(self, entry: UpdateLogEntry) -> None:
        self._write(
            self._audit_key(entry.strategy_profile, entry.entry_id),
            {**entry.to_dict(), "schema_version": SCHEMA_VERSION},
        )

    def load_audit_entries(self, strategy_profile: str, limit: int = 20) -> tuple[UpdateLogEntry, ...]:
        prefix = f"audit/updates/{_clean_key(strategy_profile)}/"
        keys = self._list_cloud_keys(prefix)
        if not keys:
            keys = self._list_local_json_keys(prefix)
        entries: list[UpdateLogEntry] = []
        for key in sorted(keys, reverse=True)[:limit]:
            data = self._read(key)
            if data:
                entry = _audit_from_dict(data)
                if entry:
                    entries.append(entry)
        return tuple(entries)

    def list_snapshot_profiles(self, domain: str) -> tuple[str, ...]:
        prefix = f"daily/{_clean_key(domain)}/"
        profiles: set[str] = set()

        local_dir = self._local_path(prefix)
        if local_dir.exists():
            for path in local_dir.iterdir():
                if path.is_dir():
                    profiles.add(path.name)

        for key in self._list_cloud_keys(prefix):
            normalized = str(key).replace("\\", "/")
            cloud_prefix = self.cloud_prefix.strip("/")
            if cloud_prefix and normalized.startswith(f"{cloud_prefix}/"):
                normalized = normalized[len(cloud_prefix) + 1 :]
            if not normalized.startswith(prefix):
                idx = normalized.find(prefix)
                if idx < 0:
                    continue
                normalized = normalized[idx:]
            remainder = normalized[len(prefix) :]
            profile = remainder.split("/", 1)[0].strip()
            if profile:
                profiles.add(profile)
        return tuple(sorted(profiles))

    # ── live runs (per-evaluate / per-execution records) ─────────

    def _live_run_key(
        self,
        domain: str,
        strategy_profile: str,
        recorded_at: str,
        *,
        stream_id: str = "",
    ) -> str:
        safe_time = recorded_at.replace(":", "-")
        root = f"live_runs/{_clean_key(domain)}/{_clean_key(strategy_profile)}"
        stream = str(stream_id or "").strip()
        if stream:
            return f"{root}/streams/{_clean_key(stream)}/{safe_time}.json"
        return f"{root}/{safe_time}.json"

    def save_live_run_record(
        self,
        strategy_profile: str,
        domain: str,
        payload: Mapping[str, Any],
        *,
        stream_id: str = "",
    ) -> None:
        recorded_at = str(payload.get("recorded_at") or _now_iso())
        stream = str(stream_id or payload.get("lifecycle_stream_id") or "").strip()
        stored_payload = dict(payload)
        if stream:
            stored_payload["lifecycle_stream_id"] = stream
        self._write(
            self._live_run_key(domain, strategy_profile, recorded_at, stream_id=stream),
            {**stored_payload, "schema_version": SCHEMA_VERSION},
        )

    def list_live_run_records(
        self,
        domain: str,
        *,
        strategy_profile: str | None = None,
        stream_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Load persisted live evaluation/execution records for a domain."""
        prefix = f"live_runs/{_clean_key(domain)}/"
        if strategy_profile:
            prefix = f"{prefix}{_clean_key(strategy_profile)}/"
        stream = str(stream_id or "").strip()
        if stream:
            if not strategy_profile:
                raise ValueError("strategy_profile is required when filtering live records by stream_id")
            prefix = f"{prefix}streams/{_clean_key(stream)}/"

        records: list[dict[str, Any]] = []

        local_dir = self._local_path(prefix)
        if local_dir.exists():
            for path in sorted(local_dir.rglob("*.json")):
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                except Exception:
                    continue
                if isinstance(data, Mapping):
                    records.append(dict(data))

        if self.cloud_bucket:
            for key in self._list_cloud_keys(prefix):
                data = self._read_cloud_json(key)
                if data:
                    records.append(dict(data))

        deduped: dict[str, dict[str, Any]] = {}
        for record in records:
            if stream and str(record.get("lifecycle_stream_id") or "").strip() != stream:
                continue
            dedupe_key = "|".join(
                [
                    str(record.get("strategy_profile") or ""),
                    str(record.get("lifecycle_stream_id") or ""),
                    str(record.get("recorded_at") or ""),
                    str(record.get("record_kind") or ""),
                ]
            )
            deduped[dedupe_key] = record
        ordered = list(deduped.values())
        ordered.sort(key=lambda item: str(item.get("recorded_at") or ""))
        return ordered

    # ── dashboard ────────────────────────────────────────────────

    def _dashboard_key(self) -> str:
        return "dashboard/aggregated_health.json"

    def save_dashboard(self, scores: Sequence[StrategyHealthScore]) -> None:
        self._write(
            self._dashboard_key(),
            {
                "schema_version": SCHEMA_VERSION,
                "computed_at": _now_iso(),
                "strategies": [s.to_dict() for s in scores],
            },
        )

    def load_dashboard(self) -> dict[str, Any] | None:
        return self._read(self._dashboard_key())


# ── Deserialization helpers ──────────────────────────────────────────


def _observation_date(data: Mapping[str, Any]) -> date | None:
    # Retain otherwise valid risk evidence without inventing a current date.
    try:
        return date.fromisoformat(str(data["as_of"]))
    except (KeyError, TypeError, ValueError):
        return None


def _snapshot_from_dict(data: Mapping[str, Any]) -> StrategyPerformanceSnapshot | None:
    try:
        from quant_platform_kit.strategy_lifecycle.contracts import WindowPerformance

        windows_raw = data.get("windows", {})
        windows: dict[int, WindowPerformance] = {}
        for k, v in (windows_raw or {}).items():
            if not isinstance(v, Mapping):
                continue
            windows[int(k)] = WindowPerformance(
                window_name=str(v.get("window_name", "")),
                window_days=int(v.get("window_days", 0)),
                start_date=date.fromisoformat(str(v.get("start_date", ""))) if v.get("start_date") else date.today(),
                end_date=date.fromisoformat(str(v.get("end_date", ""))) if v.get("end_date") else date.today(),
                observation_count=int(v.get("observation_count", 0)),
                total_return=float(v.get("total_return", 0)),
                cagr=float(v.get("cagr", 0)),
                volatility=float(v.get("volatility", 0)),
                sharpe_ratio=float(v.get("sharpe_ratio", 0)),
                sortino_ratio=float(v.get("sortino_ratio", 0)),
                calmar_ratio=float(v.get("calmar_ratio", 0)),
                max_drawdown=float(v.get("max_drawdown", 0)),
                win_rate=float(v.get("win_rate", 0)),
                profit_factor=v.get("profit_factor"),
                benchmark_symbol=str(v.get("benchmark_symbol", "")),
                benchmark_return=float(v.get("benchmark_return")) if v.get("benchmark_return") is not None else None,
                benchmark_cagr=float(v.get("benchmark_cagr")) if v.get("benchmark_cagr") is not None else None,
                benchmark_max_drawdown=float(v.get("benchmark_max_drawdown")) if v.get("benchmark_max_drawdown") is not None else None,
                excess_cagr=float(v.get("excess_cagr")) if v.get("excess_cagr") is not None else None,
                alpha=float(v.get("alpha")) if v.get("alpha") is not None else None,
                information_ratio=float(v.get("information_ratio")) if v.get("information_ratio") is not None else None,
                calendar_id=str(v.get("calendar_id", "") or ""),
                periods_per_year=float(v["periods_per_year"]) if v.get("periods_per_year") is not None else 252.0,
            )
        return StrategyPerformanceSnapshot(
            strategy_profile=str(data.get("strategy_profile", "")),
            domain=str(data.get("domain", "")),
            platform=str(data.get("platform", "")),
            as_of=_observation_date(data),
            windows=windows,
            latest_return=float(data["latest_return"]) if data.get("latest_return") is not None else None,
            benchmark_symbol=str(data.get("benchmark_symbol", "")),
            drift_score=float(data["drift_score"]) if data.get("drift_score") is not None else None,
            drift_status=str(data.get("drift_status", "")),
            data_freshness_days=int(data.get("data_freshness_days", 0)),
            source_artifact_path=str(data.get("source_artifact_path", "")),
            computed_at=str(data.get("computed_at", "")),
            source_revision=data.get("source_revision") if isinstance(data.get("source_revision"), str) else "",
            cost_model=data.get("cost_model") if isinstance(data.get("cost_model"), str) else "",
            observation_status=str(data.get("observation_status", "") or ""),
        )
    except Exception:
        return None


def _drift_from_dict(data: Mapping[str, Any]) -> DriftResult | None:
    try:
        from quant_platform_kit.strategy_lifecycle.contracts import DriftDimension, DriftStatus

        dimensions_raw = data.get("dimensions", {})
        dimensions: dict[str, DriftDimension] = {}
        for k, v in (dimensions_raw or {}).items():
            if not isinstance(v, Mapping):
                continue
            dimensions[k] = DriftDimension(
                metric_name=str(v.get("metric_name", k)),
                actual=float(v.get("actual", 0)),
                expected=float(v.get("expected", 0)),
                deviation=float(v.get("deviation", 0)),
                deviation_pct=float(v.get("deviation_pct", 0)),
                threshold=float(v.get("threshold", 0)),
                breached=bool(v.get("breached", False)),
            )
        return DriftResult(
            strategy_profile=str(data.get("strategy_profile", "")),
            domain=str(data.get("domain", "")),
            as_of=_observation_date(data),
            source_revision=data.get("source_revision") if isinstance(data.get("source_revision"), str) else "",
            drift_score=float(data.get("drift_score", 0)),
            status=DriftStatus(str(data.get("status", "healthy"))),
            dimensions=dimensions,
            previous_status=DriftStatus(str(data["previous_status"])) if data.get("previous_status") else None,
            baseline_param_set_id=str(data["baseline_param_set_id"]) if data.get("baseline_param_set_id") else None,
            baseline_available=bool(data.get("baseline_available", True)),
            baseline_param_version=(
                int(data["baseline_param_version"])
                if data.get("baseline_param_version") is not None
                else None
            ),
            baseline_artifact_id=(
                str(data["baseline_artifact_id"])
                if data.get("baseline_artifact_id")
                else None
            ),
            reason=str(data.get("reason", "") or ""),
        )
    except Exception:
        return None


def _finite_nonnegative_number(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("cost_inputs")
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise ValueError("cost_inputs")
    return number


def _cost_inputs_from_payload(data: Mapping[str, Any]) -> dict[str, float]:
    if "cost_inputs" not in data:
        return {}
    raw = data["cost_inputs"]
    if not isinstance(raw, Mapping):
        raise ValueError("cost_inputs")
    parsed: dict[str, float] = {}
    for key, value in raw.items():
        if not isinstance(key, str) or not key:
            raise ValueError("cost_inputs")
        parsed[key] = _finite_nonnegative_number(value)
    return parsed


def _stored_text(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("validation_identity")
    return value


def _optional_stored_date(value: object) -> date | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise ValueError("validation_identity")
    return date.fromisoformat(value)


def _required_stored_date(value: object) -> date:
    if not isinstance(value, str) or not value:
        raise ValueError("validation_identity")
    return date.fromisoformat(value)


def _positive_int(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError("validation_identity")
    return value


def _validation_identity_from_payload(data: Mapping[str, Any]) -> BacktestValidationIdentity | None:
    if "validation_identity" not in data or data["validation_identity"] is None:
        return None
    raw = data["validation_identity"]
    if not isinstance(raw, Mapping):
        raise ValueError("validation_identity")
    required = (
        "protocol",
        "fold_id",
        "fold_role",
        "train_start",
        "train_end",
        "test_start",
        "test_end",
        "locked_oos_start",
        "locked_oos_end",
        "purge_days",
        "embargo_days",
    )
    if any(name not in raw for name in required):
        raise ValueError("validation_identity")
    return BacktestValidationIdentity(
        protocol=_stored_text(raw["protocol"]),
        fold_id=_stored_text(raw["fold_id"]),
        fold_role=_stored_text(raw["fold_role"]),
        train_start=_optional_stored_date(raw["train_start"]),
        train_end=_optional_stored_date(raw["train_end"]),
        test_start=_required_stored_date(raw["test_start"]),
        test_end=_required_stored_date(raw["test_end"]),
        locked_oos_start=_required_stored_date(raw["locked_oos_start"]),
        locked_oos_end=_required_stored_date(raw["locked_oos_end"]),
        purge_days=_positive_int(raw["purge_days"]),
        embargo_days=_positive_int(raw["embargo_days"]),
    )


def _backtest_from_dict(data: Mapping[str, Any]) -> BacktestResult | None:
    try:
        return BacktestResult(
            strategy_profile=str(data.get("strategy_profile", "")),
            domain=str(data.get("domain", "")),
            param_set_id=str(data.get("param_set_id", "")),
            params=dict(data.get("params", {})),
            param_version=int(data.get("param_version", 1)),
            sharpe_ratio=float(data["sharpe_ratio"]) if data.get("sharpe_ratio") is not None else None,
            calmar_ratio=float(data["calmar_ratio"]) if data.get("calmar_ratio") is not None else None,
            sortino_ratio=float(data["sortino_ratio"]) if data.get("sortino_ratio") is not None else None,
            max_drawdown=float(data["max_drawdown"]) if data.get("max_drawdown") is not None else None,
            cagr=float(data["cagr"]) if data.get("cagr") is not None else None,
            volatility=float(data["volatility"]) if data.get("volatility") is not None else None,
            win_rate=float(data["win_rate"]) if data.get("win_rate") is not None else None,
            total_return=float(data["total_return"]) if data.get("total_return") is not None else None,
            start_date=date.fromisoformat(str(data["start_date"])) if data.get("start_date") else None,
            end_date=date.fromisoformat(str(data["end_date"])) if data.get("end_date") else None,
            observation_count=int(data.get("observation_count", 0)),
            benchmark_symbol=str(data.get("benchmark_symbol", "")),
            benchmark_cagr=float(data["benchmark_cagr"]) if data.get("benchmark_cagr") is not None else None,
            benchmark_max_drawdown=(
                float(data["benchmark_max_drawdown"]) if data.get("benchmark_max_drawdown") is not None else None
            ),
            excess_cagr=float(data["excess_cagr"]) if data.get("excess_cagr") is not None else None,
            oos_sharpe=float(data["oos_sharpe"]) if data.get("oos_sharpe") is not None else None,
            oos_calmar=float(data["oos_calmar"]) if data.get("oos_calmar") is not None else None,
            oos_max_drawdown=float(data["oos_max_drawdown"]) if data.get("oos_max_drawdown") is not None else None,
            walk_forward_stability=(
                float(data["walk_forward_stability"]) if data.get("walk_forward_stability") is not None else None
            ),
            run_id=str(data.get("run_id", "")),
            run_duration_seconds=float(data.get("run_duration_seconds", 0.0) or 0.0),
            source_script=str(data.get("source_script", "")),
            computed_at=str(data.get("computed_at", "")),
            source_revision=data.get("source_revision") if isinstance(data.get("source_revision"), str) else "",
            cost_model=data.get("cost_model") if isinstance(data.get("cost_model"), str) else "",
            validation_identity=_validation_identity_from_payload(data),
            cost_inputs=_cost_inputs_from_payload(data),
            periods_per_year=(
                float(data["periods_per_year"]) if data.get("periods_per_year") is not None else None
            ),
            calendar_id=str(data.get("calendar_id", "") or ""),
        )
    except Exception:
        return None


def _backtest_sort_key(result: BacktestResult, key: str) -> tuple[str, int, str]:
    computed_at = str(result.computed_at or "")
    return (computed_at, int(result.param_version or 0), str(key))


def _is_baseline_backtest(result: BacktestResult) -> bool:
    marker = str(result.param_set_id or "").strip().lower()
    return "_baseline" in marker or marker.startswith("baseline")


def _proposal_from_dict(data: Mapping[str, Any]) -> OptimizationProposal | None:
    try:
        current_metrics = _backtest_from_dict(data["current_metrics"]) if isinstance(data.get("current_metrics"), Mapping) else None
        proposed_metrics = _backtest_from_dict(data["proposed_metrics"]) if isinstance(data.get("proposed_metrics"), Mapping) else None
        return OptimizationProposal(
            strategy_profile=str(data.get("strategy_profile", "")),
            domain=str(data.get("domain", "")),
            current_params=dict(data.get("current_params", {})),
            current_metrics=current_metrics,
            proposed_params=dict(data.get("proposed_params", {})),
            proposed_metrics=proposed_metrics,
            improvement_score=float(data.get("improvement_score", 0)),
            confidence=float(data.get("confidence", 0)),
            recommendation=str(data.get("recommendation", "")),
            optimization_method=str(data.get("optimization_method", "")),
            computed_at=str(data.get("computed_at", "")),
        )
    except Exception:
        return None


def _audit_from_dict(data: Mapping[str, Any]) -> UpdateLogEntry | None:
    try:
        from quant_platform_kit.strategy_lifecycle.contracts import UpdateStage

        return UpdateLogEntry(
            strategy_profile=str(data.get("strategy_profile", "")),
            domain=str(data.get("domain", "")),
            entry_id=str(data.get("entry_id", "")),
            stage=UpdateStage(str(data.get("stage", "optimized"))),
            timestamp=str(data.get("timestamp", "")),
            operator=str(data.get("operator", "")),
            reason=str(data.get("reason", "")),
        )
    except Exception:
        return None



def _research_payload(record: ResearchTrialRecord | ResearchDailyLedger) -> dict[str, Any]:
    return {"schema_version": SCHEMA_VERSION, **record.to_dict()}


def _research_object(text: str | None) -> dict[str, Any] | None:
    if not text:
        return None
    try:
        data = json.loads(text)
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _research_same_text(current: str, expected: str, *, ledger: bool) -> None:
    if current == expected:
        return
    code = "research_ledger_malformed" if ledger else "research_trial_malformed"
    parsed = (
        _research_ledger_from_dict(_research_object(current))
        if ledger
        else _research_trial_from_dict(_research_object(current))
    )
    if parsed is None:
        raise ValueError(code)
    raise ValueError("research_trial_conflict")


def _research_date(value: object) -> date:
    if not isinstance(value, str) or not value:
        raise ValueError("window")
    parsed = date.fromisoformat(value)
    if parsed.isoformat() != value:
        raise ValueError("window")
    return parsed


_POSITION_FIELDS = frozenset({"symbol", "quantity", "valuation"})
_DAY_FIELDS = frozenset({"session_date", "cash", "positions", "trade_net_cashflow", "fees", "nav", "daily_return"})
_LEDGER_FIELDS = frozenset({
    "schema_version", "trial_id", "domain", "strategy_profile", "run_id", "param_version",
    "input_id", "calendar_id", "periods_per_year", "cost_source", "cost_inputs",
    "initial_session_date", "initial_nav", "initial_cash", "initial_positions", "days", "synthetic",
})
_TRIAL_FIELDS = frozenset({
    "schema_version", "trial_id", "domain", "strategy_profile", "status", "candidate_config_id",
    "actual_params", "param_set_id", "source_revision", "input_id", "window_start", "window_end",
    "calendar_id", "periods_per_year", "cost_source", "cost_inputs", "reason_code", "synthetic",
    "run_id", "param_version",
})


def _research_positions(value: object) -> tuple[ResearchPositionMark, ...]:
    if not isinstance(value, list):
        raise ValueError("position_mark")
    marks: list[ResearchPositionMark] = []
    for item in value:
        if not isinstance(item, dict) or set(item) != _POSITION_FIELDS:
            raise ValueError("position_mark")
        marks.append(ResearchPositionMark(symbol=item["symbol"], quantity=item["quantity"], valuation=item["valuation"]))
    return tuple(marks)


def _research_days(value: object) -> tuple[ResearchLedgerDay, ...]:
    if not isinstance(value, list) or not value:
        raise ValueError("ledger_dates")
    days: list[ResearchLedgerDay] = []
    for item in value:
        if not isinstance(item, dict) or set(item) != _DAY_FIELDS:
            raise ValueError("ledger_dates")
        days.append(ResearchLedgerDay(
            session_date=_research_date(item["session_date"]),
            cash=item["cash"],
            positions=_research_positions(item["positions"]),
            trade_net_cashflow=item["trade_net_cashflow"],
            fees=item["fees"],
            nav=item["nav"],
            daily_return=item["daily_return"],
        ))
    return tuple(days)


def _research_ledger_from_dict(data: Mapping[str, Any] | None) -> ResearchDailyLedger | None:
    if not isinstance(data, dict) or set(data) != _LEDGER_FIELDS or data.get("schema_version") != SCHEMA_VERSION:
        return None
    try:
        return ResearchDailyLedger(
            trial_id=data["trial_id"],
            domain=data["domain"],
            strategy_profile=data["strategy_profile"],
            run_id=data["run_id"],
            param_version=data["param_version"],
            input_id=data["input_id"],
            calendar_id=data["calendar_id"],
            periods_per_year=data["periods_per_year"],
            cost_source=data["cost_source"],
            cost_inputs=data["cost_inputs"],
            initial_session_date=_research_date(data["initial_session_date"]),
            initial_nav=data["initial_nav"],
            initial_cash=data["initial_cash"],
            initial_positions=_research_positions(data["initial_positions"]),
            days=_research_days(data["days"]),
            synthetic=data["synthetic"],
        )
    except Exception:
        return None


def _research_trial_from_dict(data: Mapping[str, Any] | None) -> ResearchTrialRecord | None:
    if not isinstance(data, dict) or set(data) != _TRIAL_FIELDS or data.get("schema_version") != SCHEMA_VERSION:
        return None
    try:
        return ResearchTrialRecord(
            trial_id=data["trial_id"],
            domain=data["domain"],
            strategy_profile=data["strategy_profile"],
            status=data["status"],
            candidate_config_id=data["candidate_config_id"],
            actual_params=data["actual_params"],
            param_set_id=data["param_set_id"],
            source_revision=data["source_revision"],
            input_id=data["input_id"],
            window_start=_research_date(data["window_start"]),
            window_end=_research_date(data["window_end"]),
            calendar_id=data["calendar_id"],
            periods_per_year=data["periods_per_year"],
            cost_source=data["cost_source"],
            cost_inputs=data["cost_inputs"],
            reason_code=data["reason_code"],
            synthetic=data["synthetic"],
            run_id=data["run_id"],
            param_version=data["param_version"],
        )
    except Exception:
        return None


def _research_trial_continues(started: ResearchTrialRecord, terminal: ResearchTrialRecord) -> bool:
    if started.status is not ResearchTrialStatus.STARTED or terminal.status is ResearchTrialStatus.STARTED:
        return False
    if (
        started.trial_id != terminal.trial_id
        or started.domain != terminal.domain
        or started.strategy_profile != terminal.strategy_profile
        or started.candidate_config_id != terminal.candidate_config_id
        or started.input_id != terminal.input_id
        or started.window_start != terminal.window_start
        or started.window_end != terminal.window_end
        or started.calendar_id != terminal.calendar_id
        or started.periods_per_year != terminal.periods_per_year
        or started.synthetic is not terminal.synthetic
    ):
        return False
    if started.actual_params is not None and started.actual_params != terminal.actual_params:
        return False
    if started.param_set_id is not None and started.param_set_id != terminal.param_set_id:
        return False
    if started.source_revision is not None and started.source_revision != terminal.source_revision:
        return False
    if started.cost_source is not None and started.cost_source != terminal.cost_source:
        return False
    if started.cost_inputs and dict(started.cost_inputs) != dict(terminal.cost_inputs):
        return False
    return True


def _research_result_matches(result: BacktestResult, trial: ResearchTrialRecord, ledger: ResearchDailyLedger) -> bool:
    if trial.actual_params is None or not trial.param_set_id or not trial.source_revision:
        return False
    return (
        dict(result.params) == dict(trial.actual_params)
        and result.param_set_id == trial.param_set_id
        and result.source_revision == trial.source_revision
        and result.run_id == trial.run_id
        and result.param_version == trial.param_version
        and result.domain == trial.domain
        and result.strategy_profile == trial.strategy_profile
        and result.start_date == trial.window_start
        and result.end_date == trial.window_end
        and result.calendar_id == trial.calendar_id
        and result.periods_per_year == trial.periods_per_year
        and result.cost_model == trial.cost_source
        and dict(result.cost_inputs) == dict(trial.cost_inputs)
        and result.observation_count == ledger.observation_count
        and result.total_return == ledger.total_return
        and ledger.trial_id == trial.trial_id
        and ledger.run_id == trial.run_id
        and ledger.param_version == trial.param_version
        and ledger.domain == trial.domain
        and ledger.strategy_profile == trial.strategy_profile
        and ledger.input_id == trial.input_id
        and ledger.calendar_id == trial.calendar_id
        and ledger.periods_per_year == trial.periods_per_year
        and ledger.cost_source == trial.cost_source
        and dict(ledger.cost_inputs) == dict(trial.cost_inputs)
        and ledger.window_start == trial.window_start
        and ledger.window_end == trial.window_end
        and ledger.synthetic is trial.synthetic
    )
