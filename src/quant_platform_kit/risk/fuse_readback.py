"""Shared FUSE-2 pre-trade readback contract for broker adapters (fail-closed)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
import re
from typing import Any

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$", re.ASCII)
_ALLOWED_MODES = frozenset({"enforce", "observe"})
_TRADING_SESSION_STATES = frozenset({"regular", "half_day"})
_NON_TRADING_SESSION_STATES = frozenset({"closed", "unscheduled_closure", "unknown"})
_ALLOWED_SESSION_STATES = _TRADING_SESSION_STATES | _NON_TRADING_SESSION_STATES


def _parse_iso_date(value: object) -> date | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    if not _DATE_RE.fullmatch(stripped):
        return None
    try:
        return date.fromisoformat(stripped)
    except ValueError:
        return None


def _coerce_strict_bool(value: object) -> bool | None:
    return value if isinstance(value, bool) else None


def _validate_record_fields(
    *,
    trade_date: object,
    session_allowed: object,
    session_state: object,
    fuse_latched: object,
    fuse_level: object,
    blocks_orders: object,
    blocks_eligibility: object,
    calendar_version: object,
    spec_digest: object,
) -> tuple[str, bool, str, bool, str, bool, bool, str, str]:
    parsed_day = _parse_iso_date(trade_date)
    allowed = _coerce_strict_bool(session_allowed)
    latched = _coerce_strict_bool(fuse_latched)
    blk_orders = _coerce_strict_bool(blocks_orders)
    blk_elig = _coerce_strict_bool(blocks_eligibility)

    if (
        parsed_day is None
        or allowed is None
        or not isinstance(session_state, str)
        or not session_state.strip()
        or latched is None
        or not isinstance(fuse_level, str)
        or not fuse_level.strip()
        or blk_orders is None
        or blk_elig is None
        or not isinstance(calendar_version, str)
        or not isinstance(spec_digest, str)
    ):
        raise ValueError("FUSE_READBACK_INVALID")

    norm_state = session_state.strip()
    if norm_state not in _ALLOWED_SESSION_STATES:
        raise ValueError("FUSE_READBACK_INVALID")
    # Non-trading / unknown sessions cannot claim session_allowed=True or unblock orders/eligibility.
    if norm_state in _NON_TRADING_SESSION_STATES and (allowed or not blk_orders or not blk_elig):
        raise ValueError("FUSE_READBACK_INVALID")

    return (
        str(trade_date).strip(),
        allowed,
        norm_state,
        latched,
        fuse_level.strip(),
        blk_orders,
        blk_elig,
        calendar_version.strip(),
        spec_digest.strip(),
    )


@dataclass(frozen=True)
class FuseReadbackRecord:
    """Redacted daily FUSE session & circuit-breaker readback snapshot."""

    trade_date: str
    session_allowed: bool
    session_state: str
    fuse_latched: bool
    fuse_level: str
    blocks_orders: bool
    blocks_eligibility: bool
    calendar_version: str = ""
    spec_digest: str = ""

    def __post_init__(self) -> None:
        (
            norm_date,
            allowed,
            norm_state,
            latched,
            norm_level,
            blk_orders,
            blk_elig,
            norm_cal,
            norm_digest,
        ) = _validate_record_fields(
            trade_date=self.trade_date,
            session_allowed=self.session_allowed,
            session_state=self.session_state,
            fuse_latched=self.fuse_latched,
            fuse_level=self.fuse_level,
            blocks_orders=self.blocks_orders,
            blocks_eligibility=self.blocks_eligibility,
            calendar_version=self.calendar_version,
            spec_digest=self.spec_digest,
        )
        object.__setattr__(self, "trade_date", norm_date)
        object.__setattr__(self, "session_allowed", allowed)
        object.__setattr__(self, "session_state", norm_state)
        object.__setattr__(self, "fuse_latched", latched)
        object.__setattr__(self, "fuse_level", norm_level)
        object.__setattr__(self, "blocks_orders", blk_orders)
        object.__setattr__(self, "blocks_eligibility", blk_elig)
        object.__setattr__(self, "calendar_version", norm_cal)
        object.__setattr__(self, "spec_digest", norm_digest)

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> FuseReadbackRecord:
        """Construct from a mapping using strict field validation."""
        if not isinstance(payload, Mapping):
            raise ValueError("FUSE_READBACK_INVALID")
        return cls(
            trade_date=payload.get("trade_date"),  # type: ignore[arg-type]
            session_allowed=payload.get("session_allowed"),  # type: ignore[arg-type]
            session_state=payload.get("session_state"),  # type: ignore[arg-type]
            fuse_latched=payload.get("fuse_latched"),  # type: ignore[arg-type]
            fuse_level=payload.get("fuse_level"),  # type: ignore[arg-type]
            blocks_orders=payload.get("blocks_orders"),  # type: ignore[arg-type]
            blocks_eligibility=payload.get("blocks_eligibility"),  # type: ignore[arg-type]
            calendar_version=payload.get("calendar_version", ""),  # type: ignore[arg-type]
            spec_digest=payload.get("spec_digest", ""),  # type: ignore[arg-type]
        )


@dataclass(frozen=True)
class FuseReadbackDecision:
    """Result of evaluating FUSE readback alongside legacy new-risk switches."""

    effective_mode: str
    blocks_new_risk: bool
    would_block: bool
    reason_codes: tuple[str, ...]
    stale_or_invalid: bool
    legacy_switch_enabled: bool | None
    legacy_tighter_block: bool
    observe_window_expired: bool = False
    calendar_version: str = ""
    spec_digest: str = ""


def _resolve_effective_mode(
    mode: object,
    current_day: date | None,
    observe_until: object,
) -> tuple[str, tuple[str, ...], bool]:
    normalized = mode.strip().lower() if isinstance(mode, str) else ""
    if normalized not in _ALLOWED_MODES:
        return "enforce", ("FUSE_READBACK_MODE_INVALID_FAIL_CLOSED",), False
    if normalized == "enforce":
        return "enforce", (), False
    cutoff = _parse_iso_date(observe_until)
    if current_day is None or cutoff is None:
        return "enforce", ("FUSE_OBSERVE_WINDOW_INVALID_FAIL_CLOSED",), False
    if current_day > cutoff:
        # Normal two-week rollout expiry promotes observe -> enforce without inventing a failure reason;
        # the current readback record itself then determines whether new risk is permitted.
        return "enforce", (), True
    return "observe", (), False


def _parse_fuse_record(
    record: FuseReadbackRecord | Mapping[str, Any] | None,
) -> tuple[FuseReadbackRecord | None, bool, tuple[str, ...]]:
    if isinstance(record, FuseReadbackRecord):
        try:
            _validate_record_fields(
                trade_date=record.trade_date,
                session_allowed=record.session_allowed,
                session_state=record.session_state,
                fuse_latched=record.fuse_latched,
                fuse_level=record.fuse_level,
                blocks_orders=record.blocks_orders,
                blocks_eligibility=record.blocks_eligibility,
                calendar_version=record.calendar_version,
                spec_digest=record.spec_digest,
            )
            return record, False, ()
        except ValueError:
            return None, True, ("FUSE_READBACK_INVALID_FAIL_CLOSED",)
    if isinstance(record, Mapping):
        try:
            return FuseReadbackRecord.from_mapping(record), False, ()
        except ValueError:
            return None, True, ("FUSE_READBACK_INVALID_FAIL_CLOSED",)
    if record is None:
        return None, True, ("FUSE_READBACK_MISSING_FAIL_CLOSED",)
    return None, True, ("FUSE_READBACK_INVALID_FAIL_CLOSED",)


def _evaluate_record_flags(
    parsed_record: FuseReadbackRecord,
    current_day: date | None,
) -> tuple[bool, list[str]]:
    stale = False
    reasons: list[str] = []
    record_day = _parse_iso_date(parsed_record.trade_date)
    if current_day is None or record_day is None or record_day != current_day:
        stale = True
        reasons.append("FUSE_READBACK_STALE_FAIL_CLOSED")
    if not parsed_record.session_allowed:
        reasons.append("FUSE_SESSION_BLOCKED")
    if parsed_record.blocks_orders:
        reasons.append("FUSE_ORDERS_BLOCKED")
    if parsed_record.blocks_eligibility:
        reasons.append("FUSE_ELIGIBILITY_BLOCKED")
    if parsed_record.fuse_latched:
        reasons.append("FUSE_LATCHED_BLOCKED")
    return stale, reasons


def evaluate_fuse_readback(
    record: FuseReadbackRecord | Mapping[str, Any] | None,
    *,
    current_trade_date: str,
    mode: object = "enforce",
    legacy_switch_enabled: object = True,
    observe_until: object = None,
) -> FuseReadbackDecision:
    """Evaluate same-day FUSE readback under FUSE-2 rules (fail-closed)."""
    current_day = _parse_iso_date(current_trade_date)
    effective_mode, mode_reasons, observe_expired = _resolve_effective_mode(
        mode, current_day, observe_until
    )

    if isinstance(legacy_switch_enabled, bool):
        legacy_flag: bool | None = legacy_switch_enabled
        legacy_tighter = not legacy_switch_enabled
    else:
        legacy_flag = None
        legacy_tighter = True

    parsed_record, stale_or_invalid, parse_reasons = _parse_fuse_record(record)
    fuse_reasons: list[str] = [*mode_reasons, *parse_reasons]
    cal_ver = parsed_record.calendar_version if parsed_record is not None else ""
    spec_digest = parsed_record.spec_digest if parsed_record is not None else ""

    if parsed_record is not None:
        record_stale, flag_reasons = _evaluate_record_flags(parsed_record, current_day)
        stale_or_invalid = stale_or_invalid or record_stale
        fuse_reasons.extend(flag_reasons)

    fuse_only_reasons = tuple(dict.fromkeys(fuse_reasons))
    combined_reasons = list(fuse_only_reasons)
    if legacy_flag is None:
        combined_reasons.append("LEGACY_NEW_RISK_SWITCH_INVALID_FAIL_CLOSED")
    elif not legacy_flag:
        combined_reasons.append("LEGACY_NEW_RISK_SWITCH_DISABLED")

    would_block = bool(fuse_only_reasons) or legacy_tighter
    blocks_new_risk = legacy_tighter if effective_mode == "observe" else would_block

    return FuseReadbackDecision(
        effective_mode=effective_mode,
        blocks_new_risk=blocks_new_risk,
        would_block=would_block,
        reason_codes=tuple(dict.fromkeys(combined_reasons)),
        stale_or_invalid=stale_or_invalid,
        legacy_switch_enabled=legacy_flag,
        legacy_tighter_block=legacy_tighter,
        observe_window_expired=observe_expired,
        calendar_version=cal_ver,
        spec_digest=spec_digest,
    )


__all__ = [
    "FuseReadbackDecision",
    "FuseReadbackRecord",
    "evaluate_fuse_readback",
]
