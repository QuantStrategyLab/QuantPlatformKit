"""Durable, immutable execution commands for delayed broker routing.

This module deliberately separates a strategy decision from broker execution.
It is an opt-in primitive: platform runtimes must explicitly configure a
durable store and integrate a paper-only consumer before using it for orders.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date, datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any


EXECUTION_COMMAND_SCHEMA_VERSION = "execution_command.v1"
EXECUTION_COMMAND_EVENT_SCHEMA_VERSION = "execution_command_event.v1"
DEFAULT_EXECUTION_COMMAND_NAMESPACE = "execution_commands"


class ExecutionCommandState(StrEnum):
    QUEUED = "queued"
    CLAIMED = "claimed"
    SUBMITTED = "submitted"
    ACCEPTED = "accepted"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    RECONCILIATION_REQUIRED = "reconciliation_required"


TERMINAL_EXECUTION_COMMAND_STATES = frozenset(
    {
        ExecutionCommandState.FILLED,
        ExecutionCommandState.CANCELLED,
        ExecutionCommandState.REJECTED,
    }
)

_ALLOWED_TRANSITIONS: dict[ExecutionCommandState, frozenset[ExecutionCommandState]] = {
    ExecutionCommandState.QUEUED: frozenset({ExecutionCommandState.CLAIMED, ExecutionCommandState.CANCELLED}),
    ExecutionCommandState.CLAIMED: frozenset(
        {
            ExecutionCommandState.SUBMITTED,
            ExecutionCommandState.RECONCILIATION_REQUIRED,
            ExecutionCommandState.CANCELLED,
            ExecutionCommandState.REJECTED,
        }
    ),
    ExecutionCommandState.SUBMITTED: frozenset(
        {
            ExecutionCommandState.ACCEPTED,
            ExecutionCommandState.PARTIALLY_FILLED,
            ExecutionCommandState.FILLED,
            ExecutionCommandState.CANCELLED,
            ExecutionCommandState.REJECTED,
            ExecutionCommandState.RECONCILIATION_REQUIRED,
        }
    ),
    ExecutionCommandState.ACCEPTED: frozenset(
        {
            ExecutionCommandState.PARTIALLY_FILLED,
            ExecutionCommandState.FILLED,
            ExecutionCommandState.CANCELLED,
            ExecutionCommandState.REJECTED,
            ExecutionCommandState.RECONCILIATION_REQUIRED,
        }
    ),
    ExecutionCommandState.PARTIALLY_FILLED: frozenset(
        {
            ExecutionCommandState.PARTIALLY_FILLED,
            ExecutionCommandState.FILLED,
            ExecutionCommandState.CANCELLED,
            ExecutionCommandState.RECONCILIATION_REQUIRED,
        }
    ),
    ExecutionCommandState.RECONCILIATION_REQUIRED: frozenset(
        {
            ExecutionCommandState.ACCEPTED,
            ExecutionCommandState.PARTIALLY_FILLED,
            ExecutionCommandState.FILLED,
            ExecutionCommandState.CANCELLED,
            ExecutionCommandState.REJECTED,
        }
    ),
    ExecutionCommandState.FILLED: frozenset(),
    ExecutionCommandState.CANCELLED: frozenset(),
    ExecutionCommandState.REJECTED: frozenset(),
}


def _required_text(value: object, *, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field_name} is required")
    return text


def _iso_date(value: object, *, field_name: str) -> str:
    text = _required_text(value, field_name=field_name)
    try:
        return date.fromisoformat(text[:10]).isoformat()
    except ValueError as exc:
        raise ValueError(f"{field_name} must start with an ISO date") from exc


def _canonical_json(value: Mapping[str, Any]) -> str:
    try:
        return json.dumps(dict(value), ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    except (TypeError, ValueError) as exc:
        raise ValueError("execution command intent must be JSON serializable") from exc


def _safe_path_part(value: object, *, field_name: str) -> str:
    text = _required_text(value, field_name=field_name).lower()
    safe = re.sub(r"[^a-z0-9._=-]+", "-", text).strip("-.")
    if not safe:
        raise ValueError(f"{field_name} has no safe path characters")
    return safe


def _normalize_state(value: ExecutionCommandState | str) -> ExecutionCommandState:
    try:
        return ExecutionCommandState(str(value).strip().lower())
    except ValueError as exc:
        raise ValueError(f"unsupported execution command state: {value!r}") from exc


def validate_execution_command_transition(
    previous_state: ExecutionCommandState | str,
    next_state: ExecutionCommandState | str,
) -> None:
    previous = _normalize_state(previous_state)
    next_value = _normalize_state(next_state)
    if next_value not in _ALLOWED_TRANSITIONS[previous]:
        raise ValueError(f"invalid execution command transition: {previous.value} -> {next_value.value}")


@dataclass(frozen=True)
class ExecutionCommand:
    """An immutable, content-addressed broker execution intent."""

    command_id: str
    platform: str
    account_scope: str
    strategy_profile: str
    execution_mode: str
    signal_date: str
    effective_date: str
    execution_timing_contract: str
    decision_digest: str
    intent_json: str
    created_at: str

    @classmethod
    def from_decision(
        cls,
        *,
        platform: object,
        account_scope: object,
        strategy_profile: object,
        execution_mode: object,
        signal_date: object,
        effective_date: object,
        execution_timing_contract: object,
        decision_digest: object,
        intent: Mapping[str, Any],
        created_at: str | None = None,
    ) -> "ExecutionCommand":
        identity = {
            "platform": _safe_path_part(platform, field_name="platform"),
            "account_scope": _safe_path_part(account_scope, field_name="account_scope"),
            "strategy_profile": _safe_path_part(strategy_profile, field_name="strategy_profile"),
            "execution_mode": _safe_path_part(execution_mode, field_name="execution_mode"),
            "signal_date": _iso_date(signal_date, field_name="signal_date"),
            "effective_date": _iso_date(effective_date, field_name="effective_date"),
            "execution_timing_contract": _required_text(
                execution_timing_contract,
                field_name="execution_timing_contract",
            ),
            "decision_digest": _required_text(decision_digest, field_name="decision_digest"),
            "intent_json": _canonical_json(intent),
        }
        command_id = "cmd-" + hashlib.sha256(
            json.dumps(identity, separators=(",", ":"), sort_keys=True).encode("utf-8")
        ).hexdigest()[:32]
        return cls(
            command_id=command_id,
            created_at=created_at or datetime.now(timezone.utc).isoformat(),
            **identity,
        )

    @property
    def intent(self) -> dict[str, Any]:
        return dict(json.loads(self.intent_json))

    def is_due_on(self, as_of_date: object) -> bool:
        return _iso_date(as_of_date, field_name="as_of_date") == self.effective_date

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": EXECUTION_COMMAND_SCHEMA_VERSION,
            "command_id": self.command_id,
            "platform": self.platform,
            "account_scope": self.account_scope,
            "strategy_profile": self.strategy_profile,
            "execution_mode": self.execution_mode,
            "signal_date": self.signal_date,
            "effective_date": self.effective_date,
            "execution_timing_contract": self.execution_timing_contract,
            "decision_digest": self.decision_digest,
            "intent": self.intent,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ExecutionCommand":
        if str(payload.get("schema_version") or "") != EXECUTION_COMMAND_SCHEMA_VERSION:
            raise ValueError("unsupported execution command schema version")
        intent = payload.get("intent")
        if not isinstance(intent, Mapping):
            raise ValueError("execution command intent must be an object")
        command = cls.from_decision(
            platform=payload.get("platform"),
            account_scope=payload.get("account_scope"),
            strategy_profile=payload.get("strategy_profile"),
            execution_mode=payload.get("execution_mode"),
            signal_date=payload.get("signal_date"),
            effective_date=payload.get("effective_date"),
            execution_timing_contract=payload.get("execution_timing_contract"),
            decision_digest=payload.get("decision_digest"),
            intent=intent,
            created_at=str(payload.get("created_at") or ""),
        )
        if command.command_id != str(payload.get("command_id") or ""):
            raise ValueError("execution command identity does not match its immutable content")
        return command


@dataclass(frozen=True)
class ExecutionCommandEvent:
    command_id: str
    sequence: int
    previous_state: ExecutionCommandState
    state: ExecutionCommandState
    recorded_at: str
    details_json: str = "{}"

    @property
    def details(self) -> dict[str, Any]:
        return dict(json.loads(self.details_json))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": EXECUTION_COMMAND_EVENT_SCHEMA_VERSION,
            "command_id": self.command_id,
            "sequence": self.sequence,
            "previous_state": self.previous_state.value,
            "state": self.state.value,
            "recorded_at": self.recorded_at,
            "details": self.details,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ExecutionCommandEvent":
        if str(payload.get("schema_version") or "") != EXECUTION_COMMAND_EVENT_SCHEMA_VERSION:
            raise ValueError("unsupported execution command event schema version")
        details = payload.get("details")
        if not isinstance(details, Mapping):
            raise ValueError("execution command event details must be an object")
        sequence = int(payload.get("sequence") or 0)
        if sequence < 1:
            raise ValueError("execution command event sequence must be positive")
        previous_state = _normalize_state(str(payload.get("previous_state") or ""))
        state = _normalize_state(str(payload.get("state") or ""))
        validate_execution_command_transition(previous_state, state)
        return cls(
            command_id=_safe_path_part(payload.get("command_id"), field_name="command_id"),
            sequence=sequence,
            previous_state=previous_state,
            state=state,
            recorded_at=_required_text(payload.get("recorded_at"), field_name="recorded_at"),
            details_json=_canonical_json(details),
        )


@dataclass(frozen=True)
class ExecutionCommandStore:
    """Create-only command and event storage with a fail-closed claim path."""

    local_dir: str | Path | None = None
    cloud_prefix_uri: str | None = None
    project_id: str | None = None
    namespace: str = DEFAULT_EXECUTION_COMMAND_NAMESPACE
    object_store: Any = None

    def enqueue(self, command: ExecutionCommand) -> bool:
        return self._create_text(
            self._command_location(command),
            json.dumps(command.to_dict(), ensure_ascii=False, indent=2, sort_keys=True),
        )

    def list_due(self, effective_date: object) -> tuple[ExecutionCommand, ...]:
        due_date = _iso_date(effective_date, field_name="effective_date")
        commands: list[ExecutionCommand] = []
        for location in self._list_locations(self._due_prefix(due_date)):
            if not str(location).endswith("/command.json") and Path(str(location)).name != "command.json":
                continue
            commands.append(ExecutionCommand.from_dict(json.loads(self._read_text(location))))
        return tuple(sorted(commands, key=lambda command: command.command_id))

    def current_state(self, command: ExecutionCommand) -> ExecutionCommandState:
        events = self.events(command)
        return events[-1].state if events else ExecutionCommandState.QUEUED

    def events(self, command: ExecutionCommand) -> tuple[ExecutionCommandEvent, ...]:
        events: list[ExecutionCommandEvent] = []
        for location in self._list_locations(self._event_prefix(command)):
            if not str(location).endswith(".json"):
                continue
            events.append(ExecutionCommandEvent.from_dict(json.loads(self._read_text(location))))
        events.sort(key=lambda event: event.sequence)
        expected_sequence = 1
        previous_state = ExecutionCommandState.QUEUED
        for event in events:
            if event.command_id != command.command_id or event.sequence != expected_sequence:
                raise RuntimeError("execution command events are incomplete or belong to another command")
            if event.previous_state != previous_state:
                raise RuntimeError("execution command event history has an invalid previous state")
            previous_state = event.state
            expected_sequence += 1
        return tuple(events)

    def claim_due(
        self,
        command: ExecutionCommand,
        *,
        as_of_date: object,
        claimant: object,
    ) -> ExecutionCommandEvent | None:
        if not command.is_due_on(as_of_date):
            return None
        return self.append_event(
            command,
            next_state=ExecutionCommandState.CLAIMED,
            details={"claimant": _safe_path_part(claimant, field_name="claimant")},
            expected_previous_state=ExecutionCommandState.QUEUED,
        )

    def append_event(
        self,
        command: ExecutionCommand,
        *,
        next_state: ExecutionCommandState | str,
        details: Mapping[str, Any] | None = None,
        expected_previous_state: ExecutionCommandState | str | None = None,
    ) -> ExecutionCommandEvent | None:
        prior_events = self.events(command)
        previous_state = prior_events[-1].state if prior_events else ExecutionCommandState.QUEUED
        if expected_previous_state is not None and previous_state is not _normalize_state(expected_previous_state):
            return None
        state = _normalize_state(next_state)
        validate_execution_command_transition(previous_state, state)
        sequence = len(prior_events) + 1
        event = ExecutionCommandEvent(
            command_id=command.command_id,
            sequence=sequence,
            previous_state=previous_state,
            state=state,
            recorded_at=datetime.now(timezone.utc).isoformat(),
            details_json=_canonical_json(dict(details or {})),
        )
        created = self._create_text(
            self._event_location(command, sequence),
            json.dumps(event.to_dict(), ensure_ascii=False, indent=2, sort_keys=True),
        )
        return event if created else None

    def _command_location(self, command: ExecutionCommand) -> str | Path:
        return self._location(command.effective_date, command.command_id, "command.json")

    def _event_prefix(self, command: ExecutionCommand) -> str | Path:
        return self._location(command.effective_date, command.command_id, "events")

    def _event_location(self, command: ExecutionCommand, sequence: int) -> str | Path:
        return self._location(command.effective_date, command.command_id, "events", f"{sequence:08d}.json")

    def _due_prefix(self, effective_date: str) -> str | Path:
        return self._location(effective_date)

    def _location(self, effective_date: str, *parts: str) -> str | Path:
        safe_date = _iso_date(effective_date, field_name="effective_date")
        safe_parts = [_safe_path_part(part, field_name="execution command path part") for part in parts]
        if self.cloud_prefix_uri:
            root = str(self.cloud_prefix_uri).rstrip("/")
            return "/".join((root, self.namespace, EXECUTION_COMMAND_SCHEMA_VERSION, safe_date, *safe_parts))
        if self.local_dir:
            return Path(self.local_dir) / self.namespace / EXECUTION_COMMAND_SCHEMA_VERSION / safe_date / Path(*safe_parts)
        raise RuntimeError("execution command store has no durable backend")

    def _create_text(self, location: str | Path, data: str) -> bool:
        if self.cloud_prefix_uri:
            store = self.object_store or self._object_store()
            create = getattr(store, "create_text", None)
            if not callable(create):
                raise RuntimeError("cloud execution command store lacks atomic create-only support")
            return bool(create(str(location), data, "application/json"))
        path = Path(location)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = path.parent / f".{path.name}.{uuid.uuid4().hex}.tmp"
        try:
            fd = os.open(temporary_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            try:
                os.link(temporary_path, path)
            except FileExistsError:
                return False
            return True
        finally:
            temporary_path.unlink(missing_ok=True)

    def _read_text(self, location: str | Path) -> str:
        if self.cloud_prefix_uri:
            return (self.object_store or self._object_store()).read_text(str(location))
        return Path(location).read_text(encoding="utf-8")

    def _list_locations(self, prefix: str | Path) -> tuple[str | Path, ...]:
        if self.cloud_prefix_uri:
            return tuple((self.object_store or self._object_store()).list(str(prefix)))
        path = Path(prefix)
        if not path.exists():
            return ()
        return tuple(path.glob("*/command.json")) if path.name != "events" else tuple(path.glob("*.json"))

    def _object_store(self):
        try:
            from quant_platform_kit.cloud import get_object_store
        except ImportError as exc:
            raise RuntimeError("quant_platform_kit.cloud is required for cloud execution commands") from exc
        return get_object_store(project_id=self.project_id)


def build_execution_command_store_from_env(
    *,
    platform_env_prefix: str,
    env_reader: Callable[[str, str | None], str | None],
    project_id: str | None = None,
) -> ExecutionCommandStore:
    prefix = _safe_path_part(platform_env_prefix, field_name="platform_env_prefix").upper()
    return ExecutionCommandStore(
        local_dir=env_reader(f"{prefix}_EXECUTION_COMMAND_DIR", None),
        cloud_prefix_uri=env_reader(f"{prefix}_EXECUTION_COMMAND_CLOUD_URI", None),
        project_id=project_id,
    )
