import pytest
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

from quant_platform_kit.common.account_identity import BrokerAccountIdentity
from quant_platform_kit.common.account_domain import account_domain_key
from quant_platform_kit.common.execution_state import (
    AccountSubmissionError, AccountSubmissionSession, ExecutionMarkerStore, submission_binding_digest,
)
from quant_platform_kit.common.models import OrderIntent
from quant_platform_kit.common.strategy_risk_state import StrategyRiskStateIdentity, StrategyRiskStateStore, build_strategy_risk_state_transition


def fixture(tmp_path):
    domain = {"identity": {"environment": "LIVE", "platform_id": "ibkr", "server": "synthetic",
              "account_id_fingerprint": "sha256:" + "1" * 64, "lifecycle_id": "one"},
              "policy": {"capital_kind": "OWN_REAL", "product": "BROKERAGE", "phase": "LIVE",
              "account_type": "CASH", "style": "INTRADAY", "preference": "CAPITAL_PRESERVATION",
              "currency": "USD", "source": "synthetic", "effective_at": "2026-10-01T00:00:00Z",
              "valid_until": "2026-11-01T00:00:00Z", "version": "one"}}
    observed = BrokerAccountIdentity(platform_id="ibkr", account_types=("CASH",), account_modes=("LIVE",),
                                     account_id_fingerprint="sha256:" + "1" * 64)
    store = ExecutionMarkerStore(local_dir=tmp_path)
    session = AccountSubmissionSession(store, broker="ibkr", account_id="U00000001", owner_id="owner",
        profile="tqqq_growth_income", intent_id="a" * 64, release_id="b" * 64, account_domain=domain,
        observed_account_id="U00000001", broker_identity=observed, observed_at="2026-10-30T02:00:00Z",
        decision_at="2026-10-30T02:00:00Z", observed_environment="LIVE", observed_server="synthetic",
        observed_currency="USD", observed_lifecycle_id="one", clock=lambda: "2026-10-30T02:00:00Z")
    identity = StrategyRiskStateIdentity("tqqq_growth_income", "synthetic", "candidate", "c" * 64)
    intent = {"id": "intent-1", "alpha_epoch": 1, "signal_session": "2026-10-30"}
    transition = build_strategy_risk_state_transition(identity=identity, effective_session="2026-10-30",
        input_sha256="d" * 64, state={"schema_version": "tqqq_daily_state.v1", "session": "2026-10-30",
        "alpha_trend_active": True, "alpha_epoch": 1, "volatility_latch_active": False,
        "pending_intent": intent, "intent_invalidation_reason": None})
    legacy = StrategyRiskStateStore(local_dir=tmp_path / "legacy")
    legacy.append(transition)
    return session, transition, intent, domain


def test_enrollment_rejects_unbound_reserve_and_stale_state(tmp_path):
    session, transition, intent, domain = fixture(tmp_path)
    session.enroll_strategy_state(transition, legacy_store=StrategyRiskStateStore(local_dir=tmp_path / "legacy"), migration_authorization={
        "account_domain_key": account_domain_key(domain), "account_binding_sha256": submission_binding_digest({"broker": "ibkr", "account_id": "U00000001"}), "owner_id": "owner", "release_id": "b" * 64, "legacy_head_sha256": transition.transition_sha256,
        "strategy_identity": transition.identity.to_dict(), "authority_receipt_sha256": "e" * 64})
    order = OrderIntent(symbol="TQQQ", side="buy", quantity=1, account_id="U00000001")
    with pytest.raises(AccountSubmissionError, match="strategy state binding"):
        session.reserve(order)
    with pytest.raises(AccountSubmissionError, match="strategy state binding"):
        session.reserve(order, strategy_state_sha256="0" * 64, strategy_intent_sha256=submission_binding_digest(intent), strategy_session="2026-10-30")
    with pytest.raises(AccountSubmissionError, match="risk reservation"):
        session.reserve(order, strategy_state_sha256=transition.transition_sha256,
                        strategy_intent_sha256=submission_binding_digest(intent), strategy_session="2026-10-30")
    next_transition = build_strategy_risk_state_transition(identity=transition.identity, effective_session="2026-10-31",
        input_sha256="f" * 64, state={**transition.state, "session": "2026-10-31", "pending_intent": None,
        "intent_invalidation_reason": "new_session"}, previous_transition=transition)
    session.advance_strategy_state(next_transition)
    assert session.read_state()["strategy_state"]["transition_sha256"] == next_transition.transition_sha256


def test_enrollment_requires_exact_migration_binding(tmp_path):
    session, transition, _, domain = fixture(tmp_path)
    with pytest.raises(AccountSubmissionError):
        session.enroll_strategy_state(transition, legacy_store=StrategyRiskStateStore(local_dir=tmp_path / "legacy"), migration_authorization={"account_domain_key": account_domain_key(domain), "account_binding_sha256": submission_binding_digest({"broker": "ibkr", "account_id": "U00000001"}), "owner_id": "owner", "release_id": "b" * 64,
            "legacy_head_sha256": "0" * 64, "strategy_identity": transition.identity.to_dict(),
            "authority_receipt_sha256": "e" * 64})


def _reserve_risk(session, domain, order):
    snapshot = {"balance": 10000, "equity": 9500, "cash": 1000, "currency": "USD",
        "valuation_at": "2026-10-30T00:00:00Z", "source_digest": "sha256:" + "2" * 64,
        "complete": True, "position_risk": 0, "position_3x_exposure": 0,
        "account_domain_key": account_domain_key(domain), "account_id": "U00000001",
        "valid_until": "2026-10-30T04:00:00Z", "pending_3x_exposure": 0,
        "open_orders_complete": True, "positions": {}, "open_orders_empty": True}
    session.record_account_equity(snapshot=snapshot, cash_flow=0, baseline_confirmed=True)
    session.reserve_account_risk(order, snapshot=snapshot, floor=9000, cost_buffer=0, amount=10,
        risk_fraction=0.005, loss_per_unit=1, estimated_fee=0, quantity_step=1,
        product_leverage_factor=1, unit_price=100, existing_3x_exposure=0, pending_3x_exposure=0,
        leverage_hitl_approved=False, account_budget_policy={"preference": "CAPITAL_PRESERVATION", "version": "one",
        "source": "synthetic", "per_trade_fraction": 0.005, "total_future_risk_limit": 1000,
        "contract_floor": None, "floor": 9000, "cost_buffer": 0})


def test_prepared_and_unknown_fence_state_and_replay(tmp_path):
    session, transition, intent, domain = fixture(tmp_path)
    session.enroll_strategy_state(transition, legacy_store=StrategyRiskStateStore(local_dir=tmp_path / "legacy"), migration_authorization={"account_domain_key": account_domain_key(domain), "account_binding_sha256": submission_binding_digest({"broker": "ibkr", "account_id": "U00000001"}), "owner_id": "owner", "release_id": "b" * 64,
        "legacy_head_sha256": transition.transition_sha256, "strategy_identity": transition.identity.to_dict(),
        "authority_receipt_sha256": "e" * 64})
    order = OrderIntent(symbol="TQQQ", side="buy", quantity=1, account_id="U00000001")
    _reserve_risk(session, domain, order)
    grant = session.reserve(order, strategy_state_sha256=transition.transition_sha256,
                            strategy_intent_sha256=submission_binding_digest(intent), strategy_session="2026-10-30")
    successor = build_strategy_risk_state_transition(identity=transition.identity, effective_session="2026-10-31",
        input_sha256="f" * 64, state={**transition.state, "session": "2026-10-31", "pending_intent": None,
        "intent_invalidation_reason": "new_session"}, previous_transition=transition)
    with pytest.raises(AccountSubmissionError, match="advance conflict"):
        session.advance_strategy_state(successor)
    session.dispatch(grant, order, lambda: None)
    assert session.read_state()["attempts"][grant.attempt_id]["certainty"] == "UNKNOWN"
    with pytest.raises(AccountSubmissionError, match="advance conflict"):
        session.advance_strategy_state(successor)
    with pytest.raises(AccountSubmissionError):
        session.reserve(order, strategy_state_sha256=transition.transition_sha256,
                        strategy_intent_sha256=submission_binding_digest(intent), strategy_session="2026-10-30")


def test_competing_state_advance_and_reservation_have_one_winner(tmp_path):
    session, transition, intent, domain = fixture(tmp_path)
    competitor, _, _, _ = fixture(tmp_path)
    session.enroll_strategy_state(transition, legacy_store=StrategyRiskStateStore(local_dir=tmp_path / "legacy"), migration_authorization={"account_domain_key": account_domain_key(domain), "account_binding_sha256": submission_binding_digest({"broker": "ibkr", "account_id": "U00000001"}), "owner_id": "owner", "release_id": "b" * 64,
        "legacy_head_sha256": transition.transition_sha256, "strategy_identity": transition.identity.to_dict(),
        "authority_receipt_sha256": "e" * 64})
    order = OrderIntent(symbol="TQQQ", side="buy", quantity=1, account_id="U00000001")
    _reserve_risk(session, domain, order)
    successor = build_strategy_risk_state_transition(identity=transition.identity, effective_session="2026-10-31",
        input_sha256="f" * 64, state={**transition.state, "session": "2026-10-31", "pending_intent": None,
        "intent_invalidation_reason": "new_session"}, previous_transition=transition)
    barrier = Barrier(2)
    original = AccountSubmissionSession._append
    def competing_append(instance, state, kind, data):
        if kind in {"PREPARED", "STRATEGY_STATE_ADVANCED"}:
            barrier.wait(timeout=5)
        return original(instance, state, kind, data)
    def attempt(fn):
        try:
            fn()
            return "confirmed"
        except (AccountSubmissionError, OSError):
            return "blocked"
    with patch.object(AccountSubmissionSession, "_append", competing_append):
        with ThreadPoolExecutor(max_workers=2) as executor:
            first = executor.submit(attempt, lambda: session.reserve(order,
                strategy_state_sha256=transition.transition_sha256,
                strategy_intent_sha256=submission_binding_digest(intent), strategy_session="2026-10-30"))
            second = executor.submit(attempt, lambda: competitor.advance_strategy_state(successor))
            outcomes = [first.result(), second.result()]
    assert sorted(outcomes) == ["blocked", "confirmed"]


def test_migration_requires_physical_account_and_available_legacy_head(tmp_path):
    session, transition, _, domain = fixture(tmp_path)
    authorization = {
        "account_domain_key": account_domain_key(domain),
        "account_binding_sha256": submission_binding_digest({"broker": "ibkr", "account_id": "U00000001"}),
        "owner_id": "owner", "release_id": "b" * 64,
        "legacy_head_sha256": transition.transition_sha256,
        "strategy_identity": transition.identity.to_dict(), "authority_receipt_sha256": "e" * 64,
    }
    legacy = StrategyRiskStateStore(local_dir=tmp_path / "legacy")
    with pytest.raises(AccountSubmissionError, match="migration mismatch"):
        session.enroll_strategy_state(transition, legacy_store=legacy,
            migration_authorization={**authorization, "account_binding_sha256": "0" * 64})
    with patch.object(StrategyRiskStateStore, "load_chain", side_effect=OSError("storage unavailable")):
        with pytest.raises(AccountSubmissionError, match="legacy strategy state unavailable"):
            session.enroll_strategy_state(transition, legacy_store=legacy, migration_authorization=authorization)
    assert session.read_state()["generation"] == 0


def test_unenrolled_advance_has_no_journal_side_effect(tmp_path):
    session, transition, _, _ = fixture(tmp_path)
    with pytest.raises(AccountSubmissionError, match="enrollment mismatch"):
        session.advance_strategy_state(transition)
    assert session.read_state()["generation"] == 0


def test_conditional_handle_is_session_owned_and_stale_after_advance(tmp_path):
    session, transition, intent, domain = fixture(tmp_path)
    authorization = {"account_domain_key": account_domain_key(domain),
        "account_binding_sha256": submission_binding_digest({"broker": "ibkr", "account_id": "U00000001"}),
        "owner_id": "owner", "release_id": "b" * 64, "legacy_head_sha256": transition.transition_sha256,
        "strategy_identity": transition.identity.to_dict(), "authority_receipt_sha256": "e" * 64}
    session.enroll_strategy_state(transition, legacy_store=StrategyRiskStateStore(local_dir=tmp_path / "legacy"), migration_authorization=authorization)
    handle = session.conditional_planning_handle(strategy_state_sha256=transition.transition_sha256,
        strategy_intent_sha256=submission_binding_digest(intent), strategy_session="2026-10-30", input_sha256="d" * 64)
    assert session.validate_conditional_planning_handle(handle, input_sha256="d" * 64)
    with pytest.raises(AccountSubmissionError):
        session.for_intent("f" * 64).validate_conditional_planning_handle(handle, input_sha256="d" * 64)
    with pytest.raises(AccountSubmissionError):
        session.validate_conditional_planning_handle(handle, input_sha256="0" * 64)
    successor = build_strategy_risk_state_transition(identity=transition.identity, effective_session="2026-10-31",
        input_sha256="f" * 64, state={**transition.state, "session": "2026-10-31", "pending_intent": None,
        "intent_invalidation_reason": "new_session"}, previous_transition=transition)
    session.advance_strategy_state(successor)
    with pytest.raises(AccountSubmissionError):
        session.validate_conditional_planning_handle(handle, input_sha256="d" * 64)


def test_schwab_accepted_needs_broker_order_id():
    observation = {"status": "accepted", "broker_order_id": None, "filled_quantity": 0.0, "average_fill_price": None}
    assert AccountSubmissionSession._certainty(observation, 1) == "UNKNOWN"
    observation["broker_order_id"] = "broker-123"
    assert AccountSubmissionSession._certainty(observation, 1) == "KNOWN_PENDING"


def test_strategy_reduction_requires_held_position_and_fresh_complete_snapshot(tmp_path):
    session, transition, _, domain = fixture(tmp_path)
    authorization = {"account_domain_key": account_domain_key(domain),
        "account_binding_sha256": submission_binding_digest({"broker": "ibkr", "account_id": "U00000001"}),
        "owner_id": "owner", "release_id": "b" * 64, "legacy_head_sha256": transition.transition_sha256,
        "strategy_identity": transition.identity.to_dict(), "authority_receipt_sha256": "e" * 64}
    session.enroll_strategy_state(transition, legacy_store=StrategyRiskStateStore(local_dir=tmp_path / "legacy"), migration_authorization=authorization)
    snapshot = {"balance": 10000, "equity": 9500, "cash": 1000, "currency": "USD",
        "valuation_at": "2026-10-30T00:00:00Z", "source_digest": "sha256:" + "2" * 64,
        "complete": True, "position_risk": 0, "position_3x_exposure": 0,
        "account_domain_key": account_domain_key(domain), "account_id": "U00000001",
        "valid_until": "2026-10-30T04:00:00Z", "pending_3x_exposure": 0,
        "open_orders_complete": True, "positions": {"TQQQ": 2}, "open_orders_empty": True}
    session.record_account_equity(snapshot=snapshot, cash_flow=0, baseline_confirmed=True)
    for side, quantity in (("buy", 1), ("sell", 3)):
        with pytest.raises(AccountSubmissionError, match="reduction not proven"):
            session.reserve_strategy_reduction(OrderIntent(symbol="TQQQ", side=side, quantity=quantity, account_id="U00000001"))
    order = OrderIntent(symbol="TQQQ", side="sell", quantity=1, account_id="U00000001")
    grant = session.reserve_strategy_reduction(order)
    assert session.read_state()["attempts"][grant.attempt_id]["reduction_kind"] == "strategy_position"
    with pytest.raises(AccountSubmissionError, match="unresolved account submission"):
        session.reserve_strategy_reduction(order)


def test_public_order_binding_digest_matches_reservation_identity(tmp_path):
    session, _, _, _ = fixture(tmp_path)
    first = OrderIntent(symbol="TQQQ", side="buy", quantity=1, account_id="U00000001")
    changed = OrderIntent(symbol="TQQQ", side="buy", quantity=2, account_id="U00000001")
    other_account = OrderIntent(symbol="TQQQ", side="buy", quantity=1, account_id="U00000002")
    assert session.order_binding_digest(first) == session._order(first)[0]
    assert session.order_binding_digest(first) != session.order_binding_digest(changed)
    with pytest.raises(AccountSubmissionError, match="account differs"):
        session.order_binding_digest(other_account)
