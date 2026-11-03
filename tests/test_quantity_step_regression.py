import pytest
from quant_platform_kit.common.account_domain import account_domain_key
from quant_platform_kit.common.account_identity import BrokerAccountIdentity
from quant_platform_kit.common.execution_state import AccountSubmissionError, AccountSubmissionSession, ExecutionMarkerStore
from quant_platform_kit.common.models import OrderIntent


@pytest.mark.parametrize('quantity,step,allowed', [
    (1_000_000_000.1, 1.0, False),
    (10_000_000.001, 0.01, False),
    (10_000_000.02, 0.01, True),
    (100_000_000.1, 0.1, True),
    (0.1 + 0.2, 0.1, True),
    (0.01 * 29, 0.01, True),
    (0.001 * 301, 0.001, True),
])
def test_reservation_requires_quantity_step(tmp_path, quantity, step, allowed):
    # Invented fixture only: the IBKR session validator requires a U-prefixed numeric account ID.
    domain = {
        'identity': {'environment': 'LIVE', 'platform_id': 'ibkr', 'server': 'synthetic', 'account_id_fingerprint': 'sha256:' + '1' * 64, 'lifecycle_id': 'one'},
        'policy': {'capital_kind': 'OWN_REAL', 'product': 'BROKERAGE', 'phase': 'LIVE', 'account_type': 'CASH', 'style': 'INTRADAY', 'preference': 'CAPITAL_PRESERVATION', 'currency': 'USD', 'source': 'synthetic', 'effective_at': '2026-10-01T00:00:00Z', 'valid_until': '2026-11-01T00:00:00Z', 'version': 'one'},
    }
    observed = BrokerAccountIdentity(platform_id='ibkr', account_types=('CASH',), account_modes=('LIVE',), account_id_fingerprint='sha256:' + '1' * 64)
    session = AccountSubmissionSession(ExecutionMarkerStore(local_dir=tmp_path), clock=lambda: '2026-10-30T02:00:00Z', observed_at='2026-10-30T02:00:00Z', decision_at='2026-10-30T02:00:00Z', observed_environment='LIVE', observed_server='synthetic', observed_currency='USD', observed_lifecycle_id='one', broker='ibkr', account_id='U00000001', owner_id='owner', profile='profile', intent_id='a' * 64, release_id='b' * 64, account_domain=domain, observed_account_id='U00000001', broker_identity=observed)
    order = OrderIntent(symbol='VOO', side='buy', quantity=quantity, account_id='U00000001')
    with pytest.raises(AccountSubmissionError, match='risk reservation required'):
        session.reserve(order)
    snapshot = {'balance': 10000, 'equity': 9500, 'cash': 1000, 'currency': 'USD', 'valuation_at': '2026-10-30T00:00:00Z', 'source_digest': 'sha256:' + '2' * 64, 'complete': True, 'position_risk': 0, 'position_3x_exposure': 0, 'account_domain_key': account_domain_key(domain), 'account_id': 'U00000001', 'valid_until': '2026-10-30T04:00:00Z', 'pending_3x_exposure': 0, 'open_orders_complete': True, 'positions': {}, 'open_orders_empty': True}
    session.record_account_equity(snapshot=snapshot, cash_flow=0, baseline_confirmed=True)
    policy = {'preference': 'CAPITAL_PRESERVATION', 'version': 'one', 'source': 'synthetic', 'per_trade_fraction': 0.005, 'total_future_risk_limit': 1000, 'contract_floor': None, 'floor': 9000, 'cost_buffer': 0}
    kwargs = dict(snapshot=snapshot, floor=9000, cost_buffer=0, amount=40, risk_fraction=0.005, loss_per_unit=0.000000001, estimated_fee=0, quantity_step=step, product_leverage_factor=1, unit_price=1, existing_3x_exposure=0, pending_3x_exposure=0, leverage_hitl_approved=False, account_budget_policy=policy)
    if allowed:
        session.reserve_account_risk(order, **kwargs)
    else:
        with pytest.raises(AccountSubmissionError, match='quantity exceeds reserved risk or step'):
            session.reserve_account_risk(order, **kwargs)
