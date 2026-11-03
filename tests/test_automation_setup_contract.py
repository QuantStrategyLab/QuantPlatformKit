"""Synthetic, offline contract checks; no authentic authority is simulated."""
import copy
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from quant_platform_kit.common.automation_setup import SetupIntent, classify_setup_intent

FORMAT_CHECKER = FormatChecker()
assert 'date-time' in FORMAT_CHECKER.checkers


def decision_schema_validator():
    schema = json.loads((Path(__file__).parents[1] / 'src/quant_platform_kit/schemas/automation-setup-intent.v1.schema.json').read_text())
    return Draft202012Validator(schema, format_checker=FORMAT_CHECKER)


NOW = datetime(2026, 11, 3, tzinfo=timezone.utc)
REF = '00000000-0000-4000-8000-000000000001'


def subject():
    release = dict(release_id='fake-release', strategy_revision='fake-revision', effective_session='2026-11-01',
                   **{k: 'a' * 64 for k in ('manifest_sha256', 'config_sha256', 'risk_policy_sha256', 'evidence_sha256', 'plugin_bundle_sha256')})
    return dict(setup_id=REF, revision=1, predecessor_sha256=None, account_refs=[REF],
                target=dict(platform_id='fake-platform', strategy_profile='fake-profile', dry_run_only=True,
                            execution_environment='dry_run', strategy_release=release),
                control=dict(target_id=REF, platform_id='fake-platform', strategy_profile='fake-profile',
                             enabled=False, mode='dry_run', risk_limits_ref=REF, cash_policy={}),
                currency='USD', amount='100.00', cap='100.00', amount_basis='one_time', plan_ref=None,
                fee_treatment='included', reserve_treatment='outside_amount', instruments=['FAKE'],
                actions=['rebalance'], policy_ref=REF, paper_min_sessions=5)


def intent(decision=True, **changes):
    s = subject(); s.update(changes)
    obj = SetupIntent.create(s)
    if not decision:
        return obj
    d = dict(decision_ref=REF, subject_sha256=obj.subject_sha256, revision=s['revision'],
             actor_ref=REF, actor_type='human', outcome='confirmed', reviewed_at='2026-11-01T00:00:00Z',
             effective_at='2026-11-02T00:00:00Z', expires_at='2026-12-01T00:00:00Z', state_version=1, epoch=REF)
    return SetupIntent.create(s, d)


def snapshot(obj):
    return dict(setup_id=REF, revision=obj.to_dict()['subject']['revision'], subject_sha256=obj.subject_sha256,
                state_version=1, epoch=REF, decision_ref=REF, status='current', source_ref=REF,
                checked_at='2026-11-03T00:00:00Z', valid_until='2026-11-04T00:00:00Z',
                prerequisites={k: 'unknown' for k in ('paper', 'risk_release', 'reconciliation', 'alerts')},
                activation_readback='unknown')


def classify(obj, current=None):
    return classify_setup_intent(obj, now=NOW, current=snapshot(obj) if current is None else current)


def test_roundtrip_and_routine_no_reapproval():
    obj = intent(); encoded = obj.to_dict()
    assert SetupIntent.from_dict(encoded).to_dict() == encoded
    for _ in range(3):
        p = classify(obj)
        assert p['intent_status'] == 'confirmed_intent'
        assert p['requires_owner_setup'] is False
        assert p['grants_live'] is p['grants_execution_authority'] is False
        assert 'PAPER_EVIDENCE_UNQUALIFIED' in p['blocker_codes']
    encoded['subject']['account_refs'].append(REF)
    assert len(obj.to_dict()['subject']['account_refs']) == 1


@pytest.mark.parametrize('value', [None, True, '3', 3.0, 2, 6])
def test_invalid_paper_requirement(value):
    with pytest.raises(ValueError): intent(paper_min_sessions=value)


@pytest.mark.parametrize('value', [3, 4, 5])
def test_requirement_is_not_qualification(value):
    assert 'PAPER_EVIDENCE_UNQUALIFIED' in classify(intent(paper_min_sessions=value))['blocker_codes']


@pytest.mark.parametrize('value', [True, 100, 1.5, '-1', 'NaN', 'Infinity', '1e2', ' 1', '01'])
def test_exact_decimal_only(value):
    with pytest.raises(ValueError): intent(amount=value)


@pytest.mark.parametrize('field,value', [('amount', '99'), ('account_refs', ['00000000-0000-4000-8000-000000000002']),
                                        ('instruments', ['OTHER']), ('policy_ref', '00000000-0000-4000-8000-000000000002'),
                                        ('plan_ref', REF)])
def test_scope_changes_invalidate_decision(field, value):
    old = intent(); new = old.to_dict(); new['subject'][field] = value
    with pytest.raises(ValueError): SetupIntent.from_dict(new)
    p = classify_setup_intent(old, now=NOW, current=snapshot(old), proposed_subject=new['subject'])
    assert field in p['changed_fields']
    assert p['requires_owner_setup']


@pytest.mark.parametrize('key,value,code', [('state_version', 2, 'CURRENT_BINDING_MISMATCH'),
    ('epoch', '00000000-0000-4000-8000-000000000002', 'CURRENT_BINDING_MISMATCH'),
    ('subject_sha256', 'b'*64, 'CURRENT_BINDING_MISMATCH'),
    ('checked_at', '2026-11-04T00:00:00Z', 'CURRENT_SOURCE_UNAVAILABLE'),
    ('valid_until', '2026-11-02T00:00:00Z', 'CURRENT_SOURCE_UNAVAILABLE'),
    ('status', 'revoked', 'REVOKED'), ('status', 'superseded', 'SUPERSEDED')])
def test_current_snapshot_dominates(key, value, code):
    obj = intent(); s = snapshot(obj); s[key] = value
    assert code in classify(obj, s)['blocker_codes']


@pytest.mark.parametrize('field,value', [('effective_at', '2026-11-04T00:00:00Z'),
                                       ('expires_at', '2026-11-02T12:00:00Z'), ('outcome', 'rejected')])
def test_decision_time_and_rejection(field, value):
    data = intent().to_dict(); data['decision'][field] = value
    assert classify(SetupIntent.from_dict(data))['intent_status'] != 'confirmed_intent'


def test_missing_source_and_self_reported_pass_do_not_qualify():
    obj = intent()
    assert classify_setup_intent(obj, now=NOW, current=None)['intent_status'] == 'blocked'
    s = snapshot(obj); s['prerequisites'] = {k: 'pass' for k in s['prerequisites']}
    assert 'PAPER_EVIDENCE_UNQUALIFIED' in classify(obj, s)['blocker_codes']


def test_live_is_owner_needed_only():
    s = subject(); s['target'].update(execution_environment='live', dry_run_only=False)
    s['control']['mode'] = 'live'
    obj = intent(target=s['target'], control=s['control'])
    assert 'LIVE_ACTIVATION_OWNER_NEEDED' in classify(obj)['blocker_codes']
    assert classify(obj)['activation_readback'] == 'unknown'


@pytest.mark.parametrize('field', ['account_selector', 'account_identity', 'host', 'token'])
def test_sensitive_unknown_fields_never_echo(field):
    fake = 'fake-account.example.invalid?token=fake-secret-value'
    s = subject(); s['target'][field] = fake
    with pytest.raises(ValueError) as err: SetupIntent.create(s)
    assert fake not in str(err.value)
    assert err.value.__cause__ is None
    assert fake not in json.dumps(classify(intent()))


def test_reject_unknown_authority_and_tampered_digest():
    for key, value in [('may_submit', True), ('grants_live', True), ('subject_sha256', 'b'*64)]:
        data = intent().to_dict(); data[key] = value
        with pytest.raises(ValueError): SetupIntent.from_dict(data)


def test_disabled_control_explicit_environment_and_bindings():
    for mutate in [lambda s: s['target'].pop('execution_environment'),
                   lambda s: s['control'].update(enabled=True),
                   lambda s: s['control'].update(platform_id='other'),
                   lambda s: s.update(cap='99.00'),
                   lambda s: s.update(amount_basis='standing_plan', plan_ref=None)]:
        s = subject(); mutate(s)
        with pytest.raises(ValueError): SetupIntent.create(s)


def test_schema_matches_serialized_contract():
    schema = json.loads((Path(__file__).parents[1] / 'src/quant_platform_kit/schemas/automation-setup-intent.v1.schema.json').read_text())
    validator = Draft202012Validator(schema)
    assert not list(validator.iter_errors(intent().to_dict()))
    for mutate in [lambda x: x.update(grants_live=True), lambda x: x['subject'].update(may_submit=True),
                   lambda x: x['subject']['target'].update(account_selector=['fake']),
                   lambda x: x['decision'].update(expires_at=None)]:
        data = copy.deepcopy(intent().to_dict()); mutate(data)
        assert list(validator.iter_errors(data))


def test_successor_reconfirmation_and_scope_details():
    old = intent(); s = subject()
    s.update(revision=2, predecessor_sha256=old.subject_sha256, amount_basis='standing_plan', plan_ref=REF)
    s['target'].update(execution_environment='paper', dry_run_only=False)
    s['control']['mode'] = 'paper'
    s['target']['strategy_release']['config_sha256'] = 'b' * 64
    changed = classify_setup_intent(old, now=NOW, current=snapshot(old), proposed_subject=s)
    assert set(changed['changed_fields']) == {'revision', 'predecessor_sha256', 'amount_basis', 'plan_ref', 'target.execution_environment',
        'target.dry_run_only', 'target.strategy_release.config_sha256', 'control.mode'}
    new = SetupIntent.create(s)
    d = old.to_dict()['decision']
    d.update(subject_sha256=new.subject_sha256, revision=2, state_version=2)
    confirmed = SetupIntent.create(s, d)
    current = snapshot(confirmed); current['state_version'] = 2
    assert not classify(confirmed, current)['requires_owner_setup']
    assert classify(confirmed, snapshot(old))['intent_status'] == 'blocked'


@pytest.mark.parametrize('field,value', [('reviewed_at', '2026-11-01T00:00:00'), ('expires_at', None),
    ('state_version', True), ('actor_type', 'bot'), ('actor_ref', 'fake-account.example.invalid')])
def test_invalid_decision_cannot_replay(field, value):
    data = intent().to_dict(); data['decision'][field] = value
    with pytest.raises(ValueError): SetupIntent.from_dict(data)


def test_serialized_and_summary_views_exclude_sensitive_input():
    obj = intent(); fake = 'fake-host.example.invalid?token=fake-secret-value'
    for section, field in [('subject', 'account_refs'), ('decision', 'actor_ref')]:
        data = obj.to_dict()
        data[section][field] = [fake] if field == 'account_refs' else fake
        with pytest.raises(ValueError) as error: SetupIntent.from_dict(data)
        assert fake not in str(error.value)
    assert fake not in json.dumps(obj.to_dict())
    assert 'account_refs' not in classify(obj)
    assert 'actor_ref' not in classify(obj)
    assert fake not in repr(obj)


@pytest.mark.parametrize('field,value', [
    ('cash_only', 0), ('cash_only', 1), ('cash_only', 0.0),
    ('cash_only', 1.0), ('cash_only', None), ('cash_only', 'true'),
    ('effective_session', 20261101), ('effective_session', None),
    ('effective_session', '20261101'), ('effective_session', '2026-W44-7'),
    ('effective_session', '2026-11-01T00:00:00'),
    ('effective_session', '2026-02-30'),
])
def test_invalid_scalar_rejected_before_hashing(field, value, monkeypatch):
    from quant_platform_kit.common import automation_setup

    s = subject()
    if field == 'cash_only':
        s['control']['cash_policy'][field] = value
    else:
        s['target']['strategy_release'][field] = value
    hashed = []
    original = automation_setup._digest

    def track_digest(data):
        hashed.append(data)
        return original(data)

    monkeypatch.setattr(automation_setup, '_digest', track_digest)
    with pytest.raises(ValueError, match='^invalid setup intent$') as error:
        SetupIntent.create(s)
    assert error.value.__cause__ is None
    assert hashed == []


@pytest.mark.parametrize('cash_only', [False, True])
@pytest.mark.parametrize('effective_session', ['2026-11-01', '2024-02-29'])
def test_constructor_scalar_schema_parity(cash_only, effective_session):
    schema = json.loads((Path(__file__).parents[1] / 'src/quant_platform_kit/schemas/automation-setup-intent.v1.schema.json').read_text())
    s = subject()
    s['control']['cash_policy']['cash_only'] = cash_only
    s['target']['strategy_release']['effective_session'] = effective_session
    obj = SetupIntent.create(s)
    encoded = obj.to_dict()
    Draft202012Validator(schema).validate(encoded)
    assert encoded['subject'] == s
    assert SetupIntent.from_dict(encoded).to_dict() == encoded
    assert encoded['grants_live'] is encoded['grants_execution_authority'] is False


@pytest.mark.parametrize('field,value', [
    ('cash_only', 0), ('cash_only', 1), ('effective_session', 20261101),
    ('effective_session', '20261101'), ('effective_session', '2026-W44-7'),
])
def test_schema_invalid_scalars_rejected_on_read(field, value):
    import hashlib

    encoded = intent(decision=False).to_dict()
    s = encoded['subject']
    if field == 'cash_only':
        s['control']['cash_policy'][field] = value
    else:
        s['target']['strategy_release'][field] = value
    encoded['subject_sha256'] = hashlib.sha256(
        json.dumps(s, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    ).hexdigest()
    with pytest.raises(ValueError, match='^invalid setup intent$'):
        SetupIntent.from_dict(encoded)


@pytest.mark.parametrize('field', ['reviewed_at', 'effective_at', 'expires_at'])
@pytest.mark.parametrize('path', ['create', 'read'])
@pytest.mark.parametrize('suffix', ['+0000', '', '+00', '+00:00:00'])
def test_schema_invalid_decision_timestamp_rejected(field, path, suffix):
    schema = json.loads((Path(__file__).parents[1] / 'src/quant_platform_kit/schemas/automation-setup-intent.v1.schema.json').read_text())
    encoded = intent().to_dict()
    value = encoded['decision'][field][:-1] + suffix
    encoded['decision'][field] = value
    assert list(Draft202012Validator(schema).iter_errors(encoded))
    with pytest.raises(ValueError, match='^invalid setup intent$') as error:
        if path == 'create':
            SetupIntent.create(encoded['subject'], encoded['decision'])
        else:
            SetupIntent.from_dict(encoded)
    assert value not in str(error.value)
    assert error.value.__cause__ is None


@pytest.mark.parametrize('field', ['reviewed_at', 'effective_at', 'expires_at'])
@pytest.mark.parametrize('suffix', ['Z', '+00:00', '+01:00', '-04:00'])
def test_decision_timestamp_constructor_read_schema_parity(field, suffix):
    encoded = intent().to_dict()
    encoded['decision'][field] = encoded['decision'][field][:-1] + suffix
    validator = decision_schema_validator()
    validator.validate(encoded)
    obj = SetupIntent.create(encoded['subject'], encoded['decision'])
    assert obj.to_dict() == encoded
    validator.validate(obj.to_dict())
    assert SetupIntent.from_dict(encoded).to_dict() == encoded
    assert obj.to_dict()['grants_live'] is obj.to_dict()['grants_execution_authority'] is False


@pytest.mark.parametrize('field', ['reviewed_at', 'effective_at', 'expires_at'])
@pytest.mark.parametrize('path', ['create', 'read'])
@pytest.mark.parametrize('form', [
    'basic_date', 'space_separator', 'missing_seconds', 'week_date',
    'unicode_separator', 'comma_fraction', 'offset_minutes', 'invalid_date',
    'hour_24', 'minute_60', 'second_60', 'offset_hour_24', 'trailing_newline',
])
def test_complete_decision_datetime_rejected(field, path, form):
    encoded = intent().to_dict()
    original = encoded['decision'][field]
    forms = {
        'basic_date': original[:10].replace('-', '') + original[10:],
        'space_separator': original.replace('T', ' '),
        'missing_seconds': original.replace('T00:00:00', 'T00:00'),
        'week_date': '2026-W44-7' + original[10:],
        'unicode_separator': original.replace('T', '\u2603'),
        'comma_fraction': original.replace('00:00:00', '00:00:00,5'),
        'offset_minutes': original[:-1] + '+00:60',
        'invalid_date': '2026-02-30' + original[10:],
        'hour_24': original.replace('T00', 'T24'),
        'minute_60': original.replace('00:00:00', '00:60:00'),
        'second_60': original.replace('00:00:00', '00:00:60'),
        'offset_hour_24': original[:-1] + '+24:00',
        'trailing_newline': original + '\n',
    }
    value = forms[form]
    encoded['decision'][field] = value
    validator = decision_schema_validator()
    errors = list(validator.iter_errors(encoded))
    # rfc3339-validator's end anchor permits a final newline; the boundary must not.
    if form != 'trailing_newline':
        assert errors
        assert not validator.format_checker.conforms(value, 'date-time')
    with pytest.raises(ValueError, match='^invalid setup intent$') as error:
        if path == 'create':
            SetupIntent.create(encoded['subject'], encoded['decision'])
        else:
            SetupIntent.from_dict(encoded)
    assert value not in str(error.value)
    assert error.value.__cause__ is None


def test_datetime_oracle_is_active():
    validator = decision_schema_validator()
    assert 'date-time' in validator.format_checker.checkers
    assert validator.format_checker.conforms('2026-11-01T00:00:00Z', 'date-time')
    assert not validator.format_checker.conforms('20261101T00:00:00Z', 'date-time')
    assert not validator.format_checker.conforms('2026-11-01 00:00:00Z', 'date-time')
    assert not validator.format_checker.conforms('2026-11-01T00:00Z', 'date-time')


@pytest.mark.parametrize('field', ['reviewed_at', 'effective_at', 'expires_at'])
@pytest.mark.parametrize('form', ['fraction', 'lower_t', 'long_fraction', 'fraction_offset'])
def test_complete_decision_datetime_preserves_valid_strings(field, form):
    encoded = intent().to_dict()
    original = encoded['decision'][field]
    encoded['decision'][field] = {
        'fraction': original[:-1] + '.123Z',
        'lower_t': original.replace('T', 't'),
        'long_fraction': original[:-1] + '.123456789Z',
        'fraction_offset': original[:-1] + '.5+01:30',
    }[form]
    validator = decision_schema_validator()
    validator.validate(encoded)
    obj = SetupIntent.create(encoded['subject'], encoded['decision'])
    assert obj.to_dict() == encoded
    validator.validate(obj.to_dict())
    assert SetupIntent.from_dict(encoded).to_dict() == encoded
    assert obj.to_dict()['grants_live'] is obj.to_dict()['grants_execution_authority'] is False


# Format-faithful fake counterpart of the dotted release in test_strategy_release.py.
@pytest.mark.parametrize('field,value', [
    ('release_id', 'fake-p2-v3.20261104'),
    ('release_id', '1' + 'r' * 127),
    ('strategy_revision', '2' + 'a' * 39),
])
def test_existing_release_identity_can_bind_setup(field, value):
    from quant_platform_kit.common.strategy_release import build_strategy_release_identity

    s = subject()
    s['target']['strategy_release'][field] = value
    identity = build_strategy_release_identity(s['target']['strategy_release'])
    assert identity.to_dict()[field] == value
    obj = SetupIntent.create(s)
    assert obj.to_dict()['subject']['target']['strategy_release'][field] == value
    assert not list(decision_schema_validator().iter_errors(obj.to_dict()))
    assert obj.to_dict()['grants_live'] is obj.to_dict()['grants_execution_authority'] is False


@pytest.mark.parametrize('field,value', [
    ('release_id', 'fake-p2-v3.20261104'),
    ('release_id', '1' + 'r' * 127),
    ('strategy_revision', '2' + 'a' * 39),
])
def test_schema_accepts_existing_release_identity(field, value):
    data = intent().to_dict()
    data['subject']['target']['strategy_release'][field] = value
    assert not list(decision_schema_validator().iter_errors(data))


@pytest.mark.parametrize('field,limit', [('release_id', 128), ('strategy_revision', 64)])
@pytest.mark.parametrize('value', ['', ' ', ' fake', 'fake ', 'fake/release',
    r'fake\release', 'fake\n', 'fake\tvalue', 'fake\x00value', 'fake?token=fake', None])
def test_malformed_release_labels_fail_closed(field, limit, value):
    s = subject()
    s['target']['strategy_release'][field] = value
    with pytest.raises(ValueError, match='^invalid setup intent$') as error:
        SetupIntent.create(s)
    assert error.value.__cause__ is None
    data = intent().to_dict()
    data['subject']['target']['strategy_release'][field] = value
    assert list(decision_schema_validator().iter_errors(data))


@pytest.mark.parametrize('field,limit', [('release_id', 128), ('strategy_revision', 64)])
def test_overlength_release_labels_fail_closed(field, limit):
    s = subject()
    s['target']['strategy_release'][field] = 'r' * (limit + 1)
    with pytest.raises(ValueError, match='^invalid setup intent$'):
        SetupIntent.create(s)
    data = intent().to_dict()
    data['subject']['target']['strategy_release'][field] = 'r' * (limit + 1)
    assert list(decision_schema_validator().iter_errors(data))
