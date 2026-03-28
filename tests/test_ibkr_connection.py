from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
import unittest

from quant_platform_kit.ibkr.connection import connect_ib, ensure_event_loop


class IbkrConnectionTests(unittest.TestCase):
    def test_ensure_event_loop_creates_loop_in_worker_thread(self) -> None:
        def worker():
            with self.assertRaises(RuntimeError):
                asyncio.get_event_loop_policy().get_event_loop()

            loop = ensure_event_loop()
            current = asyncio.get_event_loop_policy().get_event_loop()
            return loop, current

        with ThreadPoolExecutor(max_workers=1) as executor:
            loop, current = executor.submit(worker).result()

        self.assertIs(loop, current)
        self.assertFalse(loop.is_closed())
        loop.close()

    def test_connect_ib_uses_factory_and_connect_args(self) -> None:
        observed: dict[str, object] = {}

        class FakeIB:
            def connect(self, host, port, clientId, timeout):
                observed["args"] = (host, port, clientId, timeout)

        ib = connect_ib("127.0.0.1", 4001, 9, ib_factory=FakeIB)

        self.assertIsInstance(ib, FakeIB)
        self.assertEqual(observed["args"], ("127.0.0.1", 4001, 9, 20))


if __name__ == "__main__":
    unittest.main()
