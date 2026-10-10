"""Probabilistic and Deflated Sharpe Ratio (research-only, stdlib only).

References:
- Bailey, D. H. and López de Prado, M. (2012), "The Sharpe Ratio Efficient
  Frontier", Journal of Risk 15(2) -- Probabilistic Sharpe Ratio (PSR).
- Bailey, D. H. and López de Prado, M. (2014), "The Deflated Sharpe Ratio:
  Correcting for Selection Bias, Backtest Overfitting and Non-Normality",
  Journal of Portfolio Management 40(5) -- DSR.

All Sharpe ratios here are **per-period and non-annualized** (mean / sample
standard deviation of the same simple-return frequency, rf/MAR already
removed by the caller). Mixing frequencies or annualized trial Sharpes is a
caller error that this module cannot detect.

Fail-closed: any condition under which the estimate is undefined returns
``status="UNCOMPUTABLE"`` with ``value=None`` and a ``reason_code``. A missing
estimate is never reported as zero.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from statistics import NormalDist
from typing import Iterable, Mapping, Sequence

from quant_platform_kit.research_stats._validation import (
    ResearchInputError,
    finite_float,
    positive_int,
    simple_returns,
)

STATUS_COMPUTED = "COMPUTED"
STATUS_UNCOMPUTABLE = "UNCOMPUTABLE"

EULER_MASCHERONI = 0.5772156649015329
# Default observation floor mirrors the existing QPK Kelly contract v2
# minimum sample (30). It is a structural floor, not a quality threshold.
DEFAULT_MIN_OBSERVATIONS = 30
_MIN_TRIALS = 2
_STD_NORMAL = NormalDist()


@dataclass(frozen=True)
class StatResult:
    name: str
    status: str
    value: float | None
    reason_code: str | None = None
    details: Mapping[str, object] = field(default_factory=dict)

    @property
    def computed(self) -> bool:
        return self.status == STATUS_COMPUTED

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "status": self.status,
            "value": self.value,
            "reason_code": self.reason_code,
            "details": dict(self.details),
        }


def _uncomputable(name: str, reason: str, **details: object) -> StatResult:
    return StatResult(name=name, status=STATUS_UNCOMPUTABLE, value=None, reason_code=reason, details=details)


def _moments(returns: Sequence[float]) -> tuple[float, float, float, float]:
    """Return (per-period Sharpe, sample std, skewness, non-excess kurtosis).

    Sharpe uses the sample standard deviation (ddof=1). Skewness and kurtosis
    are the population (biased) moment estimators used by Bailey & López de
    Prado; kurtosis is non-excess (normal = 3).
    """
    n = len(returns)
    mean = math.fsum(returns) / n
    deviations = [r - mean for r in returns]
    m2 = math.fsum(d * d for d in deviations) / n
    if m2 <= 0.0:
        return float("nan"), 0.0, float("nan"), float("nan")
    sample_std = math.sqrt(math.fsum(d * d for d in deviations) / (n - 1))
    m3 = math.fsum(d ** 3 for d in deviations) / n
    m4 = math.fsum(d ** 4 for d in deviations) / n
    skew = m3 / m2 ** 1.5
    kurt = m4 / m2 ** 2
    return mean / sample_std, sample_std, skew, kurt


def _psr_from_moments(
    sharpe: float, benchmark: float, n: int, skew: float, kurt: float
) -> tuple[float | None, str | None, float | None]:
    variance_term = 1.0 - skew * sharpe + (kurt - 1.0) / 4.0 * sharpe * sharpe
    if not math.isfinite(variance_term) or variance_term <= 0.0:
        return None, "non_positive_sharpe_variance", None
    z = (sharpe - benchmark) * math.sqrt(n - 1) / math.sqrt(variance_term)
    if not math.isfinite(z):
        return None, "non_finite_z_score", None
    return _STD_NORMAL.cdf(z), None, z


def probabilistic_sharpe_ratio(
    returns: Iterable[object],
    *,
    sr_benchmark: object = 0.0,
    min_observations: int = DEFAULT_MIN_OBSERVATIONS,
) -> StatResult:
    """PSR: probability that the true per-period Sharpe exceeds ``sr_benchmark``.

    ``PSR = Φ((SR − SR*)·√(n−1) / √(1 − γ3·SR + (γ4−1)/4·SR²))``.
    """
    name = "probabilistic_sharpe_ratio"
    try:
        floor = positive_int(min_observations, "min_observations", minimum=3)
        series = simple_returns(returns)
        benchmark = finite_float(sr_benchmark, "sr_benchmark")
    except ResearchInputError as exc:
        return _uncomputable(name, "invalid_input", message=str(exc))
    n = len(series)
    if n < floor:
        return _uncomputable(name, "insufficient_observations", observations=n, min_observations=floor)
    sharpe, std, skew, kurt = _moments(series)
    if std <= 0.0 or not math.isfinite(sharpe):
        return _uncomputable(name, "zero_variance", observations=n)
    value, reason, z = _psr_from_moments(sharpe, benchmark, n, skew, kurt)
    details = {
        "observations": n,
        "sharpe_per_period": sharpe,
        "sr_benchmark": benchmark,
        "skewness": skew,
        "kurtosis": kurt,
    }
    if value is None:
        return _uncomputable(name, reason or "uncomputable", **details)
    details["z_score"] = z
    return StatResult(name=name, status=STATUS_COMPUTED, value=value, details=details)


def expected_max_sharpe(trial_sharpe_variance: object, n_trials: object) -> StatResult:
    """Expected maximum Sharpe under the null of zero skill across ``n_trials``.

    ``SR0 = √V · ((1−γ)·Φ⁻¹(1 − 1/N) + γ·Φ⁻¹(1 − 1/(N·e)))``.
    """
    name = "expected_max_sharpe"
    try:
        variance = finite_float(trial_sharpe_variance, "trial_sharpe_variance")
        trials = positive_int(n_trials, "n_trials", minimum=1)
    except ResearchInputError as exc:
        return _uncomputable(name, "invalid_input", message=str(exc))
    if trials < _MIN_TRIALS:
        return _uncomputable(name, "insufficient_trials", n_trials=trials, min_trials=_MIN_TRIALS)
    if variance <= 0.0:
        return _uncomputable(name, "zero_trial_sharpe_variance", n_trials=trials)
    gamma = EULER_MASCHERONI
    value = math.sqrt(variance) * (
        (1.0 - gamma) * _STD_NORMAL.inv_cdf(1.0 - 1.0 / trials)
        + gamma * _STD_NORMAL.inv_cdf(1.0 - 1.0 / (trials * math.e))
    )
    return StatResult(
        name=name,
        status=STATUS_COMPUTED,
        value=value,
        details={"n_trials": trials, "trial_sharpe_variance": variance},
    )


def deflated_sharpe_ratio(
    returns: Iterable[object],
    trial_sharpes: Iterable[object],
    *,
    n_effective_trials: int | None = None,
    min_observations: int = DEFAULT_MIN_OBSERVATIONS,
) -> StatResult:
    """DSR: PSR evaluated against the expected maximum Sharpe of all trials.

    ``trial_sharpes`` must contain the per-period Sharpe of **every** trial
    (including failed/rejected ones), on the same frequency as ``returns``.
    ``n_effective_trials`` may override the trial count (e.g. after
    clustering correlated trials) but never below two. Fewer than two trials,
    zero trial-Sharpe variance or too few observations are ``UNCOMPUTABLE``.
    """
    name = "deflated_sharpe_ratio"
    try:
        floor = positive_int(min_observations, "min_observations", minimum=3)
        series = simple_returns(returns)
        if isinstance(trial_sharpes, (str, bytes)):
            raise ResearchInputError("trial_sharpes must be a sequence of numbers")
        trials = [finite_float(v, f"trial_sharpes[{i}]") for i, v in enumerate(list(trial_sharpes))]
        if n_effective_trials is not None:
            effective = positive_int(n_effective_trials, "n_effective_trials", minimum=1)
        else:
            effective = len(trials)
    except (ResearchInputError, TypeError) as exc:
        return _uncomputable(name, "invalid_input", message=str(exc))
    if len(trials) < _MIN_TRIALS or effective < _MIN_TRIALS:
        return _uncomputable(
            name,
            "insufficient_trials",
            recorded_trials=len(trials),
            n_effective_trials=effective,
            min_trials=_MIN_TRIALS,
        )
    if effective > len(trials):
        return _uncomputable(
            name, "effective_trials_exceed_recorded", recorded_trials=len(trials), n_effective_trials=effective
        )
    n = len(series)
    if n < floor:
        return _uncomputable(name, "insufficient_observations", observations=n, min_observations=floor)
    trial_mean = math.fsum(trials) / len(trials)
    trial_variance = math.fsum((t - trial_mean) ** 2 for t in trials) / (len(trials) - 1)
    sr0 = expected_max_sharpe(trial_variance, effective)
    if not sr0.computed or sr0.value is None:
        return _uncomputable(name, sr0.reason_code or "uncomputable", **dict(sr0.details))
    sharpe, std, skew, kurt = _moments(series)
    if std <= 0.0 or not math.isfinite(sharpe):
        return _uncomputable(name, "zero_variance", observations=n)
    value, reason, z = _psr_from_moments(sharpe, sr0.value, n, skew, kurt)
    details = {
        "observations": n,
        "sharpe_per_period": sharpe,
        "expected_max_sharpe": sr0.value,
        "recorded_trials": len(trials),
        "n_effective_trials": effective,
        "trial_sharpe_variance": trial_variance,
        "skewness": skew,
        "kurtosis": kurt,
    }
    if value is None:
        return _uncomputable(name, reason or "uncomputable", **details)
    details["z_score"] = z
    return StatResult(name=name, status=STATUS_COMPUTED, value=value, details=details)
