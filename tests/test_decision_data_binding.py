from __future__ import annotations

import pytest

from quant_platform_kit.data import (
    DECISION_DATA_ASSURANCE_LEGACY,
    DECISION_DATA_ASSURANCE_VERIFIED,
    DECISION_DATA_MODE_ARTIFACT_REQUIRED,
    DECISION_DATA_MODE_LEGACY_RUNTIME_FETCH,
    DecisionDataBinding,
)


_SHA256 = "a" * 64


def test_artifact_binding_is_deterministic_and_public_safe() -> None:
    binding = DecisionDataBinding(
        binding_id="us-etf-daily-v1",
        strategy_scope="soxl_soxx_trend_income",
        mode=DECISION_DATA_MODE_ARTIFACT_REQUIRED,
        source_ids=("alpaca_sip", "ibkr_data_only"),
        as_of="2026-08-31",
        adjustment_basis="split_adjusted",
        artifact_sha256=f"sha256:{_SHA256}",
        assurance_status=DECISION_DATA_ASSURANCE_VERIFIED,
    )

    assert binding.to_dict() == {
        "schema_version": "qpk.decision_data_binding.v1",
        "binding_id": "us-etf-daily-v1",
        "strategy_scope": "soxl_soxx_trend_income",
        "mode": "artifact_required",
        "source_ids": ["alpaca_sip", "ibkr_data_only"],
        "assurance_status": "VERIFIED",
        "as_of": "2026-08-31",
        "adjustment_basis": "split_adjusted",
        "artifact_sha256": _SHA256,
    }
    assert len(binding.binding_sha256) == 64
    assert DecisionDataBinding.from_dict(binding.to_dict()) == binding


def test_legacy_binding_makes_runtime_fetch_explicit() -> None:
    binding = DecisionDataBinding(
        binding_id="legacy-yfinance-us-etf",
        strategy_scope="soxl_soxx_trend_income",
        mode=DECISION_DATA_MODE_LEGACY_RUNTIME_FETCH,
        source_ids=("yfinance",),
    )

    assert binding.assurance_status == DECISION_DATA_ASSURANCE_LEGACY
    assert binding.to_dict()["source_ids"] == ["yfinance"]


@pytest.mark.parametrize(
    "kwargs, message",
    [
        (
            {
                "mode": DECISION_DATA_MODE_ARTIFACT_REQUIRED,
                "source_ids": ("alpaca_sip",),
                "as_of": "2026-08-31",
                "adjustment_basis": "split_adjusted",
                "artifact_sha256": None,
                "assurance_status": DECISION_DATA_ASSURANCE_VERIFIED,
            },
            "artifact_sha256",
        ),
        (
            {
                "mode": DECISION_DATA_MODE_ARTIFACT_REQUIRED,
                "source_ids": ("https://private.example",),
                "as_of": "2026-08-31",
                "adjustment_basis": "split_adjusted",
                "artifact_sha256": _SHA256,
                "assurance_status": DECISION_DATA_ASSURANCE_VERIFIED,
            },
            "source_ids",
        ),
        (
            {
                "mode": DECISION_DATA_MODE_LEGACY_RUNTIME_FETCH,
                "source_ids": ("yfinance",),
                "artifact_sha256": _SHA256,
            },
            "legacy_runtime_fetch",
        ),
    ],
)
def test_binding_rejects_unverifiable_or_private_shape(kwargs: dict[str, object], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        DecisionDataBinding(
            binding_id="safe-binding",
            strategy_scope="strategy",
            **kwargs,
        )
