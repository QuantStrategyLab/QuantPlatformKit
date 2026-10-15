from unittest import mock
import pytest
from quant_platform_kit.strategy_lifecycle.audit_tasks import audit_material


def test_revision_and_material_identity_and_no_merge_authority():
    material={'repository':'QuantStrategyLab/Synthetic','revision':'a'*40,'objective':'synthetic review','evidence':{'diff':'synthetic'}}
    reviewer=mock.Mock(return_value={'status':'completed','outcome':'agree_approve'})
    result=audit_material(material,roles=['primary','secondary','verification'],reviewer=reviewer)
    first=reviewer.call_args.kwargs['operation_id']
    audit_material(material,roles=['primary','secondary','verification'],reviewer=reviewer)
    assert reviewer.call_args.kwargs['operation_id']==first
    audit_material({**material,'revision':'b'*40},roles=['primary','secondary','verification'],reviewer=reviewer)
    assert reviewer.call_args.kwargs['operation_id']!=first
    assert result['revision']==material['revision'] and result['merge_authority_granted'] is False


def test_weak_source_does_not_call_reviewer():
    reviewer=mock.Mock()
    with pytest.raises(ValueError):audit_material({'repository':'owner/repo','revision':'main','objective':'review','evidence':{}},roles=['primary'],reviewer=reviewer)
    reviewer.assert_not_called()
