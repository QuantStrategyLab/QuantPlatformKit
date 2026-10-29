import pytest

from quant_platform_kit.common.account_risk_budget import available_new_risk_budget


def test_budget_uses_equity_without_double_counting_floating_loss():
    snapshot = {"balance": 10000, "equity": 9500, "cash": 1000, "currency": "USD", "valuation_at": "2026-10-30T00:00:00Z", "source_digest": "sha256:" + "1" * 64, "complete": True}
    assert available_new_risk_budget(snapshot, currency="USD", floor=9400, reserved=20, cost_buffer=10, risk_fraction=0.005) == 50
    assert available_new_risk_budget(snapshot, currency="USD", floor=9460, reserved=20, cost_buffer=10, risk_fraction=0.005) == 10
    with pytest.raises(ValueError):
        available_new_risk_budget(snapshot, currency="EUR", floor=0, reserved=0, cost_buffer=0, risk_fraction=0.005)


def test_budget_quantity_floors_and_minimum_fee_blocks_small_orders():
    from quant_platform_kit.common.account_risk_budget import maximum_risk_quantity
    assert maximum_risk_quantity(budget=50, loss_per_unit=3, estimated_fee=2, quantity_step=1) == 16
    assert maximum_risk_quantity(budget=2, loss_per_unit=3, estimated_fee=2, quantity_step=1) == 0
