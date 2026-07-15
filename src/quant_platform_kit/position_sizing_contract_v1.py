"""Closed raw contract/validator foundation for research position sizing v1."""
from __future__ import annotations
import hashlib
import json
import math
import re
from dataclasses import asdict,dataclass
from datetime import date
from typing import Mapping

class PositionSizingContractError(ValueError): pass
_DATE=re.compile(r'^\d{4}-\d{2}-\d{2}$'); _ID=re.compile(r'^[A-Za-z0-9._:-]{1,128}$')

def _err(): raise PositionSizingContractError('invalid position sizing contract')
def _text(v):
 if type(v) is not str or not v or not v.isprintable() or len(v)>256: _err()
 return v
def _id(v):
 v=_text(v)
 if not _ID.fullmatch(v): _err()
 return v
def _num(v,lo=0.0,hi=1.0):
 if type(v) not in (int,float) or isinstance(v,bool) or not math.isfinite(float(v)): _err()
 v=float(v)
 if v<lo or v>hi: _err()
 return v
def _integer(v):
 if type(v) is not int or v<1 or v>2**53-1: _err()
 return v
def _date(v):
 v=_text(v)
 if not _DATE.fullmatch(v): _err()
 try: parsed=date.fromisoformat(v)
 except ValueError: _err()
 if parsed.isoformat()!=v: _err()
 return v
def _mapping(v, keys):
 if type(v) is not dict or set(v)!=set(keys): _err()
 return v
def _canonical(v):
 try:return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode('ascii')
 except (TypeError,ValueError,UnicodeError): _err()

@dataclass(frozen=True,slots=True)
class RawTarget:
 symbol:str; raw_weight:float
 @classmethod
 def from_raw(cls,v):
  d=_mapping(v,('symbol','raw_weight')); return cls(_id(d['symbol']),_num(d['raw_weight'],-1.0,1.0))

@dataclass(frozen=True,slots=True)
class RawEvidence:
 package_id:str; scope:str; as_of:str; valid_until:str; digest:str; sample_count:int
 @classmethod
 def from_raw(cls,v):
  d=_mapping(v,('package_id','scope','as_of','valid_until','digest','sample_count')); a=_date(d['as_of']); u=_date(d['valid_until'])
  if u<a: _err()
  return cls(_id(d['package_id']),_id(d['scope']),a,u,_id(d['digest']),_integer(d['sample_count']))

@dataclass(frozen=True,slots=True)
class RawCaps:
 symbol:str; kelly_cap:float; volatility_cap:float; correlation_cap:float; liquidity_cap:float
 @classmethod
 def from_raw(cls,v):
  d=_mapping(v,('symbol','kelly_cap','volatility_cap','correlation_cap','liquidity_cap')); return cls(_id(d['symbol']),_num(d['kelly_cap']),_num(d['volatility_cap']),_num(d['correlation_cap']),_num(d['liquidity_cap']))

@dataclass(frozen=True,slots=True)
class RawAuthorization:
 position_control_allowed:bool; consumption_evidence_status:str; bounded_budget:float; expires_at:str
 @classmethod
 def from_raw(cls,v):
  d=_mapping(v,('position_control_allowed','consumption_evidence_status','bounded_budget','expires_at'))
  if type(d['position_control_allowed']) is not bool or d['position_control_allowed'] is not True or d['consumption_evidence_status']!='automation_approved': _err()
  return cls(True,d['consumption_evidence_status'],_num(d['bounded_budget']),_date(d['expires_at']))

@dataclass(frozen=True,slots=True)
class RawPolicy:
 fractional_kelly:float; total_exposure_cap:float; cash_reserve:float; risk_scalar:float
 @classmethod
 def from_raw(cls,v):
  d=_mapping(v,('fractional_kelly','total_exposure_cap','cash_reserve','risk_scalar'))
  if d['fractional_kelly'] not in (0.25,0.5): _err()
  return cls(_num(d['fractional_kelly'],0,.5),_num(d['total_exposure_cap']),_num(d['cash_reserve']),_num(d['risk_scalar']))

@dataclass(frozen=True,slots=True)
class RawSizingInput:
 as_of:str; targets:tuple[RawTarget,...]; evidence:tuple[RawEvidence,...]; caps:tuple[RawCaps,...]; authorization:RawAuthorization; policy:RawPolicy; risk_route:str; input_digest:str


def validate_raw_input(*,as_of,targets,evidence,caps,authorization,policy,risk_route):
 try:
  as_of=_date(as_of)
  if type(targets) is not tuple or type(evidence) is not tuple or type(caps) is not tuple: _err()
  ts=tuple(RawTarget.from_raw(x) for x in targets); es=tuple(RawEvidence.from_raw(x) for x in evidence); cs=tuple(RawCaps.from_raw(x) for x in caps)
  if not es or not all(e.as_of==as_of and e.valid_until>=as_of for e in es): _err()
  if len({x.symbol for x in ts})!=len(ts) or len({x.symbol for x in cs})!=len(cs) or {x.symbol for x in ts}!={x.symbol for x in cs}: _err()
  au=RawAuthorization.from_raw(authorization); po=RawPolicy.from_raw(policy)
  if au.expires_at<as_of or type(risk_route) is not str or risk_route not in {'no_action','watch','opportunity_watch','risk_reduced','risk_off','blocked'}: _err()
 except PositionSizingContractError: raise
 except (AttributeError,TypeError,ValueError,KeyError,IndexError): _err()
 payload={'as_of':as_of,'targets':sorted((asdict(x) for x in ts),key=lambda x:tuple(x.values())), 'evidence':sorted((asdict(x) for x in es),key=lambda x:tuple(x.values())), 'caps':sorted((asdict(x) for x in cs),key=lambda x:tuple(x.values())), 'authorization':asdict(au),'policy':asdict(po),'risk_route':risk_route}
 digest=hashlib.sha256(_canonical(payload)).hexdigest()
 return RawSizingInput(as_of,ts,es,cs,au,po,risk_route,digest)
