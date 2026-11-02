"""Synthetic control-chain evidence; no issuer data, venue I/O or live authority.

Stop diagnostics and independently proved account-brake reductions are separate
paths. The tests deliberately do not manufacture a producer joining them.
"""
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest

from quant_platform_kit.common.account_domain import account_domain_key
from quant_platform_kit.common.account_identity import BrokerAccountIdentity
from quant_platform_kit.common.execution_state import (
    AccountSubmissionError, AccountSubmissionSession, ExecutionMarkerStore,
)
from quant_platform_kit.common.execution_translation import (
    translate_weight_decision_to_value_targets, translate_value_decision_to_weight_targets,
)
from quant_platform_kit.common.models import OrderIntent
from quant_platform_kit.common.strategy_contracts import PositionTarget, StrategyDecision
from quant_platform_kit.risk.account_new_risk_gate import (
    InjectedReconciliationSnapshot, NewRiskDisposition, evaluate_new_risk_admission,
)
from quant_platform_kit.risk.capital_risk_envelope import apply_combined_scale_to_targets
from quant_platform_kit.risk.gate import apply_risk_gate
from quant_platform_kit.risk.contracts import RuntimeRiskLimits


NOW = "2026-10-30T02:00:00Z"
# This generated test identity is required by the physical-account schema.
ACCOUNT = "U" + "0" * 8 + "1"
DOMAIN = {
    "identity": {"environment": "LIVE", "platform_id": "ibkr", "server": "synthetic",
                 "account_id_fingerprint": "sha256:" + "1" * 64, "lifecycle_id": "synthetic"},
    "policy": {"capital_kind": "OWN_REAL", "product": "BROKERAGE", "phase": "LIVE",
               "account_type": "CASH", "style": "INTRADAY", "preference": "CAPITAL_PRESERVATION",
               "currency": "USD", "source": "synthetic", "effective_at": "2026-10-01T00:00:00Z",
               "valid_until": "2026-11-01T00:00:00Z", "version": "synthetic-v1"},
}


class FrozenAccount:
    def __init__(self, root):
        self.store = ExecutionMarkerStore(local_dir=root)
        self.identity = BrokerAccountIdentity(platform_id="ibkr", account_types=("CASH",),
            account_modes=("LIVE",), account_id_fingerprint="sha256:" + "1" * 64)
        self.snapshot = {
            "balance": 10000, "equity": 9500, "cash": 1000, "currency": "USD",
            "valuation_at": "2026-10-30T00:00:00Z", "source_digest": "sha256:" + "2" * 64,
            "complete": True, "position_risk": 0, "position_3x_exposure": 0,
            "account_domain_key": account_domain_key(DOMAIN), "account_id": ACCOUNT,
            "valid_until": "2026-10-30T04:00:00Z", "pending_3x_exposure": 0,
            "open_orders_complete": True, "positions": {"TQQQ": 10, "SOXL": 10},
            "open_orders_empty": True,
        }
        session = self.session()
        with pytest.raises(AccountSubmissionError, match="risk reservation required"):
            session.reserve(self.order("TQQQ", "buy", 1))
        session.record_account_equity(snapshot=self.snapshot, cash_flow=0, baseline_confirmed=True)

    def session(self, profile="tqqq_growth_income", intent="a"):
        return AccountSubmissionSession(self.store, broker="ibkr", account_id=ACCOUNT,
            owner_id=profile, profile=profile, intent_id=intent * 64, release_id="b" * 64,
            account_domain=DOMAIN, observed_account_id=ACCOUNT, broker_identity=self.identity,
            observed_at=NOW, decision_at=NOW, clock=lambda: NOW,
            observed_environment="LIVE", observed_server="synthetic", observed_currency="USD",
            observed_lifecycle_id="synthetic")

    @staticmethod
    def order(symbol, side, quantity):
        return OrderIntent(symbol=symbol, side=side, quantity=quantity, account_id=ACCOUNT)

    def brake(self):
        self.snapshot = {**self.snapshot, "equity": 8000, "valuation_at": "2026-10-30T01:00:00Z",
                         "source_digest": "sha256:" + "3" * 64}
        self.session().record_account_equity(snapshot=self.snapshot, cash_flow=0)
        return evaluate_new_risk_admission(InjectedReconciliationSnapshot(
            "COMPLETE", "VERIFIED", "CLOSED", equity_usd=8000, peak_equity_usd=9500))

    def reserve_risk(self, session, order, floor=9000, amount=40):
        return session.reserve_account_risk(order, snapshot=self.snapshot, floor=floor,
            cost_buffer=0, amount=amount, risk_fraction=.005, loss_per_unit=3,
            estimated_fee=2, quantity_step=1, product_leverage_factor=3, unit_price=100,
            existing_3x_exposure=0, pending_3x_exposure=0, leverage_hitl_approved=False,
            account_budget_policy={"preference": "CAPITAL_PRESERVATION", "version": "synthetic-v1",
                "source": "synthetic", "per_trade_fraction": .005, "total_future_risk_limit": 1000,
                "floor": floor, "cost_buffer": 0, "contract_floor": None})


def report(status, filled=0, price=None):
    return SimpleNamespace(status=status, broker_order_id="synthetic-order", filled_quantity=filled,
                           average_fill_price=price)


def static_gate(decision):
    # Complete artificial product metadata isolates the static diagnostic from
    # the independent leverage-classification gate. No live policy is adopted.
    limits = RuntimeRiskLimits(allowed_symbols=("TQQQ",),
        product_leverage_factors={"TQQQ": 3}, nominal_caps={"TQQQ": 1},
        total_nominal_exposure_cap=1, total_effective_exposure_cap=3, max_positions=1)
    return apply_risk_gate(decision, runtime_risk_limits=limits,
                           portfolio_snapshot={"total_equity": 10000})


@pytest.mark.parametrize("field,value,rejected", [
    ("consecutive_losses", 5, False), ("consecutive_losses", 6, True),
    ("unrealized_pnl_pct", -.20, False), ("unrealized_pnl_pct", -.200001, True),
    ("unrealized_pnl_pct", -.35, True), ("unrealized_pnl_pct", float("nan"), True),
])
def test_static_boundaries_do_not_create_exit_orders(field, value, rejected):
    decision = StrategyDecision(positions=(PositionTarget("TQQQ", target_weight=.1),),
                                diagnostics={field: value})
    result = static_gate(decision)
    assert bool(result.positions) is not rejected
    assert bool(result.budgets) is False
    if rejected:
        assert any(flag.startswith("rejected:") for flag in result.risk_flags)
    # The gate returns a StrategyDecision, not a venue order or fill.
    assert type(result) is StrategyDecision


def test_absent_static_diagnostic_does_not_establish_mandatory_gate_coverage():
    original = StrategyDecision(positions=(PositionTarget("TQQQ", target_weight=.1),))
    assert static_gate(original).positions == original.positions
    admission = evaluate_new_risk_admission(InjectedReconciliationSnapshot(
        "UNAVAILABLE", "UNVERIFIED", "CLOSED", equity_usd=None))
    assert admission.disposition == NewRiskDisposition.NEW_RISK_PROHIBITED
    assert admission.live_authority_granted is False


@pytest.mark.parametrize("symbol", ["TQQQ", "SOXL"])
@pytest.mark.parametrize("status,filled,certainty,residual", [
    ("Submitted", 0, "KNOWN_PENDING", 10),
    ("PartiallyFilled", 4, "KNOWN_PENDING", 6),
    ("Rejected", 0, "TERMINAL", 10),
    ("Cancelled", 4, "TERMINAL", 6),
    ("Filled", 10, "TERMINAL", 0),
])
def test_independent_brake_exit_retains_actual_residual(tmp_path, symbol, status, filled, certainty, residual):
    frozen = FrozenAccount(tmp_path)
    admission = frozen.brake()
    assert admission.hard_brake_triggered
    session = frozen.session()
    sell = frozen.order(symbol, "sell", 10)
    grant = session.reserve_reduction(sell, admission=admission)
    calls = []

    def venue():
        calls.append(sell)
        # A synthetic gap fill is deliberately worse than the trigger reference.
        return report(status, filled, 65 if filled else None)

    session.dispatch(grant, sell, venue)
    before = session.read_state()["attempts"][grant.attempt_id]
    assert before["certainty"] == certainty
    assert 10 - before["filled_quantity"] == residual
    assert session.record_observation(grant, report(status, filled, 65 if filled else None)) is False
    restarted = frozen.session(intent="c")
    after = restarted.read_state()["attempts"][grant.attempt_id]
    assert after["filled_quantity"] == filled
    assert after["certainty"] == certainty
    assert len(calls) == 1
    with pytest.raises(AccountSubmissionError):
        restarted.dispatch(grant, sell, venue)
    assert len(calls) == 1
    if filled or certainty == "KNOWN_PENDING":
        with pytest.raises(AccountSubmissionError):
            restarted.reserve_reduction(sell, admission=admission)


@pytest.mark.parametrize("failure", [TimeoutError, ConnectionError])
def test_transport_error_is_unknown_and_survives_restart(tmp_path, failure):
    frozen = FrozenAccount(tmp_path)
    admission = frozen.brake()
    session = frozen.session()
    sell = frozen.order("TQQQ", "sell", 10)
    grant = session.reserve_reduction(sell, admission=admission)

    def venue(): raise failure("synthetic transport failure")

    with pytest.raises(failure): session.dispatch(grant, sell, venue)
    restarted = frozen.session("soxl_soxx_trend_income", intent="c")
    attempt = restarted.read_state()["attempts"][grant.attempt_id]
    assert attempt["certainty"] == "UNKNOWN"
    assert attempt["filled_quantity"] == 0
    with pytest.raises(AccountSubmissionError):
        restarted.reserve_reduction(frozen.order("SOXL", "sell", 10), admission=admission)
    with pytest.raises(AccountSubmissionError):
        frozen.reserve_risk(restarted, frozen.order("SOXL", "buy", 1))


@pytest.mark.parametrize("changes", [
    {"complete": False}, {"equity": float("nan")},
    {"valuation_at": "2026-10-30T03:00:00Z"},
    {"valid_until": "2026-10-30T01:59:59Z"},
    {"source_digest": ""}, {"open_orders_complete": False},
])
def test_untrusted_equity_cannot_replace_committed_checkpoint(tmp_path, changes):
    frozen = FrozenAccount(tmp_path)
    session = frozen.session()
    before = session.read_state()["equity_observation"]
    with pytest.raises((AccountSubmissionError, ValueError)):
        session.record_account_equity(snapshot={**frozen.snapshot, **changes}, cash_flow=0)
    assert frozen.session(intent="c").read_state()["equity_observation"] == before


def test_replay_and_out_of_order_observation_cannot_refresh_source(tmp_path):
    frozen = FrozenAccount(tmp_path)
    session = frozen.session()
    for at in [frozen.snapshot["valuation_at"], "2026-10-29T23:59:59Z"]:
        with pytest.raises(AccountSubmissionError, match="non-monotonic"):
            session.record_account_equity(snapshot={**frozen.snapshot, "valuation_at": at}, cash_flow=0)


def test_new_strategy_identity_cannot_remove_protected_peak_or_brake(tmp_path):
    frozen = FrozenAccount(tmp_path)
    frozen.brake()
    second = frozen.session("soxl_soxx_trend_income", intent="c")
    assert second.read_state()["equity_observation"]["peak"] == 9500
    with pytest.raises(AccountSubmissionError, match="drawdown brake"):
        frozen.reserve_risk(second, frozen.order("SOXL", "buy", 1))


def test_two_strategy_risk_reservations_share_one_budget(tmp_path):
    frozen = FrozenAccount(tmp_path)

    def compete(item):
        profile, symbol, intent = item
        try:
            frozen.reserve_risk(frozen.session(profile, intent), frozen.order(symbol, "buy", 1), 9450)
        except AccountSubmissionError:
            return False
        return True

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(compete, [("tqqq_growth_income", "TQQQ", "a"),
                                         ("soxl_soxx_trend_income", "SOXL", "c")]))
    assert sum(results) == 1
    state = frozen.session().read_state()
    assert len(state["risk_reservations"]) == 1
    assert sum(r["remaining_amount"] for r in state["risk_reservations"].values()) == 40
    assert sum(r["remaining_3x_exposure"] for r in state["risk_reservations"].values()) == 100
    # This is account risk reservation coverage, not shared settled-cash or mapper acceptance.


def test_both_strategies_can_reserve_when_risk_headroom_is_sufficient(tmp_path):
    frozen = FrozenAccount(tmp_path)
    for profile, symbol, intent in [("tqqq_growth_income", "TQQQ", "a"),
                                    ("soxl_soxx_trend_income", "SOXL", "c")]:
        frozen.reserve_risk(frozen.session(profile, intent), frozen.order(symbol, "buy", 1))
    state = frozen.session().read_state()
    assert len(state["risk_reservations"]) == 2
    assert sum(r["remaining_amount"] for r in state["risk_reservations"].values()) == 80


def test_second_strategy_is_rejected_by_shared_budget_after_confirmed_first_reservation(tmp_path):
    frozen = FrozenAccount(tmp_path)
    frozen.reserve_risk(frozen.session(), frozen.order("TQQQ", "buy", 1), floor=9450)
    second = frozen.session("soxl_soxx_trend_income", "c")
    with pytest.raises(AccountSubmissionError, match="account risk budget exceeded"):
        frozen.reserve_risk(second, frozen.order("SOXL", "buy", 1), floor=9450)
    state = second.read_state()
    assert len(state["risk_reservations"]) == 1
    assert sum(r["remaining_amount"] for r in state["risk_reservations"].values()) == 40


def test_same_order_cannot_reserve_again_under_a_second_strategy(tmp_path):
    frozen = FrozenAccount(tmp_path)
    order = frozen.order("TQQQ", "buy", 1)
    frozen.reserve_risk(frozen.session(), order)
    with pytest.raises(AccountSubmissionError, match="duplicate"):
        frozen.reserve_risk(frozen.session("soxl_soxx_trend_income", "c"), order)
    assert len(frozen.session().read_state()["risk_reservations"]) == 1


@pytest.mark.parametrize("scale", [.25, .5, 1])
def test_weight_to_notional_translation_does_not_apply_product_leverage_again(scale):
    targets = apply_combined_scale_to_targets({"TQQQ": .4, "SOXL": .2}, scale)
    decision = StrategyDecision(positions=tuple(PositionTarget(s, target_weight=w) for s, w in targets.items()))
    notionals = translate_weight_decision_to_value_targets(decision, total_equity=1000)
    assert {p.symbol: p.target_value for p in notionals.positions} == pytest.approx(
        {"TQQQ": 400 * scale, "SOXL": 200 * scale})
    restored = translate_value_decision_to_weight_targets(notionals, total_equity=1000)
    assert {p.symbol: p.target_weight for p in restored.positions} == pytest.approx(targets)
    assert sum(p.target_value for p in notionals.positions) <= 600
