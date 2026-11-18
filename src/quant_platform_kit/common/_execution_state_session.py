"""Immutable account submission arbitration session."""

from __future__ import annotations

import hashlib
import json
import math
import os
import stat
import tempfile
import threading
import uuid
from collections.abc import Callable, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path
from typing import Any

from ._execution_state_helpers import (
    _clean_relative_key,
    _first_non_empty,
    _parse_cloud_uri,
)
from ._execution_state_store import ExecutionMarkerStore
from ._execution_state_submission_models import (
    _ACCOUNT_SUBMISSION_LOCKS,
    _ACCOUNT_SUBMISSION_LOCKS_MUTEX,
    _ACCOUNT_SUBMISSION_NAMESPACE,
    _ACCOUNT_WRITER_TOKEN,
    _SUBMISSION_ACK,
    _SUBMISSION_PARTIAL,
    _SUBMISSION_TERMINAL,
    _UNSET,
    ACCOUNT_SUBMISSION_CONTRACT,
    AccountDomainObservation,
    AccountSubmissionError,
    AccountSubmissionGrant,
    RiskReservationSpec,
    _default_utc_clock,
    _resolve_observation,
    _resolve_risk_reservation_spec,
    _submission_account,
    _submission_digest,
    _submission_number,
    _submission_text,
    submission_binding_digest,
)

@dataclass(frozen=True, init=False, eq=False)
class AccountSubmissionSession:
    """Stage B: immutable account arbitration, with no UNKNOWN resolution API.

    Every writer uses one broker/physical-account sequence on the existing
    ObjectStore. A fresh, confirmed create is the only source of a grant. A
    stale listing cannot acquire the occupied next sequence. PREPARED remains
    blocking after crashes; only the original in-memory grant owner can dispatch
    it once. There is no TTL, takeover, delete, reset, or automatic reconciliation.
    """

    contract_version = ACCOUNT_SUBMISSION_CONTRACT

    def __init__(
        self,
        store: ExecutionMarkerStore,
        *,
        broker: str,
        account_id: str,
        owner_id: str,
        profile: str,
        intent_id: str,
        release_id: str,
        observation: AccountDomainObservation | None = None,
        account_domain: Any = _UNSET,
        observed_account_id: Any = _UNSET,
        broker_identity: Any = _UNSET,
        observed_at: Any = _UNSET,
        decision_at: Any = _UNSET,
        observed_environment: Any = _UNSET,
        observed_server: Any = _UNSET,
        observed_currency: Any = _UNSET,
        observed_lifecycle_id: Any = _UNSET,
        clock: Callable[[], Any] | None = None,
    ):
        if not isinstance(store, ExecutionMarkerStore) or not (store.cloud_prefix_uri or store.local_dir):
            raise AccountSubmissionError("existing durable execution store required")
        broker, account = _submission_account(broker, account_id)
        resolved_observation = _resolve_observation(
            observation,
            {
                "account_domain": account_domain,
                "observed_account_id": observed_account_id,
                "broker_identity": broker_identity,
                "observed_at": observed_at,
                "decision_at": decision_at,
                "observed_environment": observed_environment,
                "observed_server": observed_server,
                "observed_currency": observed_currency,
                "observed_lifecycle_id": observed_lifecycle_id,
            },
        )
        account_root = "v1/" + submission_binding_digest({"broker": broker, "account_id": account})
        object.__setattr__(self, "store", store)
        object.__setattr__(self, "broker", broker)
        object.__setattr__(self, "account_id", account)
        object.__setattr__(self, "owner_id", _submission_text(owner_id))
        object.__setattr__(self, "profile", _submission_text(profile))
        object.__setattr__(self, "intent_id", _submission_digest(intent_id))
        object.__setattr__(self, "release_id", _submission_digest(release_id))
        object.__setattr__(self, "account_root", account_root)
        object.__setattr__(self, "_issued", {})
        object.__setattr__(self, "_used", set())
        object.__setattr__(self, "_mutex", threading.RLock())
        object.__setattr__(self, "_failed", False)
        object.__setattr__(self, "_writer_identity", None)
        object.__setattr__(self, "observation", resolved_observation)
        object.__setattr__(self, "account_domain", resolved_observation.account_domain)
        object.__setattr__(self, "observed_account_id", resolved_observation.observed_account_id)
        object.__setattr__(self, "broker_identity", resolved_observation.broker_identity)
        object.__setattr__(self, "observed_at", resolved_observation.observed_at)
        object.__setattr__(self, "decision_at", resolved_observation.decision_at)
        object.__setattr__(self, "observed_environment", resolved_observation.observed_environment)
        object.__setattr__(self, "observed_server", resolved_observation.observed_server)
        object.__setattr__(self, "observed_currency", resolved_observation.observed_currency)
        object.__setattr__(self, "observed_lifecycle_id", resolved_observation.observed_lifecycle_id)
        object.__setattr__(self, "clock", clock if clock is not None else _default_utc_clock)
        location = self._location()
        lock_key = str(location) if store.cloud_prefix_uri else str(location.resolve())
        with _ACCOUNT_SUBMISSION_LOCKS_MUTEX:
            account_mutex = _ACCOUNT_SUBMISSION_LOCKS.setdefault(lock_key, threading.RLock())
        object.__setattr__(self, "_account_mutex", account_mutex)

    @contextmanager
    def _writer_guard(self):
        """Exclude OPEN writers through submit, or deny when exclusion is unknown.

        Local journals use the same kernel lock in every cooperating process.
        ObjectStore has no release/CAS contract: claim permanent process ownership
        instead. No lease expiry or automatic takeover can authorize a restart.
        """
        if self._failed:
            raise AccountSubmissionError("session persistence uncertain")
        if self.store.cloud_prefix_uri:
            location = self.store._cloud_uri_for_namespace(
                self.account_root, "account_writer_ownership",
            )
            # PID distinguishes forked children, which inherit the random token.
            token = f"{_ACCOUNT_WRITER_TOKEN}:{os.getpid()}"
            payload = json.dumps({"kind": "WRITER_OWNERSHIP", "token": token})
            identity = (location, payload)

            def confirm_writer():
                try:
                    if objects.read_text(location) != payload:
                        raise ValueError("different writer")
                except Exception as exc:
                    object.__setattr__(self, "_failed", True)
                    raise AccountSubmissionError("exclusive account writer identity lost or unknown") from exc

            try:
                objects = self.store._object_store()
                if self._writer_identity is None:
                    created = objects.create_text(location, payload, "application/json")
                    if created is not True and created is not False:
                        raise ValueError("unknown create result")
                elif self._writer_identity != identity:
                    raise ValueError("writer identity changed")
                confirm_writer()
            except Exception as exc:
                object.__setattr__(self, "_failed", True)
                raise AccountSubmissionError("exclusive account writer not established") from exc
            object.__setattr__(self, "_writer_identity", identity)
            yield confirm_writer
            confirm_writer()
            return
        fd = None
        try:
            import fcntl
            location = self._location().resolve() / "writer.lock"
            location.parent.mkdir(parents=True, exist_ok=True)
            # Creation is initial setup only. A known lock must never be
            # recreated: another process may still hold its detached inode.
            flags = os.O_RDWR | os.O_NOFOLLOW
            if self._writer_identity is None:
                flags |= os.O_CREAT
            fd = os.open(location, flags, 0o600)
            acquired = os.fstat(fd)
            identity = (str(location), acquired.st_dev, acquired.st_ino)
            if self._writer_identity is not None and self._writer_identity != identity:
                raise AccountSubmissionError("exclusive account writer identity changed")
            fcntl.flock(fd, fcntl.LOCK_EX)
        except (ImportError, OSError, AccountSubmissionError):
            if fd is not None:
                os.close(fd)
            object.__setattr__(self, "_failed", True)
            raise
        try:
            def confirm_writer():
                try:
                    held = os.fstat(fd)
                    named = os.stat(location, follow_symlinks=False)
                    if (not stat.S_ISREG(named.st_mode) or held.st_nlink != 1
                            or (held.st_dev, held.st_ino) != identity[1:]
                            or (named.st_dev, named.st_ino) != identity[1:]):
                        raise ValueError("lock pathname no longer names the locked inode")
                except (OSError, ValueError) as exc:
                    object.__setattr__(self, "_failed", True)
                    raise AccountSubmissionError("exclusive account writer identity lost or unknown") from exc

            confirm_writer()
            object.__setattr__(self, "_writer_identity", identity)
            yield confirm_writer
            confirm_writer()
        finally:
            os.close(fd)

    def _location(self, sequence: int | None = None):
        suffix = self.account_root + "/" + (f"{sequence:020d}.json" if sequence is not None else "")
        if self.store.cloud_prefix_uri:
            if sequence is None:
                return self.store._cloud_prefix_for_namespace(self.account_root, _ACCOUNT_SUBMISSION_NAMESPACE)
            return self.store._cloud_uri_for_namespace(suffix.removesuffix(".json"), _ACCOUNT_SUBMISSION_NAMESPACE)
        return Path(self.store.local_dir).expanduser() / _ACCOUNT_SUBMISSION_NAMESPACE / suffix

    def _order(self, order) -> tuple[str, float]:
        _, account = _submission_account(self.broker, getattr(order, "account_id", None))
        if account != self.account_id:
            raise AccountSubmissionError("submission account differs from session")
        quantity = _submission_number(getattr(order, "quantity", None))
        if quantity <= 0:
            raise AccountSubmissionError("positive submission quantity required")
        limit = getattr(order, "limit_price", None)
        if limit is not None:
            limit = _submission_number(limit)
        descriptor = {
            "account_id": account, "symbol": _submission_text(getattr(order, "symbol", "")).upper(),
            "side": _submission_text(getattr(order, "side", "")).lower(), "quantity": quantity,
            "order_type": _submission_text(getattr(order, "order_type", "market")).lower(),
            "limit_price": limit, "time_in_force": str(getattr(order, "time_in_force", None) or "DAY").upper(),
            "metadata": dict(getattr(order, "metadata", None) or {}),
        }
        if descriptor["side"] not in {"buy", "sell"}:
            raise AccountSubmissionError("unsupported submission side")
        return submission_binding_digest(descriptor), quantity

    @staticmethod
    def _event_hash(event: Mapping[str, Any]) -> str:
        return submission_binding_digest({k: v for k, v in event.items() if k != "event_sha256"})

    @staticmethod
    def _certainty(observation: Mapping[str, Any], quantity: float) -> str:
        status, order_id = observation["status"], observation["broker_order_id"]
        filled, price = observation["filled_quantity"], observation["average_fill_price"]
        if filled > quantity or (filled > 0 and (price is None or price <= 0)):
            return "UNKNOWN"
        if status in {"Rejected", "rejected", "Cancelled", "ApiCancelled"}:
            return "TERMINAL"
        if not order_id:
            return "UNKNOWN"
        if status == "Filled":
            return "TERMINAL" if filled == quantity else "UNKNOWN"
        if status in _SUBMISSION_PARTIAL:
            return "KNOWN_PENDING" if 0 < filled < quantity else "UNKNOWN"
        if status in _SUBMISSION_ACK:
            return "KNOWN_PENDING"
        return "UNKNOWN"

    def read_state(self) -> dict[str, Any]:
        """Validate and reduce all account events; absence alone grants nothing."""
        prefix = self._location()
        if self.store.cloud_prefix_uri:
            objects = self.store._object_store()
            locations = list(objects.list(str(prefix)))
            read = objects.read_text
        else:
            locations = list(prefix.glob("*.json")) if prefix.exists() else []
            def read(path):
                return path.read_text(encoding="utf-8")
        if len(locations) != len(set(map(str, locations))):
            raise AccountSubmissionError("duplicate account journal sequence")
        state: dict[str, Any] = {"generation": 0, "head_sha256": "0" * 64, "attempts": {}, "domain_binding": None, "risk_reservations": {}, "equity_observation": None, "snapshot_position_risk": 0.0, "circuit_breaker_open": False}
        for location in sorted(locations, key=str):
            sequence = state["generation"] + 1
            if str(location) != str(self._location(sequence)):
                raise AccountSubmissionError("incomplete or wrong account journal sequence")
            try:
                event = json.loads(read(location))
            except (ValueError, TypeError) as exc:
                raise AccountSubmissionError("invalid account journal JSON") from exc
            required = {"schema_version", "account_root", "sequence", "previous_sha256", "kind", "data", "event_sha256"}
            if not isinstance(event, dict) or set(event) != required:
                raise AccountSubmissionError("invalid account journal event fields")
            if (event["schema_version"] != ACCOUNT_SUBMISSION_CONTRACT or event["account_root"] != self.account_root
                    or type(event["sequence"]) is not int or event["sequence"] != sequence
                    or event["previous_sha256"] != state["head_sha256"]
                    or event["event_sha256"] != self._event_hash(event)):
                raise AccountSubmissionError("account journal schema/root/hash/sequence mismatch")
            data = event["data"]
            if not isinstance(data, dict):
                raise AccountSubmissionError("invalid account event data")
            if event["kind"] == "CIRCUIT_BREAKER_OPEN":
                from quant_platform_kit.risk.capital_risk_envelope import evaluate_capital_risk_envelope
                if set(data) != {"equity_usd", "peak_equity_usd", "drawdown_from_peak", "owner_id", "profile"} or state["circuit_breaker_open"]:
                    raise AccountSubmissionError("invalid or duplicate circuit breaker OPEN")
                _submission_text(data["owner_id"])
                _submission_text(data["profile"])
                equity = _submission_number(data["equity_usd"])
                peak = None if data["peak_equity_usd"] is None else _submission_number(data["peak_equity_usd"])
                drawdown = None if data["drawdown_from_peak"] is None else _submission_number(data["drawdown_from_peak"])
                if drawdown is None and peak is not None and peak > 0:
                    drawdown = max(0.0, 1.0 - equity / peak)
                if "DRAWDOWN_BRAKE_TRIPPED" not in evaluate_capital_risk_envelope(equity, drawdown_from_peak=drawdown).reasons:
                    raise AccountSubmissionError("circuit breaker OPEN requires a drawdown breach")
                state["circuit_breaker_open"] = True
            elif event["kind"] == "DOMAIN_BOUND":
                if set(data) != {"domain_key", "account_type", "currency"} or state["domain_binding"] is not None:
                    raise AccountSubmissionError("invalid or duplicate domain binding")
                _submission_digest(data["domain_key"])
                _submission_text(data["account_type"])
                _submission_text(data["currency"])
                state["domain_binding"] = data
            elif event["kind"] == "EQUITY_OBSERVED":
                equity_fields = {"equity", "cash_flow", "peak", "currency", "valuation_at", "source_digest", "covered_fills", "covered_fees", "position_risk", "position_3x_exposure", "protected_equity", "balance", "cash", "account_domain_key", "account_binding", "valid_until", "pending_3x_exposure", "open_orders_complete", "positions", "open_orders_empty"}
                if set(data) not in (equity_fields, equity_fields | {"pending_order_evidence"}) or state["domain_binding"] is None:
                    raise AccountSubmissionError("invalid equity observation")
                equity = _submission_number(data["equity"])
                _submission_number(data["balance"])
                _submission_number(data["cash"])
                if state["domain_binding"] is None or data["account_domain_key"] != state["domain_binding"]["domain_key"] or data["account_binding"] != submission_binding_digest({"broker": self.broker, "account_id": self.account_id}) or data["open_orders_complete"] is not True or _submission_number(data["pending_3x_exposure"]) < 0:
                    raise AccountSubmissionError("invalid snapshot account or pending observation")
                if not isinstance(data["positions"], dict) or any(not isinstance(symbol, str) or not symbol or not math.isfinite(_submission_number(qty)) for symbol, qty in data["positions"].items()) or type(data["open_orders_empty"]) is not bool:
                    raise AccountSubmissionError("invalid position or pending observation")
                from quant_platform_kit.common.account_domain import _time
                if _time(data["valid_until"]) <= _time(data["valuation_at"]):
                    raise AccountSubmissionError("invalid snapshot validity interval")
                cash_flow = _submission_number(data["cash_flow"])
                peak = _submission_number(data["peak"])
                if not isinstance(data["covered_fills"], dict) or any(not isinstance(key, str) or _submission_number(value) < 0 for key, value in data["covered_fills"].items()):
                    raise AccountSubmissionError("invalid covered attempt ids")
                if not isinstance(data["covered_fees"], dict) or any(not isinstance(key, str) or _submission_number(value) < 0 for key, value in data["covered_fees"].items()):
                    raise AccountSubmissionError("invalid covered fees")
                if _submission_number(data["position_3x_exposure"]) < 0:
                    raise AccountSubmissionError("invalid 3x position exposure")
                if _submission_number(data["position_risk"]) < 0:
                    raise AccountSubmissionError("invalid position risk")
                previous = state["equity_observation"]
                expected_peak = equity if previous is None else max(equity, previous["peak"] + cash_flow)
                expected_protected = equity if previous is None else max(equity, previous["protected_equity"])
                if data["protected_equity"] != expected_protected:
                    raise AccountSubmissionError("invalid protected equity transition")
                if equity < 0 or peak < 0 or not math.isclose(peak, expected_peak, rel_tol=1e-12, abs_tol=1e-9) or data["currency"] != state["domain_binding"]["currency"]:
                    raise AccountSubmissionError("invalid equity peak transition")
                from quant_platform_kit.common.account_domain import _time
                if previous is not None and _time(data["valuation_at"]) <= _time(previous["valuation_at"]):
                    raise AccountSubmissionError("non-monotonic equity observation")
                if "pending_order_evidence" in data:
                    from quant_platform_kit.common.pending_order_evidence import validate_pending_order_evidence
                    try:
                        validate_pending_order_evidence(data["pending_order_evidence"], observation=data,
                                                        attempts=state["attempts"], reservations=state["risk_reservations"])
                    except (ValueError, TypeError, KeyError) as exc:
                        raise AccountSubmissionError("invalid pending order evidence") from exc
                state["equity_observation"] = data
                state["snapshot_position_risk"] = _submission_number(data["position_risk"])
            elif event["kind"] == "RISK_RESERVED":
                if set(data) != {"order_sha256", "amount", "currency", "valuation_at", "source_digest", "reserved_3x_exposure", "quantity", "estimated_fee", "loss_per_unit", "quantity_step", "risk_fraction", "product_leverage_factor", "unit_price", "existing_3x_exposure", "pending_3x_exposure", "floor", "cost_buffer", "leverage_hitl_approved", "account_budget_policy"}:
                    raise AccountSubmissionError("invalid risk reservation")
                order_digest = _submission_digest(data["order_sha256"])
                amount = _submission_number(data["amount"])
                exposure = _submission_number(data["reserved_3x_exposure"])
                if amount <= 0 or exposure < 0 or order_digest in state["risk_reservations"] or state["domain_binding"] is None:
                    raise AccountSubmissionError("invalid or duplicate risk reservation")
                if data["currency"] != state["domain_binding"]["currency"]:
                    raise AccountSubmissionError("risk reservation currency mismatch")
                _submission_text(data["valuation_at"])
                _submission_text(data["source_digest"])
                quantity = _submission_number(data["quantity"])
                fee = _submission_number(data["estimated_fee"])
                for field in ("loss_per_unit", "quantity_step", "risk_fraction", "product_leverage_factor", "unit_price", "existing_3x_exposure", "pending_3x_exposure", "floor", "cost_buffer"):
                    _submission_number(data[field])
                if not isinstance(data["account_budget_policy"], dict):
                    raise AccountSubmissionError("invalid account budget policy")
                if type(data["leverage_hitl_approved"]) is not bool:
                    raise AccountSubmissionError("invalid leverage approval fact")
                if quantity <= 0 or fee < 0 or fee > amount:
                    raise AccountSubmissionError("invalid reserved quantity or fee")
                state["risk_reservations"][order_digest] = {**data, "remaining_amount": amount, "reconciled_filled": 0.0, "actual_fee": 0.0, "remaining_3x_exposure": exposure}
            elif event["kind"] == "RISK_RECONCILED":
                from quant_platform_kit.common.account_domain import _time
                if set(data) != {"attempt_id", "filled_quantity", "actual_fee", "snapshot_position_risk", "source_digest"}:
                    raise AccountSubmissionError("invalid risk reconciliation")
                attempt = state["attempts"].get(data["attempt_id"])
                observation = state["equity_observation"]
                if attempt is None or observation is None or data["source_digest"] != observation["source_digest"]:
                    raise AccountSubmissionError("risk reconciliation snapshot mismatch")
                reservation = state["risk_reservations"].get(attempt["order_sha256"])
                filled = _submission_number(data["filled_quantity"])
                fee = _submission_number(data["actual_fee"])
                position_risk = _submission_number(data["snapshot_position_risk"])
                if (reservation is None or attempt["certainty"] not in {"TERMINAL", "KNOWN_PENDING"}
                        or observation["covered_fills"].get(data["attempt_id"]) != filled
                        or observation["covered_fees"].get(data["attempt_id"]) != fee
                        or observation["position_risk"] != position_risk
                        or observation["source_digest"] == reservation["source_digest"]
                        or _time(observation["valuation_at"]) <= _time(reservation["valuation_at"])
                        or filled != attempt["filled_quantity"] or filled < reservation["reconciled_filled"]
                        or fee < reservation["actual_fee"] or position_risk < 0):
                    raise AccountSubmissionError("risk reconciliation facts mismatch")
                if attempt["certainty"] == "TERMINAL":
                    remaining = 0.0
                else:
                    remaining = (reservation["amount"] - reservation["estimated_fee"]) * (1.0 - filled / reservation["quantity"]) + max(0.0, reservation["estimated_fee"] - fee)
                remaining_3x = 0.0 if attempt["certainty"] == "TERMINAL" else reservation["reserved_3x_exposure"] * (1.0 - filled / reservation["quantity"])
                reservation.update(remaining_amount=remaining, remaining_3x_exposure=remaining_3x, reconciled_filled=filled, actual_fee=fee)
                state["snapshot_position_risk"] = position_risk
            elif event["kind"] == "PREPARED":
                keys = {"attempt_id", "fence", "intent_id", "order_sha256", "release_id", "owner_id", "profile", "quantity"}
                if set(data) not in (keys, keys | {"reduction", "reduction_source_digest"}, keys | {"new_risk"}) or ("reduction" in data and data["reduction"] is not True):
                    raise AccountSubmissionError("invalid prepared fields")
                if "new_risk" in data and (data["new_risk"] is not True or state["circuit_breaker_open"]):
                    raise AccountSubmissionError("new risk prepared while circuit breaker OPEN")
                for key in ["attempt_id", "fence", "intent_id", "order_sha256", "release_id"]:
                    _submission_digest(data[key])
                for key in ["owner_id", "profile"]:
                    _submission_text(data[key])
                quantity = _submission_number(data["quantity"])
                if quantity <= 0 or any(a["certainty"] in {"PREPARED", "UNKNOWN"} for a in state["attempts"].values()):
                    raise AccountSubmissionError("prepared event bypasses unresolved account")
                if data["attempt_id"] in state["attempts"] or any(
                    (a["intent_id"], a["order_sha256"]) == (data["intent_id"], data["order_sha256"])
                    for a in state["attempts"].values()
                ):
                    raise AccountSubmissionError("duplicate submission identity")
                if state["domain_binding"] is not None and not data.get("reduction"):
                    if (data["order_sha256"] not in state["risk_reservations"] or any(
                            a["order_sha256"] == data["order_sha256"] and not a.get("reduction")
                            for a in state["attempts"].values())):
                        raise AccountSubmissionError("account risk reservation already used or missing")
                state["attempts"][data["attempt_id"]] = {
                    **data, "generation": sequence, "event_sha256": event["event_sha256"],
                    "certainty": "PREPARED", "observation": None, "filled_quantity": 0.0,
                    "prepared_snapshot": state["equity_observation"],
                }
            elif event["kind"] == "OBSERVED":
                if set(data) not in ({"attempt_id", "observation"}, {"attempt_id", "observation", "recorded_at"}) or data["attempt_id"] not in state["attempts"]:
                    raise AccountSubmissionError("observation references unknown attempt")
                attempt = state["attempts"][data["attempt_id"]]
                observation = data["observation"]
                if not isinstance(observation, dict) or set(observation) != {
                    "status", "broker_order_id", "filled_quantity", "average_fill_price", "certainty",
                }:
                    raise AccountSubmissionError("invalid observation fields")
                if not isinstance(observation["status"], str):
                    raise AccountSubmissionError("invalid broker status")
                if observation["broker_order_id"] is not None:
                    _submission_text(observation["broker_order_id"])
                filled = _submission_number(observation["filled_quantity"])
                if observation["average_fill_price"] is not None:
                    _submission_number(observation["average_fill_price"])
                certainty = self._certainty(observation, attempt["quantity"])
                prior = attempt["observation"]
                if (certainty != observation["certainty"] or filled < attempt["filled_quantity"]
                        or filled > attempt["quantity"] or attempt["certainty"] in {"UNKNOWN", "TERMINAL"}
                        or (prior and prior["broker_order_id"] and prior["broker_order_id"] != observation["broker_order_id"])):
                    raise AccountSubmissionError("illegal or non-monotonic observation; UNKNOWN cannot be resolved")
                recorded_at = data.get("recorded_at")
                if recorded_at is not None:
                    from quant_platform_kit.common.account_domain import _time
                    try:
                        instant = _time(recorded_at)
                        previous_watermark = attempt.get("last_observation_recorded_at")
                        if previous_watermark is not None and instant < _time(previous_watermark):
                            raise ValueError("reception time moved backwards")
                    except (ValueError, TypeError) as exc:
                        raise AccountSubmissionError("invalid journal observation watermark") from exc
                    attempt["last_observation_recorded_at"] = recorded_at
                attempt.update(certainty=certainty, observation=observation, filled_quantity=filled,
                               observation_event_sha256=event["event_sha256"], observation_recorded_at=recorded_at)
            else:
                raise AccountSubmissionError("unsupported account event; no resolution API")
            state.update(generation=sequence, head_sha256=event["event_sha256"])
        return state

    def _append(self, state: Mapping[str, Any], kind: str, data: dict) -> dict:
        event = {
            "schema_version": ACCOUNT_SUBMISSION_CONTRACT, "account_root": self.account_root,
            "sequence": state["generation"] + 1, "previous_sha256": state["head_sha256"],
            "kind": kind, "data": data,
        }
        event["event_sha256"] = self._event_hash(event)
        encoded = json.dumps(event, sort_keys=True, allow_nan=False)
        location = self._location(event["sequence"])
        try:
            if self.store.cloud_prefix_uri:
                created = self.store._object_store().create_text(str(location), encoded, "application/json")
            else:
                location.parent.mkdir(parents=True, exist_ok=True)
                try:
                    fd = os.open(location, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                except FileExistsError:
                    created = False
                else:
                    with os.fdopen(fd, "w", encoding="utf-8") as handle:
                        handle.write(encoded)
                        handle.flush()
                        os.fsync(handle.fileno())
                    created = True
            if created is not True:
                raise AccountSubmissionError("account event create conflict; no submission grant")
            confirmed = self.read_state()
            if confirmed["generation"] != event["sequence"] or confirmed["head_sha256"] != event["event_sha256"]:
                raise AccountSubmissionError("account event confirmation failed")
        except Exception:
            object.__setattr__(self, "_failed", True)
            raise
        return event

    def record_circuit_breaker_open(self, *, snapshot):
        """Latch an observed drawdown breach in the existing account journal.

        OPEN is admission-only. Recovery, timeouts and caller CLOSED/reset flags
        cannot clear it. This method grants no reduction or submission authority.
        """
        from quant_platform_kit.risk.account_new_risk_gate import evaluate_new_risk_admission
        from quant_platform_kit.risk.capital_risk_envelope import evaluate_capital_risk_envelope
        with self._mutex, self._account_mutex, self._writer_guard() as confirm_writer:
            if self._failed:
                raise AccountSubmissionError("session persistence uncertain")
            if not evaluate_new_risk_admission(snapshot).hard_brake_triggered:
                raise AccountSubmissionError("circuit breaker OPEN requires a drawdown breach")
            peak = snapshot.peak_equity_usd
            # A supplemental input error cannot erase an independently valid
            # explicit drawdown breach. Replay validates the remaining facts.
            if peak is not None and (isinstance(peak, bool) or not isinstance(peak, (int, float))
                                     or not math.isfinite(float(peak)) or peak <= 0):
                peak = None
            data = {"equity_usd": _submission_number(snapshot.equity_usd),
                    "peak_equity_usd": None if peak is None else _submission_number(peak)}
            drawdown = snapshot.drawdown_from_peak
            if "INVALID_DRAWDOWN_FAIL_CLOSED" in evaluate_capital_risk_envelope(
                snapshot.equity_usd, drawdown_from_peak=drawdown,
            ).reasons:
                # Admission already verified the independent equity/peak breach.
                # Store only those valid facts; replay derives their drawdown.
                drawdown = None
            data["drawdown_from_peak"] = None if drawdown is None else _submission_number(drawdown)
            data.update(owner_id=self.owner_id, profile=self.profile)
            state = self.read_state()
            confirm_writer()
            if not state["circuit_breaker_open"]:
                self._append(state, "CIRCUIT_BREAKER_OPEN", data)

    def record_account_equity(self, *, snapshot, cash_flow, baseline_confirmed=False):
        """Record a complete account equity observation with cash-flow-adjusted peak."""
        from quant_platform_kit.common.account_risk_budget import available_new_risk_budget
        from quant_platform_kit.common.account_domain import (
            account_domain_key, account_domain_matches_broker_identity,
            account_domain_policy_active, validate_account_domain,
        )
        with self._mutex:
            if self._failed:
                raise AccountSubmissionError("session persistence uncertain")
            state = self.read_state()
            binding = state["domain_binding"]
            if binding is None or self.account_domain is None:
                raise AccountSubmissionError("bound domain required")
            domain = validate_account_domain(self.account_domain, platform_id=self.broker)
            if (binding != {"domain_key": account_domain_key(domain), "account_type": domain["policy"]["account_type"], "currency": domain["policy"]["currency"]}
                    or not account_domain_matches_broker_identity(domain, self.broker_identity, observed_environment=self.observed_environment, observed_server=self.observed_server, observed_currency=self.observed_currency, observed_lifecycle_id=self.observed_lifecycle_id)
                    or not account_domain_policy_active(domain, as_of=self.decision_at)):
                raise AccountSubmissionError("verified domain required")
            _, observed_account = _submission_account(self.broker, self.observed_account_id)
            if observed_account != self.account_id:
                raise AccountSubmissionError("account domain observation mismatch")
            # Validate completeness, identity, pending exposure, and source validity.
            if (snapshot.get("account_domain_key") != account_domain_key(domain)
                    or snapshot.get("account_id") != self.account_id
                    or snapshot.get("open_orders_complete") is not True
                    or _submission_number(snapshot.get("pending_3x_exposure")) < 0):
                raise AccountSubmissionError("snapshot account or pending observation mismatch")
            # Validate completeness, currency, time, provenance and numeric facts.
            available_new_risk_budget(snapshot, currency=binding["currency"], floor=0,
                                      reserved=0, cost_buffer=0, risk_fraction=0.005)
            from quant_platform_kit.common.account_domain import _time
            if not _time(snapshot["valuation_at"]) <= _time(self.observed_at) <= _time(self.decision_at) < _time(snapshot.get("valid_until")):
                raise AccountSubmissionError("equity snapshot is not current at decision time")
            equity = _submission_number(snapshot["equity"])
            flow = _submission_number(cash_flow)
            previous = state["equity_observation"]
            if previous is None and baseline_confirmed is not True:
                raise AccountSubmissionError("trusted initial equity baseline required")
            if equity < 0 or (previous is not None and _time(snapshot["valuation_at"]) <= _time(previous["valuation_at"])):
                raise AccountSubmissionError("invalid or non-monotonic equity observation")
            peak = equity if previous is None else max(equity, previous["peak"] + flow)
            positions = snapshot.get("positions")
            open_orders_empty = snapshot.get("open_orders_empty")
            if not isinstance(positions, dict) or any(not isinstance(symbol, str) or not symbol or not math.isfinite(_submission_number(qty)) for symbol, qty in positions.items()) or type(open_orders_empty) is not bool:
                raise AccountSubmissionError("complete positions and pending observation required")
            covered = snapshot.get("covered_fills", {})
            covered_fees = snapshot.get("covered_fees", {})
            position_risk = snapshot.get("position_risk")
            position_3x = snapshot.get("position_3x_exposure")
            if not isinstance(covered, dict) or any(not isinstance(key, str) or _submission_number(value) < 0 for key, value in covered.items()):
                raise AccountSubmissionError("invalid covered attempt ids")
            if not isinstance(covered_fees, dict) or any(not isinstance(key, str) or _submission_number(value) < 0 for key, value in covered_fees.items()):
                raise AccountSubmissionError("invalid covered fees")
            if _submission_number(position_3x) < 0:
                raise AccountSubmissionError("invalid 3x position exposure")
            if _submission_number(position_risk) < 0:
                raise AccountSubmissionError("invalid position risk")
            evidence = snapshot.get("pending_order_evidence")
            evidence_fields = {}
            if "pending_order_evidence" in snapshot:
                from quant_platform_kit.common.pending_order_evidence import validate_pending_order_evidence
                observation = {**snapshot, "account_binding": submission_binding_digest({"broker": self.broker, "account_id": self.account_id})}
                try:
                    validate_pending_order_evidence(evidence, observation=observation,
                                                    attempts=state["attempts"], reservations=state["risk_reservations"])
                except (ValueError, TypeError, KeyError) as exc:
                    raise AccountSubmissionError("invalid pending order evidence") from exc
                evidence_fields["pending_order_evidence"] = evidence
            return self._append(state, "EQUITY_OBSERVED", {
                **evidence_fields, "equity": equity, "cash_flow": flow, "peak": peak,
                "currency": binding["currency"], "valuation_at": snapshot["valuation_at"],
                "source_digest": snapshot["source_digest"], "covered_fills": covered,
                "covered_fees": covered_fees, "position_risk": position_risk, "position_3x_exposure": position_3x,
                "protected_equity": equity if previous is None else max(equity, previous["protected_equity"]),
                "balance": float(snapshot["balance"]), "cash": float(snapshot["cash"]),
                "account_domain_key": snapshot["account_domain_key"],
                "account_binding": submission_binding_digest({"broker": self.broker, "account_id": self.account_id}),
                "valid_until": snapshot["valid_until"], "pending_3x_exposure": float(snapshot["pending_3x_exposure"]),
                "open_orders_complete": True, "positions": positions, "open_orders_empty": open_orders_empty,
            })

    def reserve_account_risk(
        self,
        order,
        *,
        snapshot,
        spec: RiskReservationSpec | None = None,
        floor: Any = _UNSET,
        cost_buffer: Any = _UNSET,
        amount: Any = _UNSET,
        risk_fraction: Any = _UNSET,
        loss_per_unit: Any = _UNSET,
        estimated_fee: Any = _UNSET,
        quantity_step: Any = _UNSET,
        product_leverage_factor: Any = _UNSET,
        unit_price: Any = _UNSET,
        existing_3x_exposure: Any = _UNSET,
        pending_3x_exposure: Any = _UNSET,
        leverage_hitl_approved: Any = _UNSET,
        account_budget_policy: Any = _UNSET,
    ):
        """Atomically reserve account-currency risk; reservations are never auto-released."""
        resolved_spec = _resolve_risk_reservation_spec(
            spec,
            {
                "floor": floor,
                "cost_buffer": cost_buffer,
                "amount": amount,
                "risk_fraction": risk_fraction,
                "loss_per_unit": loss_per_unit,
                "estimated_fee": estimated_fee,
                "quantity_step": quantity_step,
                "product_leverage_factor": product_leverage_factor,
                "unit_price": unit_price,
                "existing_3x_exposure": existing_3x_exposure,
                "pending_3x_exposure": pending_3x_exposure,
                "leverage_hitl_approved": leverage_hitl_approved,
                "account_budget_policy": account_budget_policy,
            },
        )
        from quant_platform_kit.common.account_risk_budget import (
            available_new_risk_budget, maximum_risk_quantity,
        )
        from quant_platform_kit.common.account_domain import (
            account_domain_key, account_domain_matches_broker_identity,
            account_domain_policy_active, validate_account_domain,
        )

        with self._mutex:
            if self._failed or self.account_domain is None:
                raise AccountSubmissionError("bound domain and healthy journal required")
            state = self.read_state()
            if any(item["certainty"] in {"PREPARED", "UNKNOWN"} for item in state["attempts"].values()):
                raise AccountSubmissionError("unresolved account submission")
            domain = validate_account_domain(self.account_domain, platform_id=self.broker)
            binding = state["domain_binding"]
            if (binding is None or binding != {"domain_key": account_domain_key(domain),
                    "account_type": domain["policy"]["account_type"], "currency": domain["policy"]["currency"]}
                    or not account_domain_matches_broker_identity(domain, self.broker_identity, observed_environment=self.observed_environment, observed_server=self.observed_server, observed_currency=self.observed_currency, observed_lifecycle_id=self.observed_lifecycle_id)
                    or not account_domain_policy_active(domain, as_of=self.decision_at)):
                raise AccountSubmissionError("verified domain must be bound before risk reservation")
            _, observed_account = _submission_account(self.broker, self.observed_account_id)
            if observed_account != self.account_id:
                raise AccountSubmissionError("account domain observation mismatch")
            observed = state["equity_observation"]
            if observed is None or any(observed[key] != snapshot.get(key) for key in ("equity", "balance", "cash", "currency", "valuation_at", "source_digest", "account_domain_key", "valid_until", "pending_3x_exposure", "open_orders_complete")):
                raise AccountSubmissionError("matching recorded equity snapshot required")
            from quant_platform_kit.risk.capital_risk_envelope import evaluate_capital_risk_envelope
            peak = observed["peak"]
            if peak <= 0:
                raise AccountSubmissionError("positive protected peak required")
            protected_envelope = evaluate_capital_risk_envelope(
                observed["protected_equity"], drawdown_from_peak=max(0.0, 1.0 - observed["equity"] / peak),
            )
            if not protected_envelope.new_risk_allowed:
                raise AccountSubmissionError("protected drawdown brake prohibits new risk")
            order_digest, quantity = self._order(order)
            if type(resolved_spec.leverage_hitl_approved) is not bool:
                raise AccountSubmissionError("invalid leverage approval fact")
            from quant_platform_kit.common.account_domain import _time
            if not _time(observed["valuation_at"]) <= _time(self.observed_at) <= _time(self.decision_at) < _time(observed["valid_until"]):
                raise AccountSubmissionError("account valuation is stale")
            if snapshot.get("account_id") != self.account_id or resolved_spec.pending_3x_exposure != observed["pending_3x_exposure"]:
                raise AccountSubmissionError("snapshot account or pending exposure mismatch")
            factor = _submission_number(resolved_spec.product_leverage_factor)
            price = _submission_number(resolved_spec.unit_price)
            existing_3x = _submission_number(resolved_spec.existing_3x_exposure)
            pending_3x = _submission_number(resolved_spec.pending_3x_exposure)
            if factor not in (1.0, 3.0) or price <= 0 or existing_3x < 0 or pending_3x < 0 or existing_3x != observed["position_3x_exposure"]:
                raise AccountSubmissionError("known product exposure and pending exposure required")
            if factor == 3.0:
                if protected_envelope.leverage_product_cap.new_leverage_requires_hitl and resolved_spec.leverage_hitl_approved is not True:
                    raise AccountSubmissionError("leverage approval required")
                cap = protected_envelope.leverage_product_cap.max_3x_etf_weight * observed["equity"]
                reserved_3x = sum(item["remaining_3x_exposure"] for item in state["risk_reservations"].values())
                if existing_3x + pending_3x + reserved_3x + quantity * price > cap:
                    raise AccountSubmissionError("product leverage cap exceeded")
            reserved_amount = _submission_number(resolved_spec.amount)
            max_quantity = maximum_risk_quantity(
                budget=reserved_amount,
                loss_per_unit=resolved_spec.loss_per_unit,
                estimated_fee=resolved_spec.estimated_fee,
                quantity_step=resolved_spec.quantity_step,
            )
            quantity_steps = Fraction(str(quantity)) / Fraction(str(resolved_spec.quantity_step))
            if quantity > max_quantity or abs(quantity_steps - round(quantity_steps)) > Fraction(1, 10**9):
                raise AccountSubmissionError("quantity exceeds reserved risk or step")
            if reserved_amount <= 0 or order_digest in state["risk_reservations"]:
                raise AccountSubmissionError("invalid or duplicate account risk reservation")
            expected_fields = {"preference", "version", "source", "per_trade_fraction", "total_future_risk_limit", "floor", "cost_buffer", "contract_floor"}
            policy = resolved_spec.account_budget_policy
            if not isinstance(policy, Mapping) or set(policy) != expected_fields:
                raise AccountSubmissionError("explicit account budget policy required")
            if any(policy[key] != domain["policy"][key] for key in ("preference", "version", "source")):
                raise AccountSubmissionError("account budget policy binding mismatch")
            policy_fraction = _submission_number(policy["per_trade_fraction"])
            total_limit = _submission_number(policy["total_future_risk_limit"])
            if (policy_fraction != _submission_number(resolved_spec.risk_fraction) or total_limit < 0
                    or _submission_number(policy["floor"]) != _submission_number(resolved_spec.floor)
                    or _submission_number(policy["cost_buffer"]) != _submission_number(resolved_spec.cost_buffer)):
                raise AccountSubmissionError("account budget policy values mismatch")
            if domain["policy"]["capital_kind"] == "FTMO_SIMULATED":
                contract_floor = _submission_number(policy["contract_floor"])
                if contract_floor <= 0 or _submission_number(resolved_spec.floor) < contract_floor:
                    raise AccountSubmissionError("FTMO confirmed contract floor required")
                if _submission_number(resolved_spec.risk_fraction) > 0.005:
                    raise AccountSubmissionError("FTMO risk fraction exceeds offline cap")
            elif policy["contract_floor"] is not None:
                raise AccountSubmissionError("unexpected contract floor for own account")
            existing = state["snapshot_position_risk"] + sum(item["remaining_amount"] for item in state["risk_reservations"].values())
            budget = available_new_risk_budget(
                snapshot,
                currency=binding["currency"],
                floor=resolved_spec.floor,
                reserved=existing,
                cost_buffer=resolved_spec.cost_buffer,
                risk_fraction=resolved_spec.risk_fraction,
            )
            if reserved_amount > budget or existing + reserved_amount > total_limit:
                raise AccountSubmissionError("account risk budget exceeded")
            return self._append(state, "RISK_RESERVED", {
                "order_sha256": order_digest, "amount": reserved_amount, "currency": binding["currency"],
                "valuation_at": snapshot["valuation_at"], "source_digest": snapshot["source_digest"],
                "reserved_3x_exposure": quantity * price if factor == 3.0 else 0.0,
                "quantity": quantity, "estimated_fee": float(resolved_spec.estimated_fee),
                "loss_per_unit": float(resolved_spec.loss_per_unit), "quantity_step": float(resolved_spec.quantity_step),
                "risk_fraction": float(resolved_spec.risk_fraction), "product_leverage_factor": factor,
                "unit_price": price, "existing_3x_exposure": existing_3x,
                "pending_3x_exposure": pending_3x, "floor": float(resolved_spec.floor),
                "cost_buffer": float(resolved_spec.cost_buffer), "leverage_hitl_approved": resolved_spec.leverage_hitl_approved,
                "account_budget_policy": dict(policy),
            })

    def reconcile_account_risk(self, *, attempt_id, filled_quantity, actual_fee, snapshot_position_risk, source_digest):
        """Transfer observed fills into a complete recorded snapshot; UNKNOWN stays reserved."""
        from quant_platform_kit.common.account_domain import (
            account_domain_key, account_domain_matches_broker_identity,
            account_domain_policy_active, validate_account_domain,
        )
        with self._mutex:
            if self._failed:
                raise AccountSubmissionError("session persistence uncertain")
            state = self.read_state()
            if self.account_domain is None:
                raise AccountSubmissionError("verified domain required")
            domain = validate_account_domain(self.account_domain, platform_id=self.broker)
            binding = {"domain_key": account_domain_key(domain), "account_type": domain["policy"]["account_type"], "currency": domain["policy"]["currency"]}
            _, observed_account = _submission_account(self.broker, self.observed_account_id)
            if (state["domain_binding"] != binding or observed_account != self.account_id
                    or not account_domain_matches_broker_identity(domain, self.broker_identity, observed_environment=self.observed_environment, observed_server=self.observed_server, observed_currency=self.observed_currency, observed_lifecycle_id=self.observed_lifecycle_id)
                    or not account_domain_policy_active(domain, as_of=self.decision_at)):
                raise AccountSubmissionError("verified domain required")
            attempt = state["attempts"].get(attempt_id)
            if attempt is None or attempt["certainty"] not in {"TERMINAL", "KNOWN_PENDING"}:
                raise AccountSubmissionError("known broker observation required")
            reservation = state["risk_reservations"].get(attempt["order_sha256"])
            observation = state["equity_observation"]
            filled = _submission_number(filled_quantity)
            fee = _submission_number(actual_fee)
            position_risk = _submission_number(snapshot_position_risk)
            from quant_platform_kit.common.account_domain import _time
            if (reservation is None or observation is None or source_digest != observation["source_digest"]
                    or observation["covered_fills"].get(attempt_id) != filled
                    or observation["covered_fees"].get(attempt_id) != fee
                    or observation["position_risk"] != position_risk
                    or observation["source_digest"] == reservation["source_digest"]
                    or _time(observation["valuation_at"]) <= _time(reservation["valuation_at"])
                    or filled != attempt["filled_quantity"] or filled < reservation["reconciled_filled"]
                    or fee < reservation["actual_fee"] or position_risk < 0):
                raise AccountSubmissionError("risk reconciliation facts mismatch")
            return self._append(state, "RISK_RECONCILED", {
                "attempt_id": attempt_id, "filled_quantity": filled_quantity,
                "actual_fee": actual_fee, "snapshot_position_risk": snapshot_position_risk,
                "source_digest": source_digest,
            })

    def reserve_reduction(self, order, *, admission) -> AccountSubmissionGrant:
        """Reserve an account-brake reduction from a complete bound snapshot."""
        from quant_platform_kit.common.account_domain import (
            _time, account_domain_key, account_domain_matches_broker_identity,
            account_domain_policy_active, validate_account_domain,
        )
        from quant_platform_kit.risk.account_new_risk_gate import NewRiskAdmissionResult, is_proven_risk_reducing_order
        with self._mutex:
            if self._failed or self.account_domain is None or not isinstance(admission, NewRiskAdmissionResult) or not admission.hard_brake_triggered:
                raise AccountSubmissionError("verified account brake required")
            state = self.read_state()
            domain = validate_account_domain(self.account_domain, platform_id=self.broker)
            binding = {"domain_key": account_domain_key(domain), "account_type": domain["policy"]["account_type"], "currency": domain["policy"]["currency"]}
            _, account = _submission_account(self.broker, self.observed_account_id)
            observed = state["equity_observation"]
            if (state["domain_binding"] != binding or account != self.account_id or observed is None
                    or not observed["open_orders_complete"] or not observed["open_orders_empty"]
                    or not account_domain_matches_broker_identity(domain, self.broker_identity, observed_environment=self.observed_environment, observed_server=self.observed_server, observed_currency=self.observed_currency, observed_lifecycle_id=self.observed_lifecycle_id)
                    or not account_domain_policy_active(domain, as_of=self.decision_at)
                    or not _time(observed["valuation_at"]) <= _time(self.decision_at) < _time(observed["valid_until"])):
                raise AccountSubmissionError("complete verified reduction observation required")
            from quant_platform_kit.risk.capital_risk_envelope import evaluate_capital_risk_envelope
            if observed["peak"] <= 0 or "DRAWDOWN_BRAKE_TRIPPED" not in evaluate_capital_risk_envelope(
                    observed["protected_equity"], drawdown_from_peak=max(0.0, 1.0 - observed["equity"] / observed["peak"])).reasons:
                raise AccountSubmissionError("independent drawdown brake not verified")
            digest, quantity = self._order(order)
            symbol = str(getattr(order, "symbol", "")).strip().upper()
            side = str(getattr(order, "side", "")).strip().lower()
            if not is_proven_risk_reducing_order(observed["positions"].get(symbol), side, quantity, pending_quantity=0):
                raise AccountSubmissionError("order reduction not proven")
            if any(a["certainty"] in {"PREPARED", "UNKNOWN", "KNOWN_PENDING"} for a in state["attempts"].values()):
                raise AccountSubmissionError("unresolved account submission")
            for attempt_id, attempt in state["attempts"].items():
                if attempt["filled_quantity"] <= 0:
                    continue
                source = attempt["prepared_snapshot"]
                if (source is None or observed["covered_fills"].get(attempt_id) != attempt["filled_quantity"]
                        or attempt_id not in observed["covered_fees"]
                        or observed["source_digest"] == source["source_digest"]
                        or _time(observed["valuation_at"]) <= _time(source["valuation_at"])):
                    raise AccountSubmissionError("filled submission requires a newer covering snapshot")
            if any((a["intent_id"], a["order_sha256"]) == (self.intent_id, digest) for a in state["attempts"].values()):
                raise AccountSubmissionError("same intent/order already reserved")
            data = {"attempt_id": uuid.uuid4().hex + uuid.uuid4().hex, "fence": uuid.uuid4().hex + uuid.uuid4().hex,
                    "intent_id": self.intent_id, "order_sha256": digest, "release_id": self.release_id,
                    "owner_id": self.owner_id, "profile": self.profile, "quantity": quantity, "reduction": True,
                    "reduction_source_digest": observed["source_digest"]}
            event = self._append(state, "PREPARED", data)
            grant = AccountSubmissionGrant(self.account_root, data["attempt_id"], data["fence"], event["sequence"], event["event_sha256"], self.intent_id, digest, self.release_id)
            self._issued[grant.attempt_id] = grant
            return grant

    def reserve(self, order, *, new_risk=False) -> AccountSubmissionGrant:
        """Only a fresh acknowledged create can return a grant; never reclaim it."""
        with self._mutex:
            if self._failed:
                raise AccountSubmissionError("session persistence uncertain; no grant")
            digest, quantity = self._order(order)
            state = self.read_state()
            if type(new_risk) is not bool or (new_risk and state["circuit_breaker_open"]):
                raise AccountSubmissionError("new risk prohibited by circuit breaker")
            if self.account_domain is not None:
                from quant_platform_kit.common.account_domain import (
                    account_domain_key, account_domain_matches_broker_identity, account_domain_policy_active, validate_account_domain,
                )
                domain = validate_account_domain(self.account_domain, platform_id=self.broker)
                if not account_domain_policy_active(domain, as_of=self.decision_at):
                    raise AccountSubmissionError("account domain policy not active")
                try:
                    _, observed_account = _submission_account(self.broker, self.observed_account_id)
                except (ValueError, TypeError) as exc:
                    raise AccountSubmissionError("observed account identity required") from exc
                if observed_account != self.account_id or not account_domain_matches_broker_identity(domain, self.broker_identity, observed_environment=self.observed_environment, observed_server=self.observed_server, observed_currency=self.observed_currency, observed_lifecycle_id=self.observed_lifecycle_id):
                    raise AccountSubmissionError("account domain observation mismatch")
                binding = {"domain_key": account_domain_key(domain),
                           "account_type": domain["policy"]["account_type"],
                           "currency": domain["policy"]["currency"]}
                if state["domain_binding"] is None:
                    self._append(state, "DOMAIN_BOUND", binding)
                    state = self.read_state()
                if state["domain_binding"] != binding:
                    raise AccountSubmissionError("account domain binding mismatch")
            elif state["domain_binding"] is not None:
                raise AccountSubmissionError("bound account domain required")
            if self.account_domain is not None:
                reservation = state["risk_reservations"].get(digest)
                observation = state["equity_observation"]
                if reservation is None:
                    raise AccountSubmissionError("account risk reservation required")
                if observation is None or any(reservation[key] != observation[key] for key in ("valuation_at", "source_digest")):
                    raise AccountSubmissionError("account risk reservation is stale")
            if any(a["certainty"] in {"PREPARED", "UNKNOWN"} for a in state["attempts"].values()):
                raise AccountSubmissionError("unresolved UNKNOWN/account submission")
            if self.account_domain is not None and any(
                a["order_sha256"] == digest and not a.get("reduction") for a in state["attempts"].values()
            ):
                raise AccountSubmissionError("account risk reservation already used")
            if any((a["intent_id"], a["order_sha256"]) == (self.intent_id, digest) for a in state["attempts"].values()):
                raise AccountSubmissionError("same intent/order already reserved; no retry grant")
            data = {
                "attempt_id": uuid.uuid4().hex + uuid.uuid4().hex,
                "fence": uuid.uuid4().hex + uuid.uuid4().hex,
                "intent_id": self.intent_id, "order_sha256": digest, "release_id": self.release_id,
                "owner_id": self.owner_id, "profile": self.profile, "quantity": quantity,
            }
            if new_risk:
                data["new_risk"] = True
            event = self._append(state, "PREPARED", data)
            grant = AccountSubmissionGrant(self.account_root, data["attempt_id"], data["fence"],
                                           event["sequence"], event["event_sha256"], self.intent_id, digest, self.release_id)
            self._issued[grant.attempt_id] = grant
            return grant

    def _owned_grant(self, grant: AccountSubmissionGrant) -> dict:
        if (not isinstance(grant, AccountSubmissionGrant) or self._issued.get(grant.attempt_id) is not grant
                or grant.account_root != self.account_root or grant.intent_id != self.intent_id
                or grant.release_id != self.release_id):
            raise AccountSubmissionError("wrong/stale/session grant")
        state = self.read_state()
        attempt = state["attempts"].get(grant.attempt_id)
        if (not attempt or attempt["fence"] != grant.fence or attempt["generation"] != grant.generation
                or attempt["event_sha256"] != grant.event_sha256 or attempt["order_sha256"] != grant.order_sha256):
            raise AccountSubmissionError("grant fence/binding mismatch")
        return state

    def dispatch(self, grant: AccountSubmissionGrant, order, submit: Callable[[], Any], *, record_observation_watermark=False):
        """Consume exactly once at the final platform submit wrapper, then observe."""
        with self._mutex:
            if type(record_observation_watermark) is not bool:
                raise AccountSubmissionError("invalid observation watermark option")
            if self._failed:
                raise AccountSubmissionError("session persistence uncertain")
            state = self._owned_grant(grant)
            digest, _ = self._order(order)
            if digest != grant.order_sha256 or grant.attempt_id in self._used:
                raise AccountSubmissionError("wrong order or already-used grant")
            if state["attempts"][grant.attempt_id]["certainty"] != "PREPARED":
                raise AccountSubmissionError("grant no longer prepared")
            if state["attempts"][grant.attempt_id].get("new_risk") and state["circuit_breaker_open"]:
                raise AccountSubmissionError("new risk prohibited by circuit breaker")
            if self.account_domain is not None:
                from quant_platform_kit.common.account_domain import (
                    _time, account_domain_key, account_domain_matches_broker_identity,
                    account_domain_policy_active, validate_account_domain,
                )
                domain = validate_account_domain(self.account_domain, platform_id=self.broker)
                now = self.clock()
                now_text = now.isoformat() if isinstance(now, datetime) else now
                observed = state["equity_observation"]
                reservation = state["risk_reservations"].get(digest)
                binding = {"domain_key": account_domain_key(domain), "account_type": domain["policy"]["account_type"], "currency": domain["policy"]["currency"]}
                _, account = _submission_account(self.broker, self.observed_account_id)
                is_reduction = state["attempts"][grant.attempt_id].get("reduction") is True
                if (state["domain_binding"] != binding or account != self.account_id
                        or not account_domain_matches_broker_identity(domain, self.broker_identity, observed_environment=self.observed_environment, observed_server=self.observed_server, observed_currency=self.observed_currency, observed_lifecycle_id=self.observed_lifecycle_id)
                        or not account_domain_policy_active(domain, as_of=now_text)
                        or observed is None or (reservation is None and not is_reduction)
                        or (not is_reduction and any(observed[key] != reservation[key] for key in ("valuation_at", "source_digest")))
                        or (is_reduction and (not observed["open_orders_complete"] or not observed["open_orders_empty"]
                            or observed["source_digest"] != state["attempts"][grant.attempt_id]["reduction_source_digest"]))
                        or not _time(observed["valuation_at"]) <= _time(now_text) < _time(observed["valid_until"])):
                    raise AccountSubmissionError("expired or mismatched domain observation")
            with self._account_mutex:
                # Validation above can call platform code. Re-read after it and
                # serialize the final check/submit with OPEN from other sessions
                # on this account journal in the current process.
                current = self._owned_grant(grant)
                attempt = current["attempts"][grant.attempt_id]
                if attempt["certainty"] != "PREPARED":
                    raise AccountSubmissionError("grant no longer prepared")
                if attempt.get("new_risk") and current["circuit_breaker_open"]:
                    raise AccountSubmissionError("new risk prohibited by circuit breaker")
                # Acquire cross-process exclusion after the preliminary read;
                # only a read inside this guard may authorize the broker write.
                with self._writer_guard() as confirm_writer:
                    current = self._owned_grant(grant)
                    attempt = current["attempts"][grant.attempt_id]
                    if attempt["certainty"] != "PREPARED":
                        raise AccountSubmissionError("grant no longer prepared")
                    if attempt.get("new_risk") and current["circuit_breaker_open"]:
                        raise AccountSubmissionError("new risk prohibited by circuit breaker")
                    confirm_writer()
                    self._used.add(grant.attempt_id)
                    try:
                        confirm_writer()
                        report = submit()
                    except Exception as exc:
                        try:
                            confirm_writer()
                            self.record_observation(grant, None)
                        except Exception as persist_exc:
                            exc.add_note("account outcome persistence also failed: " + type(persist_exc).__name__)
                            object.__setattr__(self, "_failed", True)
                        raise
                    confirm_writer()
                    # Keep the outcome append in the same critical section so an
                    # OPEN writer cannot race its next sequence with OBSERVED.
                    if record_observation_watermark:
                        try:
                            now = self.clock()
                            recorded_at = now.isoformat() if isinstance(now, datetime) else now
                            from quant_platform_kit.common.account_domain import _time
                            _time(recorded_at)
                        except Exception:
                            recorded_at = None
                        if recorded_at is not None:
                            self.record_observation(grant, report, recorded_at=recorded_at)
                        else:
                            self.record_observation(grant, report)
                    else:
                        self.record_observation(grant, report)
                    attempt = self.read_state()["attempts"][grant.attempt_id]
                    if attempt["certainty"] == "UNKNOWN" and str(getattr(report, "status", "")).strip() in (
                        _SUBMISSION_ACK | _SUBMISSION_PARTIAL | _SUBMISSION_TERMINAL
                    ):
                        raise AccountSubmissionError("broker result facts are uncertain; original attempt retained")
                    return report

    def record_observation(self, grant: AccountSubmissionGrant, report, *, recorded_at=None) -> bool:
        """Persist original facts. Exact replay is idempotent, never a new grant."""
        with self._mutex:
            if self._failed:
                raise AccountSubmissionError("session persistence uncertain")
            state = self._owned_grant(grant)
            if grant.attempt_id not in self._used:
                raise AccountSubmissionError("grant not dispatched")
            attempt = state["attempts"][grant.attempt_id]
            prior = attempt["observation"]
            status = str(getattr(report, "status", "") or "").strip()
            order_id = str(getattr(report, "broker_order_id", "") or "").strip() or None
            invalid = False
            try:
                filled = _submission_number(getattr(report, "filled_quantity", None) or 0.0)
                price_value = getattr(report, "average_fill_price", None)
                price = _submission_number(price_value) if price_value is not None else None
                if filled < attempt["filled_quantity"] or filled > attempt["quantity"]:
                    raise AccountSubmissionError("non-monotonic fill")
                if order_id is not None:
                    _submission_text(order_id)
                if prior and prior["broker_order_id"] and order_id != prior["broker_order_id"]:
                    raise AccountSubmissionError("broker order identity changed")
            except AccountSubmissionError:
                invalid = True
                status = "Unknown"
                order_id = prior["broker_order_id"] if prior else None
                filled = attempt["filled_quantity"]
                price = prior["average_fill_price"] if prior else None
            observation = {"status": status, "broker_order_id": order_id,
                           "filled_quantity": filled, "average_fill_price": price}
            observation["certainty"] = self._certainty(observation, attempt["quantity"])
            if prior == observation:
                if invalid:
                    raise AccountSubmissionError("historical/non-monotonic observation rejected")
                return False
            if attempt["certainty"] in {"UNKNOWN", "TERMINAL"}:
                raise AccountSubmissionError("historical UNKNOWN/terminal cannot be changed")
            event_data = {"attempt_id": grant.attempt_id, "observation": observation}
            if recorded_at is not None:
                from quant_platform_kit.common.account_domain import _time
                try:
                    instant = _time(recorded_at)
                    previous_watermark = attempt.get("last_observation_recorded_at")
                    if previous_watermark is None or instant >= _time(previous_watermark):
                        event_data["recorded_at"] = recorded_at
                except (ValueError, TypeError):
                    # Optional metadata must never discard a broker observation.
                    pass
            self._append(state, "OBSERVED", event_data)
            if invalid:
                raise AccountSubmissionError("invalid/non-monotonic broker observation; UNKNOWN persisted")
            return True


