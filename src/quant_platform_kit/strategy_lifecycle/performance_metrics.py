"""Rolling performance metric calculations.

Reuses the mathematical patterns from live_strategy_health.py and live_decay_monitor.py,
packaged as standalone functions for the strategy lifecycle system.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Sequence

import numpy as np
import pandas as pd

from quant_platform_kit.strategy_lifecycle.contracts import WindowPerformance

# Standard rolling windows (in trading days)
DEFAULT_WINDOWS: tuple[int, ...] = (21, 63, 126, 252, 756)
DEFAULT_RISK_FREE_RATE: float = 0.0
TRADING_DAYS_PER_YEAR: float = 252.0


def normalize_return_series(series: pd.Series) -> pd.Series:
    """Clean and normalize a daily return series."""
    s = pd.Series(series).copy()
    if not pd.api.types.is_datetime64_any_dtype(s.index):
        s.index = pd.to_datetime(s.index, errors="coerce")
    s.index = s.index.tz_localize(None).normalize()
    s = pd.to_numeric(s, errors="coerce")
    return s.loc[s.index.notna()].dropna().sort_index()


def normalize_return_matrix(
    frame: pd.DataFrame,
    *,
    date_column: str = "as_of",
) -> pd.DataFrame:
    """Normalize a return matrix: datetime index, numeric values."""
    df = pd.DataFrame(frame).copy()
    if date_column in df.columns:
        df[date_column] = pd.to_datetime(df[date_column], errors="coerce").dt.tz_localize(None).dt.normalize()
        df = df.dropna(subset=[date_column]).set_index(date_column)
    else:
        df.index = pd.to_datetime(df.index, errors="coerce").tz_localize(None).normalize()
        df = df.loc[df.index.notna()]
    for col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.sort_index()


def compute_window_metrics(
    returns: pd.Series,
    *,
    benchmark_returns: pd.Series | None = None,
    benchmark_symbol: str = "",
    risk_free_rate: float = DEFAULT_RISK_FREE_RATE,
    window_days: int | None = None,
    window_label: str = "",
) -> WindowPerformance:
    """Compute all performance metrics for a return series.

    If benchmark_returns is provided, excess/beta/alpha/IR are also computed.
    """
    series = normalize_return_series(returns)
    if window_days and len(series) > window_days:
        series = series.iloc[-window_days:]
    actual_days = len(series)

    if series.empty:
        return _empty_window(window_label, window_days or 0, benchmark_symbol)

    equity = (1.0 + series).cumprod()
    years = max(actual_days / TRADING_DAYS_PER_YEAR, 1.0 / TRADING_DAYS_PER_YEAR)

    total_return = float(equity.iloc[-1] - 1.0)
    cagr = float(equity.iloc[-1] ** (1.0 / years) - 1.0)

    drawdown = equity / equity.cummax() - 1.0
    max_drawdown = float(drawdown.min())

    vol_daily = float(series.std(ddof=0))
    volatility = float(vol_daily * np.sqrt(TRADING_DAYS_PER_YEAR))

    excess = series.mean() - risk_free_rate / TRADING_DAYS_PER_YEAR
    sharpe = float(excess / vol_daily * np.sqrt(TRADING_DAYS_PER_YEAR)) if vol_daily else float("nan")

    downside = series.loc[series < 0.0]
    downside_std = float(downside.std(ddof=0)) if not downside.empty else 0.0
    sortino = float(series.mean() / downside_std * np.sqrt(TRADING_DAYS_PER_YEAR)) if downside_std else float("nan")

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
            bench_aligned = aligned.iloc[:, 1]
            bench_equity = (1.0 + bench_aligned).cumprod()
            bench_years = max(len(bench_aligned) / TRADING_DAYS_PER_YEAR, 1.0 / TRADING_DAYS_PER_YEAR)
            benchmark_return = float(bench_equity.iloc[-1] - 1.0)
            benchmark_cagr = float(bench_equity.iloc[-1] ** (1.0 / bench_years) - 1.0)
            bench_dd = bench_equity / bench_equity.cummax() - 1.0
            benchmark_max_dd = float(bench_dd.min())
            excess_cagr = cagr - benchmark_cagr
            # Jensen's alpha (simplified: excess over risk-free minus beta * market excess)
            bench_excess = bench_aligned.mean()
            beta = float(np.cov(aligned.iloc[:, 0], bench_aligned)[0, 1] / np.var(bench_aligned)) if np.var(bench_aligned) else 0.0
            alpha = float((series.mean() - risk_free_rate / TRADING_DAYS_PER_YEAR) - beta * bench_excess)
            # Information ratio
            tracking_error = float((aligned.iloc[:, 0] - bench_aligned).std(ddof=0))
            ir = float((series.mean() - bench_aligned.mean()) / tracking_error * np.sqrt(TRADING_DAYS_PER_YEAR)) if tracking_error else float("nan")

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
    )


def compute_windows(
    returns: pd.Series,
    *,
    benchmark_returns: pd.Series | None = None,
    benchmark_symbol: str = "",
    windows: Sequence[int] = DEFAULT_WINDOWS,
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
        )
    return result


def compare_with_backtest(
    actual: WindowPerformance,
    backtest: "BacktestResult | None",
) -> dict[str, float]:
    """Compute deviation between actual window performance and backtest expectations."""
    if backtest is None:
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


def _empty_window(label: str, window_days: int, benchmark: str) -> WindowPerformance:
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
    )
