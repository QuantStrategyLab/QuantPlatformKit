import math
import pytest
from quant_platform_kit.position_sizing_contract_v1 import PositionSizingContractError,validate_raw_input

def raw():
 return dict(as_of='2025-01-02',targets=({'symbol':'SOXL','raw_weight':.5},{'symbol':'TQQQ','raw_weight':.4}),evidence=({'package_id':'e','scope':'OOS','as_of':'2025-01-02','valid_until':'2025-02-01','digest':'d','sample_count':10},),caps=({'symbol':'SOXL','kelly_cap':.5,'volatility_cap':.5,'correlation_cap':.5,'liquidity_cap':.5},{'symbol':'TQQQ','kelly_cap':.5,'volatility_cap':.5,'correlation_cap':.5,'liquidity_cap':.5}),authorization={'position_control_allowed':True,'consumption_evidence_status':'automation_approved','bounded_budget':.8,'expires_at':'2025-02-01'},policy={'fractional_kelly':.25,'total_exposure_cap':.8,'cash_reserve':.1,'risk_scalar':1.0},risk_route='no_action')
def test_permutation_roundtrip_equality_hash_wire_digest():
 a=validate_raw_input(**raw()); b=raw(); b['targets']=tuple(reversed(b['targets'])); x=validate_raw_input(**b); assert a.to_wire()==x.to_wire() and a.canonical_bytes()==x.canonical_bytes() and a.digest()==x.digest() and a==x

def test_prefix_collision_and_mutation_isolation():
 a=raw(); a['evidence']=({'package_id':'e','scope':'OOS','as_of':'2025-01-02','valid_until':'2025-02-01','digest':'d','sample_count':10},{'package_id':'e','scope':'OOS','as_of':'2025-01-02','valid_until':'2025-02-01','digest':'d','sample_count':11}); a['targets']=({'symbol':'SOXL','raw_weight':.5},{'symbol':'TQQQ','raw_weight':.4}); x=validate_raw_input(**a); a['evidence'][0]['sample_count']=1; assert x.evidence[0].sample_count==10

def test_malformed_numeric_and_shape_sanitized():
 for value in (10**100,-10**100,True,float('nan'),float('inf')):
  b=raw(); b['targets']=({'symbol':'SOXL','raw_weight':value},{'symbol':'TQQQ','raw_weight':.4})
  with pytest.raises(PositionSizingContractError): validate_raw_input(**b)
 b=raw(); b['policy']={**b['policy'],'extra':1}
 with pytest.raises(PositionSizingContractError): validate_raw_input(**b)
 class L(list): pass
 b=raw(); b['targets']=L(b['targets'])
 with pytest.raises(PositionSizingContractError): validate_raw_input(**b)
