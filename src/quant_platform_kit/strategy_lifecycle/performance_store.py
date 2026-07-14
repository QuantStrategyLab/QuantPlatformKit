"""Unified persistence layer for strategy lifecycle data.

Follows the same local+cloud pattern as alert_marker.py.
Data is organized under partitioned GCS paths:

    gs://{bucket}/daily/{domain}/{strategy}/{date}.json
    gs://{bucket}/backtest/{domain}/{strategy}/backtest_v{n}_{stamp}.json
    gs://{bucket}/drift/{domain}/{strategy}/drift_{date}.json
    gs://{bucket}/optimization/{domain}/{strategy}/proposal_v{n}_{stamp}.json
    gs://{bucket}/dashboard/aggregated_health.json
    gs://{bucket}/audit/updates/{strategy}/{entry_id}.json
"""

from __future__ import annotations

import json
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from quant_platform_kit.cloud import get_object_store
from quant_platform_kit.strategy_lifecycle.contracts import (
    BacktestResult,
    DriftResult,
    OptimizationProposal,
    StrategyHealthScore,
    StrategyPerformanceSnapshot,
    UpdateLogEntry,
)

SCHEMA_VERSION = "strategy_lifecycle.v1"
DEFAULT_BUCKET_ENV = "LIFECYCLE_PERFORMANCE_BUCKET"
DEFAULT_LOCAL_ROOT = Path(tempfile.gettempdir()) / "quant_platform_lifecycle"
LATEST_EXECUTION_TIMING = object()
LEGACY_EXECUTION_TIMING = object()


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
        stamp = _clean_key(result.computed_at or result.run_id or result.param_set_id or _now_iso()).replace("/", "_")
        timing = "t0_missing" if result.execution_timing is None else f"t1_{str(result.execution_timing).encode().hex()}"
        return (
            f"backtest/{_clean_key(result.domain)}/{_clean_key(result.strategy_profile)}/"
            f"backtest_v{result.param_version}_{timing}_id{result.result_identity_version}_{stamp}.json"
        )

    def save_backtest_result(self, result: BacktestResult) -> None:
        self._write(
            self._backtest_key(result),
            {**result.to_dict(), "schema_version": SCHEMA_VERSION},
        )

    def load_latest_backtest(
        self,
        domain: str,
        strategy_profile: str,
        *,
        execution_timing: str | object = LATEST_EXECUTION_TIMING,
    ) -> BacktestResult | None:
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
        if execution_timing is LEGACY_EXECUTION_TIMING:
            candidates = [item for item in candidates if item[1].execution_timing is None]
        elif execution_timing is not LATEST_EXECUTION_TIMING and execution_timing is not None:
            candidates = [item for item in candidates if item[1].execution_timing == execution_timing]
        if not candidates:
            return None
        baseline_candidates = [item for item in candidates if _is_baseline_backtest(item[1])]
        selected = baseline_candidates or candidates
        selected.sort(key=lambda item: item[0])
        return selected[-1][1]

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

    def _live_run_key(self, domain: str, strategy_profile: str, recorded_at: str) -> str:
        safe_time = recorded_at.replace(":", "-")
        return f"live_runs/{_clean_key(domain)}/{_clean_key(strategy_profile)}/{safe_time}.json"

    def save_live_run_record(
        self,
        strategy_profile: str,
        domain: str,
        payload: Mapping[str, Any],
    ) -> None:
        recorded_at = str(payload.get("recorded_at") or _now_iso())
        self._write(
            self._live_run_key(domain, strategy_profile, recorded_at),
            {**dict(payload), "schema_version": SCHEMA_VERSION},
        )

    def list_live_run_records(
        self,
        domain: str,
        *,
        strategy_profile: str | None = None,
    ) -> list[dict[str, Any]]:
        """Load persisted live evaluation/execution records for a domain."""
        prefix = f"live_runs/{_clean_key(domain)}/"
        if strategy_profile:
            prefix = f"{prefix}{_clean_key(strategy_profile)}/"

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
            dedupe_key = "|".join(
                [
                    str(record.get("strategy_profile") or ""),
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
            )
        return StrategyPerformanceSnapshot(
            strategy_profile=str(data.get("strategy_profile", "")),
            domain=str(data.get("domain", "")),
            platform=str(data.get("platform", "")),
            as_of=date.fromisoformat(str(data["as_of"])) if data.get("as_of") else date.today(),
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
            as_of=date.fromisoformat(str(data["as_of"])) if data.get("as_of") else date.today(),
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
        )
    except Exception:
        return None


def _backtest_from_dict(data: Mapping[str, Any]) -> BacktestResult | None:
    try:
        return BacktestResult(
            strategy_profile=str(data.get("strategy_profile", "")),
            domain=str(data.get("domain", "")),
            param_set_id=str(data.get("param_set_id", "")),
            params=dict(data.get("params", {})),
            param_version=int(data.get("param_version", 1)),
            execution_timing=(str(data["execution_timing"]) if data.get("execution_timing") else None),
            result_identity_version=int(data.get("result_identity_version", 1)),
            persist_mode=str(data.get("persist_mode", "durable")),
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
