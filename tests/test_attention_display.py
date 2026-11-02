"""Synthetic display evidence; no broker calls or real notifications."""
from datetime import datetime, timezone

import pytest

from quant_platform_kit.risk.attention import AttentionAxes, evaluate_attention, render_attention_compact
from quant_platform_kit.risk.attention_notify import publish_attention_telegram_transition


@pytest.mark.parametrize("platform", ["schwab", "ibkr", "longbridge", "binance", "alpaca", "firstrade", "qmt"])
@pytest.mark.parametrize("locale", ["zh-CN", "en"])
def test_brokers_share_masked_identity_codes_numbers_and_run_evidence(platform, locale):
    decision = evaluate_attention(AttentionAxes(new_risk_prohibited=True))
    original = decision.to_dict()
    sent = []
    result = publish_attention_telegram_transition(
        decision=decision, platform=platform, account_alias="fake-account-42",
        strategy_profile="soxl_soxx_trend_income", locale=locale,
        guard_reason_codes=("DAILY_LOSS_UNKNOWN_FAIL_CLOSED",),
        daily_loss_context={"daily_loss_fact_status": "verified", "daily_loss_usd": 12.5, "max_daily_loss_usd": 100},
        occurred_at=datetime(2026, 11, 2, 14, 0, tzinfo=timezone.utc),
        run_url="https://console.example.invalid/runs/fake-run?token=fake-secret#fragment",
        telegram_sender=lambda **kwargs: sent.append(kwargs) or True,
    )
    text = sent[0]["text"]
    assert result == {"sent": 1, "skipped": 0, "failed": 0}
    assert "••42" in text and "fake-account" not in text
    assert "DAILY_LOSS_UNKNOWN_FAIL_CLOSED" in text
    assert "USD 12.50 / USD 100.00" in text
    assert "2026-11-02 22:00:00 SGT" in text
    assert "https://console.example.invalid/runs/fake-run" in text
    assert "fake-secret" not in text and "fragment" not in text
    assert "确认意图" not in text and "Confirming intent" not in text
    assert sent[0]["alert_key"].endswith("/new_risk_prohibited")
    assert decision.to_dict() == original


@pytest.mark.parametrize("bad", [None, "bad", "2026-11-02T14:00:00", float("nan"), True])
def test_missing_or_invalid_evidence_stays_unknown(bad):
    text = render_attention_compact(
        locale="en", platform="schwab", account_alias="unknown", strategy_profile="fake",
        decision=evaluate_attention(AttentionAxes(new_risk_prohibited=True)),
        occurred_at=bad, run_url="https://fake:fake@example.invalid/run",
        daily_loss_context={"daily_loss_fact_status": "unverified", "daily_loss_usd": 40, "max_daily_loss_usd": bad},
    )
    assert "Account unknown" in text
    assert "Run time: Unknown" in text
    assert "Run link not provided" in text
    assert "Baseline loss / limit: Unknown / Unknown" in text
    assert "USD 40" not in text
    assert "fake:fake" not in text


@pytest.mark.parametrize("url", ["http://example.invalid", "javascript:fake", "https://[", "https://example.invalid/\nfake"])
def test_bad_links_do_not_break_or_inject_message(url):
    text = render_attention_compact(
        locale="en", platform="ibkr", account_alias="fake42", strategy_profile="fake",
        decision=evaluate_attention(AttentionAxes(new_risk_prohibited=True)), run_url=url,
    )
    assert "Run link not provided" in text
    assert url not in text
