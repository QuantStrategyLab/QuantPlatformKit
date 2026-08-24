from __future__ import annotations

import pytest

from quant_platform_kit.data.multisource_assurance import (
    DATA_ASSURANCE_STATUS_DEGRADED,
    DATA_ASSURANCE_STATUS_VERIFIED,
    SOURCE_OBSERVATION_READY,
    SOURCE_OBSERVATION_UNAVAILABLE,
    DailyBar,
    DailyBarSourceObservation,
    DailyBarSourceSnapshot,
    MultiSourceDailyBarPolicy,
    assess_multisource_daily_bars,
)


def _policy() -> MultiSourceDailyBarPolicy:
    return MultiSourceDailyBarPolicy(
        scope_id="us-equity:soxl-daily",
        symbol="SOXL",
        date_cutoff="2026-08-21",
        adjustment_basis="total_return_adjusted",
        required_source_ids=("alpaca_sip", "twelve_data_eod"),
    )


def _snapshot(source_id: str, *, close: float = 100.5, adjustment_basis: str = "total_return_adjusted") -> DailyBarSourceSnapshot:
    return DailyBarSourceSnapshot(
        source_id=source_id,
        symbol="SOXL",
        date_cutoff="2026-08-21",
        adjustment_basis=adjustment_basis,
        source_artifact_sha256=("a" if source_id == "alpaca_sip" else "b") * 64,
        bars=(
            DailyBar("2026-08-20", 99.0, 101.0, 98.0, 100.0, 1_000_000),
            DailyBar("2026-08-21", 100.0, 102.0, 99.0, close, 1_100_000),
        ),
    )


def _ready(source_id: str, **kwargs: object) -> DailyBarSourceObservation:
    return DailyBarSourceObservation(source_id, SOURCE_OBSERVATION_READY, _snapshot(source_id, **kwargs))


def test_matching_independent_sources_are_verified_and_diagnostic_is_redacted() -> None:
    policy = _policy()

    result = assess_multisource_daily_bars(
        policy,
        (_ready("twelve_data_eod"), _ready("alpaca_sip")),
    )

    assert result.status == DATA_ASSURANCE_STATUS_VERIFIED
    assert result.can_publish_research_input
    assert result.findings == ()
    diagnostic = result.to_diagnostic()
    assert diagnostic["source_statuses"] == {"alpaca_sip": "READY", "twelve_data_eod": "READY"}
    assert "100.5" not in str(diagnostic)
    assert result.report_sha256 == assess_multisource_daily_bars(
        policy,
        (_ready("alpaca_sip"), _ready("twelve_data_eod")),
    ).report_sha256


def test_one_unavailable_source_is_degraded_and_cannot_publish() -> None:
    result = assess_multisource_daily_bars(
        _policy(),
        (
            _ready("alpaca_sip"),
            DailyBarSourceObservation(
                "twelve_data_eod",
                SOURCE_OBSERVATION_UNAVAILABLE,
                reason_codes=("provider_auth_or_entitlement",),
            ),
        ),
    )

    assert result.status == DATA_ASSURANCE_STATUS_DEGRADED
    assert not result.can_publish_research_input
    assert result.findings == ("required_source_unavailable", "minimum_ready_sources_not_met")
    assert result.to_diagnostic()["source_reason_codes"] == {
        "twelve_data_eod": ["provider_auth_or_entitlement"]
    }


def test_price_divergence_prevents_a_silent_fallback() -> None:
    result = assess_multisource_daily_bars(
        _policy(),
        (_ready("alpaca_sip"), _ready("twelve_data_eod", close=101.0)),
    )

    assert result.status == DATA_ASSURANCE_STATUS_DEGRADED
    assert result.findings == ("daily_bar_price_divergence",)
    assert not result.can_publish_research_input


def test_adjustment_basis_mismatch_is_not_merged() -> None:
    result = assess_multisource_daily_bars(
        _policy(),
        (_ready("alpaca_sip"), _ready("twelve_data_eod", adjustment_basis="raw")),
    )

    assert result.status == DATA_ASSURANCE_STATUS_DEGRADED
    assert result.findings == ("source_snapshot_policy_mismatch", "minimum_ready_sources_not_met")


def test_policy_requires_at_least_two_independent_sources() -> None:
    with pytest.raises(ValueError, match="at least two"):
        MultiSourceDailyBarPolicy(
            scope_id="us-equity:soxl-daily",
            symbol="SOXL",
            date_cutoff="2026-08-21",
            adjustment_basis="total_return_adjusted",
            required_source_ids=("alpaca_sip",),
            minimum_ready_sources=1,
        )
