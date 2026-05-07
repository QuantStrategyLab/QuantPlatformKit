from __future__ import annotations

import os
import unittest
from decimal import Decimal


def _api_probe_enabled() -> bool:
    return str(os.getenv("LONGBRIDGE_API_PROBE", "")).strip().lower() in {"1", "true", "yes", "on"}


@unittest.skipUnless(
    _api_probe_enabled(),
    "Set LONGBRIDGE_API_PROBE=1 with HK simulated LongPort credentials to run live API probes.",
)
class LongBridgeFractionalOrderApiProbeTests(unittest.TestCase):
    """Manual probe for LongBridge API quantity validation against a simulated account.

    These tests intentionally call the broker API. Keep them skipped in normal CI.
    """

    symbol = os.getenv("LONGBRIDGE_API_PROBE_SYMBOL", "SOXX.US")
    limit_price = Decimal(os.getenv("LONGBRIDGE_API_PROBE_LIMIT_PRICE", "0.01"))

    def setUp(self) -> None:
        try:
            from longport.openapi import Config, TradeContext
        except ImportError as exc:  # pragma: no cover - only relevant outside probe env
            raise unittest.SkipTest("longport is required for API probes") from exc

        missing = [
            name
            for name in ("LONGPORT_APP_KEY", "LONGPORT_APP_SECRET", "LONGPORT_ACCESS_TOKEN")
            if not os.getenv(name)
        ]
        if missing:
            raise unittest.SkipTest(f"Missing LongPort credentials: {', '.join(missing)}")

        config = Config(
            app_key=os.environ["LONGPORT_APP_KEY"],
            app_secret=os.environ["LONGPORT_APP_SECRET"],
            access_token=os.environ["LONGPORT_ACCESS_TOKEN"],
        )
        self.trade_context = TradeContext(config)

    def _submit_limit_buy(self, quantity: Decimal):
        from longport.openapi import OrderSide, OrderType, OutsideRTH, TimeInForceType

        return self.trade_context.submit_order(
            self.symbol,
            OrderType.LO,
            OrderSide.Buy,
            quantity,
            TimeInForceType.Day,
            submitted_price=self.limit_price,
            outside_rth=OutsideRTH.AnyTime,
            remark="qpk-fractional-api-probe",
        )

    def test_sub_one_fractional_order_is_rejected_by_openapi_quantity_validation(self) -> None:
        from longport.openapi import OpenApiException

        with self.assertRaises(OpenApiException) as raised:
            self._submit_limit_buy(Decimal("0.4326"))

        message = str(raised.exception)
        self.assertIn("SubmittedQuantity", message)
        self.assertIn("^([1-9]", message)

    def test_fractional_order_at_or_above_one_share_can_be_submitted_then_cancelled(self) -> None:
        response = self._submit_limit_buy(Decimal("1.5"))
        order_id = str(getattr(response, "order_id", "") or "").strip()
        self.assertTrue(order_id, "LongBridge accepted 1.5 quantity but did not return an order_id")

        try:
            self.trade_context.cancel_order(order_id)
        except Exception as exc:  # pragma: no cover - preserves the original acceptance assertion
            self.fail(f"LongBridge accepted 1.5 quantity but cancel failed for order_id={order_id}: {exc}")


if __name__ == "__main__":
    unittest.main()
