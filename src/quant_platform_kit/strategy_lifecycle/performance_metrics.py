"""Rolling performance metric calculations.

Reuses the mathematical patterns from live_strategy_health.py and live_decay_monitor.py,
packaged as standalone functions for the strategy lifecycle system.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Sequence

import numpy as np
import pandas as pd

from quant_platform_kit.strategy_lifecycle.contracts import (
    WindowPerformance,
    validate_periods_per_year,
)

# Standard rolling windows (in trading days)
DEFAULT_WINDOWS: tuple[int, ...] = (21, 63, 126, 252, 756)
DEFAULT_RISK_FREE_RATE: float = 0.0
# Default equity-session annualization basis. Crypto natural-day callers must
# pass periods_per_year=365.25 explicitly (see ReturnObservationContract).
TRADING_DAYS_PER_YEAR: float = 252.0
CRYPTO_DAYS_PER_YEAR: float = 365.25


def _strip_leading_warmup_nans(series: pd.Series) -> pd.Series:
    """Drop only leading NaN warm-up rows; never fill gaps with zeros."""
    values = series.to_numpy(dtype=float, copy=False)
    first = 0
    while first < len(values) and np.isnan(values[first]):
        first += 1
    return series.iloc[first:]


def _validate_ordinary_compounding_returns(series: pd.Series) -> pd.Series:
    """Reject incomplete / non-compoundable ordinary equity returns."""
    values = series.to_numpy(dtype=float, copy=False)
    if series.isna().any() or not np.isfinite(values).all():
        raise ValueError("daily returns contain NaN or infinite values")
    if (series < -1.0).any():
        raise ValueError("daily returns below -100% are invalid")
    if (series == -1.0).any():
        raise ValueError("daily return of -100% is terminal bankruptcy")
    return series


def normalize_return_series(series: pd.Series) -> pd.Series:
    """Clean daily returns; reject repeated dates rather than compound twice.

    Leading warm-up NaNs are dropped. Mid-series gaps, inf, illegal/duplicate
    dates, r<-1, and r=-1 (terminal bankruptcy) are explicit errors — never
    zero-filled into an ordinary compounding path.
    """
    s = pd.Series(series).copy()
    if not pd.api.types.is_datetime64_any_dtype(s.index):
        coerced = pd.to_datetime(s.index, errors="coerce")
        if coerced.isna().any():
            raise ValueError("daily return dates are invalid")
        s.index = coerced
    else:
        s.index = pd.DatetimeIndex(s.index)
    s.index = s.index.tz_localize(None).normalize()
    if s.index.isna().any():
        raise ValueError("daily return dates are invalid")
    if s.index.has_duplicates:
        raise ValueError("daily return dates must be unique")
    s = pd.to_numeric(s, errors="coerce")
    s = _strip_leading_warmup_nans(s.sort_index())
    return _validate_ordinary_compounding_returns(s)


def normalize_return_matrix(
    frame: pd.DataFrame,
    *,
    date_column: str = "as_of",
) -> pd.DataFrame:
    """Normalize a daily return matrix, rejecting repeated normalized dates.

    Shared all-NaN leading rows and per-strategy leading warm-up NaNs are
    allowed (staggered starts). After a column's first observation, NaN/inf,
    r<-1, and r=-1 are errors — never zero-filled.
    """
    df = pd.DataFrame(frame).copy()
    if date_column in df.columns:
        parsed = pd.to_datetime(df[date_column], errors="coerce")
        if parsed.isna().any():
            raise ValueError("daily return dates are invalid")
        df[date_column] = parsed.dt.tz_localize(None).dt.normalize()
        df = df.set_index(date_column)
    else:
        parsed = pd.to_datetime(df.index, errors="coerce")
        if parsed.isna().any():
            raise ValueError("daily return dates are invalid")
        df.index = parsed.tz_localize(None).normalize()
    if df.index.has_duplicates:
        raise ValueError("daily return dates must be unique")
    df = df.sort_index()
    for col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    # Shared leading all-NaN rows are warm-up.
    while len(df) and bool(df.iloc[0].isna().all()):
        df = df.iloc[1:]
    # Per-column leading NaNs are also warm-up; validate only after each start.
    for col in df.columns:
        _validate_ordinary_compounding_returns(_strip_leading_warmup_nans(df[col]))
    return df


def compute_window_metrics(
    returns: pd.Series,
    *,
    benchmark_returns: pd.Series | None = None,
    benchmark_symbol: str = "",
    risk_free_rate: float = DEFAULT_RISK_FREE_RATE,
    window_days: int | None = None,
    window_label: str = "",
    periods_per_year: float = TRADING_DAYS_PER_YEAR,
    calendar_id: str = "",
) -> WindowPerformance:
    """Compute all performance metrics for a return series.

    Returns are daily decimals; risk_free_rate is annual, converted to daily
    MAR by dividing by ``periods_per_year`` (default 252 for equity sessions).
    Sortino uses full-sample RMS shortfall from that MAR and the same
    excess-return numerator as Sharpe; both are annualized. Drawdowns include
    initial equity of 1 without adding an observation.

    Benchmark comparisons use only common dates, including both CAGR legs.
    Jensen's alpha remains daily; beta uses matching population covariance
    and variance and is not identifiable for a constant benchmark (alpha=None).
    Information ratio is annualized aligned active mean / population std.
    Zero ratio denominators remain NaN; absent comparisons remain None.
    """
    annualization_base = validate_periods_per_year(periods_per_year)
    resolved_calendar_id = str(calendar_id or "").strip()
    series = normalize_return_series(returns)
    if window_days and len(series) > window_days:
        series = series.iloc[-window_days:]
    actual_days = len(series)

    if series.empty:
        return _empty_window(
            window_label,
            window_days or 0,
            benchmark_symbol,
            calendar_id=resolved_calendar_id,
            periods_per_year=annualization_base,
        )

    equity = (1.0 + series).cumprod()
    years = max(actual_days / annualization_base, 1.0 / annualization_base)

    total_return = float(equity.iloc[-1] - 1.0)
    cagr = float(equity.iloc[-1] ** (1.0 / years) - 1.0)

    drawdown = equity / equity.cummax().clip(lower=1.0) - 1.0
    max_drawdown = float(drawdown.min())

    vol_daily = float(series.std(ddof=0)) if series.nunique() > 1 else 0.0
    volatility = float(vol_daily * np.sqrt(annualization_base))

    daily_risk_free = risk_free_rate / annualization_base
    excess = series.mean() - daily_risk_free
    sharpe = float(excess / vol_daily * np.sqrt(annualization_base)) if vol_daily else float("nan")

    downside = (series - daily_risk_free).clip(upper=0.0)
    downside_deviation = float(np.sqrt((downside ** 2).mean()))
    sortino = float(excess / downside_deviation * np.sqrt(annualization_base)) if downside_deviation else float("nan")

    calmar = float(cagr / abs(max_drawdown)) if max_drawdown < 0.0 else float("nan")

    # Win rate
    wins = int((series > 0).sum())
    total = len(series)
    win_rate = wins / total if total > 0 else 0.0

    # Profit factor
    gross_profit = float(series.loc[series > 0].sum()) if wins > 0 else 0.0
    gross_loss = abs(float(series.loc[series < 0].sum())) if total - wins > 0 else 0.0
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else None

    # Benchmark comparison
    benchmark_return = None
    benchmark_cagr = None
    benchmark_max_dd = None
    excess_cagr = None
    alpha = None
    ir = None
    if benchmark_returns is not None:
        bench = normalize_return_series(benchmark_returns)
        aligned = pd.concat([series, bench], axis=1, join="inner").dropna()
        if not aligned.empty:
            strategy_aligned = aligned.iloc[:, 0]
            bench_aligned = aligned.iloc[:, 1]
            bench_equity = (1.0 + bench_aligned).cumprod()
            bench_years = max(len(bench_aligned) / annualization_base, 1.0 / annualization_base)
            benchmark_return = float(bench_equity.iloc[-1] - 1.0)
            benchmark_cagr = float(bench_equity.iloc[-1] ** (1.0 / bench_years) - 1.0)
            bench_dd = bench_equity / bench_equity.cummax().clip(lower=1.0) - 1.0
            benchmark_max_dd = float(bench_dd.min())
            aligned_cagr = float((1.0 + strategy_aligned).prod() ** (1.0 / bench_years) - 1.0)
            excess_cagr = aligned_cagr - benchmark_cagr
            bench_variance = float(bench_aligned.var(ddof=0))
            # Exact constants can have tiny nonzero variance from roundoff.
            if bench_aligned.nunique() > 1 and bench_variance > 0.0:
                beta = float(np.cov(strategy_aligned, bench_aligned, ddof=0)[0, 1] / bench_variance)
                alpha = float((strategy_aligned.mean() - daily_risk_free) - beta * (bench_aligned.mean() - daily_risk_free))
            # Information ratio
            active_returns = strategy_aligned - bench_aligned
            tracking_error = float(active_returns.std(ddof=0)) if active_returns.nunique() > 1 else 0.0
            ir = float(active_returns.mean() / tracking_error * np.sqrt(annualization_base)) if tracking_error else float("nan")

    return WindowPerformance(
        window_name=window_label or f"{actual_days}d",
        window_days=window_days or actual_days,
        start_date=date.fromisoformat(str(series.index[0].date())),
        end_date=date.fromisoformat(str(series.index[-1].date())),
        observation_count=actual_days,
        total_return=total_return,
        cagr=cagr,
        volatility=volatility,
        sharpe_ratio=sharpe,
        sortino_ratio=sortino,
        calmar_ratio=calmar,
        max_drawdown=max_drawdown,
        win_rate=win_rate,
        profit_factor=profit_factor,
        benchmark_symbol=benchmark_symbol,
        benchmark_return=benchmark_return,
        benchmark_cagr=benchmark_cagr,
        benchmark_max_drawdown=benchmark_max_dd,
        excess_cagr=excess_cagr,
        alpha=alpha,
        information_ratio=ir,
        calendar_id=resolved_calendar_id,
        periods_per_year=annualization_base,
    )


def compute_windows(
    returns: pd.Series,
    *,
    benchmark_returns: pd.Series | None = None,
    benchmark_symbol: str = "",
    windows: Sequence[int] = DEFAULT_WINDOWS,
    periods_per_year: float = TRADING_DAYS_PER_YEAR,
    calendar_id: str = "",
) -> dict[int, WindowPerformance]:
    """Compute metrics for multiple rolling windows."""
    series = normalize_return_series(returns)
    result: dict[int, WindowPerformance] = {}
    for w in windows:
        label = _window_label(w)
        sliced = series if w >= len(series) else series.iloc[-w:]
        result[w] = compute_window_metrics(
            sliced,
            benchmark_returns=benchmark_returns,
            benchmark_symbol=benchmark_symbol,
            window_days=w,
            window_label=label,
            periods_per_year=periods_per_year,
            calendar_id=calendar_id,
        )
    return result


def compare_with_backtest(
    actual: WindowPerformance,
    backtest: "BacktestResult | None",
) -> dict[str, float]:
    """Compute deviation between actual window performance and backtest expectations.

    Returns an empty mapping when the baseline lacks an explicit annualization
    basis or the basis disagrees with ``actual.periods_per_year``. Callers must
    treat that as not-comparable rather than zero drift.
    """
    if backtest is None:
        return {}
    if backtest.periods_per_year is None:
        return {}
    if float(backtest.periods_per_year) != float(actual.periods_per_year):
        return {}
    diffs: dict[str, float] = {}
    if backtest.sharpe_ratio is not None and not np.isnan(actual.sharpe_ratio):
        diffs["sharpe_deviation"] = abs(actual.sharpe_ratio - backtest.sharpe_ratio)
    if backtest.cagr is not None and not np.isnan(actual.cagr):
        diffs["cagr_deviation_pct"] = abs(actual.cagr - backtest.cagr) / max(abs(backtest.cagr), 0.001)
    if backtest.max_drawdown is not None and not np.isnan(actual.max_drawdown):
        backtest_dd = abs(backtest.max_drawdown)
        actual_dd = abs(actual.max_drawdown)
        diffs["drawdown_ratio"] = actual_dd / max(backtest_dd, 0.001)
    if backtest.volatility is not None and not np.isnan(actual.volatility):
        diffs["volatility_deviation_pct"] = abs(actual.volatility - backtest.volatility) / max(backtest.volatility, 0.001)
    if backtest.win_rate is not None and not np.isnan(actual.win_rate):
        diffs["win_rate_deviation_pct"] = abs(actual.win_rate - backtest.win_rate) / max(backtest.win_rate, 0.001)
    return diffs


def annualization_basis_is_comparable(
    actual: WindowPerformance,
    backtest: "BacktestResult | None",
) -> bool:
    """True only when baseline declares the same periods_per_year as actual."""
    if backtest is None or backtest.periods_per_year is None:
        return False
    return float(backtest.periods_per_year) == float(actual.periods_per_year)


# ── helpers ─────────────────────────────────────────────────────────


def _window_label(days: int) -> str:
    if days <= 21:
        return "trailing_1m"
    if days <= 63:
        return "trailing_3m"
    if days <= 126:
        return "trailing_6m"
    if days <= 252:
        return "trailing_1y"
    return "trailing_3y"


def _empty_window(
    label: str,
    window_days: int,
    benchmark: str,
    *,
    calendar_id: str = "",
    periods_per_year: float = TRADING_DAYS_PER_YEAR,
) -> WindowPerformance:
    return WindowPerformance(
        window_name=label or "empty",
        window_days=window_days,
        start_date=date.today() - timedelta(days=window_days),
        end_date=date.today(),
        observation_count=0,
        total_return=float("nan"),
        cagr=float("nan"),
        volatility=float("nan"),
        sharpe_ratio=float("nan"),
        sortino_ratio=float("nan"),
        calmar_ratio=float("nan"),
        max_drawdown=float("nan"),
        win_rate=float("nan"),
        benchmark_symbol=benchmark,
        calendar_id=calendar_id,
        periods_per_year=periods_per_year,
    )
