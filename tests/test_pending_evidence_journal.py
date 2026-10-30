"""Fictional account identifiers and synthetic reports; no real account data."""
from quant_platform_kit.common.execution_state import ExecutionMarkerStore
from types import SimpleNamespace
import tempfile
import unittest

def _account_report(status, filled, price):
    return SimpleNamespace(status=status, broker_order_id="one", filled_quantity=filled, average_fill_price=price)


class JournalEvidenceTest(unittest.TestCase):
  def test_session_evidence_and_legacy(self):
    temp = tempfile.TemporaryDirectory()
    self.addCleanup(temp.cleanup)
    tmp_path = temp.name
    from quant_platform_kit.common.account_identity import BrokerAccountIdentity
    from quant_platform_kit.common.execution_state import AccountSubmissionError, AccountSubmissionSession
    from quant_platform_kit.common.models import OrderIntent
    domain = {
        "identity": {"environment": "LIVE", "platform_id": "ibkr", "server": "synthetic", "account_id_fingerprint": "sha256:" + "1" * 64, "lifecycle_id": "one"},
        "policy": {"capital_kind": "OWN_REAL", "product": "BROKERAGE", "phase": "LIVE", "account_type": "CASH", "style": "INTRADAY", "preference": "CAPITAL_PRESERVATION", "currency": "USD", "source": "synthetic", "effective_at": "2026-10-01T00:00:00Z", "valid_until": "2026-11-01T00:00:00Z", "version": "one"},
    }
    observed = BrokerAccountIdentity(platform_id="ibkr", account_types=("CASH",), account_modes=("LIVE",), account_id_fingerprint="sha256:" + "1" * 64)
    from quant_platform_kit.common.account_domain import account_domain_key
    store = ExecutionMarkerStore(local_dir=tmp_path)
    def session(**extra):
        return AccountSubmissionSession(store, clock=lambda: "2026-10-30T03:00:00Z", observed_at="2026-10-30T03:30:00Z", decision_at="2026-10-30T03:30:00Z", observed_environment="LIVE", observed_server="synthetic", observed_currency="USD", observed_lifecycle_id="one", broker="ibkr", account_id="U00000001", owner_id="owner", profile="profile", intent_id="a" * 64, release_id="b" * 64, **extra)
    order = OrderIntent(symbol="VOO", side="buy", quantity=2, account_id="U00000001")
    with self.assertRaisesRegex(AccountSubmissionError, "mismatch"):
        session(account_domain=domain, observed_account_id="U00000002", broker_identity=observed).reserve(order)
    bound = session(account_domain=domain, observed_account_id="U00000001", broker_identity=observed)
    with self.assertRaisesRegex(AccountSubmissionError, "risk reservation required"):
        bound.reserve(order)
    assert bound.read_state()["domain_binding"]["account_type"] == "CASH"
    snapshot = {"balance": 10000, "equity": 9500, "cash": 1000, "currency": "USD", "valuation_at": "2026-10-30T00:00:00Z", "source_digest": "sha256:" + "2" * 64, "complete": True, "position_risk": 0, "position_3x_exposure": 0, "account_domain_key": account_domain_key(domain), "account_id": "U00000001", "valid_until": "2026-10-30T04:00:00Z", "pending_3x_exposure": 0, "open_orders_complete": True, "positions": {"VOO": 2}, "open_orders_empty": True}
    bound.record_account_equity(snapshot=snapshot, cash_flow=0, baseline_confirmed=True)
    down = {**snapshot, "equity": 9000, "valuation_at": "2026-10-30T01:00:00Z"}
    bound.record_account_equity(snapshot=down, cash_flow=0)
    snapshot = {**snapshot, "equity": 9500, "valuation_at": "2026-10-30T02:00:00Z"}
    bound.record_account_equity(snapshot=snapshot, cash_flow=500)
    assert bound.read_state()["equity_observation"]["peak"] == 10000
    bound.reserve_account_risk(order, snapshot=snapshot, floor=9000, cost_buffer=10, amount=40, risk_fraction=0.005, loss_per_unit=3, estimated_fee=2, quantity_step=1, product_leverage_factor=3, unit_price=3000, existing_3x_exposure=0, pending_3x_exposure=0, leverage_hitl_approved=True, account_budget_policy={"preference": "CAPITAL_PRESERVATION", "version": "one", "source": "synthetic", "per_trade_fraction": 0.005, "total_future_risk_limit": 1000, "contract_floor": None, "floor": 9000, "cost_buffer": 10})
    second = OrderIntent(symbol="QQQM", side="buy", quantity=1, account_id="U00000001")
    with self.assertRaisesRegex(AccountSubmissionError, "product leverage cap exceeded"):
        bound.reserve_account_risk(second, snapshot=snapshot, floor=9000, cost_buffer=0, amount=10,
                                   risk_fraction=0.005, loss_per_unit=1, estimated_fee=0, quantity_step=1,
                                   product_leverage_factor=3, unit_price=10000, existing_3x_exposure=0,
                                   pending_3x_exposure=0, leverage_hitl_approved=True, account_budget_policy={"preference": "CAPITAL_PRESERVATION", "version": "one", "source": "synthetic", "per_trade_fraction": 0.005, "total_future_risk_limit": 1000})
    with self.assertRaisesRegex(AccountSubmissionError, "budget exceeded"):
        bound.reserve_account_risk(second, snapshot=snapshot, floor=9450, cost_buffer=10, amount=1, risk_fraction=0.005, loss_per_unit=0.5, estimated_fee=0, quantity_step=1, product_leverage_factor=1, unit_price=100, existing_3x_exposure=0, pending_3x_exposure=0, leverage_hitl_approved=False, account_budget_policy={"preference": "CAPITAL_PRESERVATION", "version": "one", "source": "synthetic", "per_trade_fraction": 0.005, "total_future_risk_limit": 1000, "contract_floor": None, "floor": 9450, "cost_buffer": 10})
    grant = bound.reserve(order)
    report = bound.dispatch(grant, order, lambda: _account_report("PartiallyFilled", filled=1, price=100), record_observation_watermark=True)
    assert report.status == "PartiallyFilled"
    after_fill = {**snapshot, "valuation_at": "2026-10-30T03:00:00Z", "source_digest": "sha256:" + "3" * 64, "covered_fills": {grant.attempt_id: 1}, "covered_fees": {grant.attempt_id: 2}, "position_risk": 3, "position_3x_exposure": 3000, "pending_3x_exposure": 3000, "open_orders_empty": False}
    bound.record_account_equity(snapshot=after_fill, cash_flow=0)
    bound.reconcile_account_risk(attempt_id=grant.attempt_id, filled_quantity=1, actual_fee=2,
                                 snapshot_position_risk=3, source_digest=after_fill["source_digest"])
    state = bound.read_state()
    reservation = next(iter(state["risk_reservations"].values()))
    assert reservation["remaining_amount"] == 19
    assert reservation["actual_fee"] == 2
    assert state["snapshot_position_risk"] == 3



    assert reservation["remaining_3x_exposure"] == 3000
    with self.assertRaisesRegex(AccountSubmissionError, "product leverage cap exceeded"):
        bound.reserve_account_risk(second, snapshot=after_fill, floor=9000, cost_buffer=10, amount=5, risk_fraction=0.005, loss_per_unit=1, estimated_fee=0, quantity_step=1, product_leverage_factor=3, unit_price=501, existing_3x_exposure=3000, pending_3x_exposure=3000, leverage_hitl_approved=True, account_budget_policy={"preference": "CAPITAL_PRESERVATION", "version": "one", "source": "synthetic", "per_trade_fraction": 0.005, "total_future_risk_limit": 1000, "contract_floor": None, "floor": 9000, "cost_buffer": 10})

    from quant_platform_kit.common.execution_state import submission_binding_digest
    attempt = state["attempts"][grant.attempt_id]
    next_snapshot = {**after_fill, "valuation_at": "2026-10-30T03:20:00Z", "source_digest": "sha256:" + "4" * 64}
    evidence = {"schema_version": "pending_order_evidence.v1", "account_domain_key": account_domain_key(domain), "account_binding": submission_binding_digest({"broker": "ibkr", "account_id": "U00000001"}), "currency": "USD", "source_digest": next_snapshot["source_digest"], "source_version": "synthetic", "valuation_at": next_snapshot["valuation_at"], "observed_through": "2026-10-30T03:10:00Z", "orders": [{"attempt_id": grant.attempt_id, "broker_order_id": "one", "journal_observation_sha256": attempt["observation_event_sha256"], "remaining_quantity": 1, "remaining_fee": 0, "pending_3x_exposure": 3000}]}
    bad = {**evidence, "observed_through": "2026-10-30T02:59:00Z"}
    before = bound.read_state()["generation"]
    for value in (True, -1, float("nan"), float("inf"), 10 ** 400):
        bad_order = {**evidence["orders"][0], "remaining_fee": value}
        invalid = {**evidence, "orders": [bad_order]}
        with self.subTest(value=str(value)[:20]), self.assertRaisesRegex(AccountSubmissionError, "invalid pending order evidence"):
            bound.record_account_equity(snapshot={**next_snapshot, "pending_order_evidence": invalid}, cash_flow=0)
        self.assertEqual(bound.read_state()["generation"], before)
    with self.assertRaisesRegex(AccountSubmissionError, "invalid pending order evidence"):
        bound.record_account_equity(snapshot={**next_snapshot, "pending_order_evidence": bad}, cash_flow=0)
    self.assertEqual(bound.read_state()["generation"], before)
    bound.record_account_equity(snapshot={**next_snapshot, "pending_order_evidence": evidence}, cash_flow=0)
    self.assertEqual(bound.read_state()["equity_observation"]["pending_order_evidence"], evidence)
    with self.assertRaisesRegex(AccountSubmissionError, "product leverage cap exceeded"):
        bound.reserve_account_risk(second, snapshot=next_snapshot, floor=9000, cost_buffer=10, amount=5, risk_fraction=0.005, loss_per_unit=1, estimated_fee=0, quantity_step=1, product_leverage_factor=3, unit_price=501, existing_3x_exposure=3000, pending_3x_exposure=3000, leverage_hitl_approved=True, account_budget_policy={"preference": "CAPITAL_PRESERVATION", "version": "one", "source": "synthetic", "per_trade_fraction": 0.005, "total_future_risk_limit": 1000, "contract_floor": None, "floor": 9000, "cost_buffer": 10})

    # Even a rehashed event cannot bypass semantic replay validation.
    import json
    path = bound._location(bound.read_state()["generation"])
    event = json.loads(path.read_text())
    event["data"]["pending_order_evidence"]["orders"][0]["remaining_quantity"] = 2
    event["event_sha256"] = bound._event_hash(event)
    path.write_text(json.dumps(event))
    with self.assertRaisesRegex(AccountSubmissionError, "invalid pending order evidence"):
        bound.read_state()

  def test_unknown_and_legacy_replay(self):
    temp = tempfile.TemporaryDirectory()
    self.addCleanup(temp.cleanup)
    tmp_path = temp.name
    from quant_platform_kit.common.account_identity import BrokerAccountIdentity
    from quant_platform_kit.common.execution_state import AccountSubmissionError, AccountSubmissionSession
    from quant_platform_kit.common.models import OrderIntent
    domain = {
        "identity": {"environment": "LIVE", "platform_id": "ibkr", "server": "synthetic", "account_id_fingerprint": "sha256:" + "1" * 64, "lifecycle_id": "one"},
        "policy": {"capital_kind": "OWN_REAL", "product": "BROKERAGE", "phase": "LIVE", "account_type": "CASH", "style": "INTRADAY", "preference": "CAPITAL_PRESERVATION", "currency": "USD", "source": "synthetic", "effective_at": "2026-10-01T00:00:00Z", "valid_until": "2026-11-01T00:00:00Z", "version": "one"},
    }
    observed = BrokerAccountIdentity(platform_id="ibkr", account_types=("CASH",), account_modes=("LIVE",), account_id_fingerprint="sha256:" + "1" * 64)
    from quant_platform_kit.common.account_domain import account_domain_key
    store = ExecutionMarkerStore(local_dir=tmp_path)
    def session(**extra):
        return AccountSubmissionSession(store, clock=lambda: "2026-10-30T03:00:00Z", observed_at="2026-10-30T03:30:00Z", decision_at="2026-10-30T03:30:00Z", observed_environment="LIVE", observed_server="synthetic", observed_currency="USD", observed_lifecycle_id="one", broker="ibkr", account_id="U00000001", owner_id="owner", profile="profile", intent_id="a" * 64, release_id="b" * 64, **extra)
    order = OrderIntent(symbol="VOO", side="buy", quantity=2, account_id="U00000001")
    with self.assertRaisesRegex(AccountSubmissionError, "mismatch"):
        session(account_domain=domain, observed_account_id="U00000002", broker_identity=observed).reserve(order)
    bound = session(account_domain=domain, observed_account_id="U00000001", broker_identity=observed)
    with self.assertRaisesRegex(AccountSubmissionError, "risk reservation required"):
        bound.reserve(order)
    assert bound.read_state()["domain_binding"]["account_type"] == "CASH"
    snapshot = {"balance": 10000, "equity": 9500, "cash": 1000, "currency": "USD", "valuation_at": "2026-10-30T00:00:00Z", "source_digest": "sha256:" + "2" * 64, "complete": True, "position_risk": 0, "position_3x_exposure": 0, "account_domain_key": account_domain_key(domain), "account_id": "U00000001", "valid_until": "2026-10-30T04:00:00Z", "pending_3x_exposure": 0, "open_orders_complete": True, "positions": {"VOO": 2}, "open_orders_empty": True}
    bound.record_account_equity(snapshot=snapshot, cash_flow=0, baseline_confirmed=True)
    down = {**snapshot, "equity": 9000, "valuation_at": "2026-10-30T01:00:00Z"}
    bound.record_account_equity(snapshot=down, cash_flow=0)
    snapshot = {**snapshot, "equity": 9500, "valuation_at": "2026-10-30T02:00:00Z"}
    bound.record_account_equity(snapshot=snapshot, cash_flow=500)
    assert bound.read_state()["equity_observation"]["peak"] == 10000
    bound.reserve_account_risk(order, snapshot=snapshot, floor=9000, cost_buffer=10, amount=40, risk_fraction=0.005, loss_per_unit=3, estimated_fee=2, quantity_step=1, product_leverage_factor=3, unit_price=3000, existing_3x_exposure=0, pending_3x_exposure=0, leverage_hitl_approved=True, account_budget_policy={"preference": "CAPITAL_PRESERVATION", "version": "one", "source": "synthetic", "per_trade_fraction": 0.005, "total_future_risk_limit": 1000, "contract_floor": None, "floor": 9000, "cost_buffer": 10})
    second = OrderIntent(symbol="QQQM", side="buy", quantity=1, account_id="U00000001")
    with self.assertRaisesRegex(AccountSubmissionError, "product leverage cap exceeded"):
        bound.reserve_account_risk(second, snapshot=snapshot, floor=9000, cost_buffer=0, amount=10,
                                   risk_fraction=0.005, loss_per_unit=1, estimated_fee=0, quantity_step=1,
                                   product_leverage_factor=3, unit_price=10000, existing_3x_exposure=0,
                                   pending_3x_exposure=0, leverage_hitl_approved=True, account_budget_policy={"preference": "CAPITAL_PRESERVATION", "version": "one", "source": "synthetic", "per_trade_fraction": 0.005, "total_future_risk_limit": 1000})
    with self.assertRaisesRegex(AccountSubmissionError, "budget exceeded"):
        bound.reserve_account_risk(second, snapshot=snapshot, floor=9450, cost_buffer=10, amount=1, risk_fraction=0.005, loss_per_unit=0.5, estimated_fee=0, quantity_step=1, product_leverage_factor=1, unit_price=100, existing_3x_exposure=0, pending_3x_exposure=0, leverage_hitl_approved=False, account_budget_policy={"preference": "CAPITAL_PRESERVATION", "version": "one", "source": "synthetic", "per_trade_fraction": 0.005, "total_future_risk_limit": 1000, "contract_floor": None, "floor": 9450, "cost_buffer": 10})
    grant = bound.reserve(order)
    bound.dispatch(grant, order, lambda: SimpleNamespace(status="mystery", broker_order_id=None, filled_quantity=0, average_fill_price=None))
    restarted = session(account_domain=domain, observed_account_id="U00000001", broker_identity=observed)
    state = restarted.read_state()
    self.assertEqual(state["attempts"][grant.attempt_id]["certainty"], "UNKNOWN")
    self.assertIsNone(state["attempts"][grant.attempt_id]["observation_recorded_at"])
    with self.assertRaisesRegex(AccountSubmissionError, "unresolved"):
        restarted.reserve_account_risk(second, snapshot=snapshot, floor=9000, cost_buffer=10, amount=5, risk_fraction=0.005, loss_per_unit=1, estimated_fee=0, quantity_step=1, product_leverage_factor=3, unit_price=501, existing_3x_exposure=0, pending_3x_exposure=0, leverage_hitl_approved=True, account_budget_policy={"preference": "CAPITAL_PRESERVATION", "version": "one", "source": "synthetic", "per_trade_fraction": 0.005, "total_future_risk_limit": 1000, "contract_floor": None, "floor": 9000, "cost_buffer": 10})
    with self.assertRaisesRegex(AccountSubmissionError, "UNKNOWN/terminal"):
        bound.record_observation(grant, _account_report("Submitted", filled=0, price=None))
