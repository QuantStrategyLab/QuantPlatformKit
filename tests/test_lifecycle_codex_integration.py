from datetime import date
from unittest.mock import Mock, patch

from quant_platform_kit.strategy_lifecycle.codex_integration import _run_drift_phase
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
