"""Canonical immutable raw position-sizing contract; no sizing logic."""
from __future__ import annotations
import hashlib
import json
import math
import re
from dataclasses import dataclass
from datetime import date
_DATE=re.compile(r'^\d{4}-\d{2}-\d{2}$'); _ID=re.compile(r'^[A-Za-z0-9._:-]{1,128}$'); _SAFE=2**53-1
class PositionSizingContractError(ValueError): pass
def _fail(): raise PositionSizingContractError('invalid position sizing contract')
def _str(v):
 if type(v) is not str or not v or len(v)>256 or not v.isprintable(): _fail()
 return v
def _id(v):
 v=_str(v)
 if not _ID.fullmatch(v): _fail()
 return v
def _num(v,lo=None,hi=None):
 if type(v) is int:
  if abs(v)>_SAFE: _fail()
 elif type(v) is not float: _fail()
 if not math.isfinite(v): _fail()
 try: out=float(v)
 except (OverflowError,ValueError): _fail()
 if out==0.0: return 0.0
 if lo is not None and out<lo or hi is not None and out>hi: _fail()
 return out
def _date(v):
 v=_str(v)
 if not _DATE.fullmatch(v): _fail()
 try: parsed=date.fromisoformat(v)
 except ValueError: _fail()
 if parsed.isoformat()!=v: _fail()
 return v
def _dict(v,keys):
 if type(v) is not dict or set(v)!=set(keys): _fail()
 return v
def _bytes(v):
 try:return json.dumps(v,ensure_ascii=True,sort_keys=True,separators=(',',':'),allow_nan=False).encode('ascii')
 except (TypeError,ValueError,UnicodeError): _fail()
@dataclass(frozen=True,slots=True)
class Target:
 symbol:str; raw_weight:float
 @classmethod
 def parse(cls,v):
  d=_dict(v,('symbol','raw_weight')); return cls(_id(d['symbol']),_num(d['raw_weight']))
 def wire(self): return {'raw_weight':self.raw_weight,'symbol':self.symbol}
@dataclass(frozen=True,slots=True)
class Evidence:
 package_id:str; scope:str; as_of:str; valid_until:str; digest:str; sample_count:int
 @classmethod
 def parse(cls,v):
  d=_dict(v,('package_id','scope','as_of','valid_until','digest','sample_count')); a=_date(d['as_of']); u=_date(d['valid_until'])
  if u<a or type(d['sample_count']) is not int or not 1<=d['sample_count']<=_SAFE: _fail()
  return cls(_id(d['package_id']),_id(d['scope']),a,u,_id(d['digest']),d['sample_count'])
 def wire(self): return {'as_of':self.as_of,'digest':self.digest,'package_id':self.package_id,'sample_count':self.sample_count,'scope':self.scope,'valid_until':self.valid_until}
@dataclass(frozen=True,slots=True)
class Caps:
 symbol:str; kelly_cap:float; volatility_cap:float; correlation_cap:float; liquidity_cap:float
 @classmethod
 def parse(cls,v):
  d=_dict(v,('symbol','kelly_cap','volatility_cap','correlation_cap','liquidity_cap')); return cls(_id(d['symbol']),_num(d['kelly_cap']),_num(d['volatility_cap']),_num(d['correlation_cap']),_num(d['liquidity_cap']))
 def wire(self): return {'correlation_cap':self.correlation_cap,'kelly_cap':self.kelly_cap,'liquidity_cap':self.liquidity_cap,'symbol':self.symbol,'volatility_cap':self.volatility_cap}
@dataclass(frozen=True,slots=True)
class Authorization:
 position_control_allowed:bool; consumption_evidence_status:str; bounded_budget:float; expires_at:str
 @classmethod
 def parse(cls,v):
  d=_dict(v,('position_control_allowed','consumption_evidence_status','bounded_budget','expires_at'))
  if type(d['position_control_allowed']) is not bool: _fail()
  return cls(d['position_control_allowed'],_id(d['consumption_evidence_status']),_num(d['bounded_budget']),_date(d['expires_at']))
 def wire(self): return {'bounded_budget':self.bounded_budget,'consumption_evidence_status':self.consumption_evidence_status,'expires_at':self.expires_at,'position_control_allowed':self.position_control_allowed}
@dataclass(frozen=True,slots=True)
class Policy:
 fractional_kelly:float; total_exposure_cap:float; cash_reserve:float; risk_scalar:float
 @classmethod
 def parse(cls,v):
  d=_dict(v,('fractional_kelly','total_exposure_cap','cash_reserve','risk_scalar'))
  return cls(_num(d['fractional_kelly']),_num(d['total_exposure_cap']),_num(d['cash_reserve']),_num(d['risk_scalar']))
 def wire(self): return {'cash_reserve':self.cash_reserve,'fractional_kelly':self.fractional_kelly,'risk_scalar':self.risk_scalar,'total_exposure_cap':self.total_exposure_cap}

def _sort(xs): return tuple(sorted(xs,key=lambda x:tuple(x.wire().items())))
@dataclass(frozen=True,eq=False,slots=True)
class CanonicalSizingInput:
 as_of:str; targets:tuple[Target,...]; evidence:tuple[Evidence,...]; caps:tuple[Caps,...]; authorization:Authorization; policy:Policy; risk_route:str
 def to_wire(self):
  _validate_value(self)
  return {'as_of':self.as_of,'authorization':self.authorization.wire(),'caps':[x.wire() for x in self.caps],'evidence':[x.wire() for x in self.evidence],'policy':self.policy.wire(),'risk_route':self.risk_route,'targets':[x.wire() for x in self.targets]}
 @classmethod
 def from_wire(cls,v):
  if type(v) is not dict or set(v)!={'as_of','authorization','caps','evidence','policy','risk_route','targets'}: _fail()
  return _build(v['as_of'],v['targets'],v['evidence'],v['caps'],v['authorization'],v['policy'],v['risk_route'])
 def canonical_bytes(self): return _bytes(self.to_wire())
 def digest(self): return hashlib.sha256(self.canonical_bytes()).hexdigest()
 def __hash__(self): return hash(self.canonical_bytes())
 def __eq__(self,other):
  if not isinstance(other,CanonicalSizingInput): return NotImplemented
  return self.canonical_bytes()==other.canonical_bytes()
def _validate_value(x):
 try:
  _build(x.as_of,tuple(t.wire() for t in x.targets),tuple(e.wire() for e in x.evidence),tuple(c.wire() for c in x.caps),x.authorization.wire(),x.policy.wire(),x.risk_route)
 except PositionSizingContractError: raise
 except (AttributeError,TypeError,ValueError,KeyError,IndexError,OverflowError): _fail()
def _build(as_of,targets,evidence,caps,authorization,policy,risk_route):
 try:
  a=_date(as_of)
  if type(targets) not in (tuple,list) or type(evidence) not in (tuple,list) or type(caps) not in (tuple,list): _fail()
  ts=_sort(tuple(Target.parse(v) for v in targets)); es=_sort(tuple(Evidence.parse(v) for v in evidence)); cs=_sort(tuple(Caps.parse(v) for v in caps))
  if not es: _fail()
  if len({x.symbol for x in ts})!=len(ts) or len({x.symbol for x in cs})!=len(cs) or {x.symbol for x in ts}!={x.symbol for x in cs}: _fail()
  au=Authorization.parse(authorization); po=Policy.parse(policy)
  if au.expires_at<a or type(risk_route) is not str or risk_route not in {'no_action','watch','opportunity_watch','risk_reduced','risk_off','blocked'}: _fail()
  return CanonicalSizingInput(a,ts,es,cs,au,po,risk_route)
 except PositionSizingContractError: raise
 except (AttributeError,TypeError,ValueError,KeyError,IndexError,OverflowError): _fail()
def validate_raw_input(*,as_of,targets,evidence,caps,authorization,policy,risk_route): return _build(as_of,targets,evidence,caps,authorization,policy,risk_route)
