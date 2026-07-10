from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from quant_platform_kit.common.strategy_contracts import PositionTarget, StrategyDecision
from quant_platform_kit.strategy_lifecycle.performance_monitor import (
    PerformanceMonitor,
    infer_strategy_domain,
    run_monitor,
    try_record_platform_execution,
)
from quant_platform_kit.strategy_lifecycle.performance_store import PerformanceStore


class PerformanceMonitorTests(unittest.TestCase):
    def test_record_persists_live_run_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = PerformanceStore(local_root=Path(tmp))
            monitor = PerformanceMonitor(store=store)
            decision = StrategyDecision(
                positions=(PositionTarget(symbol="BTCUSDT", target_weight=0.5, role="target"),),
                risk_flags=("risk_gate:passed",),
            )
            result = monitor.record(
                "crypto_live_pool_rotation",
                decision,
                {"filled_orders": 1},
                domain="crypto",
            )
            self.assertTrue(result["ok"])
            files = list(Path(tmp).rglob("live_runs/crypto/crypto_live_pool_rotation/*.json"))
            self.assertEqual(len(files), 1)
            payload = files[0].read_text(encoding="utf-8")
            self.assertIn("BTCUSDT", payload)
            self.assertIn("filled_orders", payload)

    def test_record_execution_persists_execution_only_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = PerformanceStore(local_root=Path(tmp))
            monitor = PerformanceMonitor(store=store)
            result = monitor.record_execution(
                "global_etf_rotation",
                {"orders_filled": ["VOO"], "status": "ok"},
                domain="us_equity",
            )
            self.assertTrue(result["ok"])
            files = list(Path(tmp).rglob("live_runs/us_equity/global_etf_rotation/*.json"))
            self.assertEqual(len(files), 1)
            payload = files[0].read_text(encoding="utf-8")
            self.assertIn("record_kind", payload)
            self.assertIn("orders_filled", payload)

    def test_infer_strategy_domain_from_profile_prefix(self) -> None:
        self.assertEqual(infer_strategy_domain("cn_index_etf_tactical_rotation"), "cn_equity")
        self.assertEqual(infer_strategy_domain("hk_global_etf_tactical_rotation"), "hk_equity")
        self.assertEqual(infer_strategy_domain("crypto_live_pool_rotation"), "crypto")
        self.assertEqual(infer_strategy_domain("global_etf_rotation"), "us_equity")

    def test_try_record_platform_execution_swallows_errors(self) -> None:
        try_record_platform_execution("", {"status": "ok"})

    def test_run_monitor_fails_closed_when_no_profiles_found(self) -> None:
        class EmptyCollector:
            def collect(self, _domain: str) -> dict[str, pd.Series]:
                return {}

        with self.assertRaisesRegex(RuntimeError, "No strategy return series found"):
            run_monitor("us_equity", collector=EmptyCollector())


if __name__ == "__main__":
    unittest.main()
