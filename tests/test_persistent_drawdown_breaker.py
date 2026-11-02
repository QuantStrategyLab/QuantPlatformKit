"""Synthetic durable admission-only drawdown breaker regressions."""
from dataclasses import replace
from types import SimpleNamespace

import pytest

from quant_platform_kit.common.execution_state import (
    AccountSubmissionError, AccountSubmissionSession, ExecutionMarkerStore,
)
from quant_platform_kit.risk.account_new_risk_gate import InjectedReconciliationSnapshot


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
