import copy

import pytest

from quant_platform_kit.common.account_domain import account_domain_key, validate_account_domain
from quant_platform_kit.common.runtime_target import build_runtime_target


def domain():
    return {
        "identity": {"environment": "DEMO", "platform_id": "mt5", "server": "test", "account_id_fingerprint": "sha256:" + "1" * 64, "lifecycle_id": "one"},
        "policy": {"capital_kind": "FTMO_SIMULATED", "product": "FTMO_CFD_2_STEP", "phase": "FREE_TRIAL", "account_type": "STANDARD", "style": "INTRADAY", "preference": "CAPITAL_PRESERVATION", "currency": "USD", "source": "synthetic", "effective_at": "2026-10-29T00:00:00Z", "valid_until": "2026-11-12T00:00:00Z", "version": "one"},
    }


def test_policy_version_does_not_change_identity_key():
    original = domain()
    changed = copy.deepcopy(original)
    changed["policy"]["version"] = "two"
    assert account_domain_key(original) == account_domain_key(changed)
    changed["identity"]["lifecycle_id"] = "two"
    assert account_domain_key(original) != account_domain_key(changed)


def test_domain_is_optional_and_validated_when_present():
    old = build_runtime_target(platform_id="mt5", strategy_profile="demo", dry_run_only=True)
    assert "account_domain" not in old.to_dict()
    target = build_runtime_target(platform_id="mt5", strategy_profile="demo", dry_run_only=True, account_domain=domain())
    assert target.to_dict()["account_domain"] == domain()
    bad = domain()
    bad["policy"]["phase"] = "LIVE"
    with pytest.raises(ValueError):
        validate_account_domain(bad)
    bad = domain()
    bad["policy"]["effective_at"] = "2026-10-29T00:00:00"
    with pytest.raises(ValueError):
        validate_account_domain(bad)


def test_domain_requires_independent_matching_broker_facts():
    from quant_platform_kit.common.account_domain import account_domain_matches_broker_identity
    from quant_platform_kit.common.account_identity import BrokerAccountIdentity

    observed = BrokerAccountIdentity(platform_id="mt5", account_types=("STANDARD",), account_modes=("DEMO",), account_id_fingerprint="sha256:" + "1" * 64)
    assert account_domain_matches_broker_identity(domain(), observed, observed_environment="DEMO", observed_server="test", observed_currency="USD", observed_lifecycle_id="one")
    changed = domain()
    changed["policy"]["account_type"] = "SWING"
    assert not account_domain_matches_broker_identity(changed, observed, observed_environment="DEMO", observed_server="test", observed_currency="USD", observed_lifecycle_id="one")
    assert not account_domain_matches_broker_identity(domain(), None)


def test_policy_validity_is_bounded_by_explicit_utc_time():
    from quant_platform_kit.common.account_domain import account_domain_policy_active
    assert account_domain_policy_active(domain(), as_of="2026-10-30T00:00:00Z")
    assert not account_domain_policy_active(domain(), as_of="2026-11-12T00:00:00Z")
    with pytest.raises(ValueError):
        account_domain_policy_active(domain(), as_of="2026-10-30T00:00:00")


def test_domain_rejects_contradictory_modes_and_execution_environment():
    from quant_platform_kit.common.account_domain import account_domain_matches_broker_identity
    from quant_platform_kit.common.account_identity import BrokerAccountIdentity
    common = dict(observed_environment="DEMO", observed_server="test", observed_currency="USD", observed_lifecycle_id="one")
    both = BrokerAccountIdentity(platform_id="mt5", account_types=("STANDARD", "SWING"), account_modes=("DEMO",), account_id_fingerprint="sha256:" + "1" * 64)
    wrong_mode = BrokerAccountIdentity(platform_id="mt5", account_types=("STANDARD",), account_modes=("LIVE",), account_id_fingerprint="sha256:" + "1" * 64)
    assert not account_domain_matches_broker_identity(domain(), both, **common)
    assert not account_domain_matches_broker_identity(domain(), wrong_mode, **common)
    with pytest.raises(ValueError):
        build_runtime_target(platform_id="mt5", strategy_profile="demo", dry_run_only=False, execution_environment="live", account_domain=domain())
    assert build_runtime_target(platform_id="mt5", strategy_profile="demo", dry_run_only=False, execution_environment="paper", account_domain=domain())
