import unittest

from quant_platform_kit.binance.account import ensure_asset_available, get_total_balance, manage_usdt_earn_buffer


class FakeClient:
    def __init__(self):
        self.redeem_calls = []
        self.subscribe_calls = []

    def get_asset_balance(self, *, asset):
        values = {
            "USDT": {"free": "80", "locked": "20"},
            "BNB": {"free": "0.1", "locked": "0"},
        }
        return values[asset]

    def get_simple_earn_flexible_product_position(self, *, asset):
        values = {
            "USDT": {"rows": [{"productId": "earn-usdt", "totalAmount": "50"}]},
            "BNB": {"rows": [{"productId": "earn-bnb", "totalAmount": "0.2"}]},
        }
        return values[asset]

    def get_simple_earn_flexible_product_list(self, *, asset):
        return {"rows": [{"productId": f"{asset.lower()}-product"}]}

    def redeem_simple_earn_flexible_product(self, **kwargs):
        self.redeem_calls.append(kwargs)

    def subscribe_simple_earn_flexible_product(self, **kwargs):
        self.subscribe_calls.append(kwargs)


class BinanceAccountTests(unittest.TestCase):
    def test_get_total_balance_combines_spot_and_earn(self):
        client = FakeClient()
        self.assertEqual(get_total_balance(client, "USDT"), 150.0)

    def test_ensure_asset_available_redeems_shortfall(self):
        client = FakeClient()
        redeemed = []
        ok = ensure_asset_available(client, "USDT", 120.0, on_redeem=redeemed.append, sleep_fn=lambda _: None)
        self.assertTrue(ok)
        self.assertEqual(len(client.redeem_calls), 1)
        self.assertAlmostEqual(redeemed[0], 40.04, places=2)

    def test_manage_usdt_earn_buffer_subscribes_excess(self):
        client = FakeClient()
        subscribed = []
        manage_usdt_earn_buffer(client, 60.0, on_subscribe=subscribed.append)
        self.assertEqual(len(client.subscribe_calls), 1)
        self.assertEqual(subscribed, [20.0])


if __name__ == "__main__":
    unittest.main()
