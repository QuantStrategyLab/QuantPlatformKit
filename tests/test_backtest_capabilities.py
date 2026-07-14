from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from quant_platform_kit.strategy_lifecycle.capabilities import (
    BacktestCapabilities,
    BacktestRequest,
    CapabilityError,
    ExecutionTiming,
    LegacyCapabilityAdapter,
    PersistMode,
    canonical_profile_id,
    serialize_request,
    validate_capability,
)


def test_legacy_durable_without_timing_is_expressible() -> None:
    request = BacktestRequest(profile="soxl_soxx_trend_income", params={"lookback": 20})
    capabilities = LegacyCapabilityAdapter.capabilities()
    validate_capability(request, capabilities)
    assert request.persist_mode is PersistMode.DURABLE
    assert request.execution_timing is None


@pytest.mark.parametrize("timing", [ExecutionTiming.NEXT_OPEN, ExecutionTiming.NEXT_CLOSE])
def test_explicit_timing_requires_declared_capability(timing: ExecutionTiming) -> None:
    request = BacktestRequest(profile="SOXL", params={}, execution_timing=timing)
    with pytest.raises(CapabilityError, match="execution_timing"):
        validate_capability(request, LegacyCapabilityAdapter.capabilities())
    validate_capability(request, BacktestCapabilities(execution_timings=frozenset({timing})))


def test_ephemeral_requires_explicit_capability() -> None:
    request = BacktestRequest(profile="TQQQ", params={}, persist_mode=PersistMode.EPHEMERAL)
    with pytest.raises(CapabilityError, match="ephemeral"):
        validate_capability(request, LegacyCapabilityAdapter.capabilities())
    validate_capability(request, BacktestCapabilities(ephemeral=True))


def test_version_mismatch_fails_closed_before_runner() -> None:
    request = BacktestRequest(profile="TQQQ", params={})
    with pytest.raises(CapabilityError, match="contract_version"):
        validate_capability(request, BacktestCapabilities(contract_version=2))


def test_request_is_keyword_only_and_immutable() -> None:
    request = BacktestRequest(profile="SOXL", params={"lookback": 20})
    with pytest.raises(TypeError):
        BacktestRequest("SOXL", {})
    with pytest.raises(FrozenInstanceError):
        request.profile = "TQQQ"
    with pytest.raises(TypeError):
        request.params["lookback"] = 30


def test_kwargs_and_signature_are_not_capability_evidence() -> None:
    request = BacktestRequest(profile="SOXL", params={}, execution_timing=ExecutionTiming.NEXT_OPEN)
    kwargs_like = BacktestCapabilities()
    with pytest.raises(CapabilityError):
        validate_capability(request, kwargs_like)


def test_canonical_ids_and_serialization_shape_are_pure() -> None:
    request = BacktestRequest(profile="soxl_soxx_trend_income", params={"lookback": 20})
    assert canonical_profile_id(request.profile) == "SOXL"
    assert serialize_request(request) == {
        "contract_version": 1,
        "profile": "soxl_soxx_trend_income",
        "params": {"lookback": 20},
        "execution_timing": None,
        "persist_mode": "durable",
    }
