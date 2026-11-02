"""Independent synthetic acceptance checks. No broker or cloud access."""
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

from quant_platform_kit.common.execution_state import (
    AccountSubmissionError, AccountSubmissionSession, ExecutionMarkerStore,
    claim_account_owner,
)
from quant_platform_kit.risk.account_new_risk_gate import InjectedReconciliationSnapshot


def session(path):
    return AccountSubmissionSession(
        ExecutionMarkerStore(local_dir=path), broker="ibkr", account_id="DU00000001",
        owner_id="synthetic-owner", profile="synthetic-profile",
        intent_id="1" * 64, release_id="2" * 64,
    )


def order():
    return SimpleNamespace(account_id="DU00000001", symbol="TQQQ", side="buy", quantity=1)


def test_cross_process_open_after_final_read_must_prevent_submit(tmp_path, monkeypatch):
    """A scheduling pause after final read must not permit post-OPEN new risk."""
    first = session(tmp_path)
    assert claim_account_owner(first.store, broker=first.broker,
        account_id=first.account_id, owner_id=first.owner_id).allowed
    grant = first.reserve(order(), new_risk=True)
    original = AccountSubmissionSession._owned_grant
    reads, calls, opened = [], [], []
    source = Path(sys.modules[AccountSubmissionSession.__module__].__file__).resolve().parents[2]
    child = '''
import sys
sys.path.insert(0, sys.argv[1])
from quant_platform_kit.common.execution_state import AccountSubmissionSession, ExecutionMarkerStore, claim_account_owner
from quant_platform_kit.risk.account_new_risk_gate import InjectedReconciliationSnapshot
s = AccountSubmissionSession(ExecutionMarkerStore(local_dir=sys.argv[2]), broker="ibkr", account_id="DU00000001", owner_id="synthetic-owner", profile="synthetic-profile", intent_id="3"*64, release_id="4"*64)
assert claim_account_owner(s.store, broker=s.broker, account_id=s.account_id, owner_id=s.owner_id).allowed
s.record_circuit_breaker_open(snapshot=InjectedReconciliationSnapshot(observation_status="COMPLETE", reconciliation_status="VERIFIED", circuit_breaker_state="CLOSED", equity_usd=40000, peak_equity_usd=50000, drawdown_from_peak=.2))
assert s.read_state()["circuit_breaker_open"] is True
print("OPEN durably confirmed; same-owner fence allowed")
'''

    def pause_after_final_read(self, candidate):
        state = original(self, candidate)
        if self is first:
            reads.append(True)
            if len(reads) == 2:
                # Only inject a scheduling pause; use the real read, append,
                # readback, owner fence and a fresh interpreter in the child.
                result = subprocess.run([sys.executable, "-c", child, str(source), str(tmp_path)],
                    capture_output=True, text=True, timeout=20)
                assert result.returncode == 0, result.stderr
                opened.append(result.stdout.strip())
        return state

    def submit():
        actual = session(tmp_path).read_state()
        calls.append(actual["circuit_breaker_open"])
        return SimpleNamespace(status="Unknown", broker_order_id=None, filled_quantity=0)

    monkeypatch.setattr(AccountSubmissionSession, "_owned_grant", pause_after_final_read)
    error = None
    try:
        first.dispatch(grant, order(), submit)
    except AccountSubmissionError as exc:
        error = str(exc)
    assert opened == ["OPEN durably confirmed; same-owner fence allowed"]
    state = first.read_state()
    assert state["circuit_breaker_open"] is True
    assert calls == [], (
        f"submit executed with current OPEN={calls}; dispatch error={error!r}; "
        f"final certainty={state['attempts'][grant.attempt_id]['certainty']}"
    )


def test_local_lock_covers_submit_and_open_in_another_process(tmp_path):
    import time

    first = session(tmp_path)
    grant = first.reserve(order(), new_risk=True)
    repo = Path(__file__).resolve().parents[1]
    child = '''
import sys, fcntl
from pathlib import Path
sys.path.insert(0, sys.argv[1])
sys.path.insert(0, sys.argv[1] + "/src")
from tests.test_cross_process_dispatch import session
from quant_platform_kit.risk.account_new_risk_gate import InjectedReconciliationSnapshot
s = session(Path(sys.argv[2]))
original = fcntl.flock
def lock(fd, operation):
    Path(sys.argv[3]).write_text("attempting")
    return original(fd, operation)
fcntl.flock = lock
s.record_circuit_breaker_open(snapshot=InjectedReconciliationSnapshot(observation_status="COMPLETE", reconciliation_status="VERIFIED", circuit_breaker_state="CLOSED", equity_usd=40000, peak_equity_usd=50000, drawdown_from_peak=.2))
assert s.read_state()["circuit_breaker_open"] is True
print("OPEN confirmed")
'''
    children = []

    def submit():
        ready = tmp_path / 'ready'
        process = subprocess.Popen(
            [sys.executable, '-c', child, str(repo), str(tmp_path), str(ready)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        children.append(process)
        deadline = time.monotonic() + 10
        while not ready.exists() and time.monotonic() < deadline:
            time.sleep(.01)
        assert ready.exists()
        assert process.poll() is None
        assert first.read_state()['circuit_breaker_open'] is False
        return SimpleNamespace(status='Unknown', broker_order_id=None, filled_quantity=0)

    first.dispatch(grant, order(), submit)
    stdout, stderr = children[0].communicate(timeout=20)
    assert children[0].returncode == 0, stderr
    assert stdout.strip() == 'OPEN confirmed'
    state = first.read_state()
    assert state['circuit_breaker_open'] is True
    assert state['attempts'][grant.attempt_id]['certainty'] == 'UNKNOWN'


class _FileObjects:
    """Synthetic shared ObjectStore for independent-process ownership checks."""
    prefix = 'gs://synthetic-bucket/test/'

    def __init__(self, root):
        self.root = Path(root)

    def path(self, uri):
        assert uri.startswith(self.prefix)
        return self.root / uri.removeprefix(self.prefix)

    def list(self, prefix):
        return [self.prefix + str(p.relative_to(self.root))
                for p in self.root.rglob('*.json')
                if (self.prefix + str(p.relative_to(self.root))).startswith(prefix)]

    def read_text(self, uri):
        return self.path(uri).read_text()

    def create_text(self, uri, text, content_type):
        path = self.path(uri)
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with path.open('x') as handle:
                handle.write(text)
        except FileExistsError:
            return False
        return True


class _FileStore(ExecutionMarkerStore):
    def _object_store(self):
        return _FileObjects(self.local_dir)


def cloud_session(path, intent='1'):
    return AccountSubmissionSession(
        _FileStore(local_dir=path, cloud_prefix_uri='gs://synthetic-bucket/test'),
        broker='ibkr', account_id='DU00000001', owner_id='synthetic-owner',
        profile='synthetic-profile', intent_id=intent * 64, release_id='2' * 64,
    )


def test_cloud_exclusive_process_owner_denies_same_owner_restart(tmp_path):
    first = cloud_session(tmp_path)
    with first._account_mutex, first._writer_guard():
        pass
    child = '''
import sys
sys.path.insert(0, sys.argv[1])
sys.path.insert(0, sys.argv[1] + "/src")
from tests.test_cross_process_dispatch import cloud_session, order
from quant_platform_kit.common.execution_state import AccountSubmissionError
from quant_platform_kit.risk.account_new_risk_gate import InjectedReconciliationSnapshot
s = cloud_session(sys.argv[2], intent="3")
g = s.reserve(order(), new_risk=True)
calls = []
try:
    s.dispatch(g, order(), lambda: calls.append(True))
except AccountSubmissionError as exc:
    assert "exclusive account writer" in str(exc)
else:
    raise AssertionError("restart dispatched")
assert calls == []
assert g.attempt_id not in s._used
assert s.read_state()["attempts"][g.attempt_id]["certainty"] == "PREPARED"
try:
    s.record_circuit_breaker_open(snapshot=InjectedReconciliationSnapshot(observation_status="COMPLETE", reconciliation_status="VERIFIED", circuit_breaker_state="CLOSED", equity_usd=40000, peak_equity_usd=50000, drawdown_from_peak=.2))
except AccountSubmissionError:
    pass
else:
    raise AssertionError("other process wrote OPEN")
print("restart denied")
'''
    result = subprocess.run([sys.executable, '-c', child,
        str(Path(__file__).resolve().parents[1]), str(tmp_path)],
        capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == 'restart denied'
    assert first.read_state()['circuit_breaker_open'] is False


def test_cloud_ownership_readback_failure_never_consumes_or_submits(tmp_path, monkeypatch):
    import pytest

    first = cloud_session(tmp_path)
    grant = first.reserve(order(), new_risk=True)
    original = _FileObjects.read_text

    def read(self, uri):
        if 'account_writer_ownership/' in uri:
            raise OSError('synthetic ownership read failure')
        return original(self, uri)

    monkeypatch.setattr(_FileObjects, 'read_text', read)
    calls = []
    with pytest.raises(AccountSubmissionError, match='exclusive account writer'):
        first.dispatch(grant, order(), lambda: calls.append(True))
    assert calls == []
    assert grant.attempt_id not in first._used
    assert first.read_state()['attempts'][grant.attempt_id]['certainty'] == 'PREPARED'


def test_local_lock_failure_never_consumes_or_submits(tmp_path, monkeypatch):
    import fcntl
    import pytest

    first = session(tmp_path)
    grant = first.reserve(order(), new_risk=True)

    def fail(*args):
        raise OSError('synthetic locking unavailable')

    monkeypatch.setattr(fcntl, 'flock', fail)
    calls = []
    with pytest.raises(OSError, match='locking unavailable'):
        first.dispatch(grant, order(), lambda: calls.append(True))
    assert calls == []
    assert first._failed
    assert grant.attempt_id not in first._used
