"""Offline migration checks; these helpers never enable a runtime."""

import copy

import pytest

from quant_platform_kit.common.runtime_control import RuntimeControl, RuntimeControlError
from quant_platform_kit.common.runtime_control_checks import validate_dry_run_consistency


FLAG = "EXAMPLE_DRY_RUN_ONLY"
IDENT = {"target_id": "example/test", "platform_id": "example", "strategy_profile": "example_profile"}


@pytest.mark.parametrize("declared", [True, False])
@pytest.mark.parametrize("name", [FLAG, "QSL_" + FLAG])
def test_matching_explicit_flags(declared, name):
    assert validate_dry_run_consistency(
        declared_dry_run_only=declared, env={name: str(declared)}, flag_name=FLAG
    ) is declared


def test_missing_env_defaults_to_dry_run():
    assert validate_dry_run_consistency(declared_dry_run_only=True, env={}, flag_name=FLAG) is True
    with pytest.raises(RuntimeControlError, match="disagrees"):
        validate_dry_run_consistency(declared_dry_run_only=False, env={}, flag_name=FLAG)


@pytest.mark.parametrize("declared,raw", [(True, "false"), (False, "true")])
def test_target_and_env_disagreement_is_rejected(declared, raw):
    with pytest.raises(RuntimeControlError, match="disagrees"):
        validate_dry_run_consistency(declared_dry_run_only=declared, env={FLAG: raw}, flag_name=FLAG)


def test_alias_disagreement_cannot_be_hidden_by_precedence():
    with pytest.raises(RuntimeControlError, match="aliases disagree"):
        validate_dry_run_consistency(
            declared_dry_run_only=True, env={FLAG: "false", "QSL_" + FLAG: "true"}, flag_name=FLAG
        )


def test_matching_aliases_accept_existing_boolean_spellings():
    assert validate_dry_run_consistency(
        declared_dry_run_only=True, env={FLAG: " yes ", "QSL_" + FLAG: "1"}, flag_name=FLAG
    ) is True


@pytest.mark.parametrize("raw", ["", " ", "ture", "enabled", "2", None, [], {}])
@pytest.mark.parametrize("name", [FLAG, "QSL_" + FLAG])
def test_explicit_empty_or_malformed_flags_raise(raw, name):
    with pytest.raises(RuntimeControlError):
        validate_dry_run_consistency(declared_dry_run_only=True, env={name: raw}, flag_name=FLAG)


@pytest.mark.parametrize("declared", [None, "true", 1, 0, [], {}])
def test_target_requires_an_actual_boolean(declared):
    with pytest.raises(RuntimeControlError, match="must be a bool"):
        validate_dry_run_consistency(declared_dry_run_only=declared, env={}, flag_name=FLAG)


@pytest.mark.parametrize("mode,declared", [("dry_run", True), ("paper", False), ("live", False)])
def test_control_mode_distinguishes_paper_from_dry_run(mode, declared):
    control = RuntimeControl.from_mapping({**IDENT, "mode": mode})
    assert validate_dry_run_consistency(
        declared_dry_run_only=declared, env={FLAG: str(declared)}, flag_name=FLAG, control=control
    ) is declared


@pytest.mark.parametrize("mode,declared", [("dry_run", False), ("paper", True), ("live", True)])
def test_control_mode_must_also_agree(mode, declared):
    control = RuntimeControl.from_mapping({**IDENT, "mode": mode})
    with pytest.raises(RuntimeControlError, match="RuntimeControl.mode"):
        validate_dry_run_consistency(
            declared_dry_run_only=declared, env={FLAG: str(declared)}, flag_name=FLAG, control=control
        )


@pytest.mark.parametrize("name", ["", " ", "QSL_EXAMPLE_DRY_RUN_ONLY", "BAD-NAME", None])
def test_flag_name_must_be_an_unprefixed_env_name(name):
    with pytest.raises(RuntimeControlError, match="flag_name"):
        validate_dry_run_consistency(declared_dry_run_only=True, env={}, flag_name=name)


def test_only_explicit_inputs_are_used_and_nothing_is_mutated(monkeypatch):
    monkeypatch.setenv(FLAG, "false")
    env = {FLAG: "true", "UNRELATED": "ignored"}
    before = copy.deepcopy(env)
    control = RuntimeControl.safe_default(**IDENT)
    assert validate_dry_run_consistency(
        declared_dry_run_only=True, env=env, flag_name=FLAG, control=control
    ) is True
    assert env == before
    assert control == RuntimeControl.safe_default(**IDENT)
