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
              commissionReport=NS(execId=exec_id, currency='USD', commission=0.35))


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
    import json
    from pathlib import Path
    replay = json.loads((Path(__file__).parent / 'fixtures/ibkr-tqqq-sell-three.json').read_text())
    assert replay['synthetic'] is True
    b = Broker(opened=[trade(**replay['pending'])])
    assert resolve(b).status == 'pending'
    b.opened = []
    b.completed = [trade(**replay['terminal'])]
    b.executions = [fill(**replay['execution'])]
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
    completed = trade('Filled', 0, 0, 0, filledQuantity=3, permId=9901)
    completed.log = []
    result = resolve(Broker(completed=[completed], executions=[fill(permId=9901)]))
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


class ErrorEvent:
    def __init__(self):
        self.handlers = []

    def __iadd__(self, handler):
        self.handlers.append(handler)
        return self

    def __isub__(self, handler):
        self.handlers.remove(handler)
        return self

    def emit(self):
        for handler in self.handlers:
            handler(901, 321, 'synthetic-private-diagnostic', None)


@pytest.mark.parametrize('source', ['reqAllOpenOrders', 'reqCompletedOrders', 'reqExecutions'])
def test_unraised_request_error_fails_closed_and_listener_is_restored(source):
    broker = Broker(completed=[trade('Filled', 3, 0, 52)])
    broker.errorEvent = ErrorEvent()
    broker.RaiseRequestErrors = False
    original = getattr(broker, source)
    def failed(*args, **kwargs):
        broker.errorEvent.emit()
        return original(*args, **kwargs)
    setattr(broker, source, failed)
    with pytest.raises(OrderOutcomeReadError, match='^broker_outcome_read_failed$'):
        resolve(broker)
    assert broker.errorEvent.handlers == []
    assert broker.RaiseRequestErrors is False


@pytest.mark.parametrize('report', [NS(commission=0.0, execId='', currency=''),
                                   NS(commission=1.25, execId='synthetic-other', currency='USD'),
                                   NS(commission=0.0, execId='synthetic-exec-1', currency='')])
def test_absent_or_unbound_commission_stays_unknown(report):
    execution = fill()
    execution.commissionReport = report
    assert resolve(Broker(executions=[execution])).commission is None


def test_matching_zero_commission_is_known():
    execution = fill()
    execution.commissionReport.commission = 0.0
    assert resolve(Broker(executions=[execution])).commission == 0.0


@pytest.mark.parametrize('offset,expected', [(0, 'filled'), (-1, 'unknown')])
def test_execution_time_uses_broker_second_precision(offset, expected):
    from datetime import timedelta
    result = resolve_order_outcome(Broker(executions=[fill(time=NOW + timedelta(seconds=offset))]),
        '73', account_id='U00000003', client_id=7, symbol='TQQQ', side='sell', quantity=3,
        submitted_at=NOW.replace(microsecond=123456), execution_filter_factory=NS)
    assert result.status == expected


@pytest.mark.parametrize('permanent', [None, 9900, 9901])
def test_timeless_terminal_cannot_borrow_open_order_timestamp(permanent):
    old = trade('Cancelled', 0, 0, filledQuantity=0)
    old.log = []
    if permanent is not None:
        old.order.permId = permanent
    current = trade(permId=9901)
    assert resolve(Broker(opened=[current], completed=[old])).status == 'unknown'


def test_old_terminal_timestamp_cannot_borrow_newer_open_order_timestamp():
    from datetime import timedelta
    old = trade('Cancelled')
    old.log = [NS(time=NOW - timedelta(seconds=1))]
    assert resolve(Broker(opened=[trade()], completed=[old])).status == 'unknown'


def test_conflicting_execution_permanent_identity_is_unknown():
    result = resolve(Broker(completed=[trade('Filled', 3, 0, 52, permId=9900)],
                            executions=[fill(permId=9901)]))
    assert result.status == 'unknown'


@pytest.mark.parametrize('permanent', [None, 0, -1, True, 1.0, '9901'])
def test_invalid_permanent_id_cannot_date_timeless_terminal(permanent):
    old = trade('Cancelled', 0, 0, filledQuantity=0, permId=permanent)
    old.log = []
    result = resolve(Broker(completed=[old]), permanent_id=permanent)
    assert result.status == 'unknown' and not result.terminal


@pytest.mark.parametrize('trade_id', [None, 0, -1, True, 9902])
def test_timeless_cancel_cannot_borrow_unbound_execution(trade_id):
    old = trade('Cancelled', 0, 0, filledQuantity=1, permId=trade_id)
    old.log = []
    result = resolve(Broker(completed=[old], executions=[fill(1, permId=9901)]))
    assert result.status == 'unknown' and not result.terminal


@pytest.mark.parametrize('permanent', [None, 9901])
def test_timeless_partial_cancel_positive_execution_binding(permanent):
    current = trade('Cancelled', 0, 0, filledQuantity=1, permId=9901)
    current.log = []
    result = resolve(Broker(completed=[current], executions=[fill(1, permId=9901)]),
                     permanent_id=permanent)
    assert result.status == 'cancelled' and result.terminal and result.filled_qty == 1


def test_duplicate_commission_currency_conflict_is_unknown():
    first, second = fill(), fill()
    second.commissionReport.currency = 'EUR'
    result = resolve(Broker(executions=[first, second]))
    assert result.status == 'unknown' and result.commission is None


def test_mixed_commission_currencies_are_not_summed():
    first, second = fill(1), fill(2, exec_id='synthetic-exec-2')
    second.commissionReport.currency = 'EUR'
    result = resolve(Broker(executions=[first, second]))
    assert result.status == 'filled' and result.commission is None


def test_same_currency_duplicate_is_idempotent():
    first = fill()
    assert resolve(Broker(executions=[first, fill()])) == resolve(Broker(executions=[first]))


def test_same_currency_distinct_executions_sum_fees():
    result = resolve(Broker(executions=[fill(1), fill(2, exec_id='synthetic-exec-2')]))
    assert result.status == 'filled' and result.commission == 0.7
