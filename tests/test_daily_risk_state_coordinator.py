import tempfile
import unittest
from unittest.mock import patch

from quant_platform_kit.common.strategy_risk_state import (
    DailyRiskStateBootstrapAuthorization,
    StrategyRiskStateIdentity,
    StrategyRiskStateStore,
    build_strategy_risk_state_transition,
    coordinate_daily_strategy_risk_state,
    read_daily_strategy_risk_state,
)


class DailyRiskStateCoordinatorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = StrategyRiskStateStore(local_dir=self.tmp.name)
        self.identity = StrategyRiskStateIdentity("tqqq_growth_income", "test", "candidate", "a" * 64)
        self.root = build_strategy_risk_state_transition(
            identity=self.identity, effective_session="2026-01-02", input_sha256="b" * 64,
            state={"latch": True, "intent": None},
        )
        self.authorization = DailyRiskStateBootstrapAuthorization(
            self.identity, self.root.effective_session, self.root.input_sha256, self.root.transition_sha256
        )

    def test_missing_bootstrap_and_confirmed_retry(self):
        self.assertEqual(read_daily_strategy_risk_state(self.store, self.identity).status, "missing")
        self.assertEqual(coordinate_daily_strategy_risk_state(self.store, self.root).status, "missing")
        wrong = DailyRiskStateBootstrapAuthorization(self.identity, "2026-01-03", "b" * 64, self.root.transition_sha256)
        self.assertEqual(coordinate_daily_strategy_risk_state(self.store, self.root, bootstrap_authorization=wrong).status, "conflict")
        result = coordinate_daily_strategy_risk_state(self.store, self.root, bootstrap_authorization=self.authorization)
        self.assertEqual(result.status, "confirmed")
        self.assertEqual(result.transition, self.root)
        self.assertEqual(coordinate_daily_strategy_risk_state(self.store, self.root).transition, self.root)
        changed = build_strategy_risk_state_transition(
            identity=self.identity, effective_session="2026-01-02", input_sha256="c" * 64,
            state={"latch": False, "intent": "new"},
        )
        result = coordinate_daily_strategy_risk_state(self.store, changed)
        self.assertEqual(result.status, "conflict")
        self.assertIsNone(result.transition)

    def test_successor_and_faults_never_expose_unconfirmed_state(self):
        coordinate_daily_strategy_risk_state(self.store, self.root, bootstrap_authorization=self.authorization)
        successor = build_strategy_risk_state_transition(
            identity=self.identity, effective_session="2026-01-05", input_sha256="c" * 64,
            state={"latch": False, "intent": None}, previous_transition=self.root,
        )
        with patch.object(StrategyRiskStateStore, "append", side_effect=OSError("write failed")):
            result = coordinate_daily_strategy_risk_state(self.store, successor)
            self.assertEqual(result.status, "unavailable")
            self.assertIsNone(result.transition)
        with patch.object(StrategyRiskStateStore, "load_chain", side_effect=OSError("read failed")):
            self.assertEqual(read_daily_strategy_risk_state(self.store, self.identity).status, "unavailable")
            result = coordinate_daily_strategy_risk_state(self.store, successor)
            self.assertEqual(result.status, "unavailable")
            self.assertIsNone(result.transition)
        with patch.object(StrategyRiskStateStore, "load_chain", side_effect=[(self.root,), OSError("readback failed")]):
            result = coordinate_daily_strategy_risk_state(self.store, successor)
            self.assertEqual(result.status, "unavailable")
            self.assertIsNone(result.transition)
        self.assertEqual(coordinate_daily_strategy_risk_state(self.store, successor).status, "confirmed")
        stale = build_strategy_risk_state_transition(
            identity=self.identity, effective_session="2026-01-06", input_sha256="d" * 64,
            state={"latch": True}, previous_transition=self.root,
        )
        self.assertEqual(coordinate_daily_strategy_risk_state(self.store, stale).status, "conflict")

    def test_competing_successor_at_readback_is_conflict(self):
        coordinate_daily_strategy_risk_state(self.store, self.root, bootstrap_authorization=self.authorization)
        next_state = build_strategy_risk_state_transition(
            identity=self.identity, effective_session="2026-01-05", input_sha256="c" * 64,
            state={"latch": False}, previous_transition=self.root,
        )
        rival = build_strategy_risk_state_transition(
            identity=self.identity, effective_session="2026-01-06", input_sha256="d" * 64,
            state={"latch": True}, previous_transition=next_state,
        )
        with patch.object(StrategyRiskStateStore, "load_chain", side_effect=[(self.root,), (self.root, next_state, rival)]):
            with patch.object(StrategyRiskStateStore, "append"):
                result = coordinate_daily_strategy_risk_state(self.store, next_state)
        self.assertEqual(result.status, "conflict")
        self.assertIsNone(result.transition)


if __name__ == "__main__":
    unittest.main()
