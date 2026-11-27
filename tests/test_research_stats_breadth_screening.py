"""Tests for research_stats.breadth_screening (Phase 11 BREADTH)."""

from __future__ import annotations

import math
import random

import pytest

np = pytest.importorskip("numpy")

from quant_platform_kit.research_stats import (  # noqa: E402
    BREADTH_ASSET_CLASSES,
    STATUS_COMPUTED,
    STATUS_UNCOMPUTABLE,
    BreadthDatasetManifest,
    BreadthScreeningResult,
    evaluate_breadth_candidate,
)

_SHA = "a" * 64


def _make_returns(kind: str, n: int = 240, seed: int = 19) -> tuple[list[float], list[float]]:
    rng = random.Random(seed)
    bench: list[float] = []
    cand: list[float] = []
    for i in range(n):
        b = -0.045 + rng.uniform(-0.02, 0.0) if i % 8 == 0 else rng.uniform(-0.01, 0.014)
        if kind == "strong_crisis_alpha":
            c = (-0.65 * b if b < -0.02 else 0.005) + rng.uniform(-0.002, 0.003)
        elif kind == "flat_low_sharpe":
            c = (-0.50 * b if b < -0.02 else -0.001) + rng.uniform(-0.015, 0.014)
        elif kind == "co_crash":
            c = 0.90 * b + 0.004 + rng.uniform(-0.003, 0.003)
        else:
            raise ValueError(kind)
        bench.append(b)
        cand.append(c)
    return cand, bench


def _manifest(**overrides: object) -> BreadthDatasetManifest:
    base: dict[str, object] = {
        "dataset_id": "breadth-gold-1x-v1",
        "symbol": "GOLD_1X",
        "asset_class": "gold",
        "sha256": _SHA,
        "point_in_time_verified": True,
        "leverage": 1.0,
        "max_leverage_allowed": 1.0,
    }
    base.update(overrides)
    return BreadthDatasetManifest(**base)  # type: ignore[arg-type]


def test_breadth_screening_passes_gold_and_isolated_cta_futures() -> None:
    cand, bench = _make_returns("strong_crisis_alpha")
    trials = [0.02, 0.05, 0.12]

    gold = evaluate_breadth_candidate(
        cand,
        bench,
        trial_sharpes=trials,
        seed=7,
        manifest=_manifest(asset_class="gold"),
        n_resamples=250,
    )
    assert isinstance(gold, BreadthScreeningResult)
    assert gold.status == STATUS_COMPUTED
    assert gold.passes_gate is True
    assert gold.failed_gates == ()
    assert gold.tail_correlation is not None and gold.tail_correlation.passes_gate is True
    assert gold.dsr is not None and gold.dsr.value is not None and gold.dsr.value >= 0.95

    futures = evaluate_breadth_candidate(
        cand,
        bench,
        trial_sharpes=trials,
        seed=7,
        manifest=_manifest(
            dataset_id="breadth-cta-futures-v1",
            symbol="CTA_TREND_1X",
            asset_class="futures",
            roll_rule="first_notice_minus_5d_adjusted",
            margin_isolated_from_cash_buffer=True,
        ),
        n_resamples=250,
    )
    assert futures.passes_gate is True
    assert futures.failed_gates == ()
    assert futures.trial_count == 3

    from_iterators = evaluate_breadth_candidate(
        (x for x in cand),
        (x for x in bench),
        trial_sharpes=(t for t in trials),
        seed=7,
        manifest=_manifest(asset_class="gold"),
        n_resamples=250,
        n_effective_trials=2,
    )
    assert from_iterators.passes_gate is True
    assert from_iterators.trial_count == 2


def test_breadth_screening_fails_closed_on_manifest_invariants() -> None:
    cand, bench = _make_returns("strong_crisis_alpha")
    trials = [0.02, 0.05, 0.12]

    bad_pit = evaluate_breadth_candidate(
        cand,
        bench,
        trial_sharpes=trials,
        seed=7,
        manifest=_manifest(point_in_time_verified=False),
        n_resamples=200,
    )
    assert bad_pit.passes_gate is False
    assert "unverified_point_in_time" in bad_pit.failed_gates

    bad_sha = evaluate_breadth_candidate(
        cand,
        bench,
        trial_sharpes=trials,
        seed=7,
        manifest=_manifest(sha256=_SHA + "\n"),
        n_resamples=200,
    )
    assert bad_sha.passes_gate is False
    assert "invalid_dataset_sha256" in bad_sha.failed_gates

    bad_lev_nan = evaluate_breadth_candidate(
        cand,
        bench,
        trial_sharpes=trials,
        seed=7,
        manifest=_manifest(leverage=math.nan),
        n_resamples=200,
    )
    assert bad_lev_nan.passes_gate is False
    assert "invalid_leverage" in bad_lev_nan.failed_gates

    bad_lev = evaluate_breadth_candidate(
        cand,
        bench,
        trial_sharpes=trials,
        seed=7,
        manifest=_manifest(leverage=2.0, max_leverage_allowed=1.0),
        n_resamples=200,
    )
    assert bad_lev.passes_gate is False
    assert "excess_leverage" in bad_lev.failed_gates

    bad_futures = evaluate_breadth_candidate(
        cand,
        bench,
        trial_sharpes=trials,
        seed=7,
        manifest=_manifest(
            asset_class="futures",
            roll_rule=None,
            margin_isolated_from_cash_buffer=False,
        ),
        n_resamples=200,
    )
    assert bad_futures.passes_gate is False
    assert "missing_futures_roll_rule" in bad_futures.failed_gates
    assert "futures_margin_not_isolated" in bad_futures.failed_gates

    bad_class = evaluate_breadth_candidate(
        cand,
        bench,
        trial_sharpes=trials,
        seed=7,
        manifest=_manifest(asset_class="leveraged_crypto"),
        n_resamples=200,
    )
    assert bad_class.passes_gate is False
    assert "unsupported_asset_class" in bad_class.failed_gates
    assert "futures" in BREADTH_ASSET_CLASSES


def test_breadth_screening_rejects_co_crashing_and_low_dsr_sleeves() -> None:
    co_cand, bench = _make_returns("co_crash")
    co_res = evaluate_breadth_candidate(
        co_cand,
        bench,
        trial_sharpes=[0.01, 0.05, 0.10],
        seed=3,
        manifest=_manifest(),
        n_resamples=200,
    )
    assert co_res.passes_gate is False
    assert "tail_correlation_above_limit" in co_res.failed_gates

    weak_cand, weak_bench = _make_returns("flat_low_sharpe")
    weak_res = evaluate_breadth_candidate(
        weak_cand,
        weak_bench,
        trial_sharpes=[0.01, 0.15, 0.35],
        seed=3,
        manifest=_manifest(),
        n_resamples=200,
    )
    assert weak_res.passes_gate is False
    assert "dsr_below_threshold" in weak_res.failed_gates


def test_breadth_screening_handles_uncomputable_inputs_and_to_dict() -> None:
    empty = evaluate_breadth_candidate(
        [],
        [],
        trial_sharpes=[0.01, 0.05],
        seed=1,
        manifest=_manifest(),
        n_resamples=100,
    )
    assert empty.status == STATUS_UNCOMPUTABLE
    assert empty.passes_gate is False
    assert "tail_correlation_uncomputable" in empty.failed_gates
    assert "dsr_uncomputable" in empty.failed_gates

    cand, bench = _make_returns("strong_crisis_alpha")
    for invalid_threshold in (0.0, 1.0, math.nan):
        bad_dsr = evaluate_breadth_candidate(
            cand,
            bench,
            trial_sharpes=[0.01, 0.05, 0.12],
            seed=1,
            manifest=_manifest(),
            min_dsr=invalid_threshold,
            n_resamples=150,
        )
        assert bad_dsr.status == STATUS_UNCOMPUTABLE
        assert bad_dsr.passes_gate is False
        assert "invalid_min_dsr" in bad_dsr.failed_gates

    payload = empty.to_dict()
    assert set(payload) == {
        "status",
        "passes_gate",
        "failed_gates",
        "manifest",
        "tail_correlation",
        "dsr",
        "trial_count",
        "min_dsr",
    }
