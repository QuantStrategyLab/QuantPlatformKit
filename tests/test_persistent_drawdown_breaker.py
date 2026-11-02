"""Synthetic durable admission-only drawdown breaker regressions."""
from dataclasses import replace
import json
from pathlib import Path
import subprocess
import sys
import threading
from types import SimpleNamespace

import pytest

from quant_platform_kit.common.execution_state import (
    AccountSubmissionError, AccountSubmissionSession, ExecutionMarkerStore,
)
from quant_platform_kit.risk.account_new_risk_gate import (
    InjectedReconciliationSnapshot, evaluate_new_risk_admission,
)


def session_at(path, *, account="DU00000001", profile="synthetic"):
    return AccountSubmissionSession(
        ExecutionMarkerStore(local_dir=path, cloud_prefix_uri=None),
        broker="ibkr", account_id=account, owner_id=profile, profile=profile,
        intent_id="1" * 64, release_id="2" * 64,
    )


def breached_snapshot():
    return InjectedReconciliationSnapshot(
        observation_status="COMPLETE", reconciliation_status="VERIFIED",
        circuit_breaker_state="CLOSED", equity_usd=40_000,
        peak_equity_usd=50_000, drawdown_from_peak=.2,
    )


def order():
    return SimpleNamespace(account_id="DU00000001", symbol="TQQQ", side="buy", quantity=1)


def test_open_survives_new_session_and_other_profile_without_reset(tmp_path):
    first = session_at(tmp_path)
    first.record_circuit_breaker_open(snapshot=breached_snapshot())
    second = session_at(tmp_path, profile="other-synthetic")
    assert second.read_state()["circuit_breaker_open"] is True
    second.record_circuit_breaker_open(snapshot=breached_snapshot())
    assert second.read_state()["generation"] == 1
    assert session_at(tmp_path, account="DU00000002").read_state()["circuit_breaker_open"] is False
    with pytest.raises(AccountSubmissionError, match="breaker"):
        second.reserve(order(), new_risk=True)


def test_prepared_new_risk_cannot_dispatch_after_another_session_trips(tmp_path):
    first = session_at(tmp_path)
    grant = first.reserve(order(), new_risk=True)
    session_at(tmp_path, profile="other-synthetic").record_circuit_breaker_open(snapshot=breached_snapshot())
    calls = []
    with pytest.raises(AccountSubmissionError, match="breaker"):
        first.dispatch(grant, order(), lambda: calls.append(True))
    assert calls == []
    assert first.read_state()["attempts"][grant.attempt_id]["certainty"] == "PREPARED"


@pytest.mark.parametrize("snapshot", [
    replace(breached_snapshot(), drawdown_from_peak=0, peak_equity_usd=40_000),
    replace(breached_snapshot(), equity_usd=float("nan")),
    replace(breached_snapshot(), drawdown_from_peak=True, peak_equity_usd=None),
])
def test_nonbreach_or_invalid_input_cannot_create_open(tmp_path, snapshot):
    session = session_at(tmp_path)
    with pytest.raises((AccountSubmissionError, ValueError)):
        session.record_circuit_breaker_open(snapshot=snapshot)
    assert session.read_state()["generation"] == 0


def test_corrupt_and_reset_shaped_events_fail_closed(tmp_path):
    session = session_at(tmp_path)
    session.record_circuit_breaker_open(snapshot=breached_snapshot())
    path = session._location(1)
    original = path.read_text()
    import json
    event = json.loads(original)
    event["kind"] = "CIRCUIT_BREAKER_RESET"
    event["event_sha256"] = session._event_hash(event)
    path.write_text(json.dumps(event))
    with pytest.raises(AccountSubmissionError):
        session.read_state()
    path.write_text(original.replace('"sequence": 1', '"sequence": 2'))
    with pytest.raises(AccountSubmissionError):
        session.read_state()


def test_failed_write_and_readback_never_allow_new_risk(tmp_path, monkeypatch):
    session = session_at(tmp_path)
    monkeypatch.setattr("quant_platform_kit.common.execution_state.os.open",
                        lambda *_a, **_k: (_ for _ in ()).throw(OSError("synthetic write failure")))
    with pytest.raises(OSError):
        session.record_circuit_breaker_open(snapshot=breached_snapshot())
    assert session._failed
    with pytest.raises(AccountSubmissionError):
        session.reserve(order(), new_risk=True)


def test_restart_in_separate_process_restores_open(tmp_path):
    import subprocess
    import sys
    from pathlib import Path
    session_at(tmp_path).record_circuit_breaker_open(snapshot=breached_snapshot())
    code = '''
import sys
sys.path.insert(0, sys.argv[1])
from quant_platform_kit.common.execution_state import AccountSubmissionSession, ExecutionMarkerStore
s = AccountSubmissionSession(ExecutionMarkerStore(local_dir=sys.argv[2]), broker="ibkr", account_id="DU00000001", owner_id="other", profile="other", intent_id="3"*64, release_id="4"*64)
assert s.read_state()["circuit_breaker_open"] is True
'''
    result = subprocess.run([sys.executable, "-c", code, str(Path(__file__).resolve().parents[1] / "src"), str(tmp_path)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_conflicting_open_create_and_failed_confirmation_poison_session(tmp_path, monkeypatch):
    session = session_at(tmp_path)
    stale_state = session.read_state()
    session_at(tmp_path, profile="other").record_circuit_breaker_open(snapshot=breached_snapshot())
    monkeypatch.setattr(AccountSubmissionSession, "read_state", lambda self: stale_state)
    with pytest.raises(AccountSubmissionError, match="conflict"):
        session.record_circuit_breaker_open(snapshot=breached_snapshot())
    assert session._failed
    with pytest.raises(AccountSubmissionError):
        session.reserve(order(), new_risk=True)


def test_failed_readback_poison_session(tmp_path, monkeypatch):
    session = session_at(tmp_path)
    original = AccountSubmissionSession.read_state
    reads = []
    def read(self):
        reads.append(True)
        if len(reads) > 1:
            raise OSError("synthetic readback failure")
        return original(self)
    monkeypatch.setattr(AccountSubmissionSession, "read_state", read)
    with pytest.raises(OSError, match="readback"):
        session.record_circuit_breaker_open(snapshot=breached_snapshot())
    assert session._failed


@pytest.mark.parametrize("invalid_drawdown", [
    float("nan"), float("inf"), float("-inf"), -1., True, False,
    "unknown", "0.2", [], {},
])
def test_valid_peak_breach_with_invalid_drawdown_survives_process_restart(tmp_path, invalid_drawdown):
    snapshot = replace(breached_snapshot(), drawdown_from_peak=invalid_drawdown)
    admission = evaluate_new_risk_admission(snapshot)
    assert admission.risk_input_invalid is True
    assert admission.hard_brake_triggered is True
    first = session_at(tmp_path)
    first.record_circuit_breaker_open(snapshot=snapshot)
    event = json.loads(first._location(1).read_text())
    assert event["kind"] == "CIRCUIT_BREAKER_OPEN"
    assert event["data"]["equity_usd"] == 40_000
    assert event["data"]["peak_equity_usd"] == 50_000
    # Replay derives the breach from valid peak/equity; no invalid fact is stored.
    assert event["data"]["drawdown_from_peak"] is None
    code = '''
import sys
sys.path.insert(0, sys.argv[1])
from types import SimpleNamespace
from quant_platform_kit.common.execution_state import AccountSubmissionSession, AccountSubmissionError, ExecutionMarkerStore
s = AccountSubmissionSession(ExecutionMarkerStore(local_dir=sys.argv[2]), broker="ibkr", account_id="DU00000001", owner_id="other", profile="other", intent_id="3"*64, release_id="4"*64)
assert s.read_state()["circuit_breaker_open"] is True
try:
    s.reserve(SimpleNamespace(account_id="DU00000001", symbol="SOXL", side="buy", quantity=1), new_risk=True)
except AccountSubmissionError:
    pass
else:
    raise AssertionError("restarted session admitted new risk after peak breach")
'''
    result = subprocess.run([sys.executable, "-c", code, str(Path(__file__).resolve().parents[1] / "src"), str(tmp_path)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    recovered = replace(breached_snapshot(), equity_usd=50_000, drawdown_from_peak=0)
    assert evaluate_new_risk_admission(recovered).hard_brake_triggered is False
    restarted = session_at(tmp_path, profile="other")
    with pytest.raises(AccountSubmissionError, match="breaker"):
        restarted.reserve(order(), new_risk=True)
    assert restarted.read_state()["generation"] == 1


def test_open_completed_during_order_validation_blocks_final_dispatch(tmp_path, monkeypatch):
    first = session_at(tmp_path)
    grant = first.reserve(order(), new_risk=True)
    validating, opened = threading.Event(), threading.Event()
    failures, calls = [], []
    original = AccountSubmissionSession._order

    def validate(self, intent):
        if self is first:
            validating.set()
            assert opened.wait(5)
        return original(self, intent)

    def trip():
        try:
            assert validating.wait(5)
            second = session_at(tmp_path, profile="other")
            second.record_circuit_breaker_open(snapshot=breached_snapshot())
            assert second.read_state()["circuit_breaker_open"] is True
        except BaseException as exc:
            failures.append(exc)
        finally:
            opened.set()

    monkeypatch.setattr(AccountSubmissionSession, "_order", validate)
    worker = threading.Thread(target=trip)
    worker.start()
    try:
        with pytest.raises(AccountSubmissionError, match="breaker"):
            first.dispatch(grant, order(), lambda: calls.append(True))
    finally:
        worker.join(5)
    assert not worker.is_alive()
    assert failures == []
    assert calls == []
    assert grant.attempt_id not in first._used
    assert first.read_state()["attempts"][grant.attempt_id]["certainty"] == "PREPARED"


@pytest.mark.parametrize("cloud", [False, True])
def test_open_and_final_read_submit_are_serialized_across_sessions(tmp_path, monkeypatch, cloud):
    if cloud:
        from tests.test_execution_state import _JournalObjects, _JournalStore
        objects = _JournalObjects()

        def make_session(profile):
            return AccountSubmissionSession(
                _JournalStore(objects), broker="ibkr", account_id="DU00000001",
                owner_id=profile, profile=profile, intent_id="1"*64, release_id="2"*64,
            )
    else:
        def make_session(profile):
            # Different store instances and equivalent paths share the journal.
            path = tmp_path if profile == "first" else tmp_path / "unused" / ".."
            return session_at(path, profile=profile)
        (tmp_path / "unused").mkdir()

    first, second = make_session("first"), make_session("second")
    grant = first.reserve(order(), new_risk=True)
    final_read, attempting_open, opened = threading.Event(), threading.Event(), threading.Event()
    failures, calls = [], []
    underlying = second._account_mutex

    class NotifyingLock:
        def __enter__(self):
            attempting_open.set()
            return underlying.__enter__()

        def __exit__(self, *args):
            return underlying.__exit__(*args)

    object.__setattr__(second, "_account_mutex", NotifyingLock())
    original = AccountSubmissionSession.read_state
    reads = []

    def read(self):
        state = original(self)
        if self is first:
            reads.append(True)
            if len(reads) == 2:
                final_read.set()
                assert attempting_open.wait(5)
        return state

    def trip():
        try:
            assert final_read.wait(5)
            second.record_circuit_breaker_open(snapshot=breached_snapshot())
            opened.set()
        except BaseException as exc:
            failures.append(exc)

    def submit():
        assert attempting_open.is_set()
        assert not opened.is_set()
        assert original(second)["circuit_breaker_open"] is False
        calls.append(True)
        return SimpleNamespace(status="Unknown", broker_order_id=None, filled_quantity=0)

    monkeypatch.setattr(AccountSubmissionSession, "read_state", read)
    worker = threading.Thread(target=trip)
    worker.start()
    try:
        first.dispatch(grant, order(), submit)
    finally:
        worker.join(5)
    assert not worker.is_alive()
    assert failures == []
    assert calls == [True]
    assert opened.is_set()
    assert original(second)["circuit_breaker_open"] is True
    assert original(first)["attempts"][grant.attempt_id]["certainty"] == "UNKNOWN"


def test_failed_final_readback_never_consumes_or_submits_grant(tmp_path, monkeypatch):
    first = session_at(tmp_path)
    grant = first.reserve(order(), new_risk=True)
    original = AccountSubmissionSession.read_state
    reads, calls = [], []

    def read(self):
        reads.append(True)
        if len(reads) == 2:
            raise OSError("synthetic final readback unavailable")
        return original(self)

    monkeypatch.setattr(AccountSubmissionSession, "read_state", read)
    with pytest.raises(OSError, match="final readback"):
        first.dispatch(grant, order(), lambda: calls.append(True))
    assert calls == []
    assert grant.attempt_id not in first._used
    assert original(first)["attempts"][grant.attempt_id]["certainty"] == "PREPARED"
