from __future__ import annotations

import os
import unittest
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from unittest.mock import patch
from uuid import uuid4


PROBE_ENV = "LONGBRIDGE_ORDER_API_PROBE"


@dataclass(frozen=True)
class ProbeCase:
    symbol: str
    side: str
    kind: str
    quantity: Decimal
    expect: str
    price: Decimal | None = None
    outside_rth: str | None = None
    error_contains: str | None = None


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise AssertionError(f"{name} is required when {PROBE_ENV}=1")
    return value


def _split_csv(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def _parse_decimal(value: str, *, field_name: str) -> Decimal:
    try:
        return Decimal(value)
    except InvalidOperation as exc:
        raise AssertionError(f"{field_name} must be a decimal value; got {value!r}") from exc


def _parse_key_value_case(raw_case: str) -> ProbeCase:
    fields: dict[str, str] = {}
    for raw_part in raw_case.split(","):
        part = raw_part.strip()
        if not part:
            continue
        key, sep, value = part.partition("=")
        if not sep:
            raise AssertionError(f"Probe case part must be key=value; got {part!r}")
        fields[key.strip().lower()] = value.strip()

    symbol = fields.get("symbol", "")
    side = fields.get("side", "").lower()
    kind = fields.get("kind", "").lower()
    expect = fields.get("expect", "").lower()
    quantity_text = fields.get("quantity", "")
    price_text = fields.get("price")

    if not symbol:
        raise AssertionError(f"Probe case is missing symbol: {raw_case!r}")
    if side not in {"buy", "sell"}:
        raise AssertionError(f"Probe side must be buy or sell; got {side!r}")
    if kind not in {"limit", "market"}:
        raise AssertionError(f"Probe kind must be limit or market; got {kind!r}")
    if expect not in {"accepted", "rejected"}:
        raise AssertionError(f"Probe expect must be accepted or rejected; got {expect!r}")
    if not quantity_text:
        raise AssertionError(f"Probe case is missing quantity: {raw_case!r}")
    if kind == "limit" and not price_text:
        raise AssertionError(f"Limit probe case requires price: {raw_case!r}")

    return ProbeCase(
        symbol=symbol,
        side=side,
        kind=kind,
        quantity=_parse_decimal(quantity_text, field_name="quantity"),
        expect=expect,
        price=_parse_decimal(price_text, field_name="price") if price_text else None,
        outside_rth=fields.get("outside_rth"),
        error_contains=fields.get("error_contains"),
    )


def _parse_probe_cases() -> list[ProbeCase]:
    raw_cases = os.getenv("LONGBRIDGE_ORDER_API_PROBE_CASES", "").strip()
    if raw_cases:
        return [_parse_key_value_case(raw_case) for raw_case in raw_cases.split(";") if raw_case.strip()]

    symbols = _split_csv(_required_env("LONGBRIDGE_ORDER_API_PROBE_SYMBOLS"))
    side = _required_env("LONGBRIDGE_ORDER_API_PROBE_SIDE").lower()
    kind = _required_env("LONGBRIDGE_ORDER_API_PROBE_KIND").lower()
    expect = _required_env("LONGBRIDGE_ORDER_API_PROBE_EXPECT").lower()
    quantity = _parse_decimal(_required_env("LONGBRIDGE_ORDER_API_PROBE_QUANTITY"), field_name="quantity")
    price = os.getenv("LONGBRIDGE_ORDER_API_PROBE_LIMIT_PRICE", "").strip()
    outside_rth = os.getenv("LONGBRIDGE_ORDER_API_PROBE_OUTSIDE_RTH", "").strip() or None
    error_contains = os.getenv("LONGBRIDGE_ORDER_API_PROBE_ERROR_CONTAINS", "").strip() or None

    if side not in {"buy", "sell"}:
        raise AssertionError(f"LONGBRIDGE_ORDER_API_PROBE_SIDE must be buy or sell; got {side!r}")
    if kind not in {"limit", "market"}:
        raise AssertionError(f"LONGBRIDGE_ORDER_API_PROBE_KIND must be limit or market; got {kind!r}")
    if expect not in {"accepted", "rejected"}:
        raise AssertionError(f"LONGBRIDGE_ORDER_API_PROBE_EXPECT must be accepted or rejected; got {expect!r}")
    if kind == "limit" and not price:
        raise AssertionError("LONGBRIDGE_ORDER_API_PROBE_LIMIT_PRICE is required for limit probes")

    return [
        ProbeCase(
            symbol=symbol,
            side=side,
            kind=kind,
            quantity=quantity,
            expect=expect,
            price=_parse_decimal(price, field_name="limit_price") if price else None,
            outside_rth=outside_rth,
            error_contains=error_contains,
        )
        for symbol in symbols
    ]


def _order_side(openapi_module, side: str):
    if side == "buy":
        return openapi_module.OrderSide.Buy
    if side == "sell":
        return openapi_module.OrderSide.Sell
    raise AssertionError(f"Unsupported side: {side}")


def _order_type(openapi_module, kind: str):
    if kind == "limit":
        return openapi_module.OrderType.LO
    if kind == "market":
        return openapi_module.OrderType.MO
    raise AssertionError(f"Unsupported order kind: {kind}")


def _outside_rth(openapi_module, value: str | None):
    normalized = (value or os.getenv("LONGBRIDGE_ORDER_API_PROBE_OUTSIDE_RTH", "anytime")).strip().lower()
    if normalized in {"", "none"}:
        return None
    if normalized in {"anytime", "any_time", "any-time"}:
        return openapi_module.OutsideRTH.AnyTime
    if normalized in {"rth", "rth_only", "rth-only"}:
        return openapi_module.OutsideRTH.RTHOnly
    if normalized == "overnight":
        return openapi_module.OutsideRTH.Overnight
    raise AssertionError(f"Unsupported outside_rth value: {value!r}")


class LongBridgeOrderQuantityApiProbeConfigTests(unittest.TestCase):
    def test_parse_key_value_cases_supports_multiple_symbols_and_prices(self) -> None:
        raw_cases = (
            "symbol=SOXL.US,side=buy,kind=limit,quantity=1.5,price=120,expect=rejected;"
            "symbol=BOXX.US,side=sell,kind=limit,quantity=4.6177,price=130,expect=accepted"
        )

        with patch.dict(os.environ, {"LONGBRIDGE_ORDER_API_PROBE_CASES": raw_cases}, clear=True):
            cases = _parse_probe_cases()

        self.assertEqual([case.symbol for case in cases], ["SOXL.US", "BOXX.US"])
        self.assertEqual([case.side for case in cases], ["buy", "sell"])
        self.assertEqual([case.kind for case in cases], ["limit", "limit"])
        self.assertEqual([case.quantity for case in cases], [Decimal("1.5"), Decimal("4.6177")])
        self.assertEqual([case.price for case in cases], [Decimal("120"), Decimal("130")])
        self.assertEqual([case.expect for case in cases], ["rejected", "accepted"])

    def test_parse_symbol_list_expands_one_case_per_symbol(self) -> None:
        env = {
            "LONGBRIDGE_ORDER_API_PROBE_SYMBOLS": "SOXL.US, SOXX.US, BOXX.US",
            "LONGBRIDGE_ORDER_API_PROBE_SIDE": "buy",
            "LONGBRIDGE_ORDER_API_PROBE_KIND": "limit",
            "LONGBRIDGE_ORDER_API_PROBE_EXPECT": "rejected",
            "LONGBRIDGE_ORDER_API_PROBE_QUANTITY": "0.4326",
            "LONGBRIDGE_ORDER_API_PROBE_LIMIT_PRICE": "1",
            "LONGBRIDGE_ORDER_API_PROBE_OUTSIDE_RTH": "anytime",
        }

        with patch.dict(os.environ, env, clear=True):
            cases = _parse_probe_cases()

        self.assertEqual([case.symbol for case in cases], ["SOXL.US", "SOXX.US", "BOXX.US"])
        self.assertTrue(all(case.quantity == Decimal("0.4326") for case in cases))
        self.assertTrue(all(case.price == Decimal("1") for case in cases))
        self.assertTrue(all(case.outside_rth == "anytime" for case in cases))

    def test_limit_symbol_list_requires_price(self) -> None:
        env = {
            "LONGBRIDGE_ORDER_API_PROBE_SYMBOLS": "SOXL.US",
            "LONGBRIDGE_ORDER_API_PROBE_SIDE": "buy",
            "LONGBRIDGE_ORDER_API_PROBE_KIND": "limit",
            "LONGBRIDGE_ORDER_API_PROBE_EXPECT": "rejected",
            "LONGBRIDGE_ORDER_API_PROBE_QUANTITY": "0.4326",
        }

        with patch.dict(os.environ, env, clear=True):
            with self.assertRaisesRegex(AssertionError, "LIMIT_PRICE is required"):
                _parse_probe_cases()


@unittest.skipUnless(os.getenv(PROBE_ENV) == "1", f"set {PROBE_ENV}=1 to run LongBridge API order probes")
class LongBridgeOrderQuantityApiProbeTests(unittest.TestCase):
    def test_configured_order_quantity_cases(self) -> None:
        from longport import OpenApiException
        from longport.openapi import Config, TradeContext
        import longport.openapi as openapi

        app_key = _required_env("LONGPORT_APP_KEY")
        app_secret = _required_env("LONGPORT_APP_SECRET")
        access_token = _required_env("LONGPORT_ACCESS_TOKEN")
        cases = _parse_probe_cases()
        self.assertTrue(cases, "at least one LongBridge order probe case is required")

        ctx = TradeContext(Config(app_key=app_key, app_secret=app_secret, access_token=access_token))
        for case in cases:
            with self.subTest(case=case):
                if case.kind == "market" and os.getenv("LONGBRIDGE_ORDER_API_PROBE_ALLOW_MARKET") != "1":
                    self.fail("Market probes can fill immediately; set LONGBRIDGE_ORDER_API_PROBE_ALLOW_MARKET=1")

                kwargs = {"remark": f"qpk-order-quantity-probe-{uuid4().hex[:8]}"}
                if case.kind == "limit":
                    kwargs["submitted_price"] = case.price
                    kwargs["outside_rth"] = _outside_rth(openapi, case.outside_rth)

                try:
                    response = ctx.submit_order(
                        case.symbol,
                        _order_type(openapi, case.kind),
                        _order_side(openapi, case.side),
                        case.quantity,
                        openapi.TimeInForceType.Day,
                        **kwargs,
                    )
                except OpenApiException as exc:
                    if case.expect == "rejected":
                        if case.error_contains and case.error_contains not in str(exc):
                            self.fail(
                                f"LongBridge rejected {case}, but error did not contain "
                                f"{case.error_contains!r}: {exc}"
                            )
                        continue
                    self.fail(f"LongBridge rejected {case}, expected accepted: {exc}")

                order_id = str(getattr(response, "order_id", "") or "")
                if case.expect == "rejected":
                    if order_id:
                        self._cancel_order(ctx, order_id, required=False)
                    self.fail(f"LongBridge accepted {case}, expected rejected; order_id={order_id}")

                self.assertTrue(order_id, f"LongBridge accepted {case} but returned no order_id")
                if case.kind == "limit" or os.getenv("LONGBRIDGE_ORDER_API_PROBE_CANCEL_MARKET") == "1":
                    self._cancel_order(ctx, order_id, required=case.kind == "limit")

    def _cancel_order(self, ctx, order_id: str, *, required: bool) -> None:
        try:
            ctx.cancel_order(order_id)
        except Exception as exc:
            if required:
                raise AssertionError(f"failed to cancel accepted probe order {order_id}: {exc}") from exc


if __name__ == "__main__":
    unittest.main()
