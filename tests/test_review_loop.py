import copy
import unittest
from unittest.mock import Mock

from quant_platform_kit.strategy_lifecycle.review_loop import deadman, finish_review


def reviews(verdict="approve", severity="none"):
    return {name: {"verdict": verdict, "severity": severity, "summary": "Synthetic evidence."}
            for name in ("OpenAI", "Anthropic")}


class Store:
    def __init__(self):
        self.state = None
        self.post, self.close, self.notify = Mock(), Mock(), Mock()

    def load(self, identity):
        return copy.deepcopy(self.state)

    def save(self, state):
        self.state = copy.deepcopy(state)


class LoopTests(unittest.TestCase):
    def test_pass_archives_and_closes_without_dot_or_notification(self):
        store, dot = Store(), Mock()
        state = finish_review(reviews(), identity="cycle", store=store, dot=dot)
        self.assertEqual(state["disposition"], "auto_verified")
        store.close.assert_called_once()
        store.notify.assert_not_called()
        dot.submit.assert_not_called()

    def test_flag_submits_once_and_posts_deeper_review_before_owner_notification(self):
        store, dot = Store(), Mock()
        dot.request.return_value = {"synthetic": True}
        dot.submit.return_value = {"id": "task"}
        dot.result.side_effect = [TimeoutError, {"confirmed": True, "severity": "none", "summary": "Confirmed."}]
        first = finish_review(reviews("flag"), identity="cycle", store=store, dot=dot)
        self.assertEqual(first["disposition"], "review_unavailable")
        store.notify.assert_not_called()
        final = finish_review(reviews("flag"), identity="cycle", store=store, dot=dot)
        self.assertEqual(final["disposition"], "confirmed")
        dot.submit.assert_called_once()
        store.notify.assert_called_once()
        store.post.assert_called_once()
        finish_review(reviews("flag"), identity="cycle", store=store, dot=dot)
        dot.submit.assert_called_once()
        store.notify.assert_called_once()

    def test_ambiguous_submit_is_never_repeated(self):
        store, dot = Store(), Mock()
        dot.request.return_value = {}
        dot.submit.side_effect = TimeoutError("private")
        for _ in range(2):
            finish_review(reviews("flag"), identity="cycle", store=store, dot=dot)
        dot.submit.assert_called_once()
        store.notify.assert_not_called()

    def test_severe_consensus_uses_only_existing_pause_once_then_notifies(self):
        store, pause = Store(), Mock(return_value=True)
        for _ in range(2):
            state = finish_review(reviews("flag", "risk_limit"), identity="cycle", store=store,
                                  pause_cycle=pause)
        self.assertEqual(state["pause"], "paused")
        pause.assert_called_once_with("cycle")
        store.notify.assert_called_once()

    def test_absent_pause_reports_gap_without_constructing_an_actuator(self):
        store = Store()
        state = finish_review(reviews("flag", "missing_stale_inputs"), identity="cycle", store=store)
        self.assertEqual(state["pause"], "not_available")
        self.assertIn("owner action", store.notify.call_args.args[0])

    def test_disagreement_is_not_severe_consensus_and_dismissal_closes(self):
        store, dot, pause = Store(), Mock(), Mock()
        values = reviews()
        values["OpenAI"] = reviews("flag", "data_integrity")["OpenAI"]
        dot.request.return_value = {}
        dot.submit.return_value = {"id": "task"}
        dot.result.return_value = {"confirmed": False, "severity": "none", "summary": "Not supported."}
        finish_review(values, identity="cycle", store=store, dot=dot, pause_cycle=pause)
        pause.assert_not_called()
        store.notify.assert_not_called()
        store.close.assert_called_once()

    def test_malformed_or_changed_opinion_never_closes(self):
        store = Store()
        with self.assertRaises(ValueError):
            finish_review({"one": '{"verdict":"flag","verdict":"approve"}'}, identity="cycle", store=store)
        finish_review(reviews("flag"), identity="cycle", store=store)
        with self.assertRaises(ValueError):
            finish_review(reviews(), identity="cycle", store=store)
        store.close.assert_not_called()

    def test_deadman_counts_failures_and_skips_and_resets_on_success(self):
        self.assertTrue(deadman(["failure", "skipped", "missing"]))
        self.assertFalse(deadman(["failure", "success", "failure", "failure"]))
        self.assertFalse(deadman(["unavailable", "failure"]))
        with self.assertRaises(ValueError):
            deadman([], 0)
