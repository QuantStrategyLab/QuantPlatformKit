"""Derive daily return series from persisted live execution/evaluation records."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any

import pandas as pd

_EQUITY_KEYS = (
    "total_equity",
    "total_equity_usdt",
    "equity",
    "total_strategy_equity",
    "portfolio_equity",
)


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if parsed <= 0:
        return None
    return parsed


def _nested_mapping(value: Any) -> Mapping[str, Any] | None:
    return value if isinstance(value, Mapping) else None


def extract_equity_value(payload: Mapping[str, Any] | None) -> float | None:
    """Best-effort equity extraction from a live run or execution payload."""
    if not isinstance(payload, Mapping):
        return None

    for key in _EQUITY_KEYS:
        parsed = _as_float(payload.get(key))
        if parsed is not None:
            return parsed

    execution = _nested_mapping(payload.get("execution_result"))
    if execution is not None:
        for key in _EQUITY_KEYS:
            parsed = _as_float(execution.get(key))
            if parsed is not None:
                return parsed
        portfolio = _nested_mapping(execution.get("portfolio"))
        if portfolio is not None:
            for key in _EQUITY_KEYS:
                parsed = _as_float(portfolio.get(key))
                if parsed is not None:
                    return parsed

    portfolio = _nested_mapping(payload.get("portfolio"))
    if portfolio is not None:
        for key in _EQUITY_KEYS:
            parsed = _as_float(portfolio.get(key))
            if parsed is not None:
                return parsed
    return None


def _parse_recorded_at(value: Any) -> pd.Timestamp | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return pd.Timestamp(text).tz_localize(None).normalize()
    except (TypeError, ValueError):
        return None


def live_run_records_to_return_series(records: Sequence[Mapping[str, Any]]) -> pd.Series:
    """Convert ordered live run records with equity snapshots into daily returns."""
    points: list[tuple[pd.Timestamp, float]] = []
    for record in records:
        if not isinstance(record, Mapping):
            continue
        equity = extract_equity_value(record)
        recorded_at = _parse_recorded_at(record.get("recorded_at"))
        if equity is None or recorded_at is None:
            continue
        points.append((recorded_at, equity))

    if len(points) < 2:
        return pd.Series(dtype=float)

    frame = (
        pd.DataFrame(points, columns=["date", "equity"])
        .drop_duplicates(subset=["date"], keep="last")
        .sort_values("date")
        .set_index("date")
    )
    returns = frame["equity"].pct_change().dropna()
    returns.name = "live_return"
    return returns.astype(float)


def group_live_run_records_by_profile(
    records: Sequence[Mapping[str, Any]],
) -> dict[str, list[Mapping[str, Any]]]:
    grouped: dict[str, list[Mapping[str, Any]]] = {}
    for record in records:
        if not isinstance(record, Mapping):
            continue
        profile = str(record.get("strategy_profile") or "").strip()
        if not profile:
            continue
        grouped.setdefault(profile, []).append(record)
    return grouped
