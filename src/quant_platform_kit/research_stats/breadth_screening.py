"""Phase 11 BREADTH cross-asset and futures offline screening (research-only).

Combines point-in-time dataset manifest verification, futures-specific cash
isolation and roll-rule invariants, lower-tail conditional correlation +
stationary-bootstrap UCB gating, and Deflated Sharpe Ratio (DSR) multiple-testing
accounting into one fail-closed screening boundary.

This module is research-only: it never reads accounts, calls brokers, places
orders, writes runtime risk policy, or grants paper/shadow/live authority.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Iterable

from quant_platform_kit.research_stats._validation import (
    ResearchInputError,
    finite_float,
)
from quant_platform_kit.research_stats.sharpe_inference import (
    STATUS_COMPUTED,
    STATUS_UNCOMPUTABLE,
    StatResult,
    deflated_sharpe_ratio,
)
from quant_platform_kit.research_stats.tail_correlation import (
    TailCorrelationResult,
    lower_tail_correlation_gate,
)

BREADTH_ASSET_CLASSES = (
    "equity",
    "etf",
    "gold",
    "treasury",
    "non_us_equity",
    "commodity",
    "fx",
    "futures",
)
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class BreadthDatasetManifest:
    dataset_id: str
    symbol: str
    asset_class: str
    sha256: str
    point_in_time_verified: bool
    leverage: float = 1.0
    max_leverage_allowed: float = 1.0
    roll_rule: str | None = None
    margin_isolated_from_cash_buffer: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "dataset_id": self.dataset_id,
            "symbol": self.symbol,
            "asset_class": self.asset_class,
            "sha256": self.sha256,
            "point_in_time_verified": self.point_in_time_verified,
            "leverage": self.leverage,
            "max_leverage_allowed": self.max_leverage_allowed,
            "roll_rule": self.roll_rule,
            "margin_isolated_from_cash_buffer": self.margin_isolated_from_cash_buffer,
        }


@dataclass(frozen=True)
class BreadthScreeningResult:
    status: str
    passes_gate: bool
    failed_gates: tuple[str, ...]
    manifest: BreadthDatasetManifest
    tail_correlation: TailCorrelationResult | None
    dsr: StatResult | None
    trial_count: int | None
    min_dsr: float | None

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "passes_gate": self.passes_gate,
            "failed_gates": list(self.failed_gates),
            "manifest": self.manifest.to_dict(),
            "tail_correlation": (
                None if self.tail_correlation is None else self.tail_correlation.to_dict()
            ),
            "dsr": None if self.dsr is None else self.dsr.to_dict(),
            "trial_count": self.trial_count,
            "min_dsr": self.min_dsr,
        }


def _validate_manifest(manifest: BreadthDatasetManifest) -> list[str]:
    failures: list[str] = []
    if not isinstance(manifest.dataset_id, str) or not manifest.dataset_id.strip():
        failures.append("invalid_dataset_id")
    if not isinstance(manifest.symbol, str) or not manifest.symbol.strip():
        failures.append("invalid_symbol")
    if manifest.asset_class not in BREADTH_ASSET_CLASSES:
        failures.append("unsupported_asset_class")
    if not isinstance(manifest.sha256, str) or not _SHA256_RE.fullmatch(manifest.sha256):
        failures.append("invalid_dataset_sha256")
    if manifest.point_in_time_verified is not True:
        failures.append("unverified_point_in_time")
    try:
        lev = finite_float(manifest.leverage, "leverage")
        max_lev = finite_float(manifest.max_leverage_allowed, "max_leverage_allowed")
    except ResearchInputError:
        failures.append("invalid_leverage")
    else:
        if lev <= 0.0 or max_lev <= 0.0 or lev > max_lev:
            failures.append("excess_leverage")
    if manifest.asset_class == "futures":
        if not isinstance(manifest.roll_rule, str) or not manifest.roll_rule.strip():
            failures.append("missing_futures_roll_rule")
        if manifest.margin_isolated_from_cash_buffer is not True:
            failures.append("futures_margin_not_isolated")
    return failures


def _materialize_series(values: Iterable[object]) -> object:
    if isinstance(values, (str, bytes)):
        return values
    try:
        return tuple(values)
    except TypeError:
        return values


def evaluate_breadth_candidate(
    candidate_returns: Iterable[object],
    benchmark_returns: Iterable[object],
    *,
    trial_sharpes: Iterable[object],
    seed: int,
    manifest: BreadthDatasetManifest,
    mean_block_length: object = 5.0,
    n_resamples: int = 1000,
    tail_quantile: object = 0.10,
    confidence: object = 0.95,
    max_tail_correlation: object = 0.50,
    min_tail_observations: int = 10,
    min_dsr: object = 0.95,
    n_effective_trials: int | None = None,
) -> BreadthScreeningResult:
    """Run all offline Phase 11 BREADTH screening gates on a candidate sleeve."""
    failed = _validate_manifest(manifest)

    cand_seq = _materialize_series(candidate_returns)
    bench_seq = _materialize_series(benchmark_returns)
    trials_seq = _materialize_series(trial_sharpes)

    try:
        dsr_threshold = finite_float(min_dsr, "min_dsr")
        if not 0.0 < dsr_threshold < 1.0:
            raise ResearchInputError("min_dsr must be in (0, 1)")
    except ResearchInputError:
        failed.append("invalid_min_dsr")
        dsr_threshold = None

    tail_result = lower_tail_correlation_gate(
        cand_seq,  # type: ignore[arg-type]
        bench_seq,  # type: ignore[arg-type]
        seed=seed,
        mean_block_length=mean_block_length,
        n_resamples=n_resamples,
        tail_quantile=tail_quantile,
        confidence=confidence,
        max_tail_correlation=max_tail_correlation,
        min_tail_observations=min_tail_observations,
    )
    if tail_result.status != STATUS_COMPUTED:
        failed.append("tail_correlation_uncomputable")
    elif not tail_result.passes_gate:
        failed.append("tail_correlation_above_limit")

    dsr_result = deflated_sharpe_ratio(
        cand_seq,  # type: ignore[arg-type]
        trials_seq,  # type: ignore[arg-type]
        n_effective_trials=n_effective_trials,
    )
    recorded_trials = dsr_result.details.get("n_effective_trials")
    trial_count: int | None = None
    if (
        isinstance(recorded_trials, (int, float))
        and not isinstance(recorded_trials, bool)
        and math.isfinite(recorded_trials)
        and float(recorded_trials).is_integer()
    ):
        trial_count = int(recorded_trials)

    if dsr_result.status != STATUS_COMPUTED or dsr_result.value is None:
        failed.append("dsr_uncomputable")
    elif dsr_threshold is not None and dsr_result.value < dsr_threshold:
        failed.append("dsr_below_threshold")

    failed_tuple = tuple(failed)
    uncomputable_gates = {"invalid_min_dsr", "tail_correlation_uncomputable", "dsr_uncomputable"}
    overall_status = (
        STATUS_UNCOMPUTABLE
        if any(gate in uncomputable_gates for gate in failed_tuple)
        else STATUS_COMPUTED
    )
    passes = overall_status == STATUS_COMPUTED and len(failed_tuple) == 0
    return BreadthScreeningResult(
        status=overall_status,
        passes_gate=passes,
        failed_gates=failed_tuple,
        manifest=manifest,
        tail_correlation=tail_result,
        dsr=dsr_result,
        trial_count=trial_count,
        min_dsr=dsr_threshold,
    )
