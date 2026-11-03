"""Validation of optional order-level evidence; this does not release risk."""
from __future__ import annotations

import math
import re
from fractions import Fraction
from typing import Any, Mapping

from .account_domain import _time


def _number(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("evidence amount must be numeric")
    try:
        value = float(value)
    except OverflowError as exc:
        raise ValueError("evidence amount must be finite and nonnegative") from exc
    if not math.isfinite(value) or value < 0:
        raise ValueError("evidence amount must be finite and nonnegative")
    return value


def validate_pending_order_evidence(evidence: object, *, observation: Mapping[str, Any],
                                    attempts: Mapping[str, Any], reservations: Mapping[str, Any]) -> None:
    """Check a snapshot's asserted coverage against the journal at recording time.

    The source's coverage assertion and economics require independent verification.
    No amount validated here is an authorization to subtract or release risk.
    """
    fields = {"schema_version", "account_domain_key", "account_binding", "currency",
              "source_digest", "source_version", "valuation_at", "observed_through", "orders"}
    if not isinstance(evidence, dict) or set(evidence) != fields or evidence["schema_version"] != "pending_order_evidence.v1":
        raise ValueError("invalid pending order evidence envelope")
    for field in ("account_domain_key", "account_binding", "currency", "source_digest", "valuation_at"):
        if evidence[field] != observation[field]:
            raise ValueError("pending evidence snapshot binding mismatch")
    source_version = evidence["source_version"]
    if not isinstance(source_version, str) or not source_version.strip() or source_version != source_version.strip():
        raise ValueError("pending evidence source version required")
    through = _time(evidence["observed_through"])
    if through > _time(evidence["valuation_at"]):
        raise ValueError("pending evidence watermark after valuation")
    orders = evidence["orders"]
    if not isinstance(orders, list):
        raise ValueError("pending evidence orders must be a list")
    seen_attempts, seen_orders = set(), set()
    total = 0.0
    for order in orders:
        keys = {"attempt_id", "broker_order_id", "journal_observation_sha256", "remaining_quantity",
                "remaining_fee", "pending_3x_exposure"}
        if not isinstance(order, dict) or set(order) != keys:
            raise ValueError("invalid pending order evidence")
        attempt_id, broker_id = order["attempt_id"], order["broker_order_id"]
        if not isinstance(attempt_id, str) or not re.fullmatch(r"[0-9a-f]{64}", attempt_id):
            raise ValueError("invalid pending evidence attempt")
        if not isinstance(broker_id, str) or not broker_id.strip() or broker_id != broker_id.strip():
            raise ValueError("invalid pending evidence broker order")
        if attempt_id in seen_attempts or broker_id in seen_orders:
            raise ValueError("duplicate pending evidence identity")
        seen_attempts.add(attempt_id)
        seen_orders.add(broker_id)
        attempt = attempts.get(attempt_id)
        if not attempt or attempt.get("certainty") != "KNOWN_PENDING":
            raise ValueError("pending evidence requires known pending attempt")
        last = attempt.get("observation") or {}
        if (last.get("broker_order_id") != broker_id
                or not attempt.get("observation_recorded_at")
                or order["journal_observation_sha256"] != attempt.get("observation_event_sha256")
                or through < _time(attempt["observation_recorded_at"])):
            raise ValueError("pending evidence does not cover journal observation")
        reservation = reservations.get(attempt["order_sha256"])
        if not reservation or reservation["reconciled_filled"] != attempt["filled_quantity"]:
            raise ValueError("pending evidence requires reconciled reservation")
        remaining = _number(order["remaining_quantity"])
        if Fraction(str(remaining)) != Fraction(str(attempt["quantity"])) - Fraction(str(attempt["filled_quantity"])):
            raise ValueError("pending evidence remaining quantity mismatch")
        _number(order["remaining_fee"])
        total += _number(order["pending_3x_exposure"])
    if total > _number(observation["pending_3x_exposure"]):
        raise ValueError("pending evidence exceeds aggregate exposure")
