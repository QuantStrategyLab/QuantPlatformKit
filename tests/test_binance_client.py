import unittest

from quant_platform_kit.binance.client import connect_client


class FakeClient:
    def __init__(self, api_key, api_secret, options):
        self.api_key = api_key
        self.api_secret = api_secret
        self.options = options
        self.ping_called = False

    def ping(self):
        self.ping_called = True


class BinanceClientTests(unittest.TestCase):
    def test_connect_client_builds_and_pings_client(self):
        client = connect_client("api", "secret", timeout=12, client_factory=FakeClient)
        self.assertEqual(client.api_key, "api")
        self.assertEqual(client.api_secret, "secret")
        self.assertEqual(client.options, {"timeout": 12})
        self.assertTrue(client.ping_called)


if __name__ == "__main__":
    unittest.main()
