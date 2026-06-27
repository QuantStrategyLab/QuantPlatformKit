#!/usr/bin/env python3
"""Cross-platform fractional / notional DCA execution verification.

Runs broker-boundary payload checks and execution-layer simulations without
live broker credentials. Exit code 0 only when all automated checks pass.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import types
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[2]
QPK_SRC = ROOT / "QuantPlatformKit" / "src"
for path in (str(QPK_SRC),):
    if path not in sys.path:
        sys.path.insert(0, path)


@dataclass
class CheckResult:
    platform: str
    scenario: str
    status: str  # pass | fail | warn | skip
    detail: str
    payload: dict[str, Any] = field(default_factory=dict)


RESULTS: list[CheckResult] = []


def record(platform: str, scenario: str, status: str, detail: str, **payload: Any) -> None:
    RESULTS.append(
        CheckResult(platform=platform, scenario=scenario, status=status, detail=detail, payload=payload)
    )


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def verify_qpk_schwab() -> None:
    import types
    from unittest.mock import patch

    from quant_platform_kit.common.models import OrderIntent
    from quant_platform_kit.schwab.execution import build_equity_dollar_buy_market_order, submit_equity_order

    order = build_equity_dollar_buy_market_order("QQQM", 50.0)
    leg = order["orderLegCollection"][0]
    if leg["quantityType"] != "DOLLARS" or leg["quantity"] != 50.0:
        record("Schwab", "dollar_order_json", "fail", f"unexpected leg: {leg}")
    else:
        record("Schwab", "dollar_order_json", "pass", "quantityType=DOLLARS quantity=50")

    try:
        build_equity_dollar_buy_market_order("QQQM", 0.5)
        record("Schwab", "min_notional_guard", "fail", "expected ValueError for $0.50")
    except ValueError:
        record("Schwab", "min_notional_guard", "pass", "rejects notional below $1")

    captured: dict[str, Any] = {}

    class FakeResponse:
        status_code = 201
        text = ""
        headers = {"Location": "/orders/999"}

    class FakeClient:
        def __init__(self):
            self.last_call = None

        def place_order(self, account_hash, payload):
            self.last_call = (account_hash, payload)
            return FakeResponse()

    buy_client = FakeClient()
    report = submit_equity_order(
        buy_client,
        "hash-1",
        OrderIntent(
            symbol="QQQM",
            side="buy",
            quantity=0,
            order_type="market",
            metadata={"notional_usd": 50.0},
        ),
    )
    captured["order"] = buy_client.last_call[1] if buy_client.last_call else None
    if report.status != "accepted":
        record("Schwab", "submit_notional_path", "fail", f"status={report.status}")
    elif captured.get("order", {}).get("orderLegCollection", [{}])[0].get("quantityType") != "DOLLARS":
        record("Schwab", "submit_notional_path", "fail", "submit path did not use DOLLARS")
    else:
        record("Schwab", "submit_notional_path", "pass", "accepted with DOLLARS payload")

    equities_module = types.ModuleType("schwab.orders.equities")
    equities_module.equity_sell_market = lambda symbol, quantity: ("sell_market", symbol, quantity)
    equities_module.equity_buy_market = lambda symbol, quantity: ("buy_market", symbol, quantity)
    equities_module.equity_buy_limit = lambda symbol, quantity, price: ("buy_limit", symbol, quantity, price)
    with patch.dict(sys.modules, {"schwab.orders.equities": equities_module}):
        sell_client = FakeClient()
        sell_report = submit_equity_order(
            sell_client,
            "hash-1",
            OrderIntent(symbol="QQQM", side="sell", quantity=1, metadata={"notional_usd": 50.0}),
        )
    order_payload = sell_client.last_call[1] if hasattr(sell_client, "last_call") else captured.get("order")
    if isinstance(order_payload, dict) and order_payload.get("orderLegCollection", [{}])[0].get("quantityType") == "DOLLARS":
        record("Schwab", "sell_ignores_notional_metadata", "fail", "sell incorrectly used DOLLARS path")
    elif sell_report.status == "accepted":
        record("Schwab", "sell_ignores_notional_metadata", "pass", "sell uses share-quantity path")
    else:
        record("Schwab", "sell_ignores_notional_metadata", "fail", f"unexpected sell report: {sell_report}")


def verify_qpk_longbridge() -> None:
    from quant_platform_kit.longbridge.execution import submit_order

    longport_module = types.ModuleType("longport")
    openapi_module = types.ModuleType("longport.openapi")
    openapi_module.OrderSide = types.SimpleNamespace(Buy="Buy", Sell="Sell")
    openapi_module.OrderType = types.SimpleNamespace(LO="LO", MO="MO")
    openapi_module.TimeInForceType = types.SimpleNamespace(Day="Day")
    sys.modules["longport"] = longport_module
    sys.modules["longport.openapi"] = openapi_module

    class FakeCtx:
        def __init__(self):
            self.submit_args = None

        def submit_order(self, symbol, order_type, side, quantity, tif, **kwargs):
            self.submit_args = (symbol, order_type, side, quantity, tif, kwargs)
            return types.SimpleNamespace(order_id="LB-1")

    ctx = FakeCtx()
    report = submit_order(
        ctx,
        "QQQM.US",
        order_kind="market",
        side="buy",
        quantity=0.1,
        allow_fractional_shares=True,
        quantity_step=0.0001,
    )
    qty = str(ctx.submit_args[3]) if ctx.submit_args else None
    if report.status != "submitted" or qty != "0.1":
        record("LongBridge", "fractional_market_buy", "fail", f"status={report.status} qty={qty}")
    else:
        record("LongBridge", "fractional_market_buy", "pass", "submitted quantity=0.1")

    blocked = submit_order(
        FakeCtx(),
        "QQQM.US",
        order_kind="market",
        side="buy",
        quantity=0.1,
        allow_fractional_shares=False,
    )
    if blocked.status != "rejected":
        record("LongBridge", "whole_share_gate", "fail", f"expected reject, got {blocked.status}")
    else:
        record("LongBridge", "whole_share_gate", "pass", "blocks sub-share buy without flag")


def verify_qpk_ibkr() -> None:
    from quant_platform_kit.common.models import OrderIntent
    from quant_platform_kit.ibkr.execution import submit_order_intent

    report = submit_order_intent(
        object(),
        OrderIntent(symbol="QQQM", side="buy", quantity=0, metadata={"notional_usd": 50.0}),
        wait_seconds=0,
    )
    if report.status != "rejected" or report.raw_payload.get("skip_reason") != "ibkr_fractional_equity_api_unsupported":
        record("IBKR", "notional_rejected", "fail", f"unexpected report: {report}")
    else:
        record("IBKR", "notional_rejected", "pass", "rejects notional equity at API layer")


def verify_firstrade_execution_layer() -> None:
    platform_root = ROOT / "FirstradePlatform"
    if str(platform_root) not in sys.path:
        sys.path.insert(0, str(platform_root))
    from application.execution_service import execute_value_target_plan

    class FakeQuote:
        def __init__(self, price: float):
            self.last_price = price

    class FakeMarketDataPort:
        def get_quote(self, symbol: str):
            return FakeQuote(500.0)

    class FakeExecutionPort:
        def __init__(self):
            self.orders = []

        def submit_order(self, order_intent):
            self.orders.append(order_intent)
            return types.SimpleNamespace(
                symbol=order_intent.symbol,
                side=order_intent.side,
                quantity=order_intent.metadata.get("notional_usd", order_intent.quantity),
                status="previewed",
                broker_order_id="FT-1",
                raw_payload={"notional": True},
            )

    port = FakeExecutionPort()
    result = execute_value_target_plan(
        plan={
            "allocation": {"targets": {"QQQM": 50.0}},
            "portfolio": {"market_values": {"QQQM": 0.0}, "liquid_cash": 100.0, "sellable_quantities": {}},
            "execution": {"current_min_trade": 1.0, "investable_cash": 100.0},
        },
        market_data_port=FakeMarketDataPort(),
        execution_port=port,
        dry_run_only=True,
        notional_buy_execution=True,
    )
    if not result.action_done or not port.orders:
        record("Firstrade", "dca_notional_intent", "fail", "no order submitted")
        return
    order = port.orders[0]
    notional = order.metadata.get("notional_usd")
    if order.order_type != "market" or notional != 50.0:
        record("Firstrade", "dca_notional_intent", "fail", f"order_type={order.order_type} notional={notional}")
    else:
        record("Firstrade", "dca_notional_intent", "pass", "market buy metadata.notional_usd=50")

    whole_port = FakeExecutionPort()
    whole_result = execute_value_target_plan(
        plan={
            "allocation": {"targets": {"QQQM": 50.0}},
            "portfolio": {"market_values": {"QQQM": 0.0}, "liquid_cash": 100.0, "sellable_quantities": {}},
            "execution": {"current_min_trade": 1.0, "investable_cash": 100.0},
        },
        market_data_port=FakeMarketDataPort(),
        execution_port=whole_port,
        dry_run_only=True,
        notional_buy_execution=False,
    )
    if whole_result.action_done and whole_port.orders and whole_port.orders[0].metadata.get("notional_usd"):
        record("Firstrade", "rotation_no_notional", "fail", "rotation path emitted notional order")
    elif whole_result.action_done and whole_port.orders and int(whole_port.orders[0].quantity or 0) == 0:
        record("Firstrade", "rotation_no_notional", "warn", "whole-share path skipped $50 buy (qty=0 at $500)")
    else:
        record(
            "Firstrade",
            "rotation_no_notional",
            "pass",
            "rotation path uses share qty, not notional metadata",
        )


def _run_subprocess_check(platform: str, platform_dir: Path, script: str) -> None:
    env = dict(**{k: v for k, v in __import__("os").environ.items()})
    env["PYTHONPATH"] = f"{QPK_SRC}:{platform_dir}"
    proc = subprocess.run(
        [sys.executable, "-c", script],
        cwd=str(platform_dir),
        env=env,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "subprocess failed").strip().splitlines()[-1]
        record(platform, "execution_layer", "fail", detail)
        return
    try:
        payload = json.loads(proc.stdout.strip().splitlines()[-1])
    except json.JSONDecodeError:
        record(platform, "execution_layer", "fail", f"bad subprocess output: {proc.stdout!r}")
        return
    for item in payload:
        record(platform, item["scenario"], item["status"], item["detail"])


def verify_longbridge_execution_layer() -> None:
    script = r'''
import json
from application.execution_service import execute_rebalance_cycle
from quant_platform_kit.common.models import ExecutionReport, QuoteSnapshot
from quant_platform_kit.common.port_adapters import CallableExecutionPort, CallableMarketDataPort

captured = []
result = execute_rebalance_cycle(
    trade_context=object(),
    plan={"allocation": {"strategy_symbols": ("QQQM",), "risk_symbols": ("QQQM",), "income_symbols": (), "targets": {"QQQM": 50.0}}},
    portfolio={"market_values": {"QQQM": 0.0}, "quantities": {"QQQM": 0}, "sellable_quantities": {"QQQM": 0}, "liquid_cash": 50.0},
    execution={"trade_threshold_value": 1.0, "current_min_trade": 1.0, "investable_cash": 50.0},
    allocation={"strategy_symbols": ("QQQM",), "risk_symbols": ("QQQM",), "income_symbols": (), "targets": {"QQQM": 50.0}},
    fetch_replanned_state=lambda: (
        {"allocation": {"strategy_symbols": ("QQQM",), "risk_symbols": ("QQQM",), "income_symbols": (), "targets": {"QQQM": 50.0}}},
         {"market_values": {"QQQM": 0.0}, "quantities": {"QQQM": 0}, "sellable_quantities": {"QQQM": 0}, "liquid_cash": 50.0},
         {"trade_threshold_value": 1.0, "current_min_trade": 1.0, "investable_cash": 50.0},
         {"strategy_symbols": ("QQQM",), "risk_symbols": ("QQQM",), "income_symbols": (), "targets": {"QQQM": 50.0}},
    ),
    market_data_port=CallableMarketDataPort(quote_loader=lambda symbol: QuoteSnapshot(symbol=symbol, as_of="2026-06-28", last_price=500.0)),
    estimate_max_purchase_quantity=lambda *_a, **_k: 0.1,
    execution_port=CallableExecutionPort(lambda order_intent: (captured.append(order_intent), ExecutionReport(symbol=order_intent.symbol, side=order_intent.side, quantity=order_intent.quantity, status="accepted", broker_order_id="LB-1"))[-1]),
    notify_issue=lambda *_a, **_k: None,
    translator=lambda key, **kwargs: key,
    with_prefix=lambda message: message,
    fractional_buy_execution=True,
    buy_quantity_step=0.0001,
    min_order_notional_usd=100.0,
    limit_sell_discount=1.0,
    limit_buy_premium=1.0,
)
out = []
if result.action_done and captured and abs(float(captured[0].quantity) - 0.1) < 1e-6 and captured[0].order_type == "market":
    out.append({"scenario": "dca_fractional_qty", "status": "pass", "detail": "market buy quantity=0.1"})
else:
    out.append({"scenario": "dca_fractional_qty", "status": "fail", "detail": f"action_done={result.action_done} captured={captured}"})
out.append({"scenario": "live_api_fractional", "status": "warn", "detail": "decimal qty depends on LongBridge account entitlement; no API fractional flag on submit"})
print(json.dumps(out))
'''
    _run_subprocess_check("LongBridge", ROOT / "LongBridgePlatform", script)


def verify_schwab_execution_layer() -> None:
    script = r'''
import json
from application.execution_service import execute_rebalance_cycle
from quant_platform_kit.common.models import ExecutionReport, QuoteSnapshot
from quant_platform_kit.common.port_adapters import CallableExecutionPort, CallableMarketDataPort

captured = []
plan = {
    "account_hash": "demo",
    "allocation": {"target_mode": "value", "strategy_symbols": ("QQQM",), "risk_symbols": ("QQQM",), "income_symbols": (), "safe_haven_symbols": (), "targets": {"QQQM": 50.0}},
    "portfolio": {"market_values": {"QQQM": 0.0}, "quantities": {"QQQM": 0}, "liquid_cash": 50.0, "cash_sweep_symbol": ""},
    "execution": {"trade_threshold_value": 1.0, "reserved_cash": 0.0},
}
execute_rebalance_cycle(
    client=object(),
    plan=plan,
    portfolio=plan["portfolio"],
    execution=plan["execution"],
    allocation=plan["allocation"],
    fetch_managed_snapshot=lambda _c: None,
    market_data_port=CallableMarketDataPort(quote_loader=lambda symbol: QuoteSnapshot(symbol=symbol, as_of="2026-06-28", last_price=500.0, ask_price=500.0)),
    load_plan=lambda _s: (plan, plan["portfolio"], plan["execution"], plan["allocation"]),
    execution_port=CallableExecutionPort(lambda order_intent: (captured.append(order_intent), ExecutionReport(symbol=order_intent.symbol, side=order_intent.side, quantity=order_intent.quantity, status="accepted", broker_order_id="SCH-1"))[-1]),
    translator=lambda key, **kwargs: key,
    limit_buy_premium=1.0,
    sell_settle_delay_sec=0,
    publish_order_issue=lambda _m: None,
    notional_buy_execution=True,
)
out = []
if captured and captured[0].metadata.get("notional_usd") == 50.0 and captured[0].order_type == "market":
    out.append({"scenario": "dca_notional_intent", "status": "pass", "detail": "metadata.notional_usd=50 market order"})
else:
    out.append({"scenario": "dca_notional_intent", "status": "fail", "detail": f"captured={captured}"})
out.append({"scenario": "live_dollars_order", "status": "warn", "detail": "quantityType=DOLLARS needs paper/live validation"})
print(json.dumps(out))
'''
    _run_subprocess_check("Schwab", ROOT / "CharlesSchwabPlatform", script)


def verify_ibkr_policy() -> None:
    platform_root = ROOT / "InteractiveBrokersPlatform"
    qpk_caps = importlib.import_module("quant_platform_kit.common.execution_capabilities")
    qpk_strategies = importlib.import_module("quant_platform_kit.common.strategies")

    fake_registry = types.ModuleType("strategy_registry")
    fake_registry.PLATFORM_CAPABILITY_MATRIX = qpk_strategies.PlatformCapabilityMatrix(
        platform_id="ibkr",
        supported_domains=frozenset({"us_equity"}),
        supported_target_modes=frozenset({"weight", "value"}),
        supported_inputs=frozenset(),
        supported_capabilities=frozenset({"broker_client"}),
    )
    fake_registry.STRATEGY_CATALOG = qpk_strategies.StrategyCatalog(
        definitions={
            "nasdaq_sp500_smart_dca": qpk_strategies.StrategyDefinition(
                profile="nasdaq_sp500_smart_dca",
                domain="us_equity",
                supported_platforms=frozenset({"ibkr"}),
                compatible_capabilities=frozenset({qpk_caps.FRACTIONAL_SHARE_EXECUTION_CAPABILITY}),
            ),
        }
    )
    sys.modules["strategy_registry"] = fake_registry
    policy = _load_module("ibkr_runtime_execution_policy", platform_root / "runtime_execution_policy.py")
    reason = policy.dca_execution_unsupported_reason("nasdaq_sp500_smart_dca")
    if reason != policy.IBKR_FRACTIONAL_EQUITY_API_UNSUPPORTED_SKIP_REASON:
        record("IBKR", "dca_policy_skip", "fail", f"reason={reason}")
    else:
        record("IBKR", "dca_policy_skip", "pass", "DCA profile blocked with ibkr-specific reason")


def print_report() -> int:
    counts = {"pass": 0, "fail": 0, "warn": 0, "skip": 0}
    print("\n=== Fractional / Notional DCA Verification ===\n")
    current_platform = None
    for item in RESULTS:
        if item.platform != current_platform:
            current_platform = item.platform
            print(f"\n[{current_platform}]")
        counts[item.status] = counts.get(item.status, 0) + 1
        icon = {"pass": "OK", "fail": "FAIL", "warn": "WARN", "skip": "SKIP"}[item.status]
        print(f"  {icon:4} {item.scenario}: {item.detail}")
        if item.payload:
            print(f"       payload={json.dumps(item.payload, default=str)}")

    print(
        f"\nSummary: pass={counts['pass']} fail={counts['fail']} "
        f"warn={counts['warn']} skip={counts.get('skip', 0)}"
    )
    if counts["fail"]:
        print("\nSome automated checks failed — fix before enabling live DCA.")
        return 1
    if counts["warn"]:
        print("\nAutomated checks passed; see WARN items for paper/live validation still required.")
    else:
        print("\nAll automated checks passed.")
    return 0


def main() -> int:
    checks: list[tuple[str, Callable[[], None]]] = [
        ("Schwab QPK", verify_qpk_schwab),
        ("LongBridge QPK", verify_qpk_longbridge),
        ("IBKR QPK", verify_qpk_ibkr),
        ("Firstrade execution", verify_firstrade_execution_layer),
        ("LongBridge execution", verify_longbridge_execution_layer),
        ("Schwab execution", verify_schwab_execution_layer),
        ("IBKR policy", verify_ibkr_policy),
    ]
    for label, fn in checks:
        try:
            fn()
        except Exception as exc:
            record("?", label, "fail", f"exception: {exc}")
    return print_report()


if __name__ == "__main__":
    raise SystemExit(main())
