"""Collect daily return data from market-specific snapshot pipeline artifacts."""

from __future__ import annotations

from pathlib import Path
from typing import Mapping, Sequence

import pandas as pd

from quant_platform_kit.strategy_lifecycle.live_equity import (
    group_live_run_records_by_profile,
    live_run_records_to_return_series,
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
            series = frame[column].dropna()
            if not series.empty:
                strategies[col_str] = series
        return strategies

    def _store_instance(self) -> PerformanceStore:
        if self._store is not None:
            return self._store
        return PerformanceStore.from_env()

    def collect_from_live_runs(self, domain: str) -> Mapping[str, pd.Series]:
        """Build per-strategy return series from persisted live run equity snapshots."""
        records = self._store_instance().list_live_run_records(domain)
        grouped = group_live_run_records_by_profile(records)
        return {
            profile: live_run_records_to_return_series(profile_records)
            for profile, profile_records in grouped.items()
            if live_run_records_to_return_series(profile_records).size > 0
        }

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
            combined = pd.concat([merged[profile], series]).sort_index()
            merged[profile] = combined[~combined.index.duplicated(keep="last")]
        return merged

    def collect(
        self,
        domain: str,
        *,
        date_column: str = "as_of",
        benchmark_columns: Sequence[str] | None = None,
    ) -> Mapping[str, pd.Series]:
        """Collect all strategy return series for a domain.

        Returns a mapping of strategy_profile → daily return series.
        If multiple matrices are found (e.g., different portfolios), merges them.
        """
        paths = self.discover_return_matrices(domain)
        all_strategies: dict[str, pd.Series] = {}
        if paths:
            for path in paths:
                try:
                    frame = self.read_return_matrix(path, date_column=date_column)
                except Exception:
                    continue
                strategies = self.extract_strategy_columns(
                    frame, domain=domain, benchmark_columns=benchmark_columns
                )
                for name, series in strategies.items():
                    if name in all_strategies:
                        if len(series) > len(all_strategies[name]):
                            all_strategies[name] = series
                    else:
                        all_strategies[name] = series

        live_series = self.collect_from_live_runs(domain)
        return self._merge_return_series(all_strategies, live_series)

    def collect_benchmark(
        self,
        domain: str,
        benchmark_symbol: str,
        *,
        date_column: str = "as_of",
    ) -> pd.Series | None:
        """Collect the benchmark return series for a domain."""
        paths = self.discover_return_matrices(domain)
        for path in paths:
            try:
                frame = self.read_return_matrix(path, date_column=date_column)
            except Exception:
                continue
            for column in frame.columns:
                if str(column or "").strip() == benchmark_symbol:
                    return frame[column].dropna()
        return None


def resolve_strategy_benchmark(
    strategy_profile: str,
    domain: str,
    *,
    catalog_benchmarks: Mapping[str, str] | None = None,
) -> str:
    """Resolve the benchmark symbol for a strategy.

    Falls back through: catalog metadata → domain defaults.
    """
    if catalog_benchmarks and strategy_profile in catalog_benchmarks:
        return catalog_benchmarks[strategy_profile]

    # Domain defaults
    defaults = {
        "us_equity": "buy_hold_SPY",
        "crypto": "buy_hold_BTC",
        "hk_equity": "buy_hold_2800",
        "cn_equity": "buy_hold_510300",
    }
    return defaults.get(domain, "buy_hold_SPY")
