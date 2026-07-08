from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from quant_platform_kit.common.strategy_contracts import PositionTarget, StrategyDecision
from quant_platform_kit.strategy_lifecycle.performance_monitor import PerformanceMonitor
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


if __name__ == "__main__":
    unittest.main()
