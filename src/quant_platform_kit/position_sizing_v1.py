"""Pure, research-only typed position sizing constraints (v1)."""
from __future__ import annotations
import hashlib
import json
import math
import re
from dataclasses import asdict,dataclass
from typing import Mapping

class PositionSizingContractError(ValueError): pass
_DATE=re.compile(r"^\d{4}-\d{2}-\d{2}$")

def _finite(value: object, field: str, *, low: float|None=None, high: float|None=None) -> float:
 if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(float(value)): raise PositionSizingContractError(f"invalid {field}")
 result=float(value)
 if low is not None and result<low or high is not None and result>high: raise PositionSizingContractError(f"invalid {field}")
 return result

def _text(value: object, field: str) -> str:
 if not isinstance(value,str) or not value or len(value)>256 or not value.isprintable(): raise PositionSizingContractError(f"invalid {field}")
 return value

def _date(value: object, field: str) -> str:
 value=_text(value,field)
 if not _DATE.fullmatch(value): raise PositionSizingContractError(f"invalid {field}")
 try:
  from datetime import date; parsed=date.fromisoformat(value)
 except ValueError: raise PositionSizingContractError(f"invalid {field}") from None
 if parsed.isoformat()!=value: raise PositionSizingContractError(f"invalid {field}")
 return value

def _canonical(value: object) -> bytes:
 try:return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=True,allow_nan=False).encode("ascii")
 except (TypeError,ValueError,UnicodeError): raise PositionSizingContractError("invalid canonical sizing") from None

@dataclass(frozen=True,slots=True)
class StrategyTarget:
 symbol: str; raw_weight: float
 def __post_init__(self):
  _text(self.symbol,"symbol"); _finite(self.raw_weight,"raw_weight",low=-1.0,high=1.0)

@dataclass(frozen=True,slots=True)
class EvidenceRef:
 package_id: str; scope: str; as_of: str; valid_until: str; digest: str; sample_count: int
 def __post_init__(self):
  _text(self.package_id,"package_id"); _text(self.scope,"scope"); a=_date(self.as_of,"as_of"); v=_date(self.valid_until,"valid_until")
  if v<a or not _text(self.digest,"digest"): raise PositionSizingContractError("invalid evidence")
  if isinstance(self.sample_count,bool) or not isinstance(self.sample_count,int) or self.sample_count<1: raise PositionSizingContractError("invalid sample_count")

@dataclass(frozen=True,slots=True)
class SymbolCaps:
 symbol: str; kelly_cap: float; volatility_cap: float; correlation_cap: float; liquidity_cap: float
 def __post_init__(self):
  _text(self.symbol,"symbol")
  for name in ("kelly_cap","volatility_cap","correlation_cap","liquidity_cap"): _finite(getattr(self,name),name,low=0.0,high=1.0)

@dataclass(frozen=True,slots=True)
class SizingAuthorization:
 position_control_allowed: bool; consumption_evidence_status: str; bounded_budget: float; expires_at: str
 def __post_init__(self):
  if self.position_control_allowed is not True or self.consumption_evidence_status!="automation_approved": raise PositionSizingContractError("position control not authorized")
  _finite(self.bounded_budget,"bounded_budget",low=0.0,high=1.0); _date(self.expires_at,"expires_at")

@dataclass(frozen=True,slots=True)
class SizingPolicy:
 fractional_kelly: float=0.25; total_exposure_cap: float=1.0; cash_reserve: float=0.0; risk_scalar: float=1.0
 def __post_init__(self):
  _finite(self.fractional_kelly,"fractional_kelly",low=0.0,high=0.5)
  if self.fractional_kelly not in (0.25,0.5): raise PositionSizingContractError("invalid fractional_kelly")
  for name in ("total_exposure_cap","cash_reserve","risk_scalar"): _finite(getattr(self,name),name,low=0.0,high=1.0)

@dataclass(frozen=True,slots=True)
class SizedTarget:
 symbol: str; raw_weight: float; final_weight: float; caps: tuple[tuple[str,float,float],...]; binding_constraint: str

@dataclass(frozen=True,slots=True)
class PositionSizingPlan:
 as_of: str; status: str; targets: tuple[SizedTarget,...]; evidence_digest: str; policy_digest: str; input_digest: str; reject_reason: str|None=None


def build_position_sizing_plan(*, as_of: str, targets: tuple[StrategyTarget,...], evidence: tuple[EvidenceRef,...], caps: tuple[SymbolCaps,...], authorization: SizingAuthorization, policy: SizingPolicy, risk_route: str="no_action") -> PositionSizingPlan:
 as_of=_date(as_of,"as_of")
 if not isinstance(targets,tuple) or not isinstance(evidence,tuple) or not isinstance(caps,tuple): raise PositionSizingContractError("invalid immutable inputs")
 if not evidence or any(e.as_of!=as_of or e.valid_until<as_of for e in evidence): raise PositionSizingContractError("evidence mismatch")
 if authorization.expires_at<as_of: raise PositionSizingContractError("authorization expired")
 if risk_route not in {"no_action","watch","opportunity_watch","risk_reduced","risk_off","blocked"}: raise PositionSizingContractError("invalid risk route")
 names=[t.symbol for t in targets]; capmap={c.symbol:c for c in caps}
 if len(set(names))!=len(names) or len(capmap)!=len(caps) or set(names)!=set(capmap): raise PositionSizingContractError("symbol mismatch")
 input_payload={
  "as_of":as_of,
  "targets":[asdict(x) for x in sorted(targets,key=lambda x:x.symbol)],
  "evidence":[asdict(x) for x in sorted(evidence,key=lambda x:(x.package_id,x.scope,x.digest))],
  "caps":[asdict(x) for x in sorted(caps,key=lambda x:x.symbol)],
  "authorization":asdict(authorization),"policy":asdict(policy),"risk_route":risk_route,
 }
 input_digest=hashlib.sha256(_canonical(input_payload)).hexdigest()
 reserve_aware_cap=max(0.0,policy.total_exposure_cap-policy.cash_reserve)
 scalar=min(policy.risk_scalar,authorization.bounded_budget,0.0 if risk_route in {"risk_off","blocked"} else 1.0)
 built=[]
 for t in targets:
  c=capmap[t.symbol]; k=min(abs(t.raw_weight),c.kelly_cap*policy.fractional_kelly); vals=(k,c.volatility_cap,c.correlation_cap,c.liquidity_cap); uncapped=min(vals); final=uncapped*scalar; binding=("risk_scalar" if scalar<1 else ("kelly_cap" if uncapped==k else ("volatility_cap" if uncapped==c.volatility_cap else ("correlation_cap" if uncapped==c.correlation_cap else "liquidity_cap"))))
  if final==0: binding="zero_cap"
  built.append(SizedTarget(t.symbol,t.raw_weight,math.copysign(final,t.raw_weight) if final else 0.0,(("kelly",abs(t.raw_weight),k),("volatility",k,c.volatility_cap),("correlation",k,c.correlation_cap),("liquidity",k,c.liquidity_cap)),binding))
 total=sum(abs(x.final_weight) for x in built)
 if total>reserve_aware_cap and total>0:
  scale=reserve_aware_cap/total
  built=[SizedTarget(x.symbol,x.raw_weight,x.final_weight*scale,x.caps,"total_exposure") for x in built]
 ed=hashlib.sha256(_canonical(input_payload["evidence"])).hexdigest(); pd=hashlib.sha256(_canonical(asdict(policy))).hexdigest()
 return PositionSizingPlan(as_of,"ZERO_RISK" if risk_route in {"risk_off","blocked"} else "SIZED",tuple(built),ed,pd,input_digest,"risk_off_or_blocked" if risk_route in {"risk_off","blocked"} else None)
