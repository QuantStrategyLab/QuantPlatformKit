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

def test_all_numeric_zero_spellings_are_canonical():
 a=raw(); a['targets']=({'symbol':'SOXL','raw_weight':0},{'symbol':'TQQQ','raw_weight':0.0}); a['caps']=tuple({**x,'kelly_cap':0,'volatility_cap':-0.0,'correlation_cap':0.0,'liquidity_cap':0} for x in a['caps']); a['authorization']={**a['authorization'],'bounded_budget':-0.0}; a['policy']={**a['policy'],'total_exposure_cap':0,'cash_reserve':-0.0,'risk_scalar':0.0}
 b=raw(); b['targets']=({'symbol':'SOXL','raw_weight':-0.0},{'symbol':'TQQQ','raw_weight':0}); b['caps']=tuple({**x,'kelly_cap':0.0,'volatility_cap':0,'correlation_cap':-0.0,'liquidity_cap':0.0} for x in b['caps']); b['authorization']={**b['authorization'],'bounded_budget':0}; b['policy']={**b['policy'],'total_exposure_cap':-0.0,'cash_reserve':0,'risk_scalar':-0.0}
 x=validate_raw_input(**a); y=validate_raw_input(**b); assert x==y and x.to_wire()==y.to_wire() and x.canonical_bytes()==y.canonical_bytes() and x.digest()==y.digest(); assert b':-0' not in x.canonical_bytes()
 class L(list): pass
 b=raw(); b['targets']=L(b['targets'])
 with pytest.raises(PositionSizingContractError): validate_raw_input(**b)
