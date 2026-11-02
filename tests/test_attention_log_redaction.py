"""Publisher logs mask synthetic account IDs without changing deduplication."""

import pytest

from quant_platform_kit.risk.attention import (
    attention_transition_key,
    evaluate_attention,
)
from quant_platform_kit.risk.attention_notify import publish_attention_telegram_transition


@pytest.mark.parametrize("failure", ["exception", "false"])
@pytest.mark.parametrize("account", ["fake-account-12345678", "FAKE/ACCOUNT-12345678", "x"])
def test_failure_logs_redact_account_and_preserve_retry_dedup(failure, account):
    decision = evaluate_attention(new_risk_prohibited=True)
    key = attention_transition_key(
        platform="demo", account_alias=account, strategy_profile="demo-strategy",
        level=decision.level, primary_reason=decision.reason_codes[0],
    )
    logs, calls, recorded = [], [], []

    def fail(**kwargs):
        calls.append(kwargs)
        if failure == "exception":
            raise RuntimeError(account)
        return False

    kwargs = dict(
        decision=decision, platform="demo", account_alias=account,
        strategy_profile="demo-strategy", log_message=logs.append,
        record_sent_key=recorded.append,
    )
    result = publish_attention_telegram_transition(**kwargs, telegram_sender=fail)
    assert result == {"sent": 0, "skipped": int(failure == "false"), "failed": int(failure == "exception")}
    assert calls[0]["alert_key"] == key
    assert recorded == []
    assert len(logs) == 1
    assert account not in logs[0]
    assert key.split("/")[2] not in logs[0]
    assert "key=attention/demo/redacted/demo-strategy/action/new_risk_prohibited" in logs[0]
    assert ("error=RuntimeError" if failure == "exception" else "reason=telegram_not_configured_or_false") in logs[0]

    def succeed(**kwargs):
        calls.append(kwargs)
        return True

    # A failed/skipped delivery remains retryable and records the original key.
    assert publish_attention_telegram_transition(**kwargs, telegram_sender=succeed)["sent"] == 1
    assert calls[-1]["alert_key"] == key
    assert recorded == [key]
    # The original key still suppresses the next delivery before invoking sender.
    assert publish_attention_telegram_transition(
        **kwargs, telegram_sender=succeed, already_sent_keys=recorded,
    ) == {"sent": 0, "skipped": 1, "failed": 0}
    assert len(calls) == 2
    assert len(logs) == 1


def test_accounts_with_same_suffix_keep_distinct_dedup_keys():
    recorded, calls = [], []
    for account in ("fake-first-78", "fake-second-78"):
        result = publish_attention_telegram_transition(
            decision=evaluate_attention(new_risk_prohibited=True),
            platform="demo", account_alias=account, strategy_profile="demo-strategy",
            already_sent_keys=recorded, record_sent_key=recorded.append,
            telegram_sender=lambda **kwargs: calls.append(kwargs) or True,
        )
        assert result == {"sent": 1, "skipped": 0, "failed": 0}
    assert len(set(recorded)) == 2
    assert recorded == [call["alert_key"] for call in calls]
