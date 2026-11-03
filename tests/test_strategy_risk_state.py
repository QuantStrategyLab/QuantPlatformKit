from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest

from quant_platform_kit.common.strategy_risk_state import (
    StrategyRiskStateAppendStatus,
    StrategyRiskStateChainError,
    StrategyRiskStateIdentity,
    StrategyRiskStateStore,
    StrategyRiskStateTransition,
    build_strategy_risk_state_transition,
    validate_strategy_risk_state_chain,
)


def _identity(*, candidate_id: str = "soxl_soxx_core_only_p2_v3") -> StrategyRiskStateIdentity:
    return StrategyRiskStateIdentity(
        strategy_profile="soxl_soxx_trend_income",
        account_scope="paper",
        candidate_id=candidate_id,
        config_sha256="a" * 64,
    )


def _transition(*, session: str = "2026-08-24", previous: StrategyRiskStateTransition | None = None):
    return build_strategy_risk_state_transition(
        identity=_identity(),
        effective_session=session,
        input_sha256="b" * 64,
        state={"cooldown_remaining_sessions": 2, "reentry_allowed": False},
        previous_transition=previous,
    )


def test_transition_is_content_addressed_and_round_trips() -> None:
    transition = _transition()
    same = _transition()

    assert transition.transition_sha256 == same.transition_sha256
    assert transition.state == {"cooldown_remaining_sessions": 2, "reentry_allowed": False}
    assert StrategyRiskStateTransition.from_dict(transition.to_dict()) == transition


def test_transition_rejects_tampered_state() -> None:
    payload = _transition().to_dict()
    payload["state"] = {"cooldown_remaining_sessions": 0, "reentry_allowed": True}

    with pytest.raises(ValueError, match="transition_sha256 mismatch"):
        StrategyRiskStateTransition.from_dict(payload)


def test_chain_requires_exact_prior_digest_and_advancing_session() -> None:
    first = _transition(session="2026-08-24")
    second = _transition(session="2026-08-25", previous=first)

    validate_strategy_risk_state_chain([first, second])

    with pytest.raises(StrategyRiskStateChainError, match="advance"):
        _transition(session="2026-08-24", previous=first)

    alternate_root = build_strategy_risk_state_transition(
        identity=_identity(),
        effective_session="2026-08-24",
        input_sha256="c" * 64,
        state={"cooldown_remaining_sessions": 3, "reentry_allowed": False},
    )
    with pytest.raises(StrategyRiskStateChainError, match="prior transition digest"):
        validate_strategy_risk_state_chain([alternate_root, second])


def test_chain_cannot_cross_candidate_or_config_scope() -> None:
    first = _transition(session="2026-08-24")
    other_identity = _identity(candidate_id="soxl_soxx_core_only_p2_v4")

    with pytest.raises(StrategyRiskStateChainError, match="identity"):
        build_strategy_risk_state_transition(
            identity=other_identity,
            effective_session="2026-08-25",
            input_sha256="b" * 64,
            state={"cooldown_remaining_sessions": 1, "reentry_allowed": False},
            previous_transition=first,
        )


def test_root_transition_cannot_claim_a_previous_digest() -> None:
    root = _transition()
    child = _transition(session="2026-08-25", previous=root)

    with pytest.raises(StrategyRiskStateChainError, match="root transition"):
        validate_strategy_risk_state_chain([child])


def test_store_appends_one_immutable_successor_and_is_idempotent(tmp_path) -> None:
    store = StrategyRiskStateStore(local_dir=tmp_path)
    first = _transition(session="2026-08-24")
    second = _transition(session="2026-08-25", previous=first)

    created = store.append(first)
    duplicate = store.append(first)
    child = store.append(second)

    assert created.status is StrategyRiskStateAppendStatus.CREATED
    assert duplicate.status is StrategyRiskStateAppendStatus.ALREADY_APPENDED
    assert duplicate.chain_length == 1
    assert child.status is StrategyRiskStateAppendStatus.CREATED
    assert store.load_chain(first.identity) == (first, second)


def test_store_rejects_competing_or_stale_successors(tmp_path) -> None:
    store = StrategyRiskStateStore(local_dir=tmp_path)
    first = _transition(session="2026-08-24")
    accepted = _transition(session="2026-08-25", previous=first)
    competing = build_strategy_risk_state_transition(
        identity=_identity(),
        effective_session="2026-08-25",
        input_sha256="c" * 64,
        state={"cooldown_remaining_sessions": 3, "reentry_allowed": False},
        previous_transition=first,
    )
    stale = build_strategy_risk_state_transition(
        identity=_identity(),
        effective_session="2026-08-26",
        input_sha256="d" * 64,
        state={"cooldown_remaining_sessions": 1, "reentry_allowed": False},
        previous_transition=first,
    )

    store.append(first)
    store.append(accepted)

    with pytest.raises(StrategyRiskStateChainError, match="advance"):
        store.append(competing)
    with pytest.raises(StrategyRiskStateChainError, match="current chain head"):
        store.append(stale)


def test_store_requires_a_root_before_a_child(tmp_path) -> None:
    store = StrategyRiskStateStore(local_dir=tmp_path)
    first = _transition(session="2026-08-24")
    child = _transition(session="2026-08-25", previous=first)

    with pytest.raises(StrategyRiskStateChainError, match="missing its referenced predecessor"):
        store.append(child)


def _chain(length):
    transitions = []
    for index in range(length):
        transitions.append(_transition(
            session=(date(2026, 8, 24) + timedelta(days=index)).isoformat(),
            previous=transitions[-1] if transitions else None,
        ))
    return tuple(transitions)


def _saved_bytes(directory):
    # Include temporary files: a losing create or retry must leave no debris.
    return {str(path.relative_to(directory)): path.read_bytes()
            for path in directory.rglob("*") if path.is_file()}


def _observe_loads(monkeypatch, contender):
    real_load = StrategyRiskStateStore.load_chain
    observed = []

    def load(self, identity):
        chain = real_load(self, identity)
        if self is contender:
            observed.append(chain)
        return chain

    monkeypatch.setattr(StrategyRiskStateStore, "load_chain", load)
    return observed


def _assert_receipt(receipt, status, transition, length):
    assert receipt.status is status
    assert receipt.transition == transition
    assert receipt.chain_length == length
    assert receipt.to_dict() == {
        "status": status.value,
        "transition_sha256": transition.transition_sha256,
        "effective_session": transition.effective_session,
        "chain_length": length,
    }


@pytest.mark.parametrize("prefix_length", [0, 1, 4], ids=["root", "nonroot", "long-prefix"])
@pytest.mark.parametrize("tail_stage", ["none", "before-confirmation", "after-confirmation"])
def test_equal_create_race_receipt_confirms_prefix(tmp_path, monkeypatch, prefix_length, tail_stage):
    expected = _chain(prefix_length + 3)
    prefix, target = expected[:prefix_length], expected[prefix_length]
    winner = StrategyRiskStateStore(local_dir=tmp_path, cloud_prefix_uri=None)
    contender = StrategyRiskStateStore(local_dir=tmp_path, cloud_prefix_uri=None)
    for transition in prefix:
        winner.append(transition)
    original_bytes = _saved_bytes(tmp_path)
    real_create = StrategyRiskStateStore._create_text
    real_read = StrategyRiskStateStore._read_transition
    winners, losing_creates, after_winner, confirmed = [], [], [], []

    def append_tail():
        for transition in expected[prefix_length + 1:]:
            winner.append(transition)
        after_winner.append(_saved_bytes(tmp_path))

    def create(self, location, data):
        if self is contender:
            assert observed == [prefix]  # Genuine load completed before this hook.
            winners.append(winner.append(target))
            if tail_stage == "before-confirmation":
                append_tail()
            else:
                after_winner.append(_saved_bytes(tmp_path))
        created = real_create(self, location, data)
        if self is contender:
            losing_creates.append(created)
        return created

    def read(self, location):
        transition = real_read(self, location)
        if self is contender and transition == target:
            confirmed.append(transition)
            if tail_stage == "after-confirmation":
                append_tail()
        return transition

    with monkeypatch.context() as fault:
        observed = _observe_loads(fault, contender)
        fault.setattr(StrategyRiskStateStore, "_create_text", create)
        fault.setattr(StrategyRiskStateStore, "_read_transition", read)
        receipt = contender.append(target)
    assert observed == [prefix]
    assert losing_creates == [False] and confirmed == [target]
    assert len(winners) == 1
    _assert_receipt(winners[0], StrategyRiskStateAppendStatus.CREATED, target, prefix_length + 1)
    _assert_receipt(receipt, StrategyRiskStateAppendStatus.ALREADY_APPENDED, target, prefix_length + 1)
    loaded = expected[:prefix_length + 1] if tail_stage == "none" else expected
    assert contender.load_chain(_identity()) == loaded
    saved = _saved_bytes(tmp_path)
    assert saved == after_winner[-1]
    assert len(saved) == len(loaded)  # Only the immutable JSON records remain.
    assert all(saved[name] == data for name, data in original_bytes.items())
    retry = contender.append(target)
    _assert_receipt(retry, StrategyRiskStateAppendStatus.ALREADY_APPENDED, target, len(loaded))
    assert _saved_bytes(tmp_path) == saved


@pytest.mark.parametrize("prefix_length", [0, 1, 4], ids=["root", "nonroot", "long-prefix"])
def test_different_create_race_preserves_winner(tmp_path, monkeypatch, prefix_length):
    expected = _chain(prefix_length + 1)
    prefix, target = expected[:prefix_length], expected[prefix_length]
    alternative = build_strategy_risk_state_transition(
        identity=_identity(), effective_session=target.effective_session,
        input_sha256="c" * 64, state={"cooldown_remaining_sessions": 3, "reentry_allowed": False},
        previous_transition=prefix[-1] if prefix else None,
    )
    winner = StrategyRiskStateStore(local_dir=tmp_path, cloud_prefix_uri=None)
    contender = StrategyRiskStateStore(local_dir=tmp_path, cloud_prefix_uri=None)
    for transition in prefix:
        winner.append(transition)
    original_bytes = _saved_bytes(tmp_path)
    real_create = StrategyRiskStateStore._create_text
    winners, losing_creates, after_winner = [], [], []

    def create(self, location, data):
        if self is contender:
            assert observed == [prefix]
            winners.append(winner.append(target))
            after_winner.append(_saved_bytes(tmp_path))
        created = real_create(self, location, data)
        if self is contender:
            losing_creates.append(created)
        return created

    with monkeypatch.context() as fault:
        observed = _observe_loads(fault, contender)
        fault.setattr(StrategyRiskStateStore, "_create_text", create)
        with pytest.raises(StrategyRiskStateChainError, match="already-recorded successor"):
            contender.append(alternative)
    assert observed == [prefix] and losing_creates == [False]
    assert len(winners) == 1
    _assert_receipt(winners[0], StrategyRiskStateAppendStatus.CREATED, target, len(expected))
    assert contender.load_chain(_identity()) == expected
    saved = _saved_bytes(tmp_path)
    assert saved == after_winner[0] and len(saved) == len(expected)
    assert all(saved[name] == data for name, data in original_bytes.items())


@pytest.mark.parametrize("prefix_length", [0, 1, 4], ids=["root", "nonroot", "long-prefix"])
def test_real_create_lost_ack_reopens_and_retries_exact_prefix(tmp_path, monkeypatch, prefix_length):
    expected = _chain(prefix_length + 3)
    store = StrategyRiskStateStore(local_dir=tmp_path, cloud_prefix_uri=None)
    for transition in expected[:prefix_length]:
        store.append(transition)
    original_bytes = _saved_bytes(tmp_path)
    real_create = StrategyRiskStateStore._create_text
    committed = []

    def create_then_lose_ack(self, location, data):
        created = real_create(self, location, data)
        if self is store and created:
            committed.append(Path(location).read_bytes())
            raise OSError("injected ACK loss after real durable create")
        return created

    with monkeypatch.context() as fault:
        fault.setattr(StrategyRiskStateStore, "_create_text", create_then_lose_ack)
        with pytest.raises(OSError, match="ACK loss after real durable create"):
            store.append(expected[prefix_length])
    assert len(committed) == 1
    identity = StrategyRiskStateIdentity.from_dict(_identity().to_dict())
    reopened = StrategyRiskStateStore(local_dir=tmp_path, cloud_prefix_uri=None)
    loaded = reopened.load_chain(identity)
    assert loaded == expected[:prefix_length + 1]
    saved = _saved_bytes(tmp_path)
    assert committed[0] in saved.values()
    assert len(saved) == len(loaded)
    assert all(saved[name] == data for name, data in original_bytes.items())
    for transition in loaded:
        retry = reopened.append(transition)
        _assert_receipt(retry, StrategyRiskStateAppendStatus.ALREADY_APPENDED, transition, len(loaded))
    assert reopened.load_chain(identity) == loaded and _saved_bytes(tmp_path) == saved
    for index, transition in enumerate(expected[len(loaded):], start=len(loaded) + 1):
        _assert_receipt(reopened.append(transition), StrategyRiskStateAppendStatus.CREATED, transition, index)
    assert reopened.load_chain(identity) == expected
    final_bytes = _saved_bytes(tmp_path)
    assert len(final_bytes) == len(expected)
    assert all(final_bytes[name] == data for name, data in saved.items())


def test_old_duplicate_receipt_observes_longer_chain(tmp_path):
    expected = _chain(7)
    store = StrategyRiskStateStore(local_dir=tmp_path, cloud_prefix_uri=None)
    for transition in expected:
        store.append(transition)
    saved = _saved_bytes(tmp_path)
    for transition in expected:
        _assert_receipt(store.append(transition), StrategyRiskStateAppendStatus.ALREADY_APPENDED, transition, 7)
    assert _saved_bytes(tmp_path) == saved and len(saved) == 7


@pytest.mark.parametrize("prefix_length", [0, 1, 4], ids=["root", "nonroot", "long-prefix"])
def test_created_receipt_confirms_prefix_without_chasing_later_writer(tmp_path, monkeypatch, prefix_length):
    expected = _chain(prefix_length + 3)
    store = StrategyRiskStateStore(local_dir=tmp_path, cloud_prefix_uri=None)
    follower = StrategyRiskStateStore(local_dir=tmp_path, cloud_prefix_uri=None)
    for transition in expected[:prefix_length]:
        store.append(transition)
    real_create = StrategyRiskStateStore._create_text
    created_bytes = []

    def create(self, location, data):
        created = real_create(self, location, data)
        if self is store and created:
            created_bytes.append(_saved_bytes(tmp_path))
            for transition in expected[prefix_length + 1:]:
                follower.append(transition)
        return created

    with monkeypatch.context() as fault:
        fault.setattr(StrategyRiskStateStore, "_create_text", create)
        receipt = store.append(expected[prefix_length])
    assert len(created_bytes) == 1
    _assert_receipt(receipt, StrategyRiskStateAppendStatus.CREATED, expected[prefix_length], prefix_length + 1)
    assert follower.load_chain(_identity()) == expected
    saved = _saved_bytes(tmp_path)
    assert len(saved) == len(expected)
    assert all(saved[name] == data for name, data in created_bytes[0].items())


def test_duplicate_receipt_keeps_observed_prefix_when_writer_advances_after_load(tmp_path, monkeypatch):
    expected = _chain(5)
    store = StrategyRiskStateStore(local_dir=tmp_path, cloud_prefix_uri=None)
    follower = StrategyRiskStateStore(local_dir=tmp_path, cloud_prefix_uri=None)
    for transition in expected[:3]:
        store.append(transition)
    saved = _saved_bytes(tmp_path)
    real_load = StrategyRiskStateStore.load_chain
    observed = []

    def load(self, identity):
        chain = real_load(self, identity)
        if self is store:
            observed.append(chain)
            for transition in expected[3:]:
                follower.append(transition)
        return chain

    with monkeypatch.context() as fault:
        fault.setattr(StrategyRiskStateStore, "load_chain", load)
        receipt = store.append(expected[0])
    assert observed == [expected[:3]]
    _assert_receipt(receipt, StrategyRiskStateAppendStatus.ALREADY_APPENDED, expected[0], 3)
    assert store.load_chain(_identity()) == expected
    final_bytes = _saved_bytes(tmp_path)
    assert len(final_bytes) == 5
    assert all(final_bytes[name] == data for name, data in saved.items())
