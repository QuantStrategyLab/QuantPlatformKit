"""Unified technical indicator functions for QuantStrategyLab pipelines.

Consolidates indicator logic previously duplicated across
``MarketSignalSources.derived.technical_indicators`` and
``CryptoLivePoolPipelines.indicators``.

All functions expect a pandas Series of close prices as the primary input,
returning a Series or scalar of the same index alignment.
"""

from __future__ import annotations

from typing import Any


def sma(series: Any, window: int, *, min_periods: int | None = None) -> Any:
    """Simple moving average."""
    _series = _to_series(series)
    return _series.rolling(window=window, min_periods=min_periods or window).mean()


def ema(series: Any, span: int, *, adjust: bool = True) -> Any:
    """Exponential moving average (EMA)."""
    _series = _to_series(series)
    return _series.ewm(span=span, adjust=adjust).mean()


def rsi(series: Any, window: int = 14) -> Any:
    """Relative Strength Index (RSI)."""
    import numpy as np

    _series = _to_series(series)
    delta = _series.diff()
    gain = delta.clip(lower=0).rolling(window=window).mean()
    loss = (-delta.clip(upper=0)).rolling(window=window).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100.0 - (100.0 / (1.0 + rs))


def atr(high: Any, low: Any, close: Any, window: int = 14) -> Any:
    """Average True Range."""
    import pandas as pd

    _high = _to_series(high)
    _low = _to_series(low)
    _close = _to_series(close)

    prev_close = _close.shift(1)
    tr = pd.concat(
        [
            (_high - _low).abs(),
            (_high - prev_close).abs(),
            (_low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.rolling(window=window, min_periods=window).mean()


def rolling_volatility(series: Any, window: int = 20, *, annualize: bool = True) -> Any:
    """Rolling volatility (standard deviation of log returns).

    Parameters
    ----------
    series :
        Price series.
    window :
        Rolling window in periods.
    annualize :
        If True (default), multiply by sqrt(252) for daily data.

    Returns
    -------
    Series
    """
    import numpy as np

    _series = _to_series(series)
    log_returns = np.log(_series / _series.shift(1))
    vol = log_returns.rolling(window=window, min_periods=window).std()
    if annualize:
        vol = vol * np.sqrt(252.0)
    return vol


def rolling_correlation(x: Any, y: Any, window: int = 20) -> Any:
    """Rolling Pearson correlation between two series."""
    _x = _to_series(x)
    _y = _to_series(y)
    return _x.rolling(window=window, min_periods=window).corr(_y)


def momentum(series: Any, window: int = 90) -> Any:
    """Rate-of-change over *window* periods: (price / lagged_price) - 1."""
    _series = _to_series(series)
    return _series / _series.shift(window) - 1.0


def trend_strength(series: Any, *, fast: int = 20, slow: int = 100) -> Any:
    """Trend strength as the ratio of fast to slow SMA.

    Values > 1 indicate an upward trend; < 1 indicates a downward trend.
    """
    _series = _to_series(series)
    fast_sma = sma(_series, fast)
    slow_sma = sma(_series, slow)
    return fast_sma / slow_sma.replace(0, float("nan"))


def max_drawdown(series: Any, window: int | None = None) -> Any:
    """Maximum drawdown from peak.

    If *window* is provided, computes the rolling max drawdown over that
    window; otherwise computes the cumulative max drawdown.
    """
    _series = _to_series(series)
    if window is not None:
        rolling_max = _series.rolling(window=window, min_periods=window).max()
    else:
        rolling_max = _series.expanding().max()
    return (_series - rolling_max) / rolling_max


def percentile_rank(series: Any, window: int = 252) -> Any:
    """Rolling percentile rank (0–1) of the latest value within its window."""
    _series = _to_series(series)

    def _rank(x: Any) -> float:
        if len(x) < 2:
            return 0.5
        from scipy.stats import percentileofscore  # lazy import

        return percentileofscore(x, x.iloc[-1], kind="rank") / 100.0

    return _series.rolling(window=window, min_periods=window).apply(_rank, raw=False)


def zscore(series: Any, window: int = 20) -> Any:
    """Rolling z-score (standard score)."""
    import numpy as np

    _series = _to_series(series)
    rolling_mean = _series.rolling(window=window, min_periods=window).mean()
    rolling_std = _series.rolling(window=window, min_periods=window).std()
    return (_series - rolling_mean) / rolling_std.replace(0, np.nan)


def _to_series(value: Any) -> Any:
    """Ensure the input is a pandas Series (lazy import)."""
    import pandas as pd

    if isinstance(value, pd.Series):
        return value
    if isinstance(value, pd.DataFrame):
        if value.shape[1] != 1:
            raise ValueError(f"Expected single-column DataFrame, got shape {value.shape}")
        return value.iloc[:, 0]
    return pd.Series(value)
