import dataclasses
import pytest
from quant_platform_kit.position_sizing_contract_v1 import CanonicalSizingInput,PositionSizingContractError,validate_raw_input

def raw():
 return dict(as_of='2025-01-02',targets=({'symbol':'SOXL','raw_weight':.5},{'symbol':'TQQQ','raw_weight':.4}),evidence=({'package_id':'e','scope':'OOS','as_of':'2025-01-02','valid_until':'2025-02-01','digest':'d','sample_count':10},),caps=({'symbol':'SOXL','kelly_cap':.5,'volatility_cap':.5,'correlation_cap':.5,'liquidity_cap':.5},{'symbol':'TQQQ','kelly_cap':.5,'volatility_cap':.5,'correlation_cap':.5,'liquidity_cap':.5}),authorization={'position_control_allowed':True,'consumption_evidence_status':'automation_approved','bounded_budget':.8,'expires_at':'2025-02-01'},policy={'fractional_kelly':.25,'total_exposure_cap':.8,'cash_reserve':.1,'risk_scalar':1.0},risk_route='no_action')
def test_canonical_roundtrip_and_mutation():
 source=raw(); x=validate_raw_input(**source); y=CanonicalSizingInput.from_wire(x.to_wire()); assert x==y and hash(x)==hash(y) and x.digest()==y.digest(); source['targets'][0]['raw_weight']=.1; assert {t.raw_weight for t in x.targets}=={.4,.5}

def test_forged_derived_state_and_replace_fail_closed():
 x=validate_raw_input(**raw()); forged=object.__new__(CanonicalSizingInput); object.__setattr__(forged,'as_of',x.as_of); object.__setattr__(forged,'targets',x.targets); object.__setattr__(forged,'evidence',x.evidence); object.__setattr__(forged,'caps',x.caps); object.__setattr__(forged,'authorization',x.authorization); object.__setattr__(forged,'policy',x.policy); object.__setattr__(forged,'risk_route',x.risk_route); assert forged.digest()==x.digest()
 replaced=dataclasses.replace(x,as_of='bad')
 with pytest.raises(PositionSizingContractError): replaced.digest()

def test_permutation_prefix_and_malformed():
 x=validate_raw_input(**raw()); b=raw(); b['targets']=tuple(reversed(b['targets'])); assert x==validate_raw_input(**b)
 b=raw(); b['policy']={**b['policy'],'extra':1}
 with pytest.raises(PositionSizingContractError): validate_raw_input(**b)
 class L(list): pass
 b=raw(); b['targets']=L(b['targets'])
 with pytest.raises(PositionSizingContractError): validate_raw_input(**b)
