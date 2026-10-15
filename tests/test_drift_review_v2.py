from unittest import mock
from quant_platform_kit.strategy_lifecycle.drift_review import review_critical_drifts


def test_empty_observations_do_not_call_model():
    reviewer = mock.Mock()
    result = review_critical_drifts('us_equity', [], roles=['a','b','c'], revision='a'*40, reviewer=reviewer)
    assert result['ok'] and result['count'] == 0
    reviewer.assert_not_called()


def test_pending_conflict_and_reject_never_authorize():
    for response in ({'status':'pending'}, {'status':'completed','outcome':'requires_human'}, {'status':'completed','outcome':'agree_reject'}):
        reviewer = mock.Mock(return_value=response)
        result = review_critical_drifts('us_equity',[{'profile':'synthetic','drift_score':0.8}],roles=['a','b','c'],revision='a'*40,reviewer=reviewer)
        assert not result['ok'] and result['state']=='PARKED'
        assert result['execution_authority_granted'] is False


def test_approved_advisory_is_bound_to_revision():
    reviewer=mock.Mock(return_value={'status':'completed','outcome':'agree_approve'})
    result=review_critical_drifts('us_equity',[{'profile':'synthetic'}],roles=['a','b','c'],revision='a'*40,reviewer=reviewer)
    first=reviewer.call_args.kwargs['operation_id']
    review_critical_drifts('us_equity',[{'profile':'synthetic'}],roles=['a','b','c'],revision='b'*40,reviewer=reviewer)
    assert reviewer.call_args.kwargs['operation_id'] != first
    assert result['ok'] and result['execution_authority_granted'] is False


def test_private_failure_is_sanitized():
    result=review_critical_drifts('us_equity',[{}],roles=['a','b','c'],revision='a'*40,reviewer=mock.Mock(side_effect=RuntimeError('private credential')))
    assert 'private credential' not in str(result)
    assert result['degraded'] and not result['ok']
