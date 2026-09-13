"""Derive daily return series from persisted live execution/evaluation records."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
import math
import re
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
_EXTERNAL_CASH_FLOW_INTERVAL_KEY = "external_cash_flow_interval"
_INTERVAL_RECORD_PAYLOAD_KEY = "_interval_record_payload"
_EXTERNAL_CASH_FLOW_INTERVAL_FIELDS = frozenset(
    {
        "account_scope_sha256",
        "start_at",
        "end_at",
        "end_equity_usdt",
        "net_external_cash_flow",
        "currency",
        "valuation_basis",
    }
)
_EXTERNAL_CASH_FLOW_INTERVAL_BASIS = "checkpoint_quantities_sampled_prices"
_SHA256_RE = re.compile(r"[0-9a-f]{64}")


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


def _parse_interval_timestamp(value: Any) -> pd.Timestamp | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = pd.Timestamp(text)
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.tz_convert("UTC")


def _normalize_external_cash_flow_interval(
    value: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    if not isinstance(value, Mapping) or set(value) != _EXTERNAL_CASH_FLOW_INTERVAL_FIELDS:
        return None
    scope = str(value.get("account_scope_sha256") or "").strip()
    if not _SHA256_RE.fullmatch(scope):
        return None
    start_at = _parse_interval_timestamp(value.get("start_at"))
    end_at = _parse_interval_timestamp(value.get("end_at"))
    if start_at is None or end_at is None or start_at >= end_at:
        return None
    if end_at.date() - start_at.date() > pd.Timedelta(days=1):
        return None
    equity = _as_float(value.get("end_equity_usdt"))
    flow = _as_finite_number(value.get("net_external_cash_flow"))
    if equity is None or flow is None:
        return None
    if value.get("currency") != "USDT":
        return None
    if value.get("valuation_basis") != _EXTERNAL_CASH_FLOW_INTERVAL_BASIS:
        return None
    return {
        "account_scope_sha256": scope,
        "start_at": start_at,
        "end_at": end_at,
        "end_equity_usdt": equity,
        "net_external_cash_flow": flow,
        "currency": "USDT",
        "valuation_basis": _EXTERNAL_CASH_FLOW_INTERVAL_BASIS,
    }


def _interval_logical_id(interval: Mapping[str, Any]) -> tuple[str, int, int]:
    return (
        str(interval["account_scope_sha256"]),
        int(interval["start_at"].value),
        int(interval["end_at"].value),
    )


def _intervals_are_contiguous(previous: Mapping[str, Any], current: Mapping[str, Any]) -> bool:
    return (
        previous["account_scope_sha256"] == current["account_scope_sha256"]
        and previous["currency"] == current["currency"]
        and previous["valuation_basis"] == current["valuation_basis"]
        and current["start_at"] == previous["end_at"]
    )


def _interval_record_bad_day(value: Any, recorded_at: Any) -> pd.Timestamp | None:
    if recorded_at:
        parsed_recorded_at = _parse_interval_timestamp(recorded_at)
        if parsed_recorded_at is not None:
            return parsed_recorded_at.normalize().tz_localize(None)
    candidates = []
    if isinstance(value, Mapping):
        for key in ("start_at", "end_at"):
            parsed = _parse_interval_timestamp(value.get(key))
            if parsed is not None:
                candidates.append(parsed)
    if not candidates:
        return None
    return max(candidates).normalize().tz_localize(None)


def live_interval_records_to_return_series(
    records: Sequence[Mapping[str, Any]],
) -> pd.Series:
    """Derive observation-interval returns under the end-flow convention.

    This is not exact TWR and does not represent a midnight-natural-day return.
    The current Binance producer supports USDT deposits only; signed negative
    flows remain a contract/test case and do not enable withdrawal handling.
    """
    by_id: dict[tuple[str, int, int], dict[str, Any]] = {}
    conflicting_ids: set[tuple[str, int, int]] = set()
    scopes: set[str] = set()
    invalid_days: set[pd.Timestamp] = set()
    invalid_unlocated = False
    for record in records:
        if isinstance(record, Mapping) and _INTERVAL_RECORD_PAYLOAD_KEY in record:
            raw_interval = record.get(_INTERVAL_RECORD_PAYLOAD_KEY)
            recorded_at = record.get("recorded_at")
        else:
            raw_interval = record
            recorded_at = None
        interval = _normalize_external_cash_flow_interval(raw_interval)
        if interval is None:
            bad_day = _interval_record_bad_day(raw_interval, recorded_at)
            if bad_day is None:
                invalid_unlocated = True
            else:
                invalid_days.add(bad_day)
            continue
        scopes.add(interval["account_scope_sha256"])
        logical_id = _interval_logical_id(interval)
        previous = by_id.get(logical_id)
        if previous is not None and previous != interval:
            conflicting_ids.add(logical_id)
            invalid_days.add(interval["end_at"].normalize().tz_localize(None))
            continue
        by_id[logical_id] = interval
    if len(scopes) != 1 or invalid_unlocated:
        return pd.Series(dtype=float)

    by_end: dict[tuple[str, int], set[int]] = {}
    for logical_id, interval in by_id.items():
        by_end.setdefault((logical_id[0], logical_id[2]), set()).add(logical_id[1])
    for (scope, end_ns), starts in by_end.items():
        if len(starts) > 1:
            invalid_days.add(pd.Timestamp(end_ns, tz="UTC").normalize().tz_localize(None))
            conflicting_ids.update(
                logical_id
                for logical_id in by_id
                if logical_id[0] == scope and logical_id[2] == end_ns
            )

    intervals = [interval for logical_id, interval in by_id.items() if logical_id not in conflicting_ids]
    if invalid_days:
        cutoff_day = max(invalid_days)
        intervals = [
            interval
            for interval in intervals
            if interval["end_at"].normalize().tz_localize(None) > cutoff_day
        ]
    intervals.sort(key=lambda item: (item["end_at"], item["start_at"]))
    if not intervals:
        return pd.Series(dtype=float)

    components: list[list[dict[str, Any]]] = []
    current_component: list[dict[str, Any]] = []
    for interval in intervals:
        if not current_component or _intervals_are_contiguous(current_component[-1], interval):
            current_component.append(interval)
        else:
            components.append(current_component)
            current_component = [interval]
    components.append(current_component)

    latest_component = components[-1]
    daily: dict[pd.Timestamp, dict[str, float]] = {}
    for interval in latest_component:
        day = interval["end_at"].normalize().tz_localize(None)
        point = daily.setdefault(day, {"equity": 0.0, "flow": 0.0})
        if interval["end_at"] >= point.get("end_at", pd.Timestamp.min.tz_localize("UTC")):
            point["equity"] = interval["end_equity_usdt"]
            point["end_at"] = interval["end_at"]
        point["flow"] += interval["net_external_cash_flow"]
    ordered_days = sorted(daily)
    if len(ordered_days) < 2:
        return pd.Series(dtype=float)

    segments: list[list[pd.Timestamp]] = []
    segment = [ordered_days[0]]
    for day in ordered_days[1:]:
        if day - segment[-1] != pd.Timedelta(days=1):
            segments.append(segment)
            segment = [day]
        else:
            segment.append(day)
    segments.append(segment)
    latest_days = segments[-1]
    if len(latest_days) < 2:
        return pd.Series(dtype=float)

    return_points: list[tuple[pd.Timestamp, float]] = []
    for previous_day, current_day in zip(latest_days, latest_days[1:]):
        adjusted = cash_flow_adjusted_return(
            daily[previous_day]["equity"],
            daily[current_day]["equity"],
            net_external_cash_flow=daily[current_day]["flow"],
        )
        if adjusted is None:
            return pd.Series(dtype=float)
        return_points.append((current_day, adjusted))
    result = pd.Series(
        [value for _, value in return_points],
        index=pd.Index([day for day, _ in return_points], name="date"),
        dtype=float,
        name="live_return",
    )
    return result


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
    If a declared flow is invalid, only the latest comparable segment after
    that date is returned because a plain Series cannot preserve segment
    boundaries for downstream compounding.
    """
    has_interval_records = False
    for record in records:
        if not isinstance(record, Mapping):
            continue
        candidates = [record]
        execution = _nested_mapping(record.get("execution_result"))
        if execution is not None:
            candidates.append(execution)
        for candidate in candidates:
            if _EXTERNAL_CASH_FLOW_INTERVAL_KEY in candidate:
                has_interval_records = True
                break
    if has_interval_records:
        interval_records: list[Mapping[str, Any]] = []
        for record in records:
            if not isinstance(record, Mapping):
                interval_records.append(
                    {
                        _INTERVAL_RECORD_PAYLOAD_KEY: None,
                        "recorded_at": None,
                    }
                )
                continue
            candidates = [record]
            execution = _nested_mapping(record.get("execution_result"))
            if execution is not None:
                candidates.append(execution)
            interval_candidate = None
            has_interval_key = False
            for candidate in candidates:
                if _EXTERNAL_CASH_FLOW_INTERVAL_KEY in candidate:
                    has_interval_key = True
                    interval_candidate = candidate.get(_EXTERNAL_CASH_FLOW_INTERVAL_KEY)
                    break
            interval_records.append(
                {
                    _INTERVAL_RECORD_PAYLOAD_KEY: interval_candidate
                    if has_interval_key
                    else None,
                    "recorded_at": record.get("recorded_at"),
                }
            )
        return live_interval_records_to_return_series(interval_records)

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
        # A plain return series cannot preserve separate comparable segments.
        # Keep only the latest segment so downstream metrics cannot compound
        # valid returns from opposite sides of an unknown cash-flow interval.
        frame = frame[frame["date"] > max(invalid_cash_flow_dates)]
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
