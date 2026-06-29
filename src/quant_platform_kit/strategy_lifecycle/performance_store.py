"""Unified persistence layer for strategy lifecycle data.

Follows the same local+cloud pattern as alert_marker.py.
Data is organized under partitioned GCS paths:

    gs://{bucket}/daily/{domain}/{strategy}/{date}.json
    gs://{bucket}/backtest/{domain}/{strategy}/backtest_v{n}.json
    gs://{bucket}/drift/{domain}/{strategy}/drift_{date}.json
    gs://{bucket}/optimization/{domain}/{strategy}/proposal_v{n}.json
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
DEFAULT_LOCAL_ROOT = Path(tempfile.gettempdir()) / "quant_strategy_lifecycle"


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

    def _read_cloud_json(self, key: str) -> dict[str, Any] | None:
        if not self.cloud_bucket:
            return None
        try:
            store = self._object_store()
            path = self._cloud_path(key)
            raw = store.read_bytes(self.cloud_bucket, path)
            data = json.loads(raw.decode("utf-8"))
            return data if isinstance(data, Mapping) else None
        except Exception:
            return None

    def _write_cloud_json(self, key: str, payload: Mapping[str, Any]) -> None:
        if not self.cloud_bucket:
            return
        store = self._object_store()
        path = self._cloud_path(key)
        store.write_bytes(self.cloud_bucket, path, json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"))

    def _list_cloud_keys(self, prefix: str) -> list[str]:
        if not self.cloud_bucket:
            return []
        try:
            store = self._object_store()
            return store.list_keys(self.cloud_bucket, self._cloud_path(prefix))
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
            local_dir = self._local_path(prefix)
            if local_dir.exists():
                keys = sorted(f.name for f in local_dir.glob("*.json"))
            else:
                return None
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
            return None
        data = self._read(sorted(keys)[-1])
        return _drift_from_dict(data) if data else None

    # ── backtest ─────────────────────────────────────────────────

    def _backtest_key(self, domain: str, strategy_profile: str, version: int) -> str:
        return f"backtest/{_clean_key(domain)}/{_clean_key(strategy_profile)}/backtest_v{version}.json"

    def save_backtest_result(self, result: BacktestResult) -> None:
        self._write(
            self._backtest_key(result.domain, result.strategy_profile, result.param_version),
            {**result.to_dict(), "schema_version": SCHEMA_VERSION},
        )

    def load_latest_backtest(self, domain: str, strategy_profile: str) -> BacktestResult | None:
        prefix = f"backtest/{_clean_key(domain)}/{_clean_key(strategy_profile)}/"
        keys = self._list_cloud_keys(prefix)
        if not keys:
            return None
        data = self._read(sorted(keys)[-1])
        return _backtest_from_dict(data) if data else None

    # ── optimization ─────────────────────────────────────────────

    def _proposal_key(self, domain: str, strategy_profile: str, version: int) -> str:
        return f"optimization/{_clean_key(domain)}/{_clean_key(strategy_profile)}/proposal_v{version}.json"

    def save_proposal(self, proposal: OptimizationProposal) -> None:
        version = (proposal.proposed_metrics.param_version if proposal.proposed_metrics else 1)
        self._write(
            self._proposal_key(proposal.domain, proposal.strategy_profile, version),
            {**proposal.to_dict(), "schema_version": SCHEMA_VERSION},
        )

    def load_proposal(self, domain: str, strategy_profile: str, version: int) -> OptimizationProposal | None:
        key = self._proposal_key(domain, strategy_profile, version)
        data = self._read(key)
        return _proposal_from_dict(data) if data else None

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
        entries: list[UpdateLogEntry] = []
        for key in sorted(keys, reverse=True)[:limit]:
            data = self._read(key)
            if data:
                entry = _audit_from_dict(data)
                if entry:
                    entries.append(entry)
        return tuple(entries)

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
            sharpe_ratio=float(data["sharpe_ratio"]) if data.get("sharpe_ratio") is not None else None,
            calmar_ratio=float(data["calmar_ratio"]) if data.get("calmar_ratio") is not None else None,
            max_drawdown=float(data["max_drawdown"]) if data.get("max_drawdown") is not None else None,
            cagr=float(data["cagr"]) if data.get("cagr") is not None else None,
            volatility=float(data["volatility"]) if data.get("volatility") is not None else None,
            win_rate=float(data["win_rate"]) if data.get("win_rate") is not None else None,
            start_date=date.fromisoformat(str(data["start_date"])) if data.get("start_date") else None,
            end_date=date.fromisoformat(str(data["end_date"])) if data.get("end_date") else None,
            observation_count=int(data.get("observation_count", 0)),
            benchmark_symbol=str(data.get("benchmark_symbol", "")),
        )
    except Exception:
        return None


def _proposal_from_dict(data: Mapping[str, Any]) -> OptimizationProposal | None:
    try:
        return OptimizationProposal(
            strategy_profile=str(data.get("strategy_profile", "")),
            domain=str(data.get("domain", "")),
            current_params=dict(data.get("current_params", {})),
            proposed_params=dict(data.get("proposed_params", {})),
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
