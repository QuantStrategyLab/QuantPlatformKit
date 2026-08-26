from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from quant_platform_kit.common.capital_base import (
    CapitalBaseBinding,
    CapitalBaseFinding,
    CapitalBaseSnapshot,
    CapitalScope,
    CapitalValuationBasis,
    build_capital_base_snapshot,
    validate_capital_base,
)
from quant_platform_kit.common.models import PortfolioSnapshot


NOW = datetime(2026, 8, 27, 10, 0, tzinfo=timezone.utc)


def _binding(**overrides: object) -> CapitalBaseBinding:
    values: dict[str, object] = {
        "account_scope": "broker-account-a",
        "runtime_scope": "us-equity-live-a",
        "strategy_scope": "soxl_soxx_trend_income",
        "target_currency": "USD",
        "capital_scope": CapitalScope.ACCOUNT,
        "valuation_basis": CapitalValuationBasis.BROKER_ACCOUNT_NET_LIQUIDATION,
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
        "capital_scope": CapitalScope.ACCOUNT,
        "valuation_basis": CapitalValuationBasis.BROKER_ACCOUNT_NET_LIQUIDATION,
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
        "contract_version": "qpk.capital_base.v2",
        "as_of": "2026-08-27T09:59:30Z",
        "reported_currency": "USD",
        "target_currency": "USD",
        "capital_scope": "account",
        "valuation_basis": "broker_account_net_liquidation",
        "allocation_scope_digest_sha256": None,
        "component_coverage_digest_sha256": None,
        "fx_applied": False,
        "source_digest_sha256": "a" * 64,
        "fx_source_digest_sha256": None,
        "scope_digest_sha256": _binding().scope_digest_sha256,
    }


def test_build_adapter_uses_only_canonical_snapshot_values_and_explicit_evidence() -> None:
    portfolio_snapshot = PortfolioSnapshot(
        as_of=NOW - timedelta(seconds=30),
        total_equity=100_000.0,
        metadata={
            "account_scope": "untrusted-metadata-account",
            "currency": "USDT",
            "source_digest_sha256": "f" * 64,
        },
    )

    adapted = build_capital_base_snapshot(
        portfolio_snapshot,
        account_scope="broker-account-a",
        runtime_scope="us-equity-live-a",
        strategy_scope="soxl_soxx_trend_income",
        reported_currency="USD",
        target_currency="USD",
        fx_rate_to_target=1.0,
        source_digest_sha256="a" * 64,
        capital_scope=CapitalScope.ACCOUNT,
        valuation_basis=CapitalValuationBasis.BROKER_ACCOUNT_NET_LIQUIDATION,
    )

    assert adapted.reported_equity == portfolio_snapshot.total_equity
    assert adapted.as_of == portfolio_snapshot.as_of
    assert adapted.account_scope == "broker-account-a"
    assert adapted.reported_currency == "USD"
    assert adapted.source_digest_sha256 == "a" * 64
    assert validate_capital_base(adapted, binding=_binding(), now=NOW).is_valid


def test_build_adapter_does_not_accept_platform_shaped_or_missing_evidence() -> None:
    with pytest.raises(TypeError, match="PortfolioSnapshot"):
        build_capital_base_snapshot(
            {"total_equity": 100_000.0, "as_of": NOW},  # type: ignore[arg-type]
            account_scope="broker-account-a",
            runtime_scope="us-equity-live-a",
            strategy_scope="soxl_soxx_trend_income",
            reported_currency="USD",
            target_currency="USD",
            fx_rate_to_target=1.0,
            source_digest_sha256="a" * 64,
            capital_scope=CapitalScope.ACCOUNT,
            valuation_basis=CapitalValuationBasis.BROKER_ACCOUNT_NET_LIQUIDATION,
        )

    snapshot = PortfolioSnapshot(as_of=NOW, total_equity=100_000.0)
    with pytest.raises(ValueError, match="source_digest_sha256"):
        build_capital_base_snapshot(
            snapshot,
            account_scope="broker-account-a",
            runtime_scope="us-equity-live-a",
            strategy_scope="soxl_soxx_trend_income",
            reported_currency="USD",
            target_currency="USD",
            fx_rate_to_target=1.0,
            source_digest_sha256="",
            capital_scope=CapitalScope.ACCOUNT,
            valuation_basis=CapitalValuationBasis.BROKER_ACCOUNT_NET_LIQUIDATION,
        )


def test_capital_scope_and_valuation_basis_are_strictly_bound() -> None:
    full_account_binding = _binding(
        valuation_basis=CapitalValuationBasis.FULL_ACCOUNT_MARK_TO_MARKET,
    )
    full_account = _snapshot(
        valuation_basis=CapitalValuationBasis.FULL_ACCOUNT_MARK_TO_MARKET,
        component_coverage_digest_sha256="c" * 64,
    )

    assert validate_capital_base(full_account, binding=full_account_binding, now=NOW).is_valid

    with pytest.raises(ValueError, match="requires component_coverage"):
        _snapshot(valuation_basis=CapitalValuationBasis.FULL_ACCOUNT_MARK_TO_MARKET)
    with pytest.raises(ValueError, match="must not set allocation_scope"):
        _snapshot(allocation_scope="shared-cash-ledger")


def test_allocated_sleeve_requires_an_explicit_ledger_and_coverage() -> None:
    binding = _binding(
        capital_scope=CapitalScope.ALLOCATED_SLEEVE,
        valuation_basis=CapitalValuationBasis.ALLOCATED_SLEEVE_LEDGER,
        allocation_scope="sleeve-ledger-a",
    )
    snapshot = _snapshot(
        capital_scope=CapitalScope.ALLOCATED_SLEEVE,
        valuation_basis=CapitalValuationBasis.ALLOCATED_SLEEVE_LEDGER,
        allocation_scope="sleeve-ledger-a",
        component_coverage_digest_sha256="b" * 64,
    )

    assert validate_capital_base(snapshot, binding=binding, now=NOW).is_valid
    mismatch = validate_capital_base(
        _snapshot(
            capital_scope=CapitalScope.ALLOCATED_SLEEVE,
            valuation_basis=CapitalValuationBasis.ALLOCATED_SLEEVE_LEDGER,
            allocation_scope="sleeve-ledger-b",
            component_coverage_digest_sha256="b" * 64,
        ),
        binding=binding,
        now=NOW,
    )
    assert mismatch.findings == (CapitalBaseFinding.ALLOCATION_SCOPE_MISMATCH.value,)

    with pytest.raises(ValueError, match="allocated_sleeve requires allocation_scope"):
        _snapshot(
            capital_scope=CapitalScope.ALLOCATED_SLEEVE,
            valuation_basis=CapitalValuationBasis.ALLOCATED_SLEEVE_LEDGER,
            component_coverage_digest_sha256="b" * 64,
        )


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


def test_v1_shape_remains_readable_but_never_admits_strict_value_targets() -> None:
    legacy_snapshot = CapitalBaseSnapshot(
        reported_equity=100_000.0,
        reported_currency="USD",
        target_currency="USD",
        fx_rate_to_target=1.0,
        as_of=NOW - timedelta(seconds=30),
        account_scope="broker-account-a",
        runtime_scope="us-equity-live-a",
        strategy_scope="soxl_soxx_trend_income",
        source_digest_sha256="a" * 64,
    )
    legacy_binding = CapitalBaseBinding(
        account_scope="broker-account-a",
        runtime_scope="us-equity-live-a",
        strategy_scope="soxl_soxx_trend_income",
        target_currency="USD",
    )

    result = validate_capital_base(legacy_snapshot, binding=legacy_binding, now=NOW)

    assert legacy_snapshot.contract_version == "qpk.capital_base.v1"
    assert result.findings == (CapitalBaseFinding.LEGACY_CONTRACT.value,)


def test_scale_metamorphism_preserves_normalized_value_target_weight() -> None:
    base = validate_capital_base(_snapshot(reported_equity=100_000.0), binding=_binding(), now=NOW)
    scaled = validate_capital_base(_snapshot(reported_equity=250_000.0), binding=_binding(), now=NOW)

    assert base.target_equity is not None
    assert scaled.target_equity is not None
    assert 10_000.0 / base.target_equity == 25_000.0 / scaled.target_equity
