"""Operational attention levels for notify / HITL routing (not a sizing engine).

Synthesizes capital (new-risk), operational fault, and research-drift axes into
``OK | WATCH | ACTION | HALT``. Absolute drawdown percentages are never enough:
drawdown only contributes when a mandate budget is supplied
(``dd_ratio = drawdown_from_peak / mandate_dd_budget``).

This module does not send Telegram, grant live, raise RRL, or compute Kelly.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping


class AttentionLevel(str, Enum):
    OK = "ok"
    WATCH = "watch"
    ACTION = "action"
    HALT = "halt"

    @property
    def severity_order(self) -> int:
        return {
            AttentionLevel.OK: 0,
            AttentionLevel.WATCH: 1,
            AttentionLevel.ACTION: 2,
            AttentionLevel.HALT: 3,
        }[self]


_NOTIFY_LEVELS = frozenset({AttentionLevel.ACTION, AttentionLevel.HALT})

_DRIFT_STATUS_LEVEL = {
    "critical": AttentionLevel.HALT,
    "review": AttentionLevel.ACTION,
    "watch": AttentionLevel.WATCH,
    "healthy": AttentionLevel.OK,
    "ok": AttentionLevel.OK,
}


@dataclass(frozen=True)
class AttentionAxes:
    """Explicit attention inputs; missing fields omit that axis (fail-soft)."""

    new_risk_prohibited: bool | None = None
    drift_status: str | None = None
    production_drift_status: str | None = None
    operational_uncertain: bool | None = None
    operational_fault: bool | None = None
    hard_park: bool | None = None
    drawdown_from_peak: float | None = None
    mandate_dd_budget: float | None = None


@dataclass(frozen=True)
class AttentionDecision:
    level: AttentionLevel
    reason_codes: tuple[str, ...]
    dd_ratio: float | None
    should_notify: bool
    next_step_key: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "level": self.level.value,
            "reason_codes": list(self.reason_codes),
            "dd_ratio": self.dd_ratio,
            "should_notify": self.should_notify,
            "next_step_key": self.next_step_key,
        }


def evaluate_attention(axes: AttentionAxes | Mapping[str, Any] | None = None, **kwargs: Any) -> AttentionDecision:
    """Combine explicit axes into one attention level.

    Accepts ``AttentionAxes``, a mapping, or keyword overrides. Drawdown without
    ``mandate_dd_budget`` does not raise level.
    """

    resolved = _coerce_axes(axes, kwargs)
    candidates: list[tuple[AttentionLevel, str]] = []

    if resolved.hard_park is True:
        candidates.append((AttentionLevel.HALT, "hard_park"))
    if resolved.operational_uncertain is True or resolved.operational_fault is True:
        candidates.append((AttentionLevel.HALT, "operational_uncertain"))

    drift_key = str(
        resolved.drift_status or resolved.production_drift_status or ""
    ).strip().lower()
    if drift_key:
        drift_level = _DRIFT_STATUS_LEVEL.get(drift_key)
        if drift_level is None:
            candidates.append((AttentionLevel.WATCH, "drift_status_unknown"))
        elif drift_level is AttentionLevel.HALT:
            candidates.append((AttentionLevel.HALT, "drift_critical"))
        elif drift_level is AttentionLevel.ACTION:
            candidates.append((AttentionLevel.ACTION, "drift_review"))
        elif drift_level is AttentionLevel.WATCH:
            candidates.append((AttentionLevel.WATCH, "drift_watch"))

    if resolved.new_risk_prohibited is True:
        candidates.append((AttentionLevel.ACTION, "new_risk_prohibited"))

    dd_ratio = _resolve_dd_ratio(resolved.drawdown_from_peak, resolved.mandate_dd_budget)
    if dd_ratio is not None:
        if dd_ratio >= 1.0:
            candidates.append((AttentionLevel.ACTION, "mandate_dd_exhausted"))
        elif dd_ratio >= 0.7:
            candidates.append((AttentionLevel.WATCH, "mandate_dd_elevated"))

    if not candidates:
        level = AttentionLevel.OK
        reasons: tuple[str, ...] = ()
    else:
        level = max(candidates, key=lambda item: item[0].severity_order)[0]
        # Keep every contributing reason so operators see the full stack.
        reasons = tuple(dict.fromkeys(code for _, code in candidates))

    return AttentionDecision(
        level=level,
        reason_codes=reasons,
        dd_ratio=dd_ratio,
        should_notify=level in _NOTIFY_LEVELS,
        next_step_key=_next_step_key(level, reasons),
    )


def attention_transition_key(
    *,
    platform: str,
    account_alias: str,
    strategy_profile: str,
    level: AttentionLevel | str,
    primary_reason: str,
) -> str:
    """Stable dedup key for attention notifications (not price/time based)."""

    return "/".join(
        [
            "attention",
            _clean_segment(platform),
            _clean_segment(account_alias),
            _clean_segment(strategy_profile),
            _coerce_level(level).value,
            _clean_segment(primary_reason),
        ]
    )


# Back-compat alias used by early drafts / exports.
attention_alert_key = attention_transition_key


def should_notify_attention_transition(
    *,
    previous_level: AttentionLevel | str | None,
    new_level: AttentionLevel | str,
    previous_reason_codes: tuple[str, ...] | list[str] | None = None,
    new_reason_codes: tuple[str, ...] | list[str] | None = None,
) -> bool:
    current = _coerce_level(new_level)
    if current not in _NOTIFY_LEVELS:
        return False
    prior = _coerce_level(previous_level) if previous_level is not None else None
    if prior != current:
        return True
    return tuple(previous_reason_codes or ()) != tuple(new_reason_codes or ())


def render_attention_compact(
    *,
    locale: object | None,
    platform: str,
    account_alias: str,
    strategy_profile: str,
    decision: AttentionDecision,
) -> str:
    """Four-line operator message: identity / result / reason / next step."""

    from quant_platform_kit.common.operational_notification_localization import (
        operational_notification_text,
        resolve_operational_notification_locale,
    )

    lang = resolve_operational_notification_locale(locale)
    level = decision.level
    reason = decision.reason_codes[0] if decision.reason_codes else "none"
    emoji = {
        AttentionLevel.OK: "✅",
        AttentionLevel.WATCH: "👀",
        AttentionLevel.ACTION: "⚠️",
        AttentionLevel.HALT: "🚨",
    }[level]
    title = operational_notification_text(
        lang,
        "attention_title",
        platform=platform,
        account=account_alias,
        strategy=strategy_profile,
    )
    result_key = _result_text_key(level, decision.reason_codes)
    result = operational_notification_text(lang, result_key)
    reason_line = operational_notification_text(lang, "attention_reason", code=reason)
    next_step = operational_notification_text(lang, f"attention_next_{decision.next_step_key}")
    return f"{emoji} {title}\n{result}\n{reason_line}\n{next_step}"


format_attention_compact_message = render_attention_compact


def attention_level_from_drift_status(status: object) -> AttentionLevel:
    value = getattr(status, "value", status)
    return _DRIFT_STATUS_LEVEL.get(str(value or "").strip().lower(), AttentionLevel.WATCH)


def _coerce_axes(
    axes: AttentionAxes | Mapping[str, Any] | None,
    kwargs: Mapping[str, Any],
) -> AttentionAxes:
    if isinstance(axes, AttentionAxes) and not kwargs:
        return axes
    raw: dict[str, Any] = {}
    if isinstance(axes, AttentionAxes):
        raw.update(
            {
                "new_risk_prohibited": axes.new_risk_prohibited,
                "drift_status": axes.drift_status,
                "production_drift_status": axes.production_drift_status,
                "operational_uncertain": axes.operational_uncertain,
                "operational_fault": axes.operational_fault,
                "hard_park": axes.hard_park,
                "drawdown_from_peak": axes.drawdown_from_peak,
                "mandate_dd_budget": axes.mandate_dd_budget,
            }
        )
    elif isinstance(axes, Mapping):
        raw.update(dict(axes))
    raw.update(dict(kwargs))
    return AttentionAxes(
        new_risk_prohibited=raw.get("new_risk_prohibited"),
        drift_status=raw.get("drift_status"),
        production_drift_status=raw.get("production_drift_status"),
        operational_uncertain=raw.get("operational_uncertain"),
        operational_fault=raw.get("operational_fault"),
        hard_park=raw.get("hard_park"),
        drawdown_from_peak=raw.get("drawdown_from_peak"),
        mandate_dd_budget=raw.get("mandate_dd_budget"),
    )


def _resolve_dd_ratio(
    drawdown_from_peak: float | None,
    mandate_dd_budget: float | None,
) -> float | None:
    if drawdown_from_peak is None or mandate_dd_budget is None:
        return None
    try:
        dd = float(drawdown_from_peak)
        budget = float(mandate_dd_budget)
    except (TypeError, ValueError):
        return None
    if budget <= 0.0 or dd < 0.0:
        return None
    return dd / budget


def _next_step_key(level: AttentionLevel, reasons: tuple[str, ...]) -> str:
    if "operational_uncertain" in reasons or "hard_park" in reasons:
        return "open_console_resume"
    if level is AttentionLevel.HALT:
        return "open_console_resume"
    if level is AttentionLevel.ACTION:
        return "open_console_confirm"
    if level is AttentionLevel.WATCH:
        return "console_optional"
    return "none"


def _result_text_key(level: AttentionLevel, reasons: tuple[str, ...]) -> str:
    if "new_risk_prohibited" in reasons and level in _NOTIFY_LEVELS:
        return "attention_result_new_risk_prohibited"
    return f"attention_result_{level.value}"


def _coerce_level(value: AttentionLevel | str) -> AttentionLevel:
    if isinstance(value, AttentionLevel):
        return value
    key = str(value or "").strip().lower()
    try:
        return AttentionLevel(key)
    except ValueError:
        return AttentionLevel.WATCH


def _clean_segment(value: object) -> str:
    text = str(value or "").strip().lower() or "unknown"
    return "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "-" for ch in text)[:80]


# Leveraged live profiles: path DD commonly exceeds 10%; use mandate budgets, not 0.10.
_DEFAULT_MANDATE_DD_BUDGET_BY_PROFILE: dict[str, float] = {
    "soxl_soxx_trend_income": 0.35,
    "tqqq_growth_income": 0.35,
}


def resolve_mandate_dd_budget(
    strategy_profile: object | None,
    *,
    override: float | None = None,
    environ: Mapping[str, str] | None = None,
) -> float | None:
    """Resolve mandate drawdown budget for attention (never invents 10% default).

    Precedence: explicit ``override`` → ``QSL_MANDATE_DD_BUDGET_<PROFILE>`` →
    ``QSL_MANDATE_DD_BUDGET`` → built-in leveraged profile map → ``None`` (omit DD axis).
    """

    import os

    env = environ if environ is not None else os.environ
    for candidate in (override, _env_budget(env, strategy_profile), _env_budget(env, None)):
        parsed = _optional_positive_unit(candidate)
        if parsed is not None:
            return parsed
    profile = str(strategy_profile or "").strip().lower()
    if profile in _DEFAULT_MANDATE_DD_BUDGET_BY_PROFILE:
        return _DEFAULT_MANDATE_DD_BUDGET_BY_PROFILE[profile]
    return None


def _env_budget(env: Mapping[str, str], strategy_profile: object | None) -> float | None:
    if strategy_profile is None:
        raw = env.get("QSL_MANDATE_DD_BUDGET")
    else:
        profile = str(strategy_profile or "").strip().upper().replace("-", "_")
        raw = env.get(f"QSL_MANDATE_DD_BUDGET_{profile}") if profile else None
    return _optional_positive_unit(raw)


def _optional_positive_unit(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        if isinstance(value, bool):
            return None
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or number <= 0.0 or number > 1.0:
        return None
    return number

