"""Drift alert builder / publisher tests."""

from __future__ import annotations

from datetime import date
import os
import unittest
from unittest import mock

from quant_platform_kit.strategy_lifecycle.contracts import DriftResult, DriftStatus
from quant_platform_kit.strategy_lifecycle.drift_alerts import (
    build_drift_alert,
    publish_drift_alerts,
)
from quant_platform_kit.strategy_lifecycle.drift_policy import DriftPolicy


def _policy() -> DriftPolicy:
    return DriftPolicy(notification_channels=("telegram",))


def _drift(status: DriftStatus, *, score: float = 0.8) -> DriftResult:
    return DriftResult(
        strategy_profile="soxl_soxx_trend_income",
        domain="us_equity",
        as_of=date(2026, 9, 18),
        drift_score=score,
        status=status,
        escalated=status == DriftStatus.CRITICAL,
        alert_suppressed=False,
        dimensions={},
    )


class DriftAlertTest(unittest.TestCase):
    def test_watch_does_not_build_pageable_alert(self) -> None:
        event = build_drift_alert(_drift(DriftStatus.WATCH), policy=_policy(), locale="zh")
        self.assertIsNone(event)

    def test_review_builds_attention_compact_and_transition_key(self) -> None:
        event = build_drift_alert(
            _drift(DriftStatus.REVIEW),
            policy=_policy(),
            locale="zh-CN",
            platform="ibkr",
            account_alias="U159",
        )
        assert event is not None
        self.assertEqual(event.severity, "warning")
        self.assertIn("管理站", event.body)
        self.assertEqual(
            event.alert_key,
            "attention/ibkr/u159/soxl_soxx_trend_income/action/drift_review",
        )

    def test_publish_telegram_records_only_after_send(self) -> None:
        event = build_drift_alert(
            _drift(DriftStatus.CRITICAL),
            policy=_policy(),
            locale="en",
            platform="ibkr",
        )
        assert event is not None
        recorded: list[str] = []

        def _send(**_kwargs: object) -> bool:
            return True

        counts = publish_drift_alerts(
            [event],
            telegram_sender=_send,
            record_sent_key=recorded.append,
            log_message=lambda *_a, **_k: None,
        )
        self.assertEqual(counts.get("sent"), 1)
        self.assertEqual(recorded, [event.alert_key])

        counts2 = publish_drift_alerts(
            [event],
            already_sent_keys=recorded,
            telegram_sender=_send,
            record_sent_key=recorded.append,
            log_message=lambda *_a, **_k: None,
        )
        self.assertEqual(counts2.get("skipped"), 1)
        self.assertEqual(recorded, [event.alert_key])

    def test_publish_telegram_missing_config_is_skipped_not_silent_pass(self) -> None:
        event = build_drift_alert(_drift(DriftStatus.CRITICAL), policy=_policy(), platform="lb")
        assert event is not None
        logs: list[str] = []
        cleared = {
            key: value
            for key, value in os.environ.items()
            if "TELEGRAM" not in key and "CHAT_ID" not in key
        }
        with mock.patch.dict(os.environ, cleared, clear=True):
            counts = publish_drift_alerts([event], log_message=logs.append)
        self.assertGreaterEqual(counts.get("skipped", 0), 1)
        self.assertTrue(any("telegram_not_configured" in line for line in logs))


if __name__ == "__main__":
    unittest.main()
