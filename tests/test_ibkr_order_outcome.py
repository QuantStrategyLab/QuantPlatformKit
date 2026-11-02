from datetime import datetime, timezone
from types import SimpleNamespace as NS

import pytest

from quant_platform_kit.ibkr.order_outcome import resolve_order_outcome, OrderOutcomeReadError

NOW = datetime(2026, 11, 3, 14, 31, tzinfo=timezone.utc)


def trade(status='Submitted', filled=0, remaining=3, price=0, **overrides):
    order = dict(orderId=73, account='U00000003', clientId=7, action='SELL', totalQuantity=3)
    order.update(overrides)
    return NS(order=NS(**order), contract=NS(symbol='TQQQ'),
              orderStatus=NS(status=status, filled=filled, remaining=remaining, avgFillPrice=price),
              log=[NS(time=NOW)])


def fill(qty=3, price=52, exec_id='synthetic-exec-1', **overrides):
    values = dict(orderId=73, acctNumber='U00000003', clientId=7, side='SLD', shares=qty,
                  price=price, execId=exec_id, time=NOW)
    values.update(overrides)
    return NS(execution=NS(**values), contract=NS(symbol='TQQQ'),
              commissionReport=NS(commission=0.35))


class Broker:
    def __init__(self, opened=(), completed=(), executions=()):
        self.opened, self.completed, self.executions = opened, completed, executions
        self.reads = []

    def reqAllOpenOrders(self):
        self.reads.append('open')
        return self.opened

    def reqCompletedOrders(self, apiOnly):
        self.reads.append('completed')
        return self.completed

    def reqExecutions(self, query):
        self.reads.append('executions')
        return self.executions


def resolve(broker, **kwargs):
    return resolve_order_outcome(broker, '73', account_id='U00000003', client_id=7,
                                symbol='TQQQ', side='sell', quantity=3,
                                submitted_at=NOW, execution_filter_factory=NS, **kwargs)


def test_pending_then_filled_tqqq_sell_three():
    b = Broker(opened=[trade()])
    assert resolve(b).status == 'pending'
    b.opened = []
    b.completed = [trade('Filled', 3, 0, 52)]
    b.executions = [fill()]
    result = resolve(b)
    assert (result.status, result.filled_qty, result.remaining, result.avg_price) == ('filled', 3, 0, 52)
    assert result.terminal and result.commission == 0.35
    assert result.last_update == NOW.isoformat()
    assert b.reads == ['open', 'completed', 'executions'] * 2


def test_partial_then_cancelled_preserves_fill():
    b = Broker(opened=[trade('Submitted', 1, 2, 51)], executions=[fill(1, 51)])
    assert resolve(b).status == 'partially_filled'
    assert not resolve(b).terminal
    b.opened = []
    b.completed = [trade('Cancelled', 1, 2, 51)]
    result = resolve(b)
    assert result.terminal and result.status == 'cancelled'
    assert result.filled_qty == 1 and result.remaining == 2


@pytest.mark.parametrize('status', ['Rejected', 'Cancelled', 'ApiCancelled'])
def test_zero_fill_terminal(status):
    r = resolve(Broker(completed=[trade(status)]))
    assert r.terminal and r.filled_qty == 0 and r.avg_price is None


@pytest.mark.parametrize('overrides', [dict(orderId=74), dict(account='U00000004'), dict(clientId=8),
                                      dict(action='BUY'), dict(totalQuantity=4)])
def test_identity_mismatch_never_fills(overrides):
    r = resolve(Broker(completed=[trade('Filled', 3, 0, 52, **overrides)]))
    assert r.status == 'unknown' and not r.terminal and r.filled_qty is None


@pytest.mark.parametrize('filled,remaining,price', [(3, 2, 52), (3, 0, 0), (float('nan'), 0, 52), (4, 0, 52)])
def test_invalid_facts_remain_unknown(filled, remaining, price):
    r = resolve(Broker(completed=[trade('Filled', filled, remaining, price)]))
    assert r.status == 'unknown'


def test_executions_can_confirm_full_fill_without_receipt():
    r = resolve(Broker(executions=[fill()]))
    assert r.status == 'filled' and r.filled_qty == 3


def test_conflicting_execution_duplicate_is_unknown():
    assert resolve(Broker(executions=[fill(), fill(price=53)])).status == 'unknown'


def test_missing_evidence_never_assumes_zero_fill():
    r = resolve(Broker())
    assert r.status == 'unknown' and r.filled_qty is None and r.remaining is None


def test_transport_error_is_failure_without_private_diagnostics():
    b = Broker()
    def fail():
        raise TimeoutError('synthetic-private-diagnostic')
    b.reqAllOpenOrders = fail
    with pytest.raises(OrderOutcomeReadError, match='broker_outcome_read_failed') as error:
        resolve(b)
    assert 'synthetic-private-diagnostic' not in str(error.value)


def test_invalid_timestamp_and_old_execution_are_unknown():
    assert resolve(Broker(executions=[fill(time=datetime(2020, 1, 1, tzinfo=timezone.utc))])).status == 'unknown'
    assert resolve(Broker(executions=[fill(time=NOW.replace(tzinfo=None))])).status == 'unknown'


def test_real_completed_order_shape_uses_executions_not_default_zeroes():
    completed = trade('Filled', 0, 0, 0, filledQuantity=3)
    completed.log = []
    result = resolve(Broker(completed=[completed], executions=[fill()]))
    assert result.status == 'filled' and result.filled_qty == 3


def test_completed_cancel_without_executions_requires_stable_permanent_id():
    completed = trade('Cancelled', 0, 0, 0, filledQuantity=0, permId=9901)
    completed.log = []
    b = Broker(completed=[completed])
    assert resolve(b).status == 'unknown'
    assert resolve(b, permanent_id=9901).status == 'cancelled'
    assert resolve(b, permanent_id=9902).status == 'unknown'


def test_same_integer_order_id_on_different_client_is_not_our_order():
    result = resolve(Broker(completed=[trade('Filled', 3, 0, 52, clientId=8), trade('Filled', 3, 0, 52)]))
    assert result.status == 'filled'


def test_broker_callback_diagnostics_are_suppressed_and_logger_restored(caplog):
    import logging
    b = Broker()
    logger = logging.getLogger('synthetic-outcome-broker')
    b.wrapper = NS(_logger=logger)
    def opened():
        b.wrapper._logger.error('synthetic-private-account-diagnostic')
        return []
    b.reqAllOpenOrders = opened
    resolve(b)
    assert 'synthetic-private-account-diagnostic' not in caplog.text
    assert b.wrapper._logger is logger


def test_shared_identifier_mask_never_exposes_short_ids_or_aliases():
    from quant_platform_kit.notifications._redaction import mask_identifier
    for value in ('73', 'synthetic-account-alias', 'U00000003', None):
        assert mask_identifier(value) == '<redacted>'
