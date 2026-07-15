import pytest
from quant_platform_kit.position_sizing_contract_v1 import PositionSizingContractError, validate_raw_input

def raw():
 return dict(as_of='2025-01-02',targets=({'symbol':'SOXL','raw_weight':.5},{'symbol':'TQQQ','raw_weight':.4}),evidence=({'package_id':'e','scope':'OOS','as_of':'2025-01-02','valid_until':'2025-02-01','digest':'d','sample_count':10},),caps=({'symbol':'SOXL','kelly_cap':.5,'volatility_cap':.5,'correlation_cap':.5,'liquidity_cap':.5},{'symbol':'TQQQ','kelly_cap':.5,'volatility_cap':.5,'correlation_cap':.5,'liquidity_cap':.5}),authorization={'position_control_allowed':True,'consumption_evidence_status':'automation_approved','bounded_budget':.8,'expires_at':'2025-02-01'},policy={'fractional_kelly':.25,'total_exposure_cap':.8,'cash_reserve':.1,'risk_scalar':1.0},risk_route='no_action')
def test_roundtrip_and_permutation_digest():
 a=validate_raw_input(**raw()); b=raw(); b['targets']=tuple(reversed(b['targets'])); assert a.input_digest==validate_raw_input(**b).input_digest
 b=raw(); b['evidence']=({'package_id':'e','scope':'OOS','as_of':'2025-01-02','valid_until':'2025-02-01','digest':'different','sample_count':10},); assert a.input_digest!=validate_raw_input(**b).input_digest
 b=raw(); b['targets']=list(b['targets']); decoded=validate_raw_input(**b); assert isinstance(decoded.targets,tuple); assert decoded.to_wire()['targets']==list(b['targets'])

def test_forged_element_and_sanitized_errors():
 b=raw(); b['targets']=({'symbol':'SOXL','raw_weight':.5},'bad')
 with pytest.raises(PositionSizingContractError): validate_raw_input(**b)
 b=raw(); b['evidence']=({'package_id':'e','scope':'OOS','as_of':'2025-01-02','valid_until':'2025-02-01','digest':'d','sample_count':True},)
 with pytest.raises(PositionSizingContractError): validate_raw_input(**b)

def test_unknown_missing_nonfinite_and_mutation_isolation():
 b=raw(); b['policy']={**b['policy'],'extra':1}
 with pytest.raises(PositionSizingContractError): validate_raw_input(**b)
 x=raw(); out=validate_raw_input(**x); x['targets'][0]['raw_weight']=.1; assert out.targets[0].raw_weight==.5
 for value in (10**100, -(10**100), True, float('nan'), float('inf')):
  b=raw(); b['targets']=({'symbol':'SOXL','raw_weight':value},{'symbol':'TQQQ','raw_weight':.4})
  with pytest.raises(PositionSizingContractError): validate_raw_input(**b)
 class ListSubclass(list): pass
 b=raw(); b['targets']=ListSubclass(b['targets'])
 with pytest.raises(PositionSizingContractError): validate_raw_input(**b)
