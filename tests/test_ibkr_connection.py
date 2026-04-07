from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
import unittest

from quant_platform_kit.ibkr.connection import connect_ib, ensure_event_loop, probe_tcp_endpoint


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

        class FakeConnection:
            def close(self):
                observed["socket_closed"] = True

        def fake_socket_create_connection(address, timeout):
            observed["socket_args"] = (address, timeout)
            return FakeConnection()

        ib = connect_ib(
            "127.0.0.1",
            4001,
            9,
            socket_create_connection=fake_socket_create_connection,
            ib_factory=FakeIB,
        )

        self.assertIsInstance(ib, FakeIB)
        self.assertEqual(observed["args"], ("127.0.0.1", 4001, 9, 20))


    def test_probe_tcp_endpoint_wraps_timeout(self) -> None:
        def fake_socket_create_connection(_address, _timeout):
            raise TimeoutError()

        with self.assertRaisesRegex(TimeoutError, r'TCP preflight timed out for 10\.0\.0\.8:4002'):
            probe_tcp_endpoint(
                '10.0.0.8',
                4002,
                timeout=2.5,
                socket_create_connection=fake_socket_create_connection,
            )

    def test_probe_tcp_endpoint_wraps_os_error(self) -> None:
        def fake_socket_create_connection(_address, _timeout):
            raise OSError('connection refused')

        with self.assertRaisesRegex(ConnectionError, r'TCP preflight failed for 10\.0\.0\.8:4002: connection refused'):
            probe_tcp_endpoint(
                '10.0.0.8',
                4002,
                timeout=2.5,
                socket_create_connection=fake_socket_create_connection,
            )

    def test_connect_ib_runs_tcp_preflight_before_ib_connect(self) -> None:
        observed: dict[str, object] = {}

        class FakeConnection:
            def close(self):
                observed['socket_closed'] = True

        def fake_socket_create_connection(address, timeout):
            observed['socket_args'] = (address, timeout)
            return FakeConnection()

        class FakeIB:
            def connect(self, host, port, clientId, timeout):
                observed['ib_args'] = (host, port, clientId, timeout)

        ib = connect_ib(
            '10.0.0.8',
            4002,
            9,
            timeout=20,
            tcp_preflight_timeout=3.5,
            socket_create_connection=fake_socket_create_connection,
            ib_factory=FakeIB,
        )

        self.assertIsInstance(ib, FakeIB)
        self.assertEqual(observed['socket_args'], (('10.0.0.8', 4002), 3.5))
        self.assertTrue(observed['socket_closed'])
        self.assertEqual(observed['ib_args'], ('10.0.0.8', 4002, 9, 20))


if __name__ == "__main__":
    unittest.main()
