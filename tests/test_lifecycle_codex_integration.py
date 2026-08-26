import json
import sys
from datetime import date
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch

from quant_platform_kit.strategy_lifecycle.codex_integration import (
    AutoIssueConfig,
    _process_optimization_decision,
    _run_drift_phase,
    create_github_issue,
)
from quant_platform_kit.strategy_lifecycle.contracts import DriftResult, DriftStatus


def test_drift_phase_excludes_suppressed_results_from_automation() -> None:
    suppressed = DriftResult(
        strategy_profile="missing-baseline",
        domain="us_equity",
        as_of=date(2026, 7, 11),
        drift_score=0.0,
        status=DriftStatus.REVIEW,
        alert_suppressed=True,
        baseline_available=False,
    )
    critical = DriftResult(
        strategy_profile="active-baseline",
        domain="us_equity",
        as_of=date(2026, 7, 11),
        drift_score=0.8,
        status=DriftStatus.CRITICAL,
    )

    with patch(
        "quant_platform_kit.strategy_lifecycle.drift_detector.run_drift_detection",
        return_value=[suppressed, critical],
    ):
        drifts, alerts = _run_drift_phase("us_equity", Mock())

    assert drifts == [suppressed, critical]
    assert alerts == [critical]


def test_create_github_issue_reuses_matching_open_issue() -> None:
    drift = DriftResult(
        strategy_profile="us-core",
        domain="us_equity",
        as_of=date(2026, 8, 20),
        drift_score=0.8,
        status=DriftStatus.CRITICAL,
    )
    title = "[us_equity] Drift CRITICAL: us-core (score=0.80)"
    existing_issue = {
        "number": 42,
        "title": title,
        "url": "https://github.com/QuantStrategyLab/UsEquityStrategies/issues/42",
    }
    with patch(
        "quant_platform_kit.strategy_lifecycle.codex_integration.subprocess.run",
        return_value=Mock(returncode=0, stdout=json.dumps([existing_issue]), stderr=""),
    ) as run:
        result = create_github_issue(
            drift,
            config=AutoIssueConfig(owner="QuantStrategyLab", repo="UsEquityStrategies"),
        )

    assert result["issue_url"] == existing_issue["url"]
    assert result["issue_number"] == 42
    assert result["deduplicated"] is True
    assert run.call_count == 1
    assert run.call_args.args[0][:3] == ["gh", "issue", "list"]


def test_automated_review_prepares_human_decision_without_update_or_deployment() -> None:
    drift = DriftResult(
        strategy_profile="soxl_soxx_trend_income",
        domain="us_equity",
        as_of=date(2026, 8, 27),
        drift_score=0.8,
        status=DriftStatus.CRITICAL,
    )
    proposal = SimpleNamespace(
        recommendation="promote",
        improvement_score=0.12,
    )
    verdict = SimpleNamespace(
        verdict="approve",
        to_dict=lambda: {"verdict": "approve", "requires_human": True},
    )
    store = Mock()
    store.load_latest_snapshot.return_value = None

    optimizer_module = ModuleType("quant_platform_kit.strategy_lifecycle.param_optimizer")
    optimizer_module.run_optimization = Mock(return_value=proposal)
    reviewer_module = ModuleType("quant_platform_kit.strategy_lifecycle.ai_reviewer")
    reviewer_module.review_proposal = Mock(return_value=verdict)
    reviewer_module.llm_enhanced_review = Mock()

    with (
        patch(
            "quant_platform_kit.strategy_lifecycle.codex_integration.call_ai_optimization_decision",
            return_value={"optimization_needed": True, "recommended_method": "grid_search"},
        ),
        patch.dict(
            sys.modules,
            {
                "quant_platform_kit.strategy_lifecycle.param_optimizer": optimizer_module,
                "quant_platform_kit.strategy_lifecycle.ai_reviewer": reviewer_module,
            },
        ),
    ):
        result = _process_optimization_decision(drift, store, dry_run=False)

    assert result["execution_authorized"] is False
    assert result["requires_human_approval"] is True
    assert "update_result" not in result
