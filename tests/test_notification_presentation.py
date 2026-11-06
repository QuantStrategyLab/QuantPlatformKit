"""Display boundaries retain unknown counts and all mandatory sections."""
from datetime import datetime, timezone

import pytest

from quant_platform_kit.common.operational_notification_localization import format_operational_alert, format_receipt_alert
from quant_platform_kit.notifications.presentation import render_operator_message, safe_run_url
from quant_platform_kit.risk.attention import AttentionAxes, evaluate_attention, render_attention_compact


@pytest.mark.parametrize("locale", ["zh", "en"])
def test_risk_guard_and_receipt_share_sections_without_inventing_counts(locale):
    messages = [
        format_operational_alert(locale=locale, alert_type="runtime_guard", name="Synthetic platform",
                                 context={"lookback_minutes": 60}, issues=["Synthetic fault"]),
        format_receipt_alert(locale=locale, categories={"strategy_risk_rejected": 1, "skipped_before_due": 7},
                             observed_at=datetime(2026, 1, 2, tzinfo=timezone.utc)),
        render_attention_compact(locale=locale, platform="ibkr", account_alias="",
                                 strategy_profile="synthetic_core",
                                 decision=evaluate_attention(AttentionAxes(operational_uncertain=True))),
    ]
    sections = ("结果", "范围", "证据", "覆盖", "下一步") if locale == "zh" else ("Result", "Scope", "Evidence", "Coverage", "Next step")
    for message in messages:
        positions = [message.index(f"【{section}】" if locale == "zh" else f"[{section}]") for section in sections]
        assert positions == sorted(positions)
        assert "未知" in message if locale == "zh" else "unknown" in message.lower()
        assert "成交：0" not in message and "fills: 0" not in message


@pytest.mark.parametrize("raw", ["https://example.test/run/1?secret=hidden#hidden", "https://example.test/run/1"])
def test_only_supplied_safe_link_path_is_kept(raw):
    assert safe_run_url(raw) == "https://example.test/run/1"


@pytest.mark.parametrize("raw", [None, "gs://private/object", "https://a:b@example.test/run", "https://example.test/\nsecret", "https://[broken"])
def test_invalid_links_are_unavailable(raw):
    assert safe_run_url(raw) is None


def test_budget_keeps_coverage_and_next_step_and_reports_omission():
    text = render_operator_message(title="Synthetic", locale="en", result=["Needs review"], scope=["One run"],
        evidence=["urgent issue", "optional " * 1000], coverage=["Unknown"], next_step=["Review source"], max_units=256)
    assert "urgent issue" in text and "omitted" in text
    assert "[Coverage]\nUnknown" in text and "[Next step]\nReview source" in text
    assert len(text.encode("utf-16-le")) // 2 <= 256
    with pytest.raises(ValueError, match="required_fields_exceed_budget"):
        render_operator_message(title="Synthetic", locale="en", result=["x" * 300], scope=[], evidence=[],
                                coverage=[], next_step=[], max_units=256)


def test_required_diagnostics_survive_before_optional_context():
    text = render_operator_message(title="Synthetic", locale="en", result=["Needs review"], scope=["One run"],
        evidence=["optional " * 1000, "Persistence failed"], coverage=["Unknown"], next_step=["Review source"],
        required_evidence=["Persistence failed"], max_units=256)
    assert "Persistence failed" in text
    assert text.count("Persistence failed") == 1
    assert "omitted" in text


@pytest.mark.parametrize("code", ["blocked_run", "strategy_risk_rejected", "empty_position_decision"])
@pytest.mark.parametrize("locale", ["zh", "en"])
def test_block_cause_codes_have_canonical_explanations(code, locale):
    from quant_platform_kit.common.operational_notification_localization import localize_attention_reason_code
    text = localize_attention_reason_code(locale, code)
    assert text != code
    assert "unknown" not in text.lower()


@pytest.mark.parametrize("locale", ["zh", "en"])
@pytest.mark.parametrize("category", ["skipped_before_due", "skipped_outside_window"])
@pytest.mark.parametrize("count", [3, None])
def test_accepted_receipt_with_routine_skips_needs_no_action(locale, category, count):
    text = format_receipt_alert(locale=locale, categories={"accepted": 1, category: count})
    assert ("无需操作" if locale == "zh" else "No action required") in text
    assert ("已观察到符合要求的回执" if locale == "zh" else "Acceptable receipt observed") in text


@pytest.mark.parametrize("category", ["receipt_missing", "receipt_stale", "blocked_run",
    "strategy_risk_rejected", "receipt_unacceptable", "auth_failure", "unknown_category"])
@pytest.mark.parametrize("count", [1, None])
def test_accepted_receipt_with_real_or_unknown_fault_still_needs_review(category, count):
    text = format_receipt_alert(locale="en", categories={"accepted": 1, category: count})
    assert "Receipt evidence needs review" in text


@pytest.mark.parametrize("accepted", [None, 0])
def test_routine_skips_without_accepted_receipt_still_need_review(accepted):
    text = format_receipt_alert(locale="en", categories={"accepted": accepted, "skipped_before_due": 3})
    assert "Receipt evidence needs review" in text


@pytest.mark.parametrize("required", [False, True])
@pytest.mark.parametrize("message_units", [246, 256])
def test_complete_fitting_message_keeps_diagnostic_without_omission(required, message_units):
    fields = dict(title="Diagnostic", locale="en", result=["Needs review"], scope=["One run"],
                  evidence=["Diagnostic: "], coverage=["Unknown"], next_step=["Review source"])
    empty = render_operator_message(**fields)
    diagnostic = "Diagnostic: " + "x" * (message_units - len(empty.encode("utf-16-le")) // 2)
    fields["evidence"] = [diagnostic]
    if required:
        fields["required_evidence"] = [diagnostic]
    complete = render_operator_message(**fields)
    assert len(complete.encode("utf-16-le")) // 2 == message_units
    assert render_operator_message(**fields, max_units=256) == complete
