"""Reviewer-only adverse cases; synthetic local storage and no network."""
from dataclasses import replace
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

from quant_platform_kit.common.execution_state import (
    AccountSubmissionSession, AccountSubmissionError, ExecutionMarkerStore,
)
from quant_platform_kit.risk.account_new_risk_gate import (
    InjectedReconciliationSnapshot, evaluate_new_risk_admission,
)
from tests.test_cross_process_dispatch import cloud_session, _FileObjects


def session(path):
    return AccountSubmissionSession(ExecutionMarkerStore(local_dir=path),
        broker='ibkr', account_id='DU00000001', owner_id='synthetic-owner',
        profile='synthetic-profile', intent_id='1'*64, release_id='2'*64)


def order():
    return SimpleNamespace(account_id='DU00000001', symbol='TQQQ', side='buy', quantity=1)


def breach():
    return InjectedReconciliationSnapshot(observation_status='COMPLETE',
        reconciliation_status='VERIFIED', circuit_breaker_state='CLOSED',
        equity_usd=40000., peak_equity_usd=50000., drawdown_from_peak=.2)


@pytest.mark.parametrize('peak', [float('nan'), float('inf'), -1., True, 'unknown'])
def test_valid_explicit_breach_with_invalid_peak_is_durable(tmp_path, peak):
    snapshot = replace(breach(), peak_equity_usd=peak)
    admission = evaluate_new_risk_admission(snapshot)
    assert admission.hard_brake_triggered and admission.risk_input_invalid
    first = session(tmp_path)
    error = None
    try:
        first.record_circuit_breaker_open(snapshot=snapshot)
    except AccountSubmissionError as exc:
        error = str(exc)
    source = Path(sys.modules[AccountSubmissionSession.__module__].__file__).resolve().parents[2]
    child = '''
import sys, json
from types import SimpleNamespace
sys.path.insert(0, sys.argv[1])
from quant_platform_kit.common.execution_state import AccountSubmissionSession, AccountSubmissionError, ExecutionMarkerStore
s=AccountSubmissionSession(ExecutionMarkerStore(local_dir=sys.argv[2]),broker='ibkr',account_id='DU00000001',owner_id='synthetic-owner',profile='synthetic-profile',intent_id='3'*64,release_id='4'*64)
state=s.read_state()
admitted=False
try:
 s.reserve(SimpleNamespace(account_id='DU00000001',symbol='TQQQ',side='buy',quantity=1),new_risk=True)
 admitted=True
except AccountSubmissionError: pass
print(json.dumps({'open':state['circuit_breaker_open'],'generation':state['generation'],'admitted':admitted}))
'''
    result = subprocess.run([sys.executable, '-c', child, str(source), str(tmp_path)],
        capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    import json
    state = json.loads(result.stdout)
    assert state['open'] and not state['admitted'], (error, state)


def test_replaced_local_lock_blocks_dispatch(tmp_path, monkeypatch):
    first = session(tmp_path)
    grant = first.reserve(order(), new_risk=True)
    original = AccountSubmissionSession._owned_grant
    reads, calls = [], []
    source = Path(sys.modules[AccountSubmissionSession.__module__].__file__).resolve().parents[2]
    child = '''
import sys
sys.path.insert(0, sys.argv[1])
from quant_platform_kit.common.execution_state import AccountSubmissionSession, ExecutionMarkerStore
from quant_platform_kit.risk.account_new_risk_gate import InjectedReconciliationSnapshot
s=AccountSubmissionSession(ExecutionMarkerStore(local_dir=sys.argv[2]),broker='ibkr',account_id='DU00000001',owner_id='synthetic-owner',profile='synthetic-profile',intent_id='3'*64,release_id='4'*64)
s.record_circuit_breaker_open(snapshot=InjectedReconciliationSnapshot(observation_status='COMPLETE',reconciliation_status='VERIFIED',circuit_breaker_state='CLOSED',equity_usd=40000,peak_equity_usd=50000,drawdown_from_peak=.2))
assert s.read_state()['circuit_breaker_open']
print('OPEN confirmed')
'''
    def after_read(self, candidate):
        state = original(self, candidate)
        if self is first:
            reads.append(True)
            if len(reads) == 3:  # Real final read under acquired flock.
                path = first._location().resolve() / 'writer.lock'
                # Simulate loss of the pathname's lock identity, retaining all
                # journal data and the original locked inode for inspection.
                path.rename(path.with_name('detached.lock'))
                result = subprocess.run([sys.executable, '-c', child, str(source), str(tmp_path)],
                    capture_output=True, text=True, timeout=10)
                assert result.returncode == 0, result.stderr
                assert result.stdout.strip() == 'OPEN confirmed'
        return state
    monkeypatch.setattr(AccountSubmissionSession, '_owned_grant', after_read)
    def submit():
        calls.append(first.read_state()['circuit_breaker_open'])
        return SimpleNamespace(status='Unknown', broker_order_id=None, filled_quantity=0)
    try:
        first.dispatch(grant, order(), submit)
    except (AccountSubmissionError, OSError):
        pass
    assert calls == [], f'submit ran after loss of original lock identity, OPEN={calls}'


def test_lost_cloud_ownership_before_final_read_blocks_dispatch(tmp_path, monkeypatch):
    first = cloud_session(tmp_path)
    grant = first.reserve(order(), new_risk=True)
    original = AccountSubmissionSession._owned_grant
    reads, calls = [], []
    def before_read(self, candidate):
        if self is first:
            reads.append(True)
            if len(reads) == 3:
                uri = first.store._cloud_uri_for_namespace(first.account_root, 'account_writer_ownership')
                # Storage fault/revocation after initial ownership confirmation.
                _FileObjects(tmp_path).path(uri).write_text('{"kind":"WRITER_OWNERSHIP","token":"synthetic-other-process"}')
        return original(self, candidate)
    monkeypatch.setattr(AccountSubmissionSession, '_owned_grant', before_read)
    try:
        first.dispatch(grant, order(), lambda: calls.append(True))
    except (AccountSubmissionError, OSError):
        pass
    assert calls == [], 'submit ran after exclusive ownership was lost'


@pytest.mark.parametrize('factory', [session, cloud_session])
@pytest.mark.parametrize('peak', [0., False, '50000', '', float('-inf')])
def test_invalid_peak_is_omitted_without_clearing_input_error(tmp_path, factory, peak):
    import json

    snapshot = replace(breach(), peak_equity_usd=peak)
    first = factory(tmp_path)
    first.record_circuit_breaker_open(snapshot=snapshot)
    admission = evaluate_new_risk_admission(snapshot)
    assert admission.hard_brake_triggered and admission.risk_input_invalid
    if first.store.cloud_prefix_uri:
        event = json.loads(_FileObjects(tmp_path).read_text(first._location(1)))
    else:
        event = json.loads(first._location(1).read_text())
    assert event['data']['peak_equity_usd'] is None
    assert event['data']['drawdown_from_peak'] == .2
    second = factory(tmp_path)
    assert second.read_state()['circuit_breaker_open'] is True
    with pytest.raises(AccountSubmissionError):
        second.reserve(order(), new_risk=True)


@pytest.mark.parametrize('factory,fault', [
    (factory, fault) for factory in (session, cloud_session)
    for fault in ('missing', 'replacement', 'symlink', 'unreadable')
    if factory is session or fault != 'symlink'
])
def test_identity_loss_after_final_read_fails_closed(tmp_path, monkeypatch, factory, fault):
    first = factory(tmp_path)
    grant = first.reserve(order(), new_risk=True)
    original = AccountSubmissionSession._owned_grant
    reads, calls = [], []

    def after_read(self, candidate):
        state = original(self, candidate)
        if self is first:
            reads.append(True)
            if len(reads) == 3:
                if factory is cloud_session:
                    uri = first.store._cloud_uri_for_namespace(first.account_root, 'account_writer_ownership')
                    path = _FileObjects(tmp_path).path(uri)
                else:
                    path = first._location().resolve() / 'writer.lock'
                if fault == 'missing':
                    path.unlink()
                elif fault in {'replacement', 'symlink'}:
                    detached = path.with_name('detached.lock')
                    path.rename(detached)
                    if fault == 'symlink':
                        path.symlink_to(detached)
                    else:
                        path.write_text('synthetic replacement')
                elif factory is cloud_session:
                    original_read = _FileObjects.read_text
                    def read(objects, location):
                        if location == uri:
                            raise OSError('synthetic ownership unavailable')
                        return original_read(objects, location)
                    monkeypatch.setattr(_FileObjects, 'read_text', read)
                else:
                    import os
                    original_stat = os.stat
                    def stat(location, *args, **kwargs):
                        if Path(location) == path:
                            raise OSError('synthetic lock identity unavailable')
                        return original_stat(location, *args, **kwargs)
                    monkeypatch.setattr(os, 'stat', stat)
        return state

    monkeypatch.setattr(AccountSubmissionSession, '_owned_grant', after_read)
    with pytest.raises((AccountSubmissionError, OSError)):
        first.dispatch(grant, order(), lambda: calls.append(True))
    assert calls == []
    assert first._failed
    assert grant.attempt_id not in first._used
    assert first.read_state()['attempts'][grant.attempt_id]['certainty'] == 'PREPARED'
    with pytest.raises(AccountSubmissionError):
        first.dispatch(grant, order(), lambda: calls.append(True))
    assert calls == []


@pytest.mark.parametrize('factory', [session, cloud_session])
def test_missing_established_identity_is_not_recreated(tmp_path, factory):
    first = factory(tmp_path)
    with first._writer_guard():
        pass
    grant = first.reserve(order(), new_risk=True)
    if factory is cloud_session:
        uri = first.store._cloud_uri_for_namespace(first.account_root, 'account_writer_ownership')
        path = _FileObjects(tmp_path).path(uri)
    else:
        path = first._location().resolve() / 'writer.lock'
    path.unlink()
    calls = []
    with pytest.raises((AccountSubmissionError, OSError)):
        first.dispatch(grant, order(), lambda: calls.append(True))
    assert calls == []
    assert not path.exists()
    assert first._failed


@pytest.mark.parametrize('factory', [session, cloud_session])
@pytest.mark.parametrize('boundary', ['consume', 'submit'])
def test_identity_loss_at_submit_boundary_retains_unresolved_attempt(tmp_path, factory, boundary):
    first = factory(tmp_path)
    grant = first.reserve(order(), new_risk=True)
    if factory is cloud_session:
        uri = first.store._cloud_uri_for_namespace(first.account_root, 'account_writer_ownership')
        path = _FileObjects(tmp_path).path(uri)
    else:
        path = first._location().resolve() / 'writer.lock'
    calls = []

    class FaultingSet(set):
        def add(self, value):
            super().add(value)
            path.unlink()

    if boundary == 'consume':
        object.__setattr__(first, '_used', FaultingSet())

    def submit():
        calls.append(True)
        path.unlink()
        return SimpleNamespace(status='Filled', broker_order_id='synthetic-order',
                               filled_quantity=1, average_fill_price=100)

    with pytest.raises((AccountSubmissionError, OSError)):
        first.dispatch(grant, order(), submit)
    assert calls == ([] if boundary == 'consume' else [True])
    assert first._failed
    assert grant.attempt_id in first._used
    state = first.read_state()
    assert state['attempts'][grant.attempt_id]['certainty'] == 'PREPARED'
    assert state['attempts'][grant.attempt_id]['observation'] is None
    with pytest.raises(AccountSubmissionError):
        first.dispatch(grant, order(), submit)


def test_lock_replaced_during_acquisition_cannot_authorize_submit(tmp_path, monkeypatch):
    import fcntl

    first = session(tmp_path)
    grant = first.reserve(order(), new_risk=True)
    lock = first._location().resolve() / 'writer.lock'
    original = fcntl.flock

    def acquire(fd, operation):
        original(fd, operation)
        lock.rename(lock.with_name('detached.lock'))
        lock.write_text('synthetic replacement')

    monkeypatch.setattr(fcntl, 'flock', acquire)
    calls = []
    with pytest.raises((AccountSubmissionError, OSError)):
        first.dispatch(grant, order(), lambda: calls.append(True))
    assert calls == []
    assert first._failed
    assert grant.attempt_id not in first._used
