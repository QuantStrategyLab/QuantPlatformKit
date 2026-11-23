"""Localization, notification formatting, and alert message builders for strategy plugins."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any, Callable

from quant_platform_kit.common._strategy_plugin_consumption import (
    _strategy_plugin_auto_consumption_allowed,
    _strategy_plugin_enabled_label,
    _is_strategy_position_control_notice,
    _strategy_plugin_is_notification_only,
)
from quant_platform_kit.common._strategy_plugin_loading import _coerce_strategy_plugin_signal
from quant_platform_kit.common.notification_localization import translator_uses_zh
from quant_platform_kit.common._strategy_plugin_helpers import (
    _as_bool,
    _compact_strategy_plugin_error,
    _normalize_strategy_plugin_field,
    _optional_key_part,
    _optional_string,
    _sanitize_key_part,
    _translate,
    _translate_first,
    _translator_uses_zh,
)
from quant_platform_kit.common._strategy_plugin_models import (
    PLUGIN_CRISIS_RESPONSE_SHADOW,
    PLUGIN_MACRO_RISK_GOVERNOR,
    PLUGIN_MARKET_REGIME_CONTROL,
    PLUGIN_TACO_REBOUND_SHADOW,
    STRATEGY_PLUGIN_ALERT_ACTIONS,
    STRATEGY_PLUGIN_AUTOMATED_POSITION_ACTIONS,
    STRATEGY_PLUGIN_NON_ALERT_ROUTES,
    StrategyPluginAlertMessage,
    StrategyPluginSignal,
)
from quant_platform_kit.common.display_names import display_name

_DEFAULT_STRATEGY_PLUGIN_ALERT_GUIDANCE: Mapping[tuple[str, str, str], str] = {
    (
        PLUGIN_CRISIS_RESPONSE_SHADOW,
        "true_crisis",
        "defend",
    ): (
        "Consider reducing leveraged exposure, moving to defensive or cash-like positions, "
        "and pausing new risk additions until the signal de-escalates."
    ),
    (
        PLUGIN_CRISIS_RESPONSE_SHADOW,
        "no_action",
        "blocked",
    ): (
        "The crisis route was blocked by a guard; review data freshness and context before "
        "acting on the signal."
    ),
    (
        PLUGIN_MACRO_RISK_GOVERNOR,
        "delever",
        "delever",
    ): (
        "Deterministic macro risk governor suggests reducing leveraged exposure while preserving "
        "unlevered risk exposure when the strategy opts in."
    ),
    (
        PLUGIN_MACRO_RISK_GOVERNOR,
        "crisis",
        "defend",
    ): (
        "Deterministic macro risk governor suggests moving the risk sleeve toward defensive or "
        "cash-like exposure until macro stress de-escalates."
    ),
    (
        PLUGIN_MARKET_REGIME_CONTROL,
        "risk_off",
        "defend",
    ): (
        "Unified market regime control blocks opportunity overlays and suggests moving risk exposure "
        "toward defensive or cash-like positions until the deterministic arbiter de-escalates."
    ),
    (
        PLUGIN_MARKET_REGIME_CONTROL,
        "risk_reduced",
        "delever",
    ): (
        "Unified market regime control suggests reducing leveraged exposure while preserving only the "
        "risk budget allowed by the strategy policy adapter."
    ),
    (
        PLUGIN_MARKET_REGIME_CONTROL,
        "opportunity_watch",
        "notify_manual_review",
    ): (
        "Manual review only: the unified arbiter allows the bounded TACO opportunity context, but it "
        "does not authorize broker orders or live allocation mutation."
    ),
    (
        PLUGIN_MARKET_REGIME_CONTROL,
        "blocked",
        "blocked",
    ): (
        "Unified market regime control was blocked by data-quality or freshness guards; review source "
        "artifacts before relying on the signal."
    ),
    (
        PLUGIN_TACO_REBOUND_SHADOW,
        "taco_rebound",
        "notify_manual_review",
    ): (
        "Manual review only: consider a small, pre-sized probe or staged entry with a "
        "predefined invalidation level; avoid full-size deployment from this alert alone."
    ),
}
_DEFAULT_STRATEGY_PLUGIN_ALERT_SCOPE_NOTE = (
    "Manual review notice only; the plugin does not place orders or change allocations."
)


def translate_strategy_plugin_value(
    category: str,
    raw_value: str | None,
    *,
    translator: Callable[..., str] | None = None,
) -> str:
    value = str(raw_value or "").strip() or "unknown"
    if translator is None:
        return value
    key = f"strategy_plugin_{category}_{value}"
    translated = translator(key)
    return translated if translated != key else value


def _extract_strategy_plugin_localized_message(
    signal: StrategyPluginSignal,
    *,
    section: str,
    locale: str,
) -> str | None:
    payload = signal.payload
    normalized_section = str(section or "").strip()
    normalized_locale = str(locale or "").strip()
    if not normalized_section or not normalized_locale:
        return None

    localized_messages = payload.get("localized_messages")
    if isinstance(localized_messages, Mapping):
        section_messages = localized_messages.get(normalized_section)
        if isinstance(section_messages, Mapping):
            localized = _optional_string(section_messages.get(normalized_locale))
            if localized:
                return localized
            default_locale = _optional_string(localized_messages.get("default_locale"))
            if default_locale:
                localized = _optional_string(section_messages.get(default_locale))
                if localized:
                    return localized

    if normalized_section == "notification":
        notification = payload.get("notification")
        if isinstance(notification, Mapping):
            notification_messages = notification.get("localized_messages")
            if isinstance(notification_messages, Mapping):
                localized = _optional_string(notification_messages.get(normalized_locale))
                if localized:
                    return localized
                default_locale = _optional_string(notification.get("default_locale"))
                if default_locale:
                    localized = _optional_string(notification_messages.get(default_locale))
                if localized:
                    return localized
    return None


def extract_strategy_plugin_localized_message(
    signal: StrategyPluginSignal | Any,
    *,
    section: str,
    locale: str,
) -> str | None:
    return _extract_strategy_plugin_localized_message(
        _coerce_strategy_plugin_signal(signal),
        section=section,
        locale=locale,
    )


def _strategy_plugin_consumption_notification_line(
    signal: StrategyPluginSignal,
    *,
    translator: Callable[..., str] | None = None,
) -> str | None:
    route = signal.normalized_route
    action = signal.normalized_action
    if _strategy_plugin_auto_consumption_allowed(signal, action=action):
        if action == "defend" or route == "risk_off":
            key = "strategy_plugin_consumption_auto_defend"
        elif action == "delever" or route == "risk_reduced":
            key = "strategy_plugin_consumption_auto_delever"
        else:
            key = "strategy_plugin_consumption_auto"
        return _translate(
            translator,
            key,
            fallback="Plugin impact this run: included in this cycle's position calculation",
        )
    if _strategy_plugin_is_notification_only(signal):
        return _translate(
            translator,
            "strategy_plugin_consumption_review_only",
            fallback=(
                "Plugin impact this run: review-only notice; current state did not trigger automatic "
                "position rewrites"
            ),
        )
    if action in STRATEGY_PLUGIN_AUTOMATED_POSITION_ACTIONS:
        return _translate(
            translator,
            "strategy_plugin_consumption_loaded_not_applied",
            fallback=(
                "Plugin impact this run: loaded; this state did not enable automatic position rewrites"
            ),
        )
    return None


def build_strategy_plugin_notification_lines(
    signals: Sequence[StrategyPluginSignal | Any],
    *,
    translator: Callable[..., str] | None = None,
    locale: str | None = None,
) -> tuple[str, ...]:
    lines: list[str] = []
    for raw_signal in signals:
        signal = _coerce_strategy_plugin_signal(raw_signal)
        localized_line = (
            _extract_strategy_plugin_localized_message(signal, section="notification", locale=locale)
            if locale is not None
            else None
        )
        if localized_line:
            lines.append(localized_line)
            if translator is not None:
                consumption_line = _strategy_plugin_consumption_notification_line(signal, translator=translator)
                if consumption_line:
                    lines.append(consumption_line)
            continue
        route = signal.canonical_route or "unknown_route"
        action = signal.suggested_action or "unknown_action"
        lines.append(
            _translate(
                translator,
                "strategy_plugin_line",
                fallback="Plugin: {plugin} | enabled: {enabled} | status: {route} | notice: {action}",
                plugin=translate_strategy_plugin_value("name", signal.plugin, translator=translator),
                enabled=_strategy_plugin_enabled_label(signal, translator=translator),
                mode=translate_strategy_plugin_value("mode", signal.effective_mode, translator=translator),
                route=translate_strategy_plugin_value("route", route, translator=translator),
                action=translate_strategy_plugin_value("action", action, translator=translator),
            )
        )
        consumption_line = _strategy_plugin_consumption_notification_line(signal, translator=translator)
        if consumption_line:
            lines.append(consumption_line)
    return tuple(lines)


def _strategy_plugin_error_reason(error: object, *, translator: Callable[..., str] | None = None) -> str:
    detail = _compact_strategy_plugin_error(error)
    if not detail:
        return ""
    error_type = detail.split(":", 1)[0].rsplit(".", 1)[-1].strip()
    reason_key = f"strategy_plugin_error_reason_{error_type}" if error_type else ""
    if translator is not None and reason_key:
        translated = translator(reason_key)
        if translated != reason_key:
            return translated
    if _translator_uses_zh(translator):
        translated = translator("strategy_plugin_error_reason_default") if translator is not None else ""
        if translated and translated != "strategy_plugin_error_reason_default":
            return translated
    return detail


def build_strategy_plugin_error_notification_lines(
    error: object,
    *,
    translator: Callable[..., str] | None = None,
) -> tuple[str, ...]:
    reason = _strategy_plugin_error_reason(error, translator=translator)
    if not reason:
        return ()
    return (
        _translate(
            translator,
            "strategy_plugin_error_line",
            fallback="Plugin signal failed to load: {reason}; this run falls back to built-in strategy rules",
            reason=reason,
        ),
        _translate(
            translator,
            "strategy_plugin_consumption_unavailable",
            fallback="Plugin impact this run: no usable plugin signal loaded",
        ),
    )


def _should_alert_strategy_plugin_signal(signal: StrategyPluginSignal) -> bool:
    route = signal.normalized_route
    action = signal.normalized_action
    if _is_strategy_position_control_notice(signal, action=action):
        return False
    if _is_strategy_manual_review_notification_delegated(signal):
        return False
    return (
        signal.would_trade_if_enabled
        or route not in STRATEGY_PLUGIN_NON_ALERT_ROUTES
        or action in STRATEGY_PLUGIN_ALERT_ACTIONS
    )


def should_alert_strategy_plugin_signal(signal: StrategyPluginSignal | Any) -> bool:
    return _should_alert_strategy_plugin_signal(_coerce_strategy_plugin_signal(signal))


def _is_strategy_manual_review_notification_delegated(signal: StrategyPluginSignal) -> bool:
    """Return true when a strategy artifact delegates human-review alerts to a notification target."""

    if signal.normalized_target_type != "strategy":
        return False
    controls = signal.execution_controls
    if not _as_bool(controls.get("manual_review_notification_delegated"), default=False):
        return False
    return _optional_string(controls.get("manual_review_notification_target")) is not None


def _build_strategy_plugin_alert_guidance(
    signal: StrategyPluginSignal,
    *,
    translator: Callable[..., str] | None = None,
) -> str | None:
    plugin = signal.normalized_plugin
    route = signal.normalized_route
    action = signal.normalized_action
    translated = _translate_first(
        translator,
        (
            f"strategy_plugin_guidance_{plugin}_{route}_{action}",
            f"strategy_plugin_guidance_{plugin}_{route}",
            f"strategy_plugin_guidance_{plugin}_{action}",
            f"strategy_plugin_guidance_{plugin}",
            f"strategy_plugin_guidance_{route}_{action}",
            f"strategy_plugin_guidance_{action}",
        ),
    )
    if translated:
        return translated
    return _DEFAULT_STRATEGY_PLUGIN_ALERT_GUIDANCE.get((plugin, route, action))


def build_strategy_plugin_alert_guidance(
    signal: StrategyPluginSignal | Any,
    *,
    translator: Callable[..., str] | None = None,
) -> str | None:
    return _build_strategy_plugin_alert_guidance(
        _coerce_strategy_plugin_signal(signal),
        translator=translator,
    )


def _build_strategy_plugin_alert_scope_note(
    signal: StrategyPluginSignal,
    *,
    translator: Callable[..., str] | None = None,
) -> str | None:
    controls = signal.execution_controls
    notification_profile = str(controls.get("notification_profile") or "").strip().lower()
    if notification_profile != "shadow_only" and any(
        _as_bool(controls.get(field), default=False)
        for field in (
            "broker_order_allowed",
            "repository_broker_write_allowed",
            "live_allocation_mutation_allowed",
            "repository_allocation_mutation_allowed",
            "allocation_recommendation_allowed",
            "position_sizing_allowed",
            "selection_allowed",
        )
    ):
        return None
    return (
        _translate_first(
            translator,
            (
                f"strategy_plugin_alert_scope_{signal.normalized_plugin}",
                "strategy_plugin_alert_scope",
            ),
        )
        or _DEFAULT_STRATEGY_PLUGIN_ALERT_SCOPE_NOTE
    )


def build_strategy_plugin_alert_scope_note(
    signal: StrategyPluginSignal | Any,
    *,
    translator: Callable[..., str] | None = None,
) -> str | None:
    return _build_strategy_plugin_alert_scope_note(
        _coerce_strategy_plugin_signal(signal),
        translator=translator,
    )


def _strategy_plugin_alert_locale(*, translator: Callable[..., str] | None = None) -> str:
    locale = _translate(translator, "strategy_plugin_alert_locale", fallback="en-US")
    return str(locale or "en-US").strip() or "en-US"


def _localized_strategy_plugin_label_values(
    signal: StrategyPluginSignal,
    label_name: str,
    *,
    locale: str,
) -> tuple[str, ...]:
    localized_messages = signal.payload.get("localized_messages")
    if not isinstance(localized_messages, Mapping):
        return ()
    labels = localized_messages.get("labels")
    if not isinstance(labels, Mapping):
        return ()
    label_values = labels.get(label_name)
    if not isinstance(label_values, Mapping):
        return ()

    candidates = [locale]
    if "-" in locale:
        candidates.append(locale.split("-", 1)[0])
    default_locale = _optional_string(localized_messages.get("default_locale"))
    if default_locale:
        candidates.append(default_locale)

    for candidate in candidates:
        value = label_values.get(candidate)
        if isinstance(value, str):
            text = value.strip()
            return (text,) if text else ()
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            values = tuple(str(item).strip() for item in value if str(item).strip())
            if values:
                return values
    return ()


def _strategy_plugin_reason_values(signal: StrategyPluginSignal, *, locale: str) -> tuple[str, ...]:
    localized_reasons = _localized_strategy_plugin_label_values(signal, "reason_codes", locale=locale)
    if localized_reasons:
        return localized_reasons

    payload = signal.payload
    for section_key in ("log_record", "position_control"):
        section = payload.get(section_key)
        if isinstance(section, Mapping):
            reason_codes = section.get("reason_codes")
            if isinstance(reason_codes, Sequence) and not isinstance(reason_codes, (str, bytes)):
                values = tuple(str(item).strip() for item in reason_codes if str(item).strip())
                if values:
                    return values
    return ()


def _build_strategy_plugin_alert_reason_summary(
    signal: StrategyPluginSignal,
    *,
    translator: Callable[..., str] | None = None,
) -> str:
    locale = _strategy_plugin_alert_locale(translator=translator)
    reasons = _strategy_plugin_reason_values(signal, locale=locale)
    if not reasons:
        return _translate(
            translator,
            "strategy_plugin_alert_reason_none",
            fallback="no explicit reason provided",
        )
    joiner = _translate(translator, "strategy_plugin_alert_reason_joiner", fallback=", ")
    return str(joiner).join(reasons)


def build_strategy_plugin_alert_reason_summary(
    signal: StrategyPluginSignal | Any,
    *,
    translator: Callable[..., str] | None = None,
) -> str:
    return _build_strategy_plugin_alert_reason_summary(
        _coerce_strategy_plugin_signal(signal),
        translator=translator,
    )


def _translate_first_formatted(
    translator: Callable[..., str] | None,
    keys: Sequence[str],
    **kwargs: Any,
) -> str | None:
    if translator is None:
        return None
    for key in keys:
        try:
            translated = translator(key, **kwargs)
        except TypeError:
            translated = translator(key)
        if translated != key:
            text = str(translated).strip()
            if text:
                return text
    return None


def _alert_narrative_keys(kind: str, signal: StrategyPluginSignal) -> tuple[str, ...]:
    plugin = signal.normalized_plugin
    route = signal.normalized_route
    action = signal.normalized_action
    return (
        f"strategy_plugin_{kind}_{plugin}_{route}_{action}",
        f"strategy_plugin_{kind}_{plugin}_{route}",
        f"strategy_plugin_{kind}_{plugin}_{action}",
        f"strategy_plugin_{kind}_{route}_{action}",
        f"strategy_plugin_{kind}_{route}",
        f"strategy_plugin_{kind}_{action}",
        f"strategy_plugin_{kind}_default",
    )


def _build_strategy_plugin_alert_situation(
    signal: StrategyPluginSignal,
    *,
    translator: Callable[..., str] | None = None,
    reasons: str | None = None,
) -> str:
    resolved_reasons = (
        reasons
        if reasons is not None
        else _build_strategy_plugin_alert_reason_summary(signal, translator=translator)
    )
    translated = _translate_first_formatted(
        translator,
        _alert_narrative_keys("situation", signal),
        reasons=resolved_reasons,
    )
    if translated:
        return translated
    return f"The plugin found a market state that needs attention. Trigger: {resolved_reasons}."


def build_strategy_plugin_alert_situation(
    signal: StrategyPluginSignal | Any,
    *,
    translator: Callable[..., str] | None = None,
) -> str:
    return _build_strategy_plugin_alert_situation(
        _coerce_strategy_plugin_signal(signal),
        translator=translator,
    )


def _build_strategy_plugin_alert_recommendation(
    signal: StrategyPluginSignal,
    *,
    translator: Callable[..., str] | None = None,
) -> str:
    translated = _translate_first_formatted(
        translator,
        _alert_narrative_keys("recommendation", signal),
    )
    if translated:
        return translated
    return (
        "Review manually first, then decide whether the action belongs to strategy rules or a manual process; "
        "do not treat the plugin notice as a trade instruction."
    )


def build_strategy_plugin_alert_recommendation(
    signal: StrategyPluginSignal | Any,
    *,
    translator: Callable[..., str] | None = None,
) -> str:
    return _build_strategy_plugin_alert_recommendation(
        _coerce_strategy_plugin_signal(signal),
        translator=translator,
    )


def _strategy_plugin_alert_display_context(
    raw_context: str,
    signal: StrategyPluginSignal,
    *,
    target_label: str,
    translator: Callable[..., str] | None = None,
) -> str:
    context = str(raw_context or "").strip()
    if not context:
        return ""
    normalized = context.strip().lower()
    notification_target = signal.notification_target
    if normalized == f"strategy-plugin-publish / {notification_target}".lower() and notification_target:
        return _translate(
            translator,
            "strategy_plugin_alert_context_strategy_plugin_publish",
            fallback="plugin publish / {target}",
            target=target_label,
        )
    return context


def _build_strategy_plugin_ai_audit_note(
    signal: StrategyPluginSignal,
    *,
    translator: Callable[..., str] | None = None,
) -> str | None:
    ai_audit = signal.payload.get("ai_audit")
    if not isinstance(ai_audit, Mapping) or not _as_bool(ai_audit.get("enabled"), default=False):
        return None
    status = _normalize_strategy_plugin_field(_optional_string(ai_audit.get("status")))
    if status == "ok":
        verdict = _optional_string(ai_audit.get("verdict")) or "unknown"
        assessment = _optional_string(ai_audit.get("route_assessment")) or "unknown"
        summary = _optional_string(ai_audit.get("summary")) or "no summary"
        return _translate(
            translator,
            "strategy_plugin_alert_ai_audit",
            fallback="AI audit: {status} | verdict={verdict} | assessment={assessment} | {summary}",
            status=status,
            verdict=verdict,
            assessment=assessment,
            summary=summary,
        )
    reason = _optional_string(ai_audit.get("skip_reason")) or _optional_string(ai_audit.get("error")) or "no detail"
    return _translate(
        translator,
        "strategy_plugin_alert_ai_audit_status",
        fallback="AI audit: {status} | {reason}",
        status=status,
        reason=reason,
    )


def build_strategy_plugin_ai_audit_note(
    signal: StrategyPluginSignal | Any,
    *,
    translator: Callable[..., str] | None = None,
) -> str | None:
    return _build_strategy_plugin_ai_audit_note(
        _coerce_strategy_plugin_signal(signal),
        translator=translator,
    )


def _build_strategy_plugin_alert_key(
    signal: StrategyPluginSignal,
    *,
    strategy_label: str | None = None,
    context_label: str | None = None,
    namespace: str = "strategy_plugin_alert",
) -> str:
    target_label = (
        signal.strategy
        or signal.notification_target
        or _optional_key_part(strategy_label)
        or "unknown"
    )
    payload = {
        "namespace": _optional_key_part(namespace) or "strategy_plugin_alert",
        "context": _optional_key_part(context_label) or "default",
        "target_type": signal.target_type or "strategy",
        "target": target_label,
        "plugin": signal.plugin or "unknown",
        "mode": signal.effective_mode or "unknown",
        "as_of": signal.as_of or "unknown",
        "route": signal.canonical_route or "unknown",
        "action": signal.suggested_action or "unknown",
        "would_trade_if_enabled": signal.would_trade_if_enabled,
    }
    digest = hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()[:16]
    return "/".join(
        (
            _sanitize_key_part(payload["namespace"]),
            _sanitize_key_part(payload["context"]),
            _sanitize_key_part(payload["target"]),
            _sanitize_key_part(payload["plugin"]),
            _sanitize_key_part(payload["as_of"]),
            _sanitize_key_part(payload["route"]),
            _sanitize_key_part(payload["action"]),
            digest,
        )
    )


def build_strategy_plugin_alert_key(
    signal: StrategyPluginSignal | Any,
    *,
    strategy_label: str | None = None,
    context_label: str | None = None,
    namespace: str = "strategy_plugin_alert",
) -> str:
    return _build_strategy_plugin_alert_key(
        _coerce_strategy_plugin_signal(signal),
        strategy_label=strategy_label,
        context_label=context_label,
        namespace=namespace,
    )


def build_strategy_plugin_alert_messages(
    signals: Sequence[StrategyPluginSignal | Any],
    *,
    translator: Callable[..., str] | None = None,
    strategy_label: str | None = None,
    context_label: str | None = None,
    alert_namespace: str = "strategy_plugin_alert",
) -> tuple[StrategyPluginAlertMessage, ...]:
    messages: list[StrategyPluginAlertMessage] = []
    context = str(context_label or "").strip()
    for raw_signal in signals:
        signal = _coerce_strategy_plugin_signal(raw_signal)
        if not _should_alert_strategy_plugin_signal(signal):
            continue
        route = signal.canonical_route or "unknown_route"
        action = signal.suggested_action or "unknown_action"
        plugin = translate_strategy_plugin_value("name", signal.plugin, translator=translator)
        translated_mode = translate_strategy_plugin_value(
            "mode",
            signal.effective_mode,
            translator=translator,
        )
        translated_route = translate_strategy_plugin_value("route", route, translator=translator)
        translated_action = translate_strategy_plugin_value("action", action, translator=translator)
        target_type = signal.target_type
        strategy = str(strategy_label or signal.strategy or "").strip()
        notification_target = signal.notification_target
        target_label = strategy or notification_target or "unknown"
        display_target_label = target_label
        if target_type == "notification_target" and notification_target:
            display_target_label = translate_strategy_plugin_value(
                "notification_target",
                notification_target,
                translator=translator,
            )
        elif strategy:
            display_target_label = translate_strategy_plugin_value("strategy", strategy, translator=translator)
        # Presentation only: target_label still supplies alert keys and machine metadata.
        display_target_label = display_name(
            "strategies",
            signal.strategy or strategy,
            "zh" if translator and translator_uses_zh(translator) else "en",
            fallback=display_target_label,
        )
        display_context = _strategy_plugin_alert_display_context(
            context,
            signal,
            target_label=display_target_label,
            translator=translator,
        )
        target_name_key = (
            "strategy_plugin_alert_target_name_notification_target"
            if target_type == "notification_target"
            else "strategy_plugin_alert_target_name_strategy"
        )
        target_name = _translate(
            translator,
            target_name_key,
            fallback="Notification target" if target_type == "notification_target" else "Strategy",
        )
        guidance = _build_strategy_plugin_alert_guidance(signal, translator=translator)
        reason_summary = _build_strategy_plugin_alert_reason_summary(signal, translator=translator)
        situation = _build_strategy_plugin_alert_situation(
            signal,
            translator=translator,
            reasons=reason_summary,
        )
        recommendation = _build_strategy_plugin_alert_recommendation(signal, translator=translator)
        scope_note = _build_strategy_plugin_alert_scope_note(signal, translator=translator)
        ai_audit_note = _build_strategy_plugin_ai_audit_note(signal, translator=translator)
        subject = _translate(
            translator,
            "strategy_plugin_alert_subject",
            fallback="Strategy plugin alert: {plugin} | {route}",
            strategy=display_target_label,
            plugin=plugin,
            route=translated_route,
        )
        if display_context:
            subject = f"[{display_context}] {subject}"
        body_lines = [
            _translate(translator, "strategy_plugin_alert_title", fallback="Strategy Plugin Alert"),
            "",
        ]
        if display_context:
            body_lines.append(
                _translate(
                    translator,
                    "strategy_plugin_alert_context",
                    fallback="Context: {context}",
                    context=display_context,
                )
            )
        body_lines.extend(
            [
                _translate(
                    translator,
                    "strategy_plugin_alert_target",
                    fallback="{target_name}: {target}",
                    target_name=target_name,
                    target=display_target_label,
                ),
                _translate(
                    translator,
                    "strategy_plugin_alert_plugin",
                    fallback="Plugin: {plugin}",
                    plugin=plugin,
                ),
                _translate(
                    translator,
                    "strategy_plugin_alert_as_of",
                    fallback="Signal as-of: {as_of}",
                    as_of=signal.as_of or "unknown",
                ),
                _translate(
                    translator,
                    "strategy_plugin_alert_situation",
                    fallback="Situation: {situation}",
                    situation=situation,
                ),
                _translate(
                    translator,
                    "strategy_plugin_alert_trigger",
                    fallback="Trigger: {reasons}",
                    reasons=reason_summary,
                ),
                _translate(
                    translator,
                    "strategy_plugin_alert_recommendation",
                    fallback="Suggested review: {recommendation}",
                    recommendation=recommendation,
                ),
                _translate(
                    translator,
                    "strategy_plugin_alert_status",
                    fallback="Status: {route}",
                    route=translated_route,
                ),
                _translate(
                    translator,
                    "strategy_plugin_alert_action",
                    fallback="Notice: {action}",
                    action=translated_action,
                ),
                _translate(
                    translator,
                    "strategy_plugin_alert_mode",
                    fallback="Mode: {mode}",
                    mode=translated_mode,
                ),
            ]
        )
        if guidance:
            body_lines.append(
                _translate(
                    translator,
                    "strategy_plugin_alert_guidance",
                    fallback="Manual guidance: {guidance}",
                    guidance=guidance,
                )
            )
        if ai_audit_note:
            body_lines.append(ai_audit_note)
        if scope_note:
            body_lines.append(
                _translate(
                    translator,
                    "strategy_plugin_alert_scope_note",
                    fallback="Scope: {scope_note}",
                    scope_note=scope_note,
                )
            )
        metadata = {
            "target_type": target_type,
            "target": target_label,
            "strategy": signal.strategy,
            "strategy_label": strategy or None,
            "notification_target": notification_target or None,
            "plugin": signal.plugin,
            "mode": signal.effective_mode,
            "as_of": signal.as_of,
            "canonical_route": signal.canonical_route,
            "suggested_action": signal.suggested_action,
            "would_trade_if_enabled": signal.would_trade_if_enabled,
            "context_label": context or None,
            "display_context_label": display_context or None,
            "display_target": display_target_label,
            "situation": situation,
            "recommendation": recommendation,
            "reason_summary": reason_summary,
            "guidance": guidance,
            "scope_note": scope_note,
            "ai_audit": signal.payload.get("ai_audit"),
        }
        messages.append(
            StrategyPluginAlertMessage(
                subject=subject,
                body="\n".join(body_lines),
                alert_key=_build_strategy_plugin_alert_key(
                    signal,
                    strategy_label=target_label,
                    context_label=context,
                    namespace=alert_namespace,
                ),
                metadata=metadata,
            )
        )
    return tuple(messages)

