"""Immutable owner setup intent. No execution capability or persistence.

Snapshots are injected by the authenticated consumer on every read. This
module cannot authenticate their source and never qualifies Paper evidence.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

from quant_platform_kit.notifications._redaction import redact_sensitive_data, redact_sensitive_text
from .runtime_control import RuntimeControl
from .runtime_target import build_runtime_target
from .strategy_release import build_strategy_release_identity

VERSION = 'automation_setup_intent.v1'
_RESUME = {
    'PROPOSED_SUBJECT_INVALID': 'Supply a valid proposed subject before confirming changed scope.',
    'SUCCESSOR_CONFIRMATION_REQUIRED': 'Record an authenticated owner confirmation for a successor revision bound to every changed field.',
    'OWNER_SETUP_REQUIRED': 'Record one authenticated owner decision bound to the exact accounts, amount and activation scope.',
    'REJECTED': 'Do not retry this rejected decision; a genuinely new scope needs separately authorized setup.',
    'NOT_EFFECTIVE': 'Wait until the recorded effective time and re-read the current decision.',
    'EXPIRED': 'Do not renew or replay this expired decision.',
    'CURRENT_SOURCE_UNAVAILABLE': 'Restore an authenticated readable current snapshot within its checked-at and valid-until interval.',
    'CURRENT_BINDING_MISMATCH': 'Re-read the matching current subject, decision, revision, state version and epoch.',
    'REVOKED': 'Do not reuse this revoked intent.',
    'SUPERSEDED': 'Read the confirmed successor revision; do not reuse this superseded intent.',
    'PAPER_EVIDENCE_UNQUALIFIED': 'The Paper evidence owner must qualify authentic complete-session receipts and any longer candidate window.',
    'RISK_RELEASE_NOT_VERIFIED': 'The risk/release owner must authenticate current evidence bound to the reviewed release and policy.',
    'RECONCILIATION_NOT_VERIFIED': 'The reconciliation owner must authenticate complete current reconciliation evidence.',
    'ALERTS_NOT_VERIFIED': 'The alert owner must authenticate resolution of outstanding blocking alerts.',
    'ACTIVATION_NOT_VERIFIED': 'Obtain separately authorized application evidence and authenticated exact-subject readback.',
    'LIVE_ACTIVATION_OWNER_NEEDED': 'A separate exact owner authorization and protected activation/readback are required.',
}
_SUBJECT = {'setup_id', 'revision', 'predecessor_sha256', 'account_refs', 'target', 'control',
            'currency', 'amount', 'cap', 'amount_basis', 'plan_ref', 'fee_treatment',
            'reserve_treatment', 'instruments', 'actions', 'policy_ref', 'paper_min_sessions'}
_TARGET = {'platform_id', 'strategy_profile', 'dry_run_only', 'execution_environment', 'strategy_release'}
_RELEASE = {'release_id', 'manifest_sha256', 'strategy_revision', 'config_sha256', 'risk_policy_sha256',
            'evidence_sha256', 'plugin_bundle_sha256', 'effective_session'}
_CONTROL = {'target_id', 'platform_id', 'strategy_profile', 'enabled', 'mode', 'risk_limits_ref', 'cash_policy'}
_DECISION = {'decision_ref', 'subject_sha256', 'revision', 'actor_ref', 'actor_type', 'outcome',
             'reviewed_at', 'effective_at', 'expires_at', 'state_version', 'epoch'}
_ENVELOPE = {'schema_version', 'subject', 'subject_sha256', 'decision', 'grants_live', 'grants_execution_authority'}
_CURRENT = {'setup_id', 'revision', 'subject_sha256', 'state_version', 'epoch', 'decision_ref',
            'status', 'source_ref', 'checked_at', 'valid_until', 'prerequisites', 'activation_readback'}


def _require(condition):
    if not condition:
        raise ValueError('invalid setup intent')


def _object(value, fields):
    _require(type(value) is dict and set(value) == fields)


def _integer(value):
    _require(type(value) is int and value > 0)


def _ref(value):
    _require(isinstance(value, str) and str(UUID(value)) == value)


def _sha(value):
    _require(isinstance(value, str) and re.fullmatch('[a-f0-9]{64}', value) is not None)


def _label(value, pattern='[A-Za-z][A-Za-z0-9_-]{0,63}'):
    # Contract labels, never account selectors, URLs, free text or hostnames.
    _require(isinstance(value, str) and re.fullmatch(pattern, value) is not None)
    _require(redact_sensitive_text(value) == value)


def _time(value):
    _require(isinstance(value, str))
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    _require(result.tzinfo is not None and result.utcoffset() is not None)
    return result.astimezone(timezone.utc)


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def _digest(value):
    return hashlib.sha256(_canonical(value).encode()).hexdigest()


def _subject(value):
    _object(value, _SUBJECT)
    _ref(value['setup_id']); _integer(value['revision']); _ref(value['policy_ref'])
    if value['revision'] == 1:
        _require(value['predecessor_sha256'] is None)
    else:
        _sha(value['predecessor_sha256'])
    accounts = value['account_refs']
    _require(type(accounts) is list and len(accounts) > 0 and len(set(accounts)) == len(accounts))
    for ref in accounts: _ref(ref)
    t = value['target']; _object(t, _TARGET)
    for key in ('platform_id', 'strategy_profile'): _label(t[key])
    _require(type(t['dry_run_only']) is bool)
    _require(t['execution_environment'] in ('dry_run', 'paper', 'live'))
    release = t['strategy_release']; _object(release, _RELEASE)
    _label(release['release_id'], '[A-Za-z0-9][A-Za-z0-9._-]{2,127}')
    _label(release['strategy_revision'], '[A-Za-z0-9][A-Za-z0-9._-]{0,63}')
    for key in _RELEASE - {'release_id', 'strategy_revision', 'effective_session'}: _sha(release[key])
    session = release['effective_session']
    _require(isinstance(session, str) and re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}', session) is not None)
    _require(date.fromisoformat(session).isoformat() == session)
    identity = build_strategy_release_identity(release)
    build_runtime_target(**{**t, 'strategy_release': identity})
    c = value['control']; _object(c, _CONTROL)
    _ref(c['target_id']); _ref(c['risk_limits_ref'])
    _require(c['enabled'] is False)
    _require(c['platform_id'] == t['platform_id'] and c['strategy_profile'] == t['strategy_profile'])
    _require(c['mode'] == t['execution_environment'])
    _require(type(c['cash_policy']) is dict and not (set(c['cash_policy']) - {
        'cash_only', 'reserved_cash_ratio', 'reserved_cash_floor_usd'}))
    _require(all(type(v) in (bool, int, float) for v in c['cash_policy'].values()))
    if 'cash_only' in c['cash_policy']:
        _require(type(c['cash_policy']['cash_only']) is bool)
    RuntimeControl.from_mapping(c)
    _require(isinstance(value['currency'], str) and re.fullmatch('[A-Z]{3}', value['currency']) is not None)
    for key in ('amount', 'cap'):
        _require(isinstance(value[key], str) and re.fullmatch(r'(0|[1-9][0-9]*)(\.[0-9]+)?', value[key]) is not None)
    _require(Decimal(value['amount']) <= Decimal(value['cap']))
    _require(value['amount_basis'] in ('one_time', 'standing_plan'))
    if value['amount_basis'] == 'standing_plan': _ref(value['plan_ref'])
    else: _require(value['plan_ref'] is None)
    _require(value['fee_treatment'] in ('included', 'outside_amount'))
    _require(value['reserve_treatment'] in ('included', 'outside_amount'))
    _require(type(value['paper_min_sessions']) is int and 3 <= value['paper_min_sessions'] <= 5)
    for key in ('instruments', 'actions'):
        items = value[key]
        _require(type(items) is list and len(items) > 0 and len(set(items)) == len(items))
        for item in items: _label(item)
    _require(set(value['actions']) <= {'rebalance', 'buy', 'sell', 'dca'})


def _decision(value, subject, digest):
    _object(value, _DECISION)
    for key in ('decision_ref', 'actor_ref', 'epoch'): _ref(value[key])
    _integer(value['revision']); _integer(value['state_version'])
    _require(value['subject_sha256'] == digest and value['revision'] == subject['revision'])
    _require(value['actor_type'] == 'human' and value['outcome'] in ('confirmed', 'rejected'))
    # Match the bundled schema before freezing the original timestamp strings.
    for key in ('reviewed_at', 'effective_at', 'expires_at'):
        _require(isinstance(value[key], str) and re.fullmatch(
            r'[0-9]{4}-[0-9]{2}-[0-9]{2}[Tt](?:[01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]'
            r'(?:\.[0-9]+)?(?:Z|[+-](?:[01][0-9]|2[0-3]):[0-5][0-9])', value[key]) is not None)
    _require(_time(value['reviewed_at']) <= _time(value['effective_at']) < _time(value['expires_at']))


@dataclass(frozen=True, repr=False)
class SetupIntent:
    """Canonical JSON storage prevents nested mutation; each read returns a copy.

    ``to_dict`` is a protected transport envelope, not a public list view.
    Use ``classify_setup_intent`` for the allowlisted public projection.
    """
    _json: str

    def __post_init__(self):
        try:
            data = json.loads(self._json)
            _object(data, _ENVELOPE)
            _require(data['schema_version'] == VERSION)
            _require(data['grants_live'] is False and data['grants_execution_authority'] is False)
            _subject(data['subject'])
            _require(data['subject_sha256'] == _digest(data['subject']))
            if data['decision'] is not None:
                _decision(data['decision'], data['subject'], data['subject_sha256'])
            object.__setattr__(self, '_json', _canonical(data))
        except (ValueError, TypeError, KeyError, OverflowError, AttributeError):
            raise ValueError(redact_sensitive_text('invalid setup intent')) from None

    @classmethod
    def create(cls, subject: dict, decision: dict | None = None) -> SetupIntent:
        try:
            _subject(subject)
            return cls(_canonical(dict(schema_version=VERSION, subject=subject, subject_sha256=_digest(subject),
                                       decision=decision, grants_live=False, grants_execution_authority=False)))
        except (ValueError, TypeError, KeyError, OverflowError, AttributeError):
            raise ValueError(redact_sensitive_text('invalid setup intent')) from None

    @classmethod
    def from_dict(cls, data: dict) -> SetupIntent:
        try:
            return cls(_canonical(data))
        except (ValueError, TypeError, OverflowError):
            raise ValueError(redact_sensitive_text('invalid setup intent')) from None

    @property
    def subject_sha256(self) -> str:
        return self.to_dict()['subject_sha256']

    def to_dict(self) -> dict:
        return json.loads(self._json)


def _changed_fields(before, after):
    result = []
    for key in sorted(before):
        if before[key] == after.get(key):
            continue
        if type(before[key]) is dict and type(after.get(key)) is dict:
            result.extend(key + '.' + path for path in _changed_fields(before[key], after[key]))
        else:
            result.append(key)
    return result


def classify_setup_intent(intent: SetupIntent, *, now: datetime, current, proposed_subject=None):
    """Describe intent only; current is a fresh read, never cached by this module.

    Consumer must authenticate the source and atomically compare persisted
    epoch/version on writes. No value here attests Paper/risk/runtime readiness.
    """
    _require(isinstance(now, datetime) and now.tzinfo is not None and now.utcoffset() is not None)
    data = intent.to_dict(); s = data['subject']; d = data['decision']
    blockers = []; changed = []; status = 'pending_owner'; needs_owner = d is None
    if proposed_subject is not None:
        try:
            if type(proposed_subject) is dict:
                changed = _changed_fields(s, proposed_subject)
            _subject(proposed_subject)
        except (ValueError, TypeError, KeyError, OverflowError):
            blockers.append('PROPOSED_SUBJECT_INVALID')
            needs_owner = True
        if changed:
            blockers.append('SUCCESSOR_CONFIRMATION_REQUIRED'); needs_owner = True
    if d is None:
        blockers.append('OWNER_SETUP_REQUIRED')
    elif d['outcome'] == 'rejected':
        status = 'rejected'; blockers.append('REJECTED')
    elif now < _time(d['effective_at']):
        status = 'blocked'; blockers.append('NOT_EFFECTIVE')
    elif now >= _time(d['expires_at']):
        status = 'expired'; blockers.append('EXPIRED')
    else:
        status = 'confirmed_intent'
    source_ok = False
    try:
        _object(current, _CURRENT)
        for key in ('setup_id', 'epoch', 'decision_ref', 'source_ref'): _ref(current[key])
        for key in ('revision', 'state_version'): _integer(current[key])
        _sha(current['subject_sha256'])
        _require(_time(current['checked_at']) <= now < _time(current['valid_until']))
        _require(current['status'] in ('current', 'revoked', 'superseded'))
        _object(current['prerequisites'], {'paper', 'risk_release', 'reconciliation', 'alerts'})
        _require(all(v in ('unknown', 'unqualified', 'pass', 'failed') for v in current['prerequisites'].values()))
        _require(current['activation_readback'] in ('unknown', 'pending', 'observed', 'failed'))
        source_ok = True
    except (ValueError, TypeError, KeyError, OverflowError):
        blockers.append('CURRENT_SOURCE_UNAVAILABLE'); status = 'blocked'
    if source_ok:
        expected = dict(setup_id=s['setup_id'], revision=s['revision'], subject_sha256=data['subject_sha256'])
        if d is not None: expected.update(state_version=d['state_version'], epoch=d['epoch'], decision_ref=d['decision_ref'])
        if any(current[k] != v for k, v in expected.items()):
            blockers.append('CURRENT_BINDING_MISMATCH'); status = 'blocked'
        if current['status'] != 'current':
            status = current['status']; blockers.append(status.upper())
    if changed or 'PROPOSED_SUBJECT_INVALID' in blockers: status = 'blocked'
    # These prerequisites require their owning authenticated evidence consumer.
    # Caller-supplied counts/pass strings are deliberately never qualification.
    blockers.extend(['PAPER_EVIDENCE_UNQUALIFIED', 'RISK_RELEASE_NOT_VERIFIED',
                     'RECONCILIATION_NOT_VERIFIED', 'ALERTS_NOT_VERIFIED', 'ACTIVATION_NOT_VERIFIED'])
    if s['target']['execution_environment'] == 'live': blockers.append('LIVE_ACTIVATION_OWNER_NEEDED')
    return redact_sensitive_data(dict(intent_status=status, requires_owner_setup=needs_owner,
        blocker_codes=blockers, changed_fields=changed,
        resume_condition=' '.join(code + ': ' + _RESUME[code] for code in blockers),
        activation_readback='unknown', grants_execution_authority=False, grants_live=False))
