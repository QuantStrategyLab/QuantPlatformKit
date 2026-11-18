"""Account submission contracts, observation specs, and digest helpers."""

from __future__ import annotations

import hashlib
import json
import math
import re
import threading
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from fractions import Fraction
from typing import Any

ACCOUNT_SUBMISSION_CONTRACT = "account_submission.v1"
_ACCOUNT_SUBMISSION_NAMESPACE = "account_submissions"
_SUBMISSION_ACK = frozenset({"PendingSubmit", "ApiPending", "ApiPendingSubmit", "Submitted", "PreSubmitted"})
_SUBMISSION_PARTIAL = frozenset({"Partial", "PartiallyFilled"})
_SUBMISSION_TERMINAL = frozenset({"Filled", "Rejected", "rejected", "Cancelled", "ApiCancelled"})
_ACCOUNT_SUBMISSION_LOCKS: dict[str, Any] = {}
_ACCOUNT_SUBMISSION_LOCKS_MUTEX = threading.Lock()
_ACCOUNT_WRITER_TOKEN = uuid.uuid4().hex


class AccountSubmissionError(RuntimeError):
    """No new submission permission was obtained; reconciliation may be required."""


def submission_binding_digest(value: Mapping[str, Any]) -> str:
    """Content identity; never use lossy path cleaning for account/order identity."""
    if not isinstance(value, Mapping) or not value:
        raise AccountSubmissionError("nonempty submission binding required")
    try:
        encoded = json.dumps(dict(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise AccountSubmissionError("invalid submission binding") from exc
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _submission_text(value: object) -> str:
    if not isinstance(value, str) or not value or value != value.strip() or len(value) > 256:
        raise AccountSubmissionError("invalid submission identity")
    if any(ord(char) < 32 or ord(char) > 126 for char in value):
        raise AccountSubmissionError("invalid submission identity")
    return value


def _submission_digest(value: object) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise AccountSubmissionError("invalid submission digest")
    return value


def _submission_account(broker: str, account_id: str) -> tuple[str, str]:
    broker = _submission_text(broker).lower()
    if re.fullmatch(r"[a-z][a-z0-9_-]*", broker) is None:
        raise AccountSubmissionError("invalid broker identity")
    account = _submission_text(account_id)
    if broker == "ibkr":
        account = account.upper()
        if re.fullmatch(r"(?:DU|U|F|I)[0-9]+", account) is None:
            raise AccountSubmissionError("physical IBKR account identity required")
    return broker, account


def _submission_number(value: object) -> float:
    if isinstance(value, bool):
        raise AccountSubmissionError("invalid submission quantity/price")
    try:
        result = float(value)
    except (ValueError, TypeError) as exc:
        raise AccountSubmissionError("invalid submission quantity/price") from exc
    if not math.isfinite(result) or result < 0:
        raise AccountSubmissionError("invalid submission quantity/price")
    return result


@dataclass(frozen=True)
class AccountSubmissionGrant:
    account_root: str
    attempt_id: str
    fence: str
    generation: int
    event_sha256: str
    intent_id: str
    order_sha256: str
    release_id: str


_UNSET = object()


def _default_utc_clock() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True)
class AccountDomainObservation:
    """Observed account-domain identity and timestamp evidence for an ``AccountSubmissionSession``."""

    account_domain: Mapping[str, Any] | None = None
    observed_account_id: str | None = None
    broker_identity: Any = None
    observed_at: str | None = None
    decision_at: str | None = None
    observed_environment: str | None = None
    observed_server: str | None = None
    observed_currency: str | None = None
    observed_lifecycle_id: str | None = None


@dataclass(frozen=True, slots=True)
class RiskReservationSpec:
    """Account-currency risk reservation parameters for ``AccountSubmissionSession.reserve_account_risk``."""

    floor: float
    cost_buffer: float
    amount: float
    risk_fraction: float
    loss_per_unit: float
    estimated_fee: float
    quantity_step: float
    product_leverage_factor: float
    unit_price: float
    existing_3x_exposure: float
    pending_3x_exposure: float
    leverage_hitl_approved: bool
    account_budget_policy: Mapping[str, Any]


def _resolve_observation(
    observation: AccountDomainObservation | None,
    legacy_values: dict[str, Any],
) -> AccountDomainObservation:
    if observation is not None:
        if not isinstance(observation, AccountDomainObservation):
            raise TypeError("observation must be an AccountDomainObservation")
        provided = [name for name, value in legacy_values.items() if value is not _UNSET]
        if provided:
            raise TypeError(
                "cannot specify both 'observation' and individual observation keyword arguments: "
                + ", ".join(provided)
            )
        return observation
    return AccountDomainObservation(
        account_domain=None if legacy_values["account_domain"] is _UNSET else legacy_values["account_domain"],
        observed_account_id=(
            None if legacy_values["observed_account_id"] is _UNSET else legacy_values["observed_account_id"]
        ),
        broker_identity=None if legacy_values["broker_identity"] is _UNSET else legacy_values["broker_identity"],
        observed_at=None if legacy_values["observed_at"] is _UNSET else legacy_values["observed_at"],
        decision_at=None if legacy_values["decision_at"] is _UNSET else legacy_values["decision_at"],
        observed_environment=(
            None if legacy_values["observed_environment"] is _UNSET else legacy_values["observed_environment"]
        ),
        observed_server=None if legacy_values["observed_server"] is _UNSET else legacy_values["observed_server"],
        observed_currency=(
            None if legacy_values["observed_currency"] is _UNSET else legacy_values["observed_currency"]
        ),
        observed_lifecycle_id=(
            None if legacy_values["observed_lifecycle_id"] is _UNSET else legacy_values["observed_lifecycle_id"]
        ),
    )


def _resolve_risk_reservation_spec(
    spec: RiskReservationSpec | None,
    legacy_values: dict[str, Any],
) -> RiskReservationSpec:
    if spec is not None:
        if not isinstance(spec, RiskReservationSpec):
            raise TypeError("spec must be a RiskReservationSpec")
        provided = [name for name, value in legacy_values.items() if value is not _UNSET]
        if provided:
            raise TypeError(
                "cannot specify both 'spec' and individual reservation keyword arguments: "
                + ", ".join(provided)
            )
        return spec
    missing = [name for name, value in legacy_values.items() if value is _UNSET]
    if missing:
        raise TypeError(
            "reserve_account_risk() missing required keyword-only arguments: " + ", ".join(missing)
        )
    return RiskReservationSpec(**legacy_values)



def submission_release_digest(receipt: Mapping[str, Any]) -> str:
    """Bind the loaded release identity; observation timestamps are not identity."""
    if (not isinstance(receipt, Mapping) or receipt.get("attestation_state") != "self_attested"
            or not receipt.get("release_id") or not isinstance(receipt.get("strategy_release"), Mapping)
            or not receipt["strategy_release"]):
        raise AccountSubmissionError("attested release binding required for submission")
    return submission_binding_digest({k: v for k, v in receipt.items() if k != "loaded_at"})


def submission_intent_digest(metadata: Mapping[str, Any], profile: str) -> str:
    allocation = metadata.get("allocation")
    if not isinstance(allocation, Mapping) or not allocation:
        raise AccountSubmissionError("approved allocation identity required")
    return submission_binding_digest({
        "profile": _submission_text(profile), "allocation": dict(allocation),
        **{key: metadata.get(key) for key in (
            "trade_date", "signal_date", "effective_date", "snapshot_as_of", "execution_timing_contract",
        )},
    })

