"""Derive daily return series from persisted live execution/evaluation records."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
import math
from typing import Any

import pandas as pd

_EQUITY_KEYS = (
    "total_equity",
    "total_equity_usdt",
    "equity",
    "total_strategy_equity",
    "portfolio_equity",
)
_EXTERNAL_CASH_FLOW_KEYS = (
    "net_external_cash_flow",
    "external_cash_flow",
)


def _as_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(parsed) or parsed <= 0:
        return None
    return parsed


def _as_finite_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


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


def extract_external_cash_flow(payload: Mapping[str, Any] | None) -> float | None:
    """Extract a signed external flow used for live performance adjustment.

    Producers should write one of ``net_external_cash_flow`` or
    ``external_cash_flow`` in account currency: deposits are positive and
    withdrawals are negative.  Internal cash sweeps, realized PnL and broker
    cash balances must not be supplied here.  A missing field means zero; a
    present but invalid field returns ``None`` so the affected daily return is
    excluded instead of being misreported.
    """
    if not isinstance(payload, Mapping):
        return None
    candidates: list[Mapping[str, Any]] = [payload]
    execution = _nested_mapping(payload.get("execution_result"))
    if execution is not None:
        candidates.append(execution)
        execution_portfolio = _nested_mapping(execution.get("portfolio"))
        if execution_portfolio is not None:
            candidates.append(execution_portfolio)
    portfolio = _nested_mapping(payload.get("portfolio"))
    if portfolio is not None:
        candidates.append(portfolio)
    for candidate in candidates:
        for key in _EXTERNAL_CASH_FLOW_KEYS:
            if key in candidate:
                return _as_finite_number(candidate.get(key))
    return 0.0


def cash_flow_adjusted_return(
    previous_equity: Any,
    ending_equity: Any,
    *,
    net_external_cash_flow: Any = 0.0,
) -> float | None:
    """Return a period return under an end-of-period external-flow convention.

    This is a daily time-weighted-return-compatible calculation:
    ``(ending_equity - signed_external_flow) / previous_equity - 1``.  It is
    exact when flows occur at the end of the observation period, which is the
    only timing available in persisted daily run records.  ``None`` represents
    insufficient or impossible evidence and is intentionally not coerced to a
    zero return.
    """
    start = _as_float(previous_equity)
    end = _as_float(ending_equity)
    flow = _as_finite_number(net_external_cash_flow)
    if start is None or end is None or flow is None:
        return None
    adjusted_end = end - flow
    if not math.isfinite(adjusted_end) or adjusted_end <= 0.0:
        return None
    result = (adjusted_end / start) - 1.0
    return result if math.isfinite(result) else None


def _parse_recorded_at(value: Any) -> pd.Timestamp | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return pd.Timestamp(text).tz_localize(None).normalize()
    except (TypeError, ValueError):
        return None


def live_run_records_to_return_series(records: Sequence[Mapping[str, Any]]) -> pd.Series:
    """Convert live run records to cash-flow-adjusted daily returns.

    Multiple records from the same day use the final equity observation and
    accumulate their declared external flows.  This prevents a pure deposit or
    withdrawal from becoming a spurious gain or loss in lifecycle monitoring.
    """
    points: list[tuple[pd.Timestamp, float, float]] = []
    invalid_cash_flow_dates: set[pd.Timestamp] = set()
    for record in records:
        if not isinstance(record, Mapping):
            continue
        recorded_at = _parse_recorded_at(record.get("recorded_at"))
        if recorded_at is None:
            continue
        cash_flow = extract_external_cash_flow(record)
        if cash_flow is None:
            invalid_cash_flow_dates.add(recorded_at)
            continue
        equity = extract_equity_value(record)
        if equity is None or recorded_at is None:
            continue
        points.append((recorded_at, equity, cash_flow))

    if len(points) < 2:
        return pd.Series(dtype=float)

    frame = (
        pd.DataFrame(points, columns=["date", "equity", "external_cash_flow"])
        .sort_values("date", kind="stable")
        .groupby("date", sort=True, as_index=False)
        .agg({"equity": "last", "external_cash_flow": "sum"})
    )
    if invalid_cash_flow_dates:
        frame = frame[~frame["date"].isin(invalid_cash_flow_dates)]
    if len(frame) < 2:
        return pd.Series(dtype=float)
    frame = (
        frame
        .sort_values("date", kind="stable")
        .set_index("date")
    )
    return_points: list[tuple[pd.Timestamp, float]] = []
    previous_equity: float | None = None
    for as_of, point in frame.iterrows():
        current_equity = float(point["equity"])
        if previous_equity is not None:
            adjusted_return = cash_flow_adjusted_return(
                previous_equity,
                current_equity,
                net_external_cash_flow=point["external_cash_flow"],
            )
            if adjusted_return is not None:
                return_points.append((as_of, adjusted_return))
        previous_equity = current_equity
    returns = pd.Series(
        (value for _, value in return_points),
        index=pd.Index((as_of for as_of, _ in return_points), name="date"),
        dtype=float,
    )
    returns.name = "live_return"
    return returns.astype(float)


def count_consecutive_losses(returns: pd.Series | Sequence[Any] | None) -> int:
    """Count trailing negative daily returns (zeros / NaN break the streak)."""
    if returns is None:
        return 0
    if isinstance(returns, pd.Series):
        values = [float(value) for value in returns.dropna().tolist()]
    else:
        values = []
        for value in returns:
            try:
                parsed = float(value)
            except (TypeError, ValueError):
                continue
            if parsed != parsed:  # NaN
                continue
            values.append(parsed)
    streak = 0
    for value in reversed(values):
        if value < 0.0:
            streak += 1
            continue
        break
    return streak


def consecutive_losses_from_live_run_records(
    records: Sequence[Mapping[str, Any]],
) -> int:
    """Derive consecutive loss streak from persisted live equity snapshots."""
    return count_consecutive_losses(live_run_records_to_return_series(records))


def resolve_consecutive_losses(
    *,
    domain: str,
    strategy_profile: str,
    store: Any | None = None,
) -> int | None:
    """Load live-run equity history and return trailing consecutive losses.

    Returns ``None`` when history is insufficient (fewer than two equity points).
    """
    profile = str(strategy_profile or "").strip()
    market = str(domain or "").strip()
    if not profile or not market:
        return None

    if store is None:
        from quant_platform_kit.strategy_lifecycle.performance_store import PerformanceStore

        store = PerformanceStore.from_env()

    records = store.list_live_run_records(market, strategy_profile=profile)
    series = live_run_records_to_return_series(records)
    if series.empty:
        return None
    return count_consecutive_losses(series)


def stamp_consecutive_losses_on_snapshot(
    portfolio_snapshot: Any | None,
    *,
    strategy_profile: str,
    domain: str = "",
    store: Any | None = None,
    logger: Any | None = None,
) -> Any | None:
    """Stamp trailing consecutive_losses onto portfolio metadata before evaluate.

    No-op when snapshot is missing, the field is already set, or history is
    insufficient. Never raises — platforms should call this best-effort.
    """
    if portfolio_snapshot is None:
        return None
    metadata = dict(getattr(portfolio_snapshot, "metadata", None) or {})
    if metadata.get("consecutive_losses") is not None:
        return portfolio_snapshot
    try:
        from quant_platform_kit.strategy_lifecycle.performance_monitor import infer_strategy_domain

        streak = resolve_consecutive_losses(
            domain=infer_strategy_domain(strategy_profile, explicit_domain=domain),
            strategy_profile=strategy_profile,
            store=store,
        )
    except Exception as exc:  # pragma: no cover - defensive platform boundary
        if callable(logger):
            logger(
                "strategy_consecutive_losses_resolve_failed | "
                f"profile={strategy_profile} error_type={type(exc).__name__} error={exc}"
            )
        return portfolio_snapshot
    if streak is None:
        return portfolio_snapshot
    metadata["consecutive_losses"] = int(streak)
    try:
        from dataclasses import is_dataclass, replace as dc_replace

        if is_dataclass(portfolio_snapshot) and not isinstance(portfolio_snapshot, type):
            return dc_replace(portfolio_snapshot, metadata=metadata)
    except Exception:
        pass
    if hasattr(portfolio_snapshot, "_replace"):
        return portfolio_snapshot._replace(metadata=metadata)
    # Last resort: mutate if object allows it (tests / SimpleNamespace).
    try:
        object.__setattr__(portfolio_snapshot, "metadata", metadata)
        return portfolio_snapshot
    except Exception:
        return portfolio_snapshot


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
