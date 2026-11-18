"""Research cost facts, validation receipts, and trial record contracts."""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Mapping

from ._contracts_observation import validate_periods_per_year

from ._contracts_research_ledger import (
    _RESEARCH_NON_SUCCESS,
    ResearchDailyLedger,
    ResearchTrialStatus,
    _cost_inputs,
    _finite_number,
    _label,
    _raw_identity,
    _reason_code,
    _require_date,
    _run_identity,
)


# Opt-in research companion; existing ledger/receipt serialization is unchanged.
RESEARCH_AVERAGE_COST_POLICY = "RESEARCH_LONG_ONLY_WEIGHTED_AVERAGE_BUY_COST_CAPITALIZED_V1"
RESEARCH_NETTER_COST_SOURCE = "SYNTHETIC_NATIVE_NETTER_V1"


def _research_cost_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


@dataclass(frozen=True)
class ResearchCostFacts:
    """Snapshot of declared synthetic facts, never broker or tax cost authority."""

    payload_json: str

    def __post_init__(self) -> None:
        value = json.loads(self.payload_json)
        if not isinstance(value, dict):
            raise ValueError("COST_FACT_INVALID")
        object.__setattr__(self, "payload_json", _research_cost_json(value))

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> ResearchCostFacts:
        return cls(_research_cost_json(payload))

    def to_dict(self) -> dict[str, Any]:
        return json.loads(self.payload_json)


@dataclass(frozen=True)
class ResearchCostValidationReceipt(ResearchCostFacts):
    """Immutable companion output; this does not amend a stored legacy receipt."""

    @property
    def status(self) -> str:
        return self.to_dict()["status"]


def validate_research_cost_facts(
    ledger: ResearchDailyLedger, facts: ResearchCostFacts,
    previous_receipt: ResearchCostValidationReceipt | None = None,
) -> ResearchCostValidationReceipt:
    """Check explicitly supplied research costs against the original daily book.

    No fills, prices, cost method, fees or cash are produced here. This version
    accepts the named long-only weighted-average policy only. Corrections and
    late fees are unavailable, rather than guessed or applied as new fills.
    """
    if type(ledger) is not ResearchDailyLedger or type(facts) is not ResearchCostFacts:
        raise ValueError("COST_FACT_INVALID")
    data = facts.to_dict()

    def unavailable(reason: str) -> ResearchCostValidationReceipt:
        return ResearchCostValidationReceipt.from_dict({
            "status": "UNAVAILABLE", "reason_codes": [reason],
            "scope": "OFFLINE_RESEARCH_ONLY", "broker_tax_qualified": False})

    def number(value: object, *, nonnegative: bool = False) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError("COST_FACT_INVALID")
        if nonnegative and value < 0:
            raise ValueError("COST_FACT_INVALID")
        return float(value)

    def equal(left: float, right: float, code: str = "COST_RECONCILIATION") -> None:
        if not math.isclose(left, right, rel_tol=1e-10, abs_tol=1e-9):
            raise ValueError(code)

    needed = {"policy_id", "source_label", "synthetic", "synthetic_book_id", "currency",
              "ledger_identity", "opening_book", "coverage", "corrections", "late_fees", "cutoff", "days"}
    if set(data) != needed or not isinstance(data.get("opening_book"), dict):
        return unavailable("COST_SOURCE_OR_OPENING_REQUIRED")
    if (data["policy_id"] != RESEARCH_AVERAGE_COST_POLICY
            or data["source_label"] != RESEARCH_NETTER_COST_SOURCE or data["synthetic"] is not True
            or ledger.synthetic is not True or not isinstance(data["synthetic_book_id"], str)
            or not data["synthetic_book_id"] or not re.fullmatch(r"[A-Z]{3}", str(data["currency"]))
            or ledger.cost_source != RESEARCH_AVERAGE_COST_POLICY):
        return unavailable("COST_RESEARCH_SCOPE_REQUIRED")
    if not isinstance(data["corrections"], list) or not isinstance(data["late_fees"], list):
        raise ValueError("COST_FACT_INVALID")
    if data["corrections"]:
        return unavailable("COST_CORRECTION_UNSUPPORTED")
    if data["late_fees"]:
        return unavailable("COST_LATE_FEE_UNSUPPORTED")
    if data["coverage"] != {"opening": "complete", "fills": "complete", "fees": "complete"}:
        return unavailable("COST_COVERAGE_REQUIRED")
    identity = {key: getattr(ledger, key) for key in ("trial_id", "run_id", "input_id")}
    if data["ledger_identity"] != identity or data["cutoff"] != ledger.window_end.isoformat():
        raise ValueError("COST_LEDGER_BINDING")
    opening = data["opening_book"]
    if set(opening) != {"session", "cash", "positions"} or opening["session"] != ledger.initial_session_date.isoformat():
        return unavailable("COST_OPENING_REQUIRED")
    equal(number(opening["cash"]), ledger.initial_cash)

    def positions(value: object) -> dict[str, dict[str, float]]:
        if not isinstance(value, dict):
            raise ValueError("COST_FACT_INVALID")
        result = {}
        for symbol, position in value.items():
            if not isinstance(symbol, str) or not symbol or not isinstance(position, dict):
                raise ValueError("COST_FACT_INVALID")
            if set(position) != {"quantity", "total_basis", "mark"}:
                raise KeyError("COST_OPENING_REQUIRED")
            result[symbol] = {key: number(item, nonnegative=True) for key, item in position.items()}
            if result[symbol]["mark"] <= 0:
                raise ValueError("COST_FACT_INVALID")
        return result

    try:
        current = positions(opening["positions"])
    except KeyError:
        return unavailable("COST_OPENING_REQUIRED")
    marks = {p.symbol: p for p in ledger.initial_positions}
    for symbol in set(current) | set(marks):
        position = current.get(symbol, {"quantity": 0., "total_basis": 0., "mark": 1.})
        equal(position["quantity"], marks[symbol].quantity if symbol in marks else 0.)
        equal(position["quantity"] * position["mark"], marks[symbol].valuation if symbol in marks else 0.)
        if position["quantity"] == 0:
            equal(position["total_basis"], 0.)
    initial_unrealized = sum(p["quantity"]*p["mark"]-p["total_basis"] for p in current.values())
    if not isinstance(data["days"], list) or len(data["days"]) != len(ledger.days):
        raise ValueError("COST_LEDGER_BINDING")
    seen_fills: dict[str, str] = {}
    seen_fees: set[str] = set()
    cumulative = 0.
    summaries = []
    normalized_days = []
    for declared, day in zip(data["days"], ledger.days):
        if (not isinstance(declared, dict) or set(declared) != {"session", "fills", "positions", "realized_net_cumulative"}
                or declared["session"] != day.session_date.isoformat() or not isinstance(declared["fills"], list)):
            raise ValueError("COST_LEDGER_BINDING")
        if (day.income_cashflow or day.external_cashflow or day.dividend_receivable or day.events
                or day.restricted_cash or day.option_settlement_cashflow or ledger.initial_restricted_cash
                or any(p.option_underlying is not None for p in (*ledger.initial_positions, *day.positions))):
            return unavailable("COST_EVENT_SCOPE_UNSUPPORTED")
        qty = {symbol: p["quantity"] for symbol, p in current.items()}
        basis = {symbol: p["total_basis"] for symbol, p in current.items()}
        flow = fees = realized = 0.
        unique = []
        for fill in declared["fills"]:
            if not isinstance(fill, dict):
                raise ValueError("COST_FACT_INVALID")
            key = fill.get("execution_id")
            if not isinstance(key, str) or not key:
                raise ValueError("COST_FILL_ID_REQUIRED")
            encoded = _research_cost_json(fill)
            if key in seen_fills:
                if seen_fills[key] != encoded:
                    raise ValueError("COST_FILL_CONFLICT")
                continue
            if type(fill.get("revision")) is not int or fill["revision"] != 1 or "supersedes" in fill:
                return unavailable("COST_CORRECTION_UNSUPPORTED")
            if fill.get("known_at") != declared["session"] or fill.get("event_time") != declared["session"]:
                return unavailable("COST_LATE_FEE_OR_TIME_UNSUPPORTED")
            expected = {"execution_id", "revision", "fee_id", "symbol", "side", "quantity", "price", "fee",
                        "event_time", "known_at", "basis_added", "basis_relieved", "realized_net"}
            if set(fill) != expected:
                raise ValueError("COST_FACT_INVALID")
            fee_id = fill["fee_id"]
            if not isinstance(fee_id, str) or not fee_id or fee_id in seen_fees:
                raise ValueError("COST_FEE_DUPLICATE")
            symbol = fill["symbol"]
            if not isinstance(symbol, str) or not symbol:
                raise ValueError("COST_FACT_INVALID")
            amount = number(fill["quantity"], nonnegative=True)
            price = number(fill["price"], nonnegative=True)
            fee = number(fill["fee"], nonnegative=True)
            added = number(fill["basis_added"], nonnegative=True)
            relieved = number(fill["basis_relieved"], nonnegative=True)
            net = number(fill["realized_net"])
            if amount <= 0 or price <= 0:
                raise ValueError("COST_FACT_INVALID")
            old_q, old_b = qty.get(symbol, 0.), basis.get(symbol, 0.)
            if fill["side"] == "BUY":
                equal(added, amount*price+fee)
                equal(relieved, 0.); equal(net, 0.)
                qty[symbol] = old_q+amount
                flow -= amount*price
            elif fill["side"] == "SELL" and old_q > 0 and amount <= old_q+1e-9:
                equal(added, 0.)
                equal(relieved, old_b*amount/old_q)
                equal(net, amount*price-relieved-fee)
                qty[symbol] = old_q-amount
                flow += amount*price
            else:
                raise ValueError("COST_LONG_ONLY_FILL")
            basis[symbol] = old_b+added-relieved
            fees += fee; realized += net
            seen_fills[key] = encoded; seen_fees.add(fee_id); unique.append(fill)
        equal(flow, day.trade_net_cashflow); equal(fees, day.fees)
        try:
            closing = positions(declared["positions"])
        except KeyError as exc:
            raise ValueError("COST_CLOSING_REQUIRED") from exc
        day_marks = {p.symbol: p for p in day.positions}
        for symbol in set(qty) | set(closing) | set(day_marks):
            pos = closing.get(symbol, {"quantity": 0., "total_basis": 0., "mark": 1.})
            equal(pos["quantity"], qty.get(symbol, 0.))
            equal(pos["total_basis"], basis.get(symbol, 0.))
            equal(pos["quantity"], day_marks[symbol].quantity if symbol in day_marks else 0.)
            equal(pos["quantity"]*pos["mark"], day_marks[symbol].valuation if symbol in day_marks else 0.)
        cumulative += realized
        equal(number(declared["realized_net_cumulative"]), cumulative)
        unrealized = sum(p["quantity"]*p["mark"]-p["total_basis"] for p in closing.values())
        equal(cumulative+unrealized-initial_unrealized, day.nav-ledger.initial_nav)
        summaries.append({"session": declared["session"], "positions": closing, "fills": unique,
            "realized_net_cumulative": cumulative, "unrealized": unrealized,
            "accepted_execution_ids": [f["execution_id"] for f in unique],
            "accepted_fee_ids": [f["fee_id"] for f in unique], "cash": day.cash, "nav": day.nav})
        normalized_days.append(dict(declared, fills=unique))
        current = closing
    normalized = dict(data, days=normalized_days)
    source_hash = hashlib.sha256(_research_cost_json(normalized).encode()).hexdigest()
    ledger_hash = hashlib.sha256(_research_cost_json(ledger.to_dict()).encode()).hexdigest()
    payload = {"status": "PASS_SCOPED_SYNTHETIC", "reason_codes": [], "scope": "OFFLINE_RESEARCH_ONLY",
        "broker_tax_qualified": False, "policy_id": data["policy_id"], "source_label": data["source_label"],
        "synthetic_book_id": data["synthetic_book_id"], "currency": data["currency"],
        "fee_convention": "BUY_COST_CAPITALIZED_SELL_COST_EXPENSED_ONCE",
        "source_hash": source_hash, "source_hash_basis": "DEDUPLICATED_DECLARED_SYNTHETIC_WINDOW",
        "ledger_hash": ledger_hash, "ledger_identity": identity, "opening_book": opening,
        "cutoff": data["cutoff"], "coverage": data["coverage"], "synthetic": True,
        "initial_unrealized": initial_unrealized, "source_origin_verified": False,
        "corrections_supported": False, "late_fees_supported": False,
        "calendar_qualified": False, "annualization_performed": False, "days": summaries}
    payload["receipt_id"] = hashlib.sha256(_research_cost_json(payload).encode()).hexdigest()
    if previous_receipt is not None:
        if type(previous_receipt) is not ResearchCostValidationReceipt:
            raise ValueError("COST_PREVIOUS_RECEIPT")
        prior = previous_receipt.to_dict()
        unsigned = {k:v for k,v in prior.items() if k != "receipt_id"}
        if prior.get("receipt_id") != hashlib.sha256(_research_cost_json(unsigned).encode()).hexdigest():
            raise ValueError("COST_PREVIOUS_RECEIPT")
        if (prior.get("status") != payload["status"]
                or any(prior.get(k) != payload[k] for k in ("policy_id", "source_label", "synthetic_book_id", "currency", "opening_book", "ledger_identity"))
                or prior.get("days") != summaries[:len(prior.get("days", []))]):
            raise ValueError("COST_PREVIOUS_PREFIX")
    return ResearchCostValidationReceipt.from_dict(payload)

def _actual_params(value: object, *, required: bool) -> dict[str, Any] | None:
    if value is None:
        if required:
            raise ValueError("actual_config_unknown")
        return None
    if type(value) is not dict:
        raise ValueError("actual_params")
    try:
        parsed = json.loads(json.dumps(value, sort_keys=True, allow_nan=False))
    except (TypeError, ValueError) as exc:
        raise ValueError("actual_params") from exc
    if type(parsed) is not dict or any(type(key) is not str or not key for key in parsed):
        raise ValueError("actual_params")
    return parsed


def _research_identity(value: object) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, Mapping) or not value or any(type(key) is not str or not key for key in value):
        raise ValueError("research_identity")
    try:
        parsed = json.loads(json.dumps(dict(value), sort_keys=True, allow_nan=False))
    except (TypeError, ValueError) as exc:
        raise ValueError("research_identity") from exc
    if type(parsed) is not dict or any(type(key) is not str or not key for key in parsed):
        raise ValueError("research_identity")
    return parsed


def _optional_identity(value: object, *, required: bool) -> str | None:
    if value is None:
        if required:
            raise ValueError("identity")
        return None
    return _raw_identity(value)


@dataclass(frozen=True)
class ResearchTrialRecord:
    """One research attempt. Unknown actual params stay null, never a filler.

    Failed, rejected, and aborted trials store no run or return metric. They
    may keep known cost inputs. Succeeded points at one stored result and ledger.
    """

    trial_id: str
    domain: str
    strategy_profile: str
    status: ResearchTrialStatus
    candidate_config_id: str
    actual_params: Mapping[str, Any] | None
    param_set_id: str | None
    source_revision: str | None
    input_id: str
    window_start: date
    window_end: date
    calendar_id: str
    periods_per_year: float
    cost_source: str | None
    cost_inputs: Mapping[str, float]
    reason_code: str
    synthetic: bool
    run_id: str | None
    param_version: int | None
    research_identity: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        status = self.status
        if isinstance(status, str) and not isinstance(status, ResearchTrialStatus):
            try:
                status = ResearchTrialStatus(status)
            except ValueError as exc:
                raise ValueError("status") from exc
        if not isinstance(status, ResearchTrialStatus):
            raise ValueError("status")
        succeeded = status is ResearchTrialStatus.SUCCEEDED
        trial_id = _raw_identity(self.trial_id)
        domain = _label(self.domain)
        strategy_profile = _label(self.strategy_profile)
        candidate_config_id = _raw_identity(self.candidate_config_id)
        actual_params = _actual_params(self.actual_params, required=succeeded)
        research_identity = _research_identity(self.research_identity)
        param_set_id = _optional_identity(self.param_set_id, required=succeeded)
        source_revision = _optional_identity(self.source_revision, required=succeeded)
        input_id = _raw_identity(self.input_id)
        window_start = _require_date(self.window_start)
        window_end = _require_date(self.window_end)
        if window_end < window_start:
            raise ValueError("window")
        calendar_id = _label(self.calendar_id)
        try:
            periods = validate_periods_per_year(_finite_number(self.periods_per_year))
        except ValueError as exc:
            raise ValueError("periods_per_year") from exc
        cost_source = _optional_identity(self.cost_source, required=succeeded)
        if type(self.synthetic) is not bool:
            raise ValueError("synthetic")
        cost_inputs = _cost_inputs(self.cost_inputs, allow_empty=not succeeded)
        if succeeded:
            if not isinstance(self.run_id, str):
                raise ValueError("research_trial_result_link")
            run_id: str | None = _run_identity(self.run_id)
            if type(self.param_version) is not int or self.param_version <= 0:
                raise ValueError("param_version")
            param_version: int | None = self.param_version
            reason_code = _reason_code(self.reason_code, allow_empty=True)
            if reason_code != "":
                raise ValueError("reason_code")
        else:
            if self.run_id is not None or self.param_version is not None:
                raise ValueError("research_trial_result_link")
            run_id = None
            param_version = None
            if status is ResearchTrialStatus.STARTED:
                reason_code = _reason_code(self.reason_code, allow_empty=True)
                if reason_code != "":
                    raise ValueError("reason_code")
            elif status.value not in _RESEARCH_NON_SUCCESS:
                raise ValueError("status")
            else:
                reason_code = _reason_code(self.reason_code, allow_empty=False)
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "trial_id", trial_id)
        object.__setattr__(self, "domain", domain)
        object.__setattr__(self, "strategy_profile", strategy_profile)
        object.__setattr__(self, "candidate_config_id", candidate_config_id)
        object.__setattr__(self, "actual_params", actual_params)
        object.__setattr__(self, "research_identity", research_identity)
        object.__setattr__(self, "param_set_id", param_set_id)
        object.__setattr__(self, "source_revision", source_revision)
        object.__setattr__(self, "input_id", input_id)
        object.__setattr__(self, "window_start", window_start)
        object.__setattr__(self, "window_end", window_end)
        object.__setattr__(self, "calendar_id", calendar_id)
        object.__setattr__(self, "periods_per_year", periods)
        object.__setattr__(self, "cost_source", cost_source)
        object.__setattr__(self, "cost_inputs", cost_inputs)
        object.__setattr__(self, "reason_code", reason_code)
        object.__setattr__(self, "run_id", run_id)
        object.__setattr__(self, "param_version", param_version)

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "trial_id": self.trial_id,
            "domain": self.domain,
            "strategy_profile": self.strategy_profile,
            "status": self.status.value,
            "candidate_config_id": self.candidate_config_id,
            "actual_params": None if self.actual_params is None else dict(self.actual_params),
            "param_set_id": self.param_set_id,
            "source_revision": self.source_revision,
            "input_id": self.input_id,
            "window_start": self.window_start.isoformat(),
            "window_end": self.window_end.isoformat(),
            "calendar_id": self.calendar_id,
            "periods_per_year": self.periods_per_year,
            "cost_source": self.cost_source,
            "cost_inputs": dict(self.cost_inputs),
            "reason_code": self.reason_code,
            "synthetic": self.synthetic,
            "run_id": self.run_id,
            "param_version": self.param_version,
        }
        if self.research_identity is not None:
            payload["research_identity"] = dict(self.research_identity)
        return payload


