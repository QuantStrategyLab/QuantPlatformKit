"""Tests for research_stats.tail_correlation (Phase 11 BREADTH gate)."""

from __future__ import annotations

import math
import random

import pytest

np = pytest.importorskip("numpy")

from quant_platform_kit.research_stats import (  # noqa: E402
    STATUS_COMPUTED,
    STATUS_UNCOMPUTABLE,
    TailCorrelationResult,
    lower_tail_correlation_gate,
)


def _make_series(mode: str, n: int = 300, seed: int = 7) -> tuple[list[float], list[float]]:
    rng = random.Random(seed)
    bench: list[float] = []
    cand: list[float] = []
    for i in range(n):
        b = -0.04 + rng.uniform(-0.025, 0.0) if i % 8 == 0 else rng.uniform(-0.01, 0.015)
        if mode == "co_crash":
            c = 0.85 * b + rng.uniform(-0.004, 0.004)
        elif mode == "crisis_alpha":
            c = (-0.75 * b if b < -0.02 else 0.002) + rng.uniform(-0.004, 0.004)
        elif mode == "borderline":
            # Mildly positive tail correlation (~0.35-0.45) with noisy tail draws so 95% UCB > 0.50
            c = (0.45 * b + (0.02 if i % 16 == 0 else -0.015)) + rng.uniform(-0.012, 0.012)
        else:
            raise ValueError(mode)
        bench.append(b)
        cand.append(c)
    return cand, bench


def test_tail_correlation_gate_is_deterministic_with_seed() -> None:
    cand, bench = _make_series("crisis_alpha")
    first = lower_tail_correlation_gate(cand, bench, seed=42, n_resamples=250)
    second = lower_tail_correlation_gate(cand, bench, seed=42, n_resamples=250)
    different = lower_tail_correlation_gate(cand, bench, seed=43, n_resamples=250)

    assert isinstance(first, TailCorrelationResult)
    assert first == second
    assert first.status == STATUS_COMPUTED
    assert first.method == "stationary_bootstrap"
    assert first.upper_confidence_bound != different.upper_confidence_bound


def test_tail_correlation_gate_rejects_co_crashing_sleeve() -> None:
    cand, bench = _make_series("co_crash")
    res = lower_tail_correlation_gate(cand, bench, seed=11, n_resamples=300)

    assert res.status == STATUS_COMPUTED
    assert res.estimate is not None and res.estimate > 0.70
    assert res.upper_confidence_bound is not None and res.upper_confidence_bound >= res.estimate
    assert res.passes_gate is False
    assert res.reason_code is None


def test_tail_correlation_gate_accepts_crisis_alpha_sleeve() -> None:
    cand, bench = _make_series("crisis_alpha")
    res = lower_tail_correlation_gate(cand, bench, seed=11, n_resamples=300)

    assert res.status == STATUS_COMPUTED
    assert res.observations == 300
    assert res.tail_observations >= 10
    assert res.estimate is not None and res.estimate < 0.50
    assert res.upper_confidence_bound is not None and res.upper_confidence_bound < 0.50
    assert res.passes_gate is True


def test_tail_correlation_gate_fails_when_only_ucb_exceeds_limit() -> None:
    cand, bench = _make_series("borderline")
    point_only = lower_tail_correlation_gate(
        cand,
        bench,
        seed=5,
        n_resamples=400,
        max_tail_correlation=0.99,
    )
    assert point_only.status == STATUS_COMPUTED
    assert point_only.estimate is not None
    assert point_only.upper_confidence_bound is not None
    assert point_only.estimate < point_only.upper_confidence_bound

    midpoint = (point_only.estimate + point_only.upper_confidence_bound) / 2.0
    strict = lower_tail_correlation_gate(
        cand,
        bench,
        seed=5,
        n_resamples=400,
        max_tail_correlation=midpoint,
    )
    assert strict.status == STATUS_COMPUTED
    assert strict.estimate is not None and strict.estimate < midpoint
    assert strict.upper_confidence_bound is not None and strict.upper_confidence_bound > midpoint
    assert strict.passes_gate is False


@pytest.mark.parametrize(
    "kwargs,cand_override,bench_override",
    [
        ({"seed": True}, None, None),
        ({"seed": -1}, None, None),
        ({"mean_block_length": 0.5}, None, None),
        ({"n_resamples": 20}, None, None),
        ({"tail_quantile": 0.0}, None, None),
        ({"tail_quantile": 1.0}, None, None),
        ({"confidence": 1.0}, None, None),
        ({"max_tail_correlation": -1.0}, None, None),
        ({"max_tail_correlation": 1.2}, None, None),
        ({"min_tail_observations": 1}, None, None),
        ({}, [0.01, 0.02], [0.01]),
        ({}, [0.01, math.nan, 0.02], [0.01, 0.02, 0.03]),
        ({}, [0.01, -1.0, 0.02], [0.01, 0.02, 0.03]),
    ],
)
def test_tail_correlation_gate_fails_closed_on_invalid_inputs(
    kwargs: dict[str, object],
    cand_override: list[float] | None,
    bench_override: list[float] | None,
) -> None:
    base_cand, base_bench = _make_series("crisis_alpha", n=120)
    cand = base_cand if cand_override is None else cand_override
    bench = base_bench if bench_override is None else bench_override
    params: dict[str, object] = {"seed": 1, "n_resamples": 100, **kwargs}
    res = lower_tail_correlation_gate(cand, bench, **params)  # type: ignore[arg-type]

    assert res.status == STATUS_UNCOMPUTABLE
    assert res.reason_code == "invalid_input"
    assert res.passes_gate is False


def test_tail_correlation_gate_rejects_empty_long_block_insufficient_tail_and_zero_variance() -> None:
    empty = lower_tail_correlation_gate([], [], seed=1, n_resamples=100)
    assert empty.status == STATUS_UNCOMPUTABLE
    assert empty.observations == 0
    assert empty.reason_code == "insufficient_tail_observations"
    assert empty.passes_gate is False

    cand, bench = _make_series("crisis_alpha", n=40)
    long_block = lower_tail_correlation_gate(cand, bench, seed=1, mean_block_length=41.0, n_resamples=100)
    assert long_block.status == STATUS_UNCOMPUTABLE
    assert long_block.observations == 40
    assert long_block.reason_code == "block_longer_than_sample"
    assert long_block.passes_gate is False

    small = lower_tail_correlation_gate(cand, bench, seed=1, n_resamples=100, min_tail_observations=10)
    assert small.status == STATUS_UNCOMPUTABLE
    assert small.reason_code == "insufficient_tail_observations"
    assert small.passes_gate is False

    flat_cand = [0.01] * 200
    res_flat = lower_tail_correlation_gate(flat_cand, [0.02 * ((i % 5) - 2) for i in range(200)], seed=1, n_resamples=100)
    assert res_flat.status == STATUS_UNCOMPUTABLE
    assert res_flat.reason_code == "zero_variance"
    assert res_flat.passes_gate is False


def test_tail_correlation_result_to_dict() -> None:
    cand, bench = _make_series("crisis_alpha")
    res = lower_tail_correlation_gate(cand, bench, seed=9, n_resamples=200)
    payload = res.to_dict()

    assert set(payload) == {
        "status",
        "method",
        "observations",
        "tail_observations",
        "tail_quantile",
        "confidence",
        "max_tail_correlation",
        "mean_block_length",
        "n_resamples",
        "seed",
        "estimate",
        "upper_confidence_bound",
        "passes_gate",
        "reason_code",
    }
    assert payload["passes_gate"] is True
