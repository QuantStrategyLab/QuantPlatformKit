"""Immutable records for strategy-owned, stateful risk controls.

This module deliberately records *state transitions*, not broker commands.  A
strategy owns the deterministic rule that turns a prior state and frozen market
input into the next state.  A platform may later persist these records, but
must not infer or alter the strategy rule from execution reports.

The contract is useful for controls such as a post-deleveraging cooldown.  It
has no broker imports, storage backend, scheduler, allocation, or order path.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import Any


STRATEGY_RISK_STATE_TRANSITION_SCHEMA_VERSION = "strategy_risk_state_transition.v1"

_SCOPED_IDENTIFIER_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$")
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_MAX_STATE_JSON_BYTES = 8 * 1024


class StrategyRiskStateChainError(ValueError):
    """Raised when a transition cannot be linked to its prior strategy state."""


def _scoped_identifier(value: object, *, field_name: str) -> str:
    normalized = str(value or "").strip().lower()
    if not _SCOPED_IDENTIFIER_PATTERN.fullmatch(normalized):
        raise ValueError(f"{field_name} must be a lowercase scoped identifier")
    return normalized


def _sha256(value: object, *, field_name: str) -> str:
    normalized = str(value or "").strip().lower()
    if not _SHA256_PATTERN.fullmatch(normalized):
        raise ValueError(f"{field_name} must be a lowercase SHA-256 digest")
    return normalized


def _session_date(value: object, *, field_name: str) -> str:
    normalized = str(value or "").strip()
    try:
        return date.fromisoformat(normalized).isoformat()
    except ValueError as exc:
        raise ValueError(f"{field_name} must be an ISO-8601 date") from exc


def _canonical_state_json(value: Mapping[str, object]) -> str:
    if not isinstance(value, Mapping):
        raise ValueError("state must be a JSON object")
    try:
        encoded = json.dumps(dict(value), ensure_ascii=True, allow_nan=False, separators=(",", ":"), sort_keys=True)
        decoded = json.loads(encoded)
    except (TypeError, ValueError) as exc:
        raise ValueError("state must be JSON serializable") from exc
    if not isinstance(decoded, dict):  # Defensive for unusual Mapping implementations.
        raise ValueError("state must be a JSON object")
    if not decoded:
        raise ValueError("state must not be empty")
    if len(encoded.encode("utf-8")) > _MAX_STATE_JSON_BYTES:
        raise ValueError("state exceeds the maximum serialized size")
    return encoded


@dataclass(frozen=True)
class StrategyRiskStateIdentity:
    """The immutable strategy/configuration scope of a risk-state chain.

    ``account_scope`` is a logical runtime label, not a broker account number.
    ``candidate_id`` and ``config_sha256`` prevent a state created for one
    frozen candidate from being replayed under another candidate or config.
    """

    strategy_profile: str
    account_scope: str
    candidate_id: str
    config_sha256: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "strategy_profile", _scoped_identifier(self.strategy_profile, field_name="strategy_profile"))
        object.__setattr__(self, "account_scope", _scoped_identifier(self.account_scope, field_name="account_scope"))
        object.__setattr__(self, "candidate_id", _scoped_identifier(self.candidate_id, field_name="candidate_id"))
        object.__setattr__(self, "config_sha256", _sha256(self.config_sha256, field_name="config_sha256"))

    def to_dict(self) -> dict[str, str]:
        return {
            "strategy_profile": self.strategy_profile,
            "account_scope": self.account_scope,
            "candidate_id": self.candidate_id,
            "config_sha256": self.config_sha256,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> "StrategyRiskStateIdentity":
        required = {"strategy_profile", "account_scope", "candidate_id", "config_sha256"}
        if not isinstance(value, Mapping) or set(value) != required:
            raise ValueError("strategy risk state identity has invalid fields")
        return cls(
            strategy_profile=str(value["strategy_profile"]),
            account_scope=str(value["account_scope"]),
            candidate_id=str(value["candidate_id"]),
            config_sha256=str(value["config_sha256"]),
        )


def _transition_payload(
    *,
    identity: StrategyRiskStateIdentity,
    effective_session: str,
    input_sha256: str,
    previous_transition_sha256: str | None,
    state_json: str,
) -> dict[str, object]:
    return {
        "schema_version": STRATEGY_RISK_STATE_TRANSITION_SCHEMA_VERSION,
        "identity": identity.to_dict(),
        "effective_session": effective_session,
        "input_sha256": input_sha256,
        "previous_transition_sha256": previous_transition_sha256,
        "state": json.loads(state_json),
    }


def _transition_sha256(payload: Mapping[str, object]) -> str:
    canonical = json.dumps(dict(payload), ensure_ascii=True, allow_nan=False, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class StrategyRiskStateTransition:
    """One content-addressed, append-only state transition.

    ``input_sha256`` identifies an already validated frozen input.  The
    strategy-specific rule is intentionally outside this generic contract.
    """

    identity: StrategyRiskStateIdentity
    effective_session: str
    input_sha256: str
    previous_transition_sha256: str | None
    state_json: str
    transition_sha256: str
    schema_version: str = STRATEGY_RISK_STATE_TRANSITION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.identity, StrategyRiskStateIdentity):
            raise ValueError("identity must be a StrategyRiskStateIdentity")
        if self.schema_version != STRATEGY_RISK_STATE_TRANSITION_SCHEMA_VERSION:
            raise ValueError("unsupported strategy risk state transition schema version")
        object.__setattr__(self, "effective_session", _session_date(self.effective_session, field_name="effective_session"))
        object.__setattr__(self, "input_sha256", _sha256(self.input_sha256, field_name="input_sha256"))
        previous = self.previous_transition_sha256
        if previous is not None:
            previous = _sha256(previous, field_name="previous_transition_sha256")
        object.__setattr__(self, "previous_transition_sha256", previous)
        try:
            state = json.loads(self.state_json)
        except (TypeError, ValueError) as exc:
            raise ValueError("state_json must contain JSON") from exc
        object.__setattr__(self, "state_json", _canonical_state_json(state))
        payload = _transition_payload(
            identity=self.identity,
            effective_session=self.effective_session,
            input_sha256=self.input_sha256,
            previous_transition_sha256=self.previous_transition_sha256,
            state_json=self.state_json,
        )
        expected = _transition_sha256(payload)
        actual = _sha256(self.transition_sha256, field_name="transition_sha256")
        if actual != expected:
            raise ValueError("strategy risk state transition_sha256 mismatch")
        object.__setattr__(self, "transition_sha256", actual)

    @property
    def state(self) -> dict[str, Any]:
        return dict(json.loads(self.state_json))

    def to_dict(self) -> dict[str, object]:
        return {
            **_transition_payload(
                identity=self.identity,
                effective_session=self.effective_session,
                input_sha256=self.input_sha256,
                previous_transition_sha256=self.previous_transition_sha256,
                state_json=self.state_json,
            ),
            "transition_sha256": self.transition_sha256,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> "StrategyRiskStateTransition":
        required = {
            "schema_version",
            "identity",
            "effective_session",
            "input_sha256",
            "previous_transition_sha256",
            "state",
            "transition_sha256",
        }
        if not isinstance(value, Mapping) or set(value) != required:
            raise ValueError("strategy risk state transition has invalid fields")
        identity = StrategyRiskStateIdentity.from_dict(value["identity"]) if isinstance(value["identity"], Mapping) else None
        state = value["state"]
        if identity is None or not isinstance(state, Mapping):
            raise ValueError("strategy risk state transition identity or state is invalid")
        previous = value["previous_transition_sha256"]
        if previous is not None and not isinstance(previous, str):
            raise ValueError("previous_transition_sha256 must be a string or null")
        return cls(
            schema_version=str(value["schema_version"]),
            identity=identity,
            effective_session=str(value["effective_session"]),
            input_sha256=str(value["input_sha256"]),
            previous_transition_sha256=previous,
            state_json=_canonical_state_json(state),
            transition_sha256=str(value["transition_sha256"]),
        )


def build_strategy_risk_state_transition(
    *,
    identity: StrategyRiskStateIdentity | Mapping[str, object],
    effective_session: object,
    input_sha256: object,
    state: Mapping[str, object],
    previous_transition: StrategyRiskStateTransition | None = None,
) -> StrategyRiskStateTransition:
    """Build one immutable transition after applying a strategy-owned rule."""

    normalized_identity = (
        identity if isinstance(identity, StrategyRiskStateIdentity) else StrategyRiskStateIdentity.from_dict(identity)
    )
    normalized_session = _session_date(effective_session, field_name="effective_session")
    normalized_input = _sha256(input_sha256, field_name="input_sha256")
    state_json = _canonical_state_json(state)
    if previous_transition is not None:
        validate_strategy_risk_state_transition(previous_transition, identity=normalized_identity, effective_session=normalized_session)
        previous_sha256 = previous_transition.transition_sha256
    else:
        previous_sha256 = None
    payload = _transition_payload(
        identity=normalized_identity,
        effective_session=normalized_session,
        input_sha256=normalized_input,
        previous_transition_sha256=previous_sha256,
        state_json=state_json,
    )
    return StrategyRiskStateTransition(
        identity=normalized_identity,
        effective_session=normalized_session,
        input_sha256=normalized_input,
        previous_transition_sha256=previous_sha256,
        state_json=state_json,
        transition_sha256=_transition_sha256(payload),
    )


def validate_strategy_risk_state_transition(
    previous_transition: StrategyRiskStateTransition,
    *,
    identity: StrategyRiskStateIdentity | Mapping[str, object],
    effective_session: object,
) -> None:
    """Validate that a new transition can safely follow ``previous_transition``."""

    normalized_identity = (
        identity if isinstance(identity, StrategyRiskStateIdentity) else StrategyRiskStateIdentity.from_dict(identity)
    )
    normalized_session = _session_date(effective_session, field_name="effective_session")
    if previous_transition.identity != normalized_identity:
        raise StrategyRiskStateChainError("previous transition identity does not match this risk-state chain")
    if normalized_session <= previous_transition.effective_session:
        raise StrategyRiskStateChainError("effective_session must advance beyond the previous transition")


def validate_strategy_risk_state_chain(
    transitions: tuple[StrategyRiskStateTransition, ...] | list[StrategyRiskStateTransition],
) -> None:
    """Validate an ordered append-only chain for deterministic replay."""

    if not transitions:
        return
    prior: StrategyRiskStateTransition | None = None
    for transition in transitions:
        if not isinstance(transition, StrategyRiskStateTransition):
            raise StrategyRiskStateChainError("risk-state chain contains an invalid transition")
        if prior is None:
            if transition.previous_transition_sha256 is not None:
                raise StrategyRiskStateChainError("root transition must not reference a previous transition")
        else:
            validate_strategy_risk_state_transition(
                prior,
                identity=transition.identity,
                effective_session=transition.effective_session,
            )
            if transition.previous_transition_sha256 != prior.transition_sha256:
                raise StrategyRiskStateChainError("transition does not reference the prior transition digest")
        prior = transition


__all__ = [
    "STRATEGY_RISK_STATE_TRANSITION_SCHEMA_VERSION",
    "StrategyRiskStateChainError",
    "StrategyRiskStateIdentity",
    "StrategyRiskStateTransition",
    "build_strategy_risk_state_transition",
    "validate_strategy_risk_state_chain",
    "validate_strategy_risk_state_transition",
]
