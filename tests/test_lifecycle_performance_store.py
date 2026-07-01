"""Tests for strategy_lifecycle.performance_store defaults."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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


if __name__ == "__main__":
    unittest.main()
