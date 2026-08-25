from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from quant_platform_kit.strategy_lifecycle.contracts import UpdateStage
from quant_platform_kit.strategy_lifecycle.rollback_manager import RollbackManager


def test_rollback_manager_records_only_an_owner_review_proposal() -> None:
    store = object()
    manager = RollbackManager(store=store, policy=object())

    with patch(
        "quant_platform_kit.strategy_lifecycle.rollback_manager.record_audit_entry",
        return_value=SimpleNamespace(entry_id="proposal-123"),
    ) as record_audit_entry:
        result = manager.propose_rollback(
            "soxl_soxx_trend_income",
            domain="us_equity",
            param_version_from=4,
            param_version_to=3,
            params_before={"risk_cap": 0.5},
            params_after={"risk_cap": 0.3},
        )

    assert result["proposal_recorded"] is True
    assert result["rolled_back"] is False
    assert result["rollback_executed"] is False
    assert result["execution_authorized"] is False
    assert result["requires_owner_approval"] is True
    assert result["stage"] == "rollback_proposed"
    assert result["entry_id"] == "proposal-123"
    assert record_audit_entry.call_args.kwargs["stage"] is UpdateStage.ROLLBACK_PROPOSED
    assert record_audit_entry.call_args.kwargs["approval_source"] == "not_authorized"
    assert record_audit_entry.call_args.kwargs["store"] is store


def test_legacy_rollback_alias_preserves_the_no_execution_boundary() -> None:
    manager = RollbackManager(store=object(), policy=object())

    with patch.object(manager, "propose_rollback", return_value={"rollback_executed": False}) as propose:
        result = manager.rollback("tqqq_growth_income", domain="us_equity")

    assert result == {"rollback_executed": False}
    propose.assert_called_once_with("tqqq_growth_income", domain="us_equity")
