"""Research-only statistics for backtest evidence (RS-01).

This package is **research-only**. It never reads accounts, calls brokers,
places orders, writes risk policy or grants paper/shadow/live authority.
Runtime, execution and notification modules must not import it (enforced by
``tests/test_research_stats_import_boundary.py``).

``sharpe_inference``, ``overfitting`` (PBO/CSCV) and ``cost_stress`` use only the standard library.
``bootstrap`` lazily imports numpy from the optional ``research`` extra
(``pip install 'quant-platform-kit[research]'``).
"""

from __future__ import annotations

from quant_platform_kit.research_stats.backtest_report import (
    BACKTEST_REPORT_SCHEMA_VERSION,
    BacktestReportV1,
    BenchmarkSpec,
    CostModelSpec,
    DataSpec,
    MetricEntry,
    ReportGates,
    TimingSpec,
    TrialSummary,
    UncertaintySpec,
    VetoItem,
    WalkForwardFold,
    WalkForwardSpec,
    load_backtest_report_schema,
)
from quant_platform_kit.research_stats.bootstrap import (
    BootstrapInterval,
    BootstrapResult,
    stationary_bootstrap_ci,
)
from quant_platform_kit.research_stats.cost_stress import (
    CostStressResult,
    CostStressScenario,
    cost_stress_recompute,
)
from quant_platform_kit.research_stats.overfitting import (
    PBO_METRICS,
    probability_of_backtest_overfitting,
)
from quant_platform_kit.research_stats.sharpe_inference import (
    STATUS_COMPUTED,
    STATUS_UNCOMPUTABLE,
    StatResult,
    deflated_sharpe_ratio,
    expected_max_sharpe,
    probabilistic_sharpe_ratio,
)

__all__ = [
    "BACKTEST_REPORT_SCHEMA_VERSION",
    "BacktestReportV1",
    "BenchmarkSpec",
    "BootstrapInterval",
    "BootstrapResult",
    "CostModelSpec",
    "CostStressResult",
    "CostStressScenario",
    "DataSpec",
    "MetricEntry",
    "PBO_METRICS",
    "ReportGates",
    "STATUS_COMPUTED",
    "STATUS_UNCOMPUTABLE",
    "StatResult",
    "TimingSpec",
    "TrialSummary",
    "UncertaintySpec",
    "VetoItem",
    "WalkForwardFold",
    "WalkForwardSpec",
    "cost_stress_recompute",
    "deflated_sharpe_ratio",
    "expected_max_sharpe",
    "load_backtest_report_schema",
    "probabilistic_sharpe_ratio",
    "probability_of_backtest_overfitting",
    "stationary_bootstrap_ci",
]
