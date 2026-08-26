from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from quant_platform_kit.common.capital_base import (
    CapitalBaseBinding,
    CapitalBaseFinding,
    CapitalBaseSnapshot,
    validate_capital_base,
)


NOW = datetime(2026, 8, 27, 10, 0, tzinfo=timezone.utc)


def _binding(**overrides: object) -> CapitalBaseBinding:
    values: dict[str, object] = {
        "account_scope": "broker-account-a",
        "runtime_scope": "us-equity-live-a",
        "strategy_scope": "soxl_soxx_trend_income",
        "target_currency": "USD",
        "max_age_seconds": 300.0,
    }
    values.update(overrides)
    return CapitalBaseBinding(**values)  # type: ignore[arg-type]


def _snapshot(**overrides: object) -> CapitalBaseSnapshot:
    values: dict[str, object] = {
        "reported_equity": 100_000.0,
        "reported_currency": "USD",
        "target_currency": "USD",
        "fx_rate_to_target": 1.0,
        "as_of": NOW - timedelta(seconds=30),
        "account_scope": "broker-account-a",
        "runtime_scope": "us-equity-live-a",
        "strategy_scope": "soxl_soxx_trend_income",
        "source_digest_sha256": "a" * 64,
    }
    values.update(overrides)
    return CapitalBaseSnapshot(**values)  # type: ignore[arg-type]


def test_validates_fresh_same_scope_base_and_redacts_scope_material() -> None:
    result = validate_capital_base(_snapshot(), binding=_binding(), now=NOW)

    assert result.is_valid
    assert result.target_equity == 100_000.0
    safe = result.to_safe_dict()
    assert safe["findings"] == []
    assert "broker-account-a" not in repr(safe)
    assert safe["snapshot"] == {
        "contract_version": "qpk.capital_base.v1",
        "as_of": "2026-08-27T09:59:30Z",
        "reported_currency": "USD",
        "target_currency": "USD",
        "fx_applied": False,
        "source_digest_sha256": "a" * 64,
        "fx_source_digest_sha256": None,
        "scope_digest_sha256": _binding().scope_digest_sha256,
    }


@pytest.mark.parametrize(
    ("snapshot_overrides", "binding_overrides", "finding"),
    (
        ({"account_scope": "broker-account-b"}, {}, CapitalBaseFinding.ACCOUNT_SCOPE_MISMATCH.value),
        ({"runtime_scope": "us-equity-live-b"}, {}, CapitalBaseFinding.RUNTIME_SCOPE_MISMATCH.value),
        ({"strategy_scope": "tqqq_growth_income"}, {}, CapitalBaseFinding.STRATEGY_SCOPE_MISMATCH.value),
        ({}, {"target_currency": "USDT"}, CapitalBaseFinding.TARGET_CURRENCY_MISMATCH.value),
    ),
)
def test_scope_and_currency_mismatches_fail_closed(
    snapshot_overrides: dict[str, object],
    binding_overrides: dict[str, object],
    finding: str,
) -> None:
    result = validate_capital_base(
        _snapshot(**snapshot_overrides),
        binding=_binding(**binding_overrides),
        now=NOW,
    )

    assert not result.is_valid
    assert result.findings == (finding,)
    assert result.target_equity is None


@pytest.mark.parametrize(
    ("as_of", "finding"),
    (
        (NOW - timedelta(seconds=301), CapitalBaseFinding.STALE.value),
        (NOW + timedelta(seconds=1), CapitalBaseFinding.FUTURE.value),
    ),
)
def test_freshness_is_an_explicit_admission_requirement(as_of: datetime, finding: str) -> None:
    result = validate_capital_base(_snapshot(as_of=as_of), binding=_binding(), now=NOW)

    assert not result.is_valid
    assert result.findings == (finding,)


def test_fx_conversion_requires_its_own_digest_and_scales_the_denominator() -> None:
    with pytest.raises(ValueError, match="fx_source_digest_sha256"):
        _snapshot(
            reported_currency="HKD",
            target_currency="USD",
            fx_rate_to_target=0.128,
        )

    result = validate_capital_base(
        _snapshot(
            reported_equity=780_000.0,
            reported_currency="HKD",
            target_currency="USD",
            fx_rate_to_target=0.128,
            fx_source_digest_sha256="b" * 64,
        ),
        binding=_binding(),
        now=NOW,
    )

    assert result.is_valid
    assert result.target_equity == 99_840.0


@pytest.mark.parametrize("reported_equity", (0.0, -1.0, float("inf"), True))
def test_invalid_or_zero_denominators_cannot_be_constructed(reported_equity: object) -> None:
    with pytest.raises(ValueError, match="reported_equity"):
        _snapshot(reported_equity=reported_equity)


def test_missing_or_untrusted_mapping_fails_closed() -> None:
    missing = validate_capital_base(None, binding=_binding(), now=NOW)
    unknown = validate_capital_base(
        {"unexpected": "field"},
        binding=_binding(),
        now=NOW,
    )

    assert missing.findings == (CapitalBaseFinding.MISSING.value,)
    assert unknown.findings == (CapitalBaseFinding.INVALID.value,)


def test_scale_metamorphism_preserves_normalized_value_target_weight() -> None:
    base = validate_capital_base(_snapshot(reported_equity=100_000.0), binding=_binding(), now=NOW)
    scaled = validate_capital_base(_snapshot(reported_equity=250_000.0), binding=_binding(), now=NOW)

    assert base.target_equity is not None
    assert scaled.target_equity is not None
    assert 10_000.0 / base.target_equity == 25_000.0 / scaled.target_equity
