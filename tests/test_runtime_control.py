"""Tests for the typed runtime-control contract (library only, not runtime-wired)."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from quant_platform_kit.common.runtime_control import (
    CashPolicy,
    RuntimeControl,
    RuntimeControlError,
    RuntimeMode,
    TighteningOverride,
    parse_optional_strict_bool,
    parse_strict_bool,
    resolve_runtime_control,
    resolve_runtime_control_from_env,
)

SCHEMA = json.loads(
    (Path(__file__).resolve().parents[1] / "schemas" / "runtime-control.v1.schema.json").read_text()
)
IDENT = {"target_id": "example/live", "platform_id": "example", "strategy_profile": "example_profile"}


def _document(**changes):
    payload = {
        "schema_version": "qsl.runtime_control.v1",
        **IDENT,
        "enabled": True,
        "mode": "live",
        "cash_policy": {"cash_only": True, "reserved_cash_ratio": 0.03, "reserved_cash_floor_usd": 0},
        "risk_limits_ref": "example_profile/2026-01-01",
    }
    payload.update(changes)
    return payload


@pytest.mark.parametrize("raw", ["", " ", "ture", "enabled", "2", None])
def test_strict_bool_rejects_empty_and_typos(raw):
    with pytest.raises(RuntimeControlError):
        parse_strict_bool(raw, name="FLAG")


@pytest.mark.parametrize("raw,expected", [("true", True), (" YES ", True), ("0", False), (False, False)])
def test_strict_bool_accepts_known_values(raw, expected):
    assert parse_strict_bool(raw, name="FLAG") is expected


def test_optional_strict_bool_unset_is_none():
    assert parse_optional_strict_bool(None, name="FLAG") is None
    assert parse_optional_strict_bool("  ", name="FLAG") is None
    with pytest.raises(RuntimeControlError):
        parse_optional_strict_bool("maybe", name="FLAG")


def test_safe_default_is_fail_closed():
    control = RuntimeControl.safe_default(**IDENT)
    assert control.enabled is False
    assert control.mode is RuntimeMode.DRY_RUN
    assert control.cash_policy.cash_only is True
    assert control.may_submit_live_orders is False


def test_document_round_trip_matches_schema():
    control = RuntimeControl.from_mapping(_document())
    payload = control.to_dict()
    jsonschema.validate(payload, SCHEMA)
    assert RuntimeControl.from_mapping(payload) == control
    assert control.may_submit_live_orders is True


@pytest.mark.parametrize(
    "changes",
    [
        {"mode": "LIVE!"},
        {"enabled": "ture"},
        {"cash_policy": {"cash_only": True, "reserved_cash_ratio": 1.5}},
        {"cash_policy": {"cash_only": True, "reserved_cash_ratio": 0.03, "extra": 1}},
        {"unexpected": True},
        {"schema_version": "qsl.runtime_control.v0"},
        {"target_id": ""},
    ],
)
def test_malformed_documents_raise(changes):
    with pytest.raises(RuntimeControlError):
        RuntimeControl.from_mapping(_document(**changes))


def test_document_must_match_target_identity():
    with pytest.raises(RuntimeControlError, match="strategy_profile"):
        resolve_runtime_control(**{**IDENT, "strategy_profile": "other"}, document=_document())


def test_no_document_resolves_to_safe_default():
    assert resolve_runtime_control(**IDENT) == RuntimeControl.safe_default(**IDENT)


def test_overrides_only_tighten():
    base = RuntimeControl.from_mapping(_document())
    tightened = TighteningOverride(
        enabled=False, mode=RuntimeMode.PAPER, cash_only=True, reserved_cash_ratio=0.05
    ).apply(base)
    assert tightened.enabled is False
    assert tightened.mode is RuntimeMode.PAPER
    assert tightened.cash_policy.reserved_cash_ratio == 0.05

    disabled_dry = RuntimeControl.safe_default(**IDENT)
    with pytest.raises(RuntimeControlError, match="cannot enable"):
        TighteningOverride(enabled=True).apply(disabled_dry)
    with pytest.raises(RuntimeControlError, match="cannot move mode"):
        TighteningOverride(mode=RuntimeMode.LIVE).apply(disabled_dry)
    with pytest.raises(RuntimeControlError, match="cash-only"):
        TighteningOverride(cash_only=False).apply(base)
    with pytest.raises(RuntimeControlError, match="lower the reserved"):
        TighteningOverride(reserved_cash_ratio=0.01).apply(base)


def test_env_resolution_with_emergency_brakes():
    env = {"RUNTIME_CONTROL_JSON": json.dumps(_document())}
    assert resolve_runtime_control_from_env(env, **IDENT).may_submit_live_orders is True

    braked = resolve_runtime_control_from_env({**env, "RUNTIME_TARGET_ENABLED": "false"}, **IDENT)
    assert braked.enabled is False

    # "true" never re-enables a document that is disabled.
    disabled = {"RUNTIME_CONTROL_JSON": json.dumps(_document(enabled=False))}
    assert resolve_runtime_control_from_env({**disabled, "RUNTIME_TARGET_ENABLED": "true"}, **IDENT).enabled is False

    paper = resolve_runtime_control_from_env({**env, "RUNTIME_CONTROL_MODE_OVERRIDE": "dry_run"}, **IDENT)
    assert paper.mode is RuntimeMode.DRY_RUN

    with pytest.raises(RuntimeControlError):
        resolve_runtime_control_from_env({**env, "RUNTIME_TARGET_ENABLED": "ture"}, **IDENT)
    with pytest.raises(RuntimeControlError):
        resolve_runtime_control_from_env({"RUNTIME_CONTROL_JSON": "{"}, **IDENT)
    assert resolve_runtime_control_from_env({}, **IDENT) == RuntimeControl.safe_default(**IDENT)


def test_cash_policy_can_only_raise_strategy_reserve():
    policy = CashPolicy(cash_only=True, reserved_cash_ratio=0.01, reserved_cash_floor_usd=150.0)
    assert policy.effective_reserve_ratio(0.03) == 0.03
    assert policy.effective_reserve_ratio(0.0) == 0.01
    assert policy.reserved_cash_usd(1000.0, strategy_default_ratio=0.03) == 150.0
    assert policy.reserved_cash_usd(100000.0, strategy_default_ratio=0.03) == pytest.approx(3000.0)
    with pytest.raises(RuntimeControlError):
        CashPolicy(cash_only="yes")
