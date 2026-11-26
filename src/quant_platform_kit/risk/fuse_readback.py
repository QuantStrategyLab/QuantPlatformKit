"""Shared FUSE-2 pre-trade readback contract for broker adapters (fail-closed)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
import re
from typing import Any

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$", re.ASCII)
_ALLOWED_MODES = frozenset({"enforce", "observe"})


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

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> FuseReadbackRecord:
        """Construct from a mapping using strict field validation."""
        if not isinstance(payload, Mapping):
            raise ValueError("FUSE_READBACK_INVALID")
        trade_date = payload.get("trade_date")
        session_allowed = _coerce_strict_bool(payload.get("session_allowed"))
        session_state = payload.get("session_state")
        fuse_latched = _coerce_strict_bool(payload.get("fuse_latched"))
        fuse_level = payload.get("fuse_level")
        blocks_orders = _coerce_strict_bool(payload.get("blocks_orders"))
        blocks_eligibility = _coerce_strict_bool(payload.get("blocks_eligibility"))
        if (
            _parse_iso_date(trade_date) is None
            or session_allowed is None
            or not isinstance(session_state, str)
            or not session_state.strip()
            or fuse_latched is None
            or not isinstance(fuse_level, str)
            or not fuse_level.strip()
            or blocks_orders is None
            or blocks_eligibility is None
        ):
            raise ValueError("FUSE_READBACK_INVALID")
        cal = payload.get("calendar_version", "")
        digest = payload.get("spec_digest", "")
        if not isinstance(cal, str) or not isinstance(digest, str):
            raise ValueError("FUSE_READBACK_INVALID")
        return cls(
            trade_date=str(trade_date).strip(),
            session_allowed=session_allowed,
            session_state=session_state.strip(),
            fuse_latched=fuse_latched,
            fuse_level=fuse_level.strip(),
            blocks_orders=blocks_orders,
            blocks_eligibility=blocks_eligibility,
            calendar_version=cal.strip(),
            spec_digest=digest.strip(),
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
    calendar_version: str = ""
    spec_digest: str = ""


def _resolve_effective_mode(mode: object, current_day: date | None, observe_until: object) -> tuple[str, tuple[str, ...]]:
    normalized = mode.strip().lower() if isinstance(mode, str) else ""
    if normalized not in _ALLOWED_MODES:
        return "enforce", ("FUSE_READBACK_MODE_INVALID_FAIL_CLOSED",)
    if normalized == "enforce":
        return "enforce", ()
    # Observe mode requires a valid current_trade_date and an active observe_until cutoff;
    # expired, unparseable, or missing cutoffs fail closed to enforce.
    cutoff = _parse_iso_date(observe_until)
    if current_day is None or cutoff is None:
        return "enforce", ("FUSE_OBSERVE_WINDOW_INVALID_FAIL_CLOSED",)
    if current_day > cutoff:
        return "enforce", ("FUSE_OBSERVE_WINDOW_EXPIRED_ENFORCED",)
    return "observe", ()


def evaluate_fuse_readback(
    record: FuseReadbackRecord | Mapping[str, Any] | None,
    *,
    current_trade_date: str,
    mode: str = "enforce",
    legacy_switch_enabled: bool = True,
    observe_until: str | None = None,
) -> FuseReadbackDecision:
    """Evaluate same-day FUSE readback under FUSE-2 rules (fail-closed).

    - Non-same-day, missing, or malformed readback records fail closed.
    - ``legacy_switch_enabled=False`` never disables FUSE readback. Instead,
      the tighter restriction wins: legacy disabled OR FUSE block prohibits new risk
      while always evaluating and preserving FUSE reasons.
    - When ``mode="observe"`` with an active ``observe_until >= current_trade_date``,
      FUSE-only reasons are captured in ``reason_codes`` and ``would_block=True`` while
      ``blocks_new_risk`` remains ``False`` (unless the legacy switch itself prohibits).
    """
    current_day = _parse_iso_date(current_trade_date)
    effective_mode, mode_reasons = _resolve_effective_mode(mode, current_day, observe_until)

    if isinstance(legacy_switch_enabled, bool):
        legacy_flag: bool | None = legacy_switch_enabled
        legacy_tighter = not legacy_switch_enabled
    else:
        legacy_flag = None
        legacy_tighter = True

    fuse_reasons: list[str] = list(mode_reasons)
    stale_or_invalid = False
    cal_ver = ""
    spec_digest = ""

    parsed_record: FuseReadbackRecord | None = None
    if isinstance(record, FuseReadbackRecord):
        parsed_record = record
    elif isinstance(record, Mapping):
        try:
            parsed_record = FuseReadbackRecord.from_mapping(record)
        except ValueError:
            stale_or_invalid = True
            fuse_reasons.append("FUSE_READBACK_INVALID_FAIL_CLOSED")
    elif record is None:
        stale_or_invalid = True
        fuse_reasons.append("FUSE_READBACK_MISSING_FAIL_CLOSED")
    else:
        stale_or_invalid = True
        fuse_reasons.append("FUSE_READBACK_INVALID_FAIL_CLOSED")

    if parsed_record is not None:
        cal_ver = parsed_record.calendar_version
        spec_digest = parsed_record.spec_digest
        record_day = _parse_iso_date(parsed_record.trade_date)
        if current_day is None or record_day is None or record_day != current_day:
            stale_or_invalid = True
            fuse_reasons.append("FUSE_READBACK_STALE_FAIL_CLOSED")
        if not parsed_record.session_allowed:
            fuse_reasons.append("FUSE_SESSION_BLOCKED")
        if parsed_record.blocks_orders:
            fuse_reasons.append("FUSE_ORDERS_BLOCKED")
        if parsed_record.blocks_eligibility:
            fuse_reasons.append("FUSE_ELIGIBILITY_BLOCKED")
        if parsed_record.fuse_latched:
            fuse_reasons.append("FUSE_LATCHED_BLOCKED")

    # Deduplicate while preserving deterministic order.
    fuse_only_reasons = tuple(dict.fromkeys(fuse_reasons))
    combined_reasons = list(fuse_only_reasons)
    if legacy_flag is None:
        combined_reasons.append("LEGACY_NEW_RISK_SWITCH_INVALID_FAIL_CLOSED")
    elif not legacy_flag:
        combined_reasons.append("LEGACY_NEW_RISK_SWITCH_DISABLED")

    would_block = bool(fuse_only_reasons) or legacy_tighter
    if effective_mode == "observe":
        blocks_new_risk = legacy_tighter
    else:
        blocks_new_risk = would_block

    return FuseReadbackDecision(
        effective_mode=effective_mode,
        blocks_new_risk=blocks_new_risk,
        would_block=would_block,
        reason_codes=tuple(dict.fromkeys(combined_reasons)),
        stale_or_invalid=stale_or_invalid,
        legacy_switch_enabled=legacy_flag,
        legacy_tighter_block=legacy_tighter,
        calendar_version=cal_ver,
        spec_digest=spec_digest,
    )


__all__ = [
    "FuseReadbackDecision",
    "FuseReadbackRecord",
    "evaluate_fuse_readback",
]
