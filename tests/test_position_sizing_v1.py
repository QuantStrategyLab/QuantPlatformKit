import math
import pytest
from quant_platform_kit.position_sizing_v1 import (
 EvidenceRef, PositionSizingContractError, SizingAuthorization, SizingPolicy,
 StrategyTarget, SymbolCaps, build_position_sizing_plan,
)

def inputs(k=0.25):
 return dict(as_of='2025-01-02',targets=(StrategyTarget('SOXL',.8),StrategyTarget('TQQQ',.4)),evidence=(EvidenceRef('e1','OOS','2025-01-02','2025-02-01','d1',100),),caps=(SymbolCaps('SOXL',.6,.5,.4,.3),SymbolCaps('TQQQ',.5,.5,.4,.3)),authorization=SizingAuthorization(True,'automation_approved',.8,'2025-02-01'),policy=SizingPolicy(k, .7,.1,1.0))

def test_fractional_caps_and_never_increase():
 p=build_position_sizing_plan(**inputs(.25)); assert p.status=='SIZED'; assert all(abs(x.final_weight)<=abs(x.raw_weight) for x in p.targets); assert p.targets[0].final_weight==pytest.approx(.12)
 assert build_position_sizing_plan(**inputs(.5)).targets[0].final_weight==pytest.approx(.24)

def test_total_scaling_and_risk_off():
 p=build_position_sizing_plan(**inputs()); assert sum(abs(x.final_weight) for x in p.targets)<=.7
 z=build_position_sizing_plan(**inputs(),risk_route='risk_off'); assert z.status=='ZERO_RISK' and all(x.final_weight==0 for x in z.targets)

def test_evidence_auth_and_determinism():
 p=build_position_sizing_plan(**inputs()); q=build_position_sizing_plan(**inputs()); assert p==q and p.input_digest
 with pytest.raises(PositionSizingContractError): build_position_sizing_plan(**{**inputs(),'as_of':'2025-03-01'})
 with pytest.raises(PositionSizingContractError): build_position_sizing_plan(**{**inputs(),'authorization':SizingAuthorization(False,'automation_approved',.8,'2025-02-01')})

def test_invalid_values_and_boundary():
 with pytest.raises(PositionSizingContractError): StrategyTarget('X',math.nan)
 with pytest.raises(PositionSizingContractError): SizingPolicy(.3)
 with pytest.raises(PositionSizingContractError): EvidenceRef('e','OOS','2025-01-02','2024-01-01','d',1)
 with pytest.raises(PositionSizingContractError): build_position_sizing_plan(**{**inputs(),'targets':(StrategyTarget('SOXL',.1),)})
