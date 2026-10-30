"""Fictional account IDs and synthetic broker reports; no real account data."""
import json
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from quant_platform_kit.common.execution_state import AccountSubmissionError, AccountSubmissionSession, ExecutionMarkerStore
from quant_platform_kit.common.models import OrderIntent


class WatermarkRecoveryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = ExecutionMarkerStore(local_dir=self.tmp.name)
        self.order = OrderIntent(symbol="VOO", side="buy", quantity=2, account_id="U00000001")

    def session(self, clock):
        return AccountSubmissionSession(self.store, broker="ibkr", account_id="U00000001", owner_id="test", profile="test", intent_id="a" * 64, release_id="b" * 64, clock=clock)

    def test_invalid_clock_preserves_report_and_single_submission(self):
        def failing_clock():
            raise RuntimeError("clock unavailable")
        for clock, status, expected in [(failing_clock, "Submitted", "KNOWN_PENDING"), (failing_clock, "mystery", "UNKNOWN"), (lambda: "invalid", "Submitted", "KNOWN_PENDING"), (lambda: "invalid", "mystery", "UNKNOWN")]:
            with self.subTest(expected=expected):
                # Each case uses a fresh journal.
                self.tmp.cleanup()
                self.tmp = tempfile.TemporaryDirectory()
                self.addCleanup(self.tmp.cleanup)
                self.store = ExecutionMarkerStore(local_dir=self.tmp.name)
                session = self.session(clock)
                grant = session.reserve(self.order)
                calls = []
                report = SimpleNamespace(status=status, broker_order_id="one" if status == "Submitted" else None, filled_quantity=0, average_fill_price=None)
                result = session.dispatch(grant, self.order, lambda: calls.append(1) or report, record_observation_watermark=True)
                self.assertIs(result, report)
                self.assertEqual(calls, [1])
                restarted = self.session(clock)
                attempt = restarted.read_state()["attempts"][grant.attempt_id]
                self.assertEqual(attempt["certainty"], expected)
                self.assertIsNone(attempt["observation_recorded_at"])
                with self.assertRaises(AccountSubmissionError):
                    restarted.dispatch(grant, self.order, lambda: calls.append(1) or report)
                self.assertEqual(calls, [1])

    def test_default_dispatch_preserves_two_argument_call(self):
        session = self.session(lambda: "2026-10-30T03:00:00Z")
        grant = session.reserve(self.order)
        report = SimpleNamespace(status="Submitted", broker_order_id="one", filled_quantity=0, average_fill_price=None)
        original = AccountSubmissionSession.record_observation
        calls = []
        def legacy_override(session, grant, report):
            calls.append((grant, report))
            return original(session, grant, report)
        with patch.object(AccountSubmissionSession, "record_observation", legacy_override):
            session.dispatch(grant, self.order, lambda: report)
        self.assertEqual(calls, [(grant, report)])

    def test_backwards_time_drops_watermark_and_replay_rejects_forgery(self):
        session = self.session(lambda: "2026-10-30T03:00:00Z")
        grant = session.reserve(self.order)
        session.dispatch(grant, self.order, lambda: SimpleNamespace(status="Submitted", broker_order_id="one", filled_quantity=0, average_fill_price=None), record_observation_watermark=True)
        partial = SimpleNamespace(status="PartiallyFilled", broker_order_id="one", filled_quantity=1, average_fill_price=100)
        session.record_observation(grant, partial, recorded_at="2026-10-30T02:00:00Z")
        state = session.read_state()
        attempt = state["attempts"][grant.attempt_id]
        self.assertEqual(attempt["filled_quantity"], 1)
        self.assertIsNone(attempt["observation_recorded_at"])
        self.assertEqual(attempt["last_observation_recorded_at"], "2026-10-30T03:00:00Z")
        path = session._location(state["generation"])
        event = json.loads(path.read_text())
        event["data"]["recorded_at"] = "2026-10-30T02:00:00Z"
        event["event_sha256"] = session._event_hash(event)
        path.write_text(json.dumps(event))
        with self.assertRaisesRegex(AccountSubmissionError, "invalid journal observation watermark"):
            session.read_state()
