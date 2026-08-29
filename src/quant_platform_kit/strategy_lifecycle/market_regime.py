"""Market regime detection — prevents false drift alarms during broad market moves.

When the entire market is in turmoil, all strategies may drift simultaneously.
This module detects regime states and provides dynamic threshold adjustments so
the drift detector doesn't cry wolf during a market-wide selloff.
"""

from __future__ import annotations

import enum
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd

from quant_platform_kit.strategy_lifecycle.performance_metrics import (
    TRADING_DAYS_PER_YEAR,
    normalize_return_series,
)


class MarketRegime(str, enum.Enum):
    """Market regime classification."""

    NORMAL = "normal"        # Standard market conditions
    ELEVATED = "elevated"    # Higher vol, above-average correlations
    STRESS = "stress"        # Extreme vol, correlations → 1, tail events
    UNKNOWN = "unknown"      # Insufficient data


@dataclass(frozen=True)
class MarketRegimeResult:
    """Snapshot of current market regime with supporting metrics."""

    regime: MarketRegime
    as_of: date

    # Volatility metrics
    volatility_20d: float         # annualized
    volatility_60d: float
    volatility_20d_percentile: float  # vs 3-year history, 0-1

    # Correlation metrics
    avg_pairwise_correlation: float    # across benchmark universe
    correlation_percentile: float

    # Tail risk
    var_95_daily: float           # daily VaR at 95%
    cvar_95_daily: float
    max_daily_loss_20d: float

    # Regime shift detection
    regime_changed: bool = False
    previous_regime: MarketRegime | None = None



    def to_risk_context(self):
        """Adapt to risk.contracts.RegimeContext for RiskEngine consumption."""
        from quant_platform_kit.risk.contracts import RegimeContext as RiskRegimeContext

        # Map lifecycle MarketRegime enum → risk regime string constants.
        regime_value = getattr(self.regime, "value", str(self.regime))
        corr = self.avg_pairwise_correlation
        if corr != corr:  # NaN
            corr = 0.0
        return RiskRegimeContext(
            as_of=self.as_of.isoformat() if hasattr(self.as_of, "isoformat") else str(self.as_of),
            volatility_percentile=float(self.volatility_20d_percentile),
            pairwise_correlation=float(corr),
            regime=str(regime_value),
            vix_level=None,
            credit_spread=None,
        )


@dataclass(frozen=True)
class DynamicDriftThresholds:
    """Thresholds adjusted for current market regime.

    In NORMAL regime: use baseline thresholds.
    In ELEVATED: relax thresholds by 50% (e.g. 0.50 → 0.75 for CAGR drift).
    In STRESS: relax by 100% — focus on drawdown breach, suppress false alarms.
    """

    cagr_deviation_pct: float
    sharpe_deviation: float
    max_drawdown_multiplier: float
    volatility_deviation_pct: float
    win_rate_deviation_pct: float

    @classmethod
    def from_baseline(
        cls,
        baseline: Mapping[str, float],
        *,
        regime: MarketRegime,
    ) -> "DynamicDriftThresholds":
        """Apply regime-based relaxation to baseline thresholds."""
        if regime == MarketRegime.STRESS:
            factor = 2.0  # 100% relaxation — only catch extreme outliers
        elif regime == MarketRegime.ELEVATED:
            factor = 1.5  # 50% relaxation
        else:
            factor = 1.0

        return cls(
            cagr_deviation_pct=baseline.get("cagr_deviation_pct", 0.50) * factor,
            sharpe_deviation=baseline.get("sharpe_deviation", 0.50) * factor,
            max_drawdown_multiplier=baseline.get("max_drawdown_multiplier", 1.50),
            volatility_deviation_pct=baseline.get("volatility_deviation_pct", 0.30) * factor,
            win_rate_deviation_pct=baseline.get("win_rate_deviation_pct", 0.20) * (1.0 + (factor - 1.0) * 0.5),
        )

    def to_dict(self) -> dict[str, float]:
        return {
            "cagr_deviation_pct": self.cagr_deviation_pct,
            "sharpe_deviation": self.sharpe_deviation,
            "max_drawdown_multiplier": self.max_drawdown_multiplier,
            "volatility_deviation_pct": self.volatility_deviation_pct,
            "win_rate_deviation_pct": self.win_rate_deviation_pct,
        }


# ── Regime Detection Engine ──────────────────────────────────────────


class RegimeDetector:
    """Detect current market regime from benchmark return history.

    Usage::

        detector = RegimeDetector(benchmark_returns=spy_returns)
        ctx = detector.detect()
        thresholds = DynamicDriftThresholds.from_baseline(baseline, regime=ctx.regime)
    """

    # Configuration
    VOL_PERCENTILE_ELEVATED = 0.75    # vol above 75th %ile → elevated
    VOL_PERCENTILE_STRESS = 0.90      # vol above 90th %ile → stress
    CORR_PERCENTILE_STRESS = 0.85     # correlation above 85th %ile → stress
    MIN_HISTORY_DAYS = 252            # minimum history for percentile calculation
    CORRELATION_WINDOW_DAYS = 60

    def __init__(self, *, benchmark_returns: pd.Series | None = None):
        self._benchmark = normalize_return_series(benchmark_returns) if benchmark_returns is not None else None
        self._last_regime: MarketRegime | None = None

    def detect(
        self,
        *,
        benchmark_returns: pd.Series | None = None,
        universe_returns: pd.DataFrame | None = None,
    ) -> MarketRegimeResult:
        """Detect the current market regime.

        Args:
            benchmark_returns: Daily returns for the primary benchmark (e.g. SPY).
            universe_returns: DataFrame of returns for multiple assets (for correlation).

        Returns:
            MarketRegimeResult with regime classification and supporting metrics.
        """
        bm = normalize_return_series(benchmark_returns) if benchmark_returns is not None else self._benchmark
        if bm is None or len(bm) < self.MIN_HISTORY_DAYS:
            return MarketRegimeResult(
                regime=MarketRegime.UNKNOWN,
                as_of=date.today(),
                volatility_20d=float("nan"),
                volatility_60d=float("nan"),
                volatility_20d_percentile=0.5,
                avg_pairwise_correlation=float("nan"),
                correlation_percentile=0.5,
                var_95_daily=float("nan"),
                cvar_95_daily=float("nan"),
                max_daily_loss_20d=float("nan"),
            )

        # ── Volatility ──────────────────────────────────────────
        vol_20d = float(bm.tail(20).std(ddof=0) * np.sqrt(TRADING_DAYS_PER_YEAR))
        vol_60d = float(bm.tail(60).std(ddof=0) * np.sqrt(TRADING_DAYS_PER_YEAR))

        # Rolling 20-day vol history for percentile
        rolling_vol = bm.rolling(20).std(ddof=0) * np.sqrt(TRADING_DAYS_PER_YEAR)
        rolling_vol = rolling_vol.dropna()
        vol_percentile = float((rolling_vol < vol_20d).mean()) if len(rolling_vol) > 0 else 0.5

        # ── Correlation ─────────────────────────────────────────
        avg_corr, corr_percentile = self._compute_correlation_metrics(bm, universe_returns)

        # ── Tail risk ───────────────────────────────────────────
        var_95 = float(bm.tail(252).quantile(0.05))
        cvar_95 = float(bm.tail(252)[bm.tail(252) <= var_95].mean()) if not bm.tail(252).empty else float("nan")
        max_loss_20d = float(bm.tail(20).min())

        # ── Regime classification ───────────────────────────────
        regime = self._classify(vol_percentile, corr_percentile)

        previous = self._last_regime
        changed = previous is not None and previous != regime
        self._last_regime = regime

        return MarketRegimeResult(
            regime=regime,
            as_of=date.today(),
            volatility_20d=vol_20d,
            volatility_60d=vol_60d,
            volatility_20d_percentile=round(vol_percentile, 4),
            avg_pairwise_correlation=round(avg_corr, 4) if not np.isnan(avg_corr) else float("nan"),
            correlation_percentile=round(corr_percentile, 4) if not np.isnan(corr_percentile) else 0.5,
            var_95_daily=round(var_95, 6),
            cvar_95_daily=round(cvar_95, 6) if not np.isnan(cvar_95) else float("nan"),
            max_daily_loss_20d=round(max_loss_20d, 6),
            regime_changed=changed,
            previous_regime=previous,
        )

    def _classify(self, vol_percentile: float, corr_percentile: float) -> MarketRegime:
        """Classify regime from vol and correlation percentiles."""
        if vol_percentile >= self.VOL_PERCENTILE_STRESS or corr_percentile >= self.CORR_PERCENTILE_STRESS:
            return MarketRegime.STRESS
        if vol_percentile >= self.VOL_PERCENTILE_ELEVATED:
            return MarketRegime.ELEVATED
        return MarketRegime.NORMAL

    def _compute_correlation_metrics(
        self,
        benchmark: pd.Series,
        universe: pd.DataFrame | None,
    ) -> tuple[float, float]:
        """Compute average pairwise correlation and its rolling-history percentile.

        A correlation value is not itself a percentile: mapping ``[-1, 1]`` to
        ``[0, 1]`` conflates high absolute correlation with correlation that is
        unusually high for this universe.  We instead compare the current
        60-day average pairwise correlation against the historical sequence of
        equivalent 60-day observations.  The method deliberately returns the
        neutral fallback when there is less than one full year of aligned
        history, rather than manufacturing precision from a short sample.
        """
        if universe is None or universe.empty:
            return float("nan"), 0.5

        frame = pd.DataFrame(universe).copy()
        # Align with benchmark
        common = frame.index.intersection(benchmark.index).sort_values()
        if len(common) < self.MIN_HISTORY_DAYS:
            return float("nan"), 0.5

        # Use up to 10 columns to keep it cheap
        cols = [c for c in frame.columns if str(c).strip() and not str(c).startswith("buy_hold_")][:10]
        if len(cols) < 3:
            return float("nan"), 0.5

        aligned = frame.loc[common, cols]
        rolling_averages = []
        for end in range(self.CORRELATION_WINDOW_DAYS, len(aligned) + 1):
            average = self._average_pairwise_correlation(
                aligned.iloc[end - self.CORRELATION_WINDOW_DAYS:end]
            )
            if np.isfinite(average):
                rolling_averages.append(average)

        if not rolling_averages:
            return float("nan"), 0.5

        average = rolling_averages[-1]
        history = np.asarray(rolling_averages, dtype=float)
        percentile = float((history < average).mean())
        return average, percentile

    @staticmethod
    def _average_pairwise_correlation(frame: pd.DataFrame) -> float:
        """Return the finite lower-triangle mean of a correlation matrix."""
        corr_matrix = frame.corr()
        values = corr_matrix.to_numpy()[np.tril_indices(len(corr_matrix), k=-1)]
        finite_values = values[np.isfinite(values)]
        return float(np.mean(finite_values)) if len(finite_values) else float("nan")


# ── Convenience factory ──────────────────────────────────────────────


def detect_market_regime(
    domain: str,
    *,
    benchmark_symbol: str | None = None,
) -> MarketRegimeResult:
    """Detect market regime for a domain using available return data.

    This is a convenience wrapper that auto-discovers benchmark data.
    """
    from quant_platform_kit.strategy_lifecycle.return_collector import ReturnCollector

    collector = ReturnCollector()

    # Domain-specific benchmark
    if benchmark_symbol is None:
        defaults = {"us_equity": "buy_hold_SPY", "crypto": "buy_hold_BTC",
                     "hk_equity": "buy_hold_2800", "cn_equity": "buy_hold_510300"}
        benchmark_symbol = defaults.get(domain, "buy_hold_SPY")

    benchmark = collector.collect_benchmark(domain, benchmark_symbol)
    detector = RegimeDetector(benchmark_returns=benchmark)
    return detector.detect()
