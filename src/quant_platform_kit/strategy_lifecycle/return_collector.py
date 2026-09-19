"""Collect daily return data from market-specific snapshot pipeline artifacts."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Mapping, Sequence

import pandas as pd

from quant_platform_kit.strategy_lifecycle.contracts import (
    LiveReturnCollectionResult,
    ReturnObservationContract,
    merge_return_observation_contract,
    resolve_return_observation_contract,
)
from quant_platform_kit.strategy_lifecycle.live_equity import (
    group_live_run_records_by_profile,
    live_run_records_to_return_series_result,
)
from quant_platform_kit.strategy_lifecycle.performance_metrics import normalize_return_matrix
from quant_platform_kit.strategy_lifecycle.performance_store import PerformanceStore

# Per-market default artifact directories — override via env vars.
_DEFAULT_ARTIFACT_ROOTS: Mapping[str, str] = {
    "us_equity": "UsEquitySnapshotPipelines/data/output",
    "crypto": "CryptoLivePoolPipelines/data/output",
    "hk_equity": "HkEquitySnapshotPipelines/data/output",
    "cn_equity": "CnEquitySnapshotPipelines/data/output",
}

_RETURN_MATRIX_FILENAME = "portfolio_and_tracker_returns.csv"


class MissingStrategyBenchmarkError(ValueError):
    """Raised when strict monitoring has no explicit benchmark binding."""


class ReturnCollector:
    """Discover and read return matrices from market pipeline artifact directories.

    Usage::

        collector = ReturnCollector()
        returns_map = collector.collect(domain="us_equity")
        for strategy, series in returns_map.items():
            ...
    """

    def __init__(
        self,
        *,
        artifact_roots: Mapping[str, str | Path] | None = None,
        projects_root: Path | None = None,
        store: PerformanceStore | None = None,
    ):
        import os

        self._projects_root = projects_root or Path(os.environ.get("QUANT_PROJECTS_ROOT", str(Path.cwd())))
        self._store = store
        roots: dict[str, Path] = {}
        merged = dict(_DEFAULT_ARTIFACT_ROOTS)
        if artifact_roots:
            merged.update({k: str(v) for k, v in artifact_roots.items()})
        for domain, rel in merged.items():
            path = self._projects_root / rel
            if path.exists():
                roots[domain] = path
        self._artifact_roots = roots

    def discover_return_matrices(self, domain: str) -> list[Path]:
        """Find all return matrix CSV files for a domain."""
        root = self._artifact_roots.get(domain)
        if root is None:
            return []
        ignored = {"monthly_report_bundle", "monthly_review_inputs_health", "__pycache__"}
        paths: list[Path] = []
        for path in sorted(root.rglob(_RETURN_MATRIX_FILENAME)):
            if any(part in ignored or part.startswith("live_strategy_health") for part in path.parts):
                continue
            paths.append(path)
        return paths

    def read_return_matrix(self, path: str | Path, *, date_column: str = "as_of") -> pd.DataFrame:
        """Read and normalize a single return matrix CSV."""
        return normalize_return_matrix(pd.read_csv(str(path)), date_column=date_column)

    def extract_strategy_columns(
        self,
        frame: pd.DataFrame,
        *,
        domain: str,
        benchmark_columns: Sequence[str] | None = None,
    ) -> Mapping[str, pd.Series]:
        """Extract per-strategy return series from a return matrix.

        Excludes benchmark and buy-hold columns; keeps only strategy returns.
        """
        ignored = {"as_of", "date"}
        if benchmark_columns:
            ignored.update(benchmark_columns)
        # Also filter out buy-and-hold columns
        strategies: dict[str, pd.Series] = {}
        for column in frame.columns:
            col_str = str(column or "").strip()
            if not col_str or col_str in ignored or col_str.startswith("buy_hold_"):
                continue
            # Keep mid-series gaps for normalize/metrics to reject; only drop
            # all-null columns. Never fill zeros to beautify incomplete series.
            series = pd.to_numeric(frame[column], errors="coerce")
            if series.notna().any():
                strategies[col_str] = series
        return strategies

    def _store_instance(self) -> PerformanceStore:
        if self._store is not None:
            return self._store
        return PerformanceStore.from_env()

    def collect_from_live_runs_result(
        self,
        domain: str,
        *,
        stream_id: str | None = None,
        observation_contract: ReturnObservationContract | None = None,
        session_holidays: frozenset[str] | Sequence[str] | None = None,
        holiday_source: str | None = None,
        holiday_coverage_start: date | None = None,
        holiday_coverage_end: date | None = None,
    ) -> LiveReturnCollectionResult:
        """Collect live returns and report incomplete calendars/gaps explicitly.

        Callers that need XNYS/XHKG holiday semantics must supply a non-synthetic
        ``holiday_source`` plus inclusive coverage bounds (and the holiday dates).
        Synthetic sources are never treated as real exchange evidence.
        """
        base = observation_contract or resolve_return_observation_contract(domain)
        holidays: frozenset[str] | None = None
        if session_holidays is not None:
            holidays = frozenset(str(day).strip() for day in session_holidays if str(day).strip())
        contract = merge_return_observation_contract(
            base,
            session_holidays=holidays,
            holiday_source=holiday_source,
            holiday_coverage_start=holiday_coverage_start,
            holiday_coverage_end=holiday_coverage_end,
        )
        records = self._store_instance().list_live_run_records(domain)
        grouped = group_live_run_records_by_profile(records)
        series_by_profile: dict[str, pd.Series] = {}
        incomplete_by_profile: dict[str, str] = {}
        requested_stream = str(stream_id or "").strip()
        for profile, profile_records in grouped.items():
            streams = {
                str(record.get("lifecycle_stream_id") or "").strip()
                for record in profile_records
            }
            if requested_stream:
                if requested_stream not in streams:
                    continue
                profile_records = [
                    record
                    for record in profile_records
                    if str(record.get("lifecycle_stream_id") or "").strip() == requested_stream
                ]
            elif len(streams) > 1:
                continue
            derived = live_run_records_to_return_series_result(
                profile_records,
                observation_contract=contract,
            )
            if derived.status == "ok" and not derived.series.empty:
                series_by_profile[profile] = derived.series
                continue
            if derived.status == "truncated_after_observation_gap" and not derived.series.empty:
                # Explicit truncation: usable latest segment, not silent full success.
                series_by_profile[profile] = derived.series
                incomplete_by_profile[profile] = (
                    f"{derived.status}:{derived.detail or 'latest_contiguous_segment'}"
                )
                continue
            incomplete_by_profile[profile] = (
                f"{derived.status}:{derived.detail}" if derived.detail else derived.status
            )
        return LiveReturnCollectionResult(
            series_by_profile=series_by_profile,
            incomplete_by_profile=incomplete_by_profile,
        )

    def collect_from_live_runs(
        self,
        domain: str,
        *,
        stream_id: str | None = None,
        observation_contract: ReturnObservationContract | None = None,
        session_holidays: frozenset[str] | Sequence[str] | None = None,
        holiday_source: str | None = None,
        holiday_coverage_start: date | None = None,
        holiday_coverage_end: date | None = None,
    ) -> Mapping[str, pd.Series]:
        """Build per-strategy returns without merging independent account streams.

        A caller that needs live monitoring must supply a specific stream when
        more than one stream has reported the same strategy profile.  Skipping
        that ambiguous profile is safer than deriving a false equity curve
        from separate broker accounts.

        Incomplete calendars are omitted from the returned mapping; use
        ``collect_from_live_runs_result`` to inspect ``incomplete_by_profile``.
        """
        return self.collect_from_live_runs_result(
            domain,
            stream_id=stream_id,
            observation_contract=observation_contract,
            session_holidays=session_holidays,
            holiday_source=holiday_source,
            holiday_coverage_start=holiday_coverage_start,
            holiday_coverage_end=holiday_coverage_end,
        ).series_by_profile

    def _merge_return_series(
        self,
        existing: Mapping[str, pd.Series],
        incoming: Mapping[str, pd.Series],
    ) -> dict[str, pd.Series]:
        merged = dict(existing)
        for profile, series in incoming.items():
            if profile not in merged or merged[profile].empty:
                merged[profile] = series
                continue
            if series.empty:
                continue
            # Prefer the observation_status already attached to the higher-priority
            # (CSV/research) series when both sources contribute.
            preferred_status = str(
                getattr(merged[profile], "attrs", {}).get("observation_status")
                or getattr(series, "attrs", {}).get("observation_status")
                or "ok"
            )
            combined = pd.concat([merged[profile], series]).sort_index()
            combined = combined[~combined.index.duplicated(keep="last")]
            combined.attrs["observation_status"] = preferred_status
            merged[profile] = combined
        return merged

    def collect(
        self,
        domain: str,
        *,
        date_column: str = "as_of",
        benchmark_columns: Sequence[str] | None = None,
        live_stream_id: str | None = None,
        observation_contract: ReturnObservationContract | None = None,
        session_holidays: frozenset[str] | Sequence[str] | None = None,
        holiday_source: str | None = None,
        holiday_coverage_start: date | None = None,
        holiday_coverage_end: date | None = None,
    ) -> Mapping[str, pd.Series]:
        """Collect all strategy return series for a domain.

        Returns a mapping of strategy_profile → daily return series.
        If multiple matrices are found (e.g., different portfolios), merges them.
        Series may carry ``attrs["observation_status"]`` for live completeness.
        """
        paths = self.discover_return_matrices(domain)
        all_strategies: dict[str, pd.Series] = {}
        if paths:
            for path in paths:
                try:
                    frame = self.read_return_matrix(path, date_column=date_column)
                except Exception as exc:
                    raise ValueError(f"invalid return matrix at {path}: {exc}") from exc
                strategies = self.extract_strategy_columns(
                    frame, domain=domain, benchmark_columns=benchmark_columns
                )
                for name, series in strategies.items():
                    stamped = series.copy()
                    stamped.attrs["observation_status"] = "ok"
                    if name in all_strategies:
                        if len(stamped) > len(all_strategies[name]):
                            all_strategies[name] = stamped
                    else:
                        all_strategies[name] = stamped

        live_kwargs = {
            "observation_contract": observation_contract,
            "session_holidays": session_holidays,
            "holiday_source": holiday_source,
            "holiday_coverage_start": holiday_coverage_start,
            "holiday_coverage_end": holiday_coverage_end,
        }
        if live_stream_id:
            live_outcome = self.collect_from_live_runs_result(
                domain, stream_id=live_stream_id, **live_kwargs
            )
        else:
            live_outcome = self.collect_from_live_runs_result(domain, **live_kwargs)

        live_series: dict[str, pd.Series] = {}
        for profile, series in live_outcome.series_by_profile.items():
            stamped = series.copy()
            reason = str(live_outcome.incomplete_by_profile.get(profile) or "")
            if reason.startswith("truncated_after_observation_gap"):
                stamped.attrs["observation_status"] = "truncated_after_observation_gap"
            else:
                stamped.attrs["observation_status"] = "ok"
            live_series[profile] = stamped
        return self._merge_return_series(all_strategies, live_series)

    def collect_benchmark(
        self,
        domain: str,
        benchmark_symbol: str,
        *,
        date_column: str = "as_of",
    ) -> pd.Series | None:
        """Collect the benchmark return series for a domain.

        Normalizes every discovered matrix before returning so an earlier match
        cannot hide a later invalid file. Returns None when the symbol is absent.
        """
        paths = self.discover_return_matrices(domain)
        matched: pd.Series | None = None
        for path in paths:
            try:
                frame = self.read_return_matrix(path, date_column=date_column)
            except Exception as exc:
                raise ValueError(f"invalid return matrix at {path}: {exc}") from exc
            if matched is None:
                for column in frame.columns:
                    if str(column or "").strip() == benchmark_symbol:
                        matched = frame[column].dropna()
                        break
        return matched


def resolve_strategy_benchmark(
    strategy_profile: str,
    domain: str,
    *,
    catalog_benchmarks: Mapping[str, str] | None = None,
    require_explicit: bool = False,
) -> str:
    """Resolve the benchmark symbol for a strategy.

    In normal compatibility mode this falls back through catalog metadata then
    domain defaults. Strict mode is intended for promotion-grade or leveraged
    monitoring: every profile must have a catalog binding, preventing a silent
    and potentially inappropriate fallback to SPY.
    """
    profile = str(strategy_profile or "").strip()
    if catalog_benchmarks and profile in catalog_benchmarks:
        benchmark = str(catalog_benchmarks[profile] or "").strip()
        if benchmark:
            return benchmark
        raise MissingStrategyBenchmarkError(
            f"explicit benchmark for strategy_profile={profile!r} is blank"
        )
    if require_explicit:
        raise MissingStrategyBenchmarkError(
            f"no explicit benchmark binding for strategy_profile={profile!r}; "
            "provide a validated strategy benchmark catalog"
        )

    # Domain defaults
    defaults = {
        "us_equity": "buy_hold_SPY",
        "crypto": "buy_hold_BTC",
        "hk_equity": "buy_hold_2800",
        "cn_equity": "buy_hold_510300",
    }
    return defaults.get(domain, "buy_hold_SPY")
