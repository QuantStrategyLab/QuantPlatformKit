import unittest

from quant_platform_kit.binance.execution import format_qty


class ClientWithSymbolInfo:
    def get_symbol_info(self, symbol):
        return {
            "filters": [
                {"filterType": "LOT_SIZE", "stepSize": "0.00100000"},
            ]
        }


class ClientWithoutSymbolInfo:
    def get_symbol_info(self, symbol):
        raise RuntimeError("boom")


class BinanceExecutionTests(unittest.TestCase):
    def test_format_qty_respects_step_size(self):
        self.assertEqual(format_qty(ClientWithSymbolInfo(), "ETHUSDT", 1.23456), 1.234)

    def test_format_qty_falls_back_to_four_decimals(self):
        self.assertEqual(format_qty(ClientWithoutSymbolInfo(), "ETHUSDT", 1.23456), 1.2345)


if __name__ == "__main__":
    unittest.main()
