"""Synthetic hand-calculated cash, equity and quantity path."""
from quant_platform_kit.common.account_risk_budget import available_new_risk_budget, maximum_risk_quantity
from quant_platform_kit.common.cash_conservation import expected_cash_delta
from quant_platform_kit.strategy_lifecycle.live_equity import cash_flow_adjusted_return


def test_fill_fee_cash_flow_and_budget_quantity():
    # Buy 2 at 100, pay an actual fee of 2, and deposit 100 at period end.
    cash = 1000 + expected_cash_delta(
        [{"side": "buy", "quantity": 2, "price": 100}], [2], [100], [],
    )
    assert cash == 898
    # Mark the two shares at 90: the original floating loss is already in equity.
    equity = cash + 2 * 90
    assert equity == 1078
    assert cash_flow_adjusted_return(1000, equity, net_external_cash_flow=100) == -0.02200000000000002
    snapshot = {"balance": 1100, "equity": equity, "cash": cash, "currency": "USD", "valuation_at": "2026-10-30T00:00:00Z", "source_digest": "sha256:" + "1" * 64, "complete": True}
    budget = available_new_risk_budget(snapshot, currency="USD", floor=1000, reserved=0, cost_buffer=0, risk_fraction=0.005)
    assert budget == 5.5
    assert maximum_risk_quantity(budget=budget, loss_per_unit=2, estimated_fee=1, quantity_step=1) == 2
