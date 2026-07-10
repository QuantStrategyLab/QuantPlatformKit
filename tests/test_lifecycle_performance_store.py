"""Tests for strategy_lifecycle.performance_store defaults."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from quant_platform_kit.strategy_lifecycle.contracts import BacktestResult
from quant_platform_kit.strategy_lifecycle.performance_store import (
    DEFAULT_LOCAL_ROOT,
    PerformanceStore,
)


class PerformanceStoreDefaultsTest(unittest.TestCase):

    def test_default_local_root_uses_platform_lifecycle_name(self) -> None:
        self.assertEqual(
            DEFAULT_LOCAL_ROOT,
            Path(tempfile.gettempdir()) / "quant_platform_lifecycle",
        )

    def test_from_env_uses_default_local_root_without_override(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            store = PerformanceStore.from_env()
        self.assertEqual(store.local_root, DEFAULT_LOCAL_ROOT)

    def test_cloud_backtest_storage_uses_uri_object_store_contract(self) -> None:
        class UriObjectStore:
            def __init__(self) -> None:
                self.objects: dict[str, bytes] = {}

            def read_bytes(self, uri: str) -> bytes:
                return self.objects[uri]

            def write_bytes(self, uri: str, data: bytes, content_type: str = "application/octet-stream") -> str:
                self.objects[uri] = data
                return uri

            def list(self, prefix: str) -> list[str]:
                return sorted(uri for uri in self.objects if uri.startswith(prefix))

        with tempfile.TemporaryDirectory() as tmp:
            object_store = UriObjectStore()
            store = PerformanceStore(
                cloud_bucket="lifecycle-bucket",
                cloud_prefix="production",
                local_root=Path(tmp),
            )
            result = BacktestResult(
                strategy_profile="global_etf_rotation",
                domain="us_equity",
                param_set_id="baseline",
                params={},
                param_version=1,
                sharpe_ratio=1.0,
                calmar_ratio=1.0,
                max_drawdown=-0.1,
                cagr=0.2,
                volatility=0.2,
                win_rate=0.55,
            )
            with patch(
                "quant_platform_kit.strategy_lifecycle.performance_store.get_object_store",
                return_value=object_store,
            ):
                store.save_backtest_result(result)
                keys = store._list_cloud_keys("backtest/us_equity/global_etf_rotation/")
                payload = store._read_cloud_json(keys[0])

        self.assertEqual(len(keys), 1)
        self.assertTrue(keys[0].startswith("backtest/us_equity/global_etf_rotation/"))
        self.assertEqual(payload["strategy_profile"], "global_etf_rotation")


if __name__ == "__main__":
    unittest.main()
