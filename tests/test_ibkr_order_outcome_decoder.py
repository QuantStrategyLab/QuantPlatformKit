"""Synthetic SDK decoder integrity and diagnostic sink regressions."""
from datetime import datetime, timezone
import logging

import pytest
pytest.importorskip('ib_insync')  # Optional SDK; core sink coverage is unconditional.
from ib_insync import IB, Stock, Order, OrderStatus, Trade, TradeLogEntry

from quant_platform_kit.ibkr.order_outcome import resolve_order_outcome, OrderOutcomeReadError

NOW = datetime(2026, 11, 3, 14, 31, tzinfo=timezone.utc)
ACCOUNT = 'U00000003'  # Synthetic account only.
MARKER = 'synthetic-private-order-reference'


def decoder_broker(*, malformed):
    ib = IB()
    completed = Trade(Stock('TQQQ', 'SMART', 'USD'),
        Order(orderId=73, account=ACCOUNT, clientId=7, action='SELL',
              totalQuantity=3, permId=9901),
        OrderStatus(orderId=73, status='Filled', filled=3, remaining=0, avgFillPrice=52),
        [], [TradeLogEntry(NOW, 'Filled', '')])
    ib.reqAllOpenOrders = lambda: []
    ib.reqCompletedOrders = lambda apiOnly: [completed]
    ib.client.getReqId = lambda: 901
    fields = ['11', '901', '73', '12345', 'TQQQ', 'STK', '', '0', '', '',
              'SMART', 'USD', 'TQQQ', 'NMS', 'synthetic-exec-1',
              '20261103 14:31:00 UTC', ACCOUNT, 'SMART', 'SLD',
              'invalid-shares' if malformed else '3', '52', '9901', '7', '0',
              '3', '52', MARKER, '', '0', '', '1']
    def deliver(req_id, query):
        ib.client.decoder.interpret(fields)
        ib.wrapper.execDetailsEnd(req_id)
    ib.client.reqExecutions = deliver
    return ib


def resolve(ib):
    return resolve_order_outcome(ib, '73', account_id=ACCOUNT, client_id=7,
        symbol='TQQQ', side='sell', quantity=3, submitted_at=NOW, permanent_id=9901)


def test_decoder_failure_does_not_accept_partial_snapshot():
    with pytest.raises(OrderOutcomeReadError, match='^broker_outcome_read_failed$'):
        resolve(decoder_broker(malformed=True))


def test_decoder_failure_does_not_log_private_payload(caplog):
    with caplog.at_level(logging.DEBUG):
        try:
            resolve(decoder_broker(malformed=True))
        except OrderOutcomeReadError:
            pass
    assert MARKER not in caplog.text
    assert ACCOUNT not in caplog.text
    assert not any('Error handling fields' in r.getMessage() for r in caplog.records)


@pytest.mark.parametrize('malformed', [False, True])
def test_decoder_logger_and_listener_restored(malformed):
    ib = decoder_broker(malformed=malformed)
    original = ib.client.decoder.logger
    listeners = len(ib.errorEvent)
    try:
        resolve(ib)
    except OrderOutcomeReadError:
        assert malformed
    assert ib.client.decoder.logger is original
    assert len(ib.errorEvent) == listeners


def test_valid_decoder_control():
    outcome = resolve(decoder_broker(malformed=False))
    assert outcome.status == 'filled' and outcome.terminal and outcome.filled_qty == 3
    assert len(outcome.fills) == 1 and outcome.commission is None


@pytest.mark.parametrize('source', ['reqAllOpenOrders', 'reqCompletedOrders', 'reqExecutions'])
@pytest.mark.parametrize('disabled', [False, True])
def test_decoder_error_in_any_read_fails_even_with_logging_disabled(source, disabled, caplog):
    ib = decoder_broker(malformed=False)
    decoder = ib.client.decoder
    original_logger = decoder.logger
    original_read = getattr(ib, source)
    def failed_read(*args, **kwargs):
        # SDK's generated callback handlers also catch and log exceptions.
        decoder.interpret(['not-a-message-id', ACCOUNT, MARKER])
        return original_read(*args, **kwargs)
    setattr(ib, source, failed_read)
    old_disabled = original_logger.disabled
    original_logger.disabled = disabled
    try:
        with pytest.raises(OrderOutcomeReadError, match='^broker_outcome_read_failed$'):
            resolve(ib)
        assert decoder.logger is original_logger
        assert ACCOUNT not in caplog.text and MARKER not in caplog.text
        setattr(ib, source, original_read)
        assert resolve(ib).terminal  # Failure state does not survive the read.
    finally:
        original_logger.disabled = old_disabled


def test_decoder_logger_restored_when_read_raises():
    ib = decoder_broker(malformed=False)
    original = ib.client.decoder.logger
    def failed(*args, **kwargs):
        raise RuntimeError(MARKER)
    ib.reqExecutions = failed
    with pytest.raises(OrderOutcomeReadError, match='^broker_outcome_read_failed$'):
        resolve(ib)
    assert ib.client.decoder.logger is original
