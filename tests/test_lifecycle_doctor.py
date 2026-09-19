from datetime import date
from pathlib import Path

from quant_platform_kit.strategy_lifecycle.contracts import StrategyPerformanceSnapshot
from quant_platform_kit.strategy_lifecycle.doctor import doctor_lifecycle
from quant_platform_kit.strategy_lifecycle.performance_store import PerformanceStore


class FixedCollector:
    def __init__(self, profile: str = "strategy"):
        self.profile = profile

    def collect(self, _domain: str):
        return {self.profile: object()}


def _snapshot(**kwargs):
    return StrategyPerformanceSnapshot(
        strategy_profile="strategy",
        domain="us_equity",
        platform="test",
        as_of=date(2026, 9, 19),
        **kwargs,
    )


def test_doctor_rejects_missing_reference_and_incomplete_observation(tmp_path: Path):
    store = PerformanceStore(local_root=tmp_path)
    store.save_snapshot(
        _snapshot(
            observation_status="truncated_after_observation_gap",
            drift_status="not_comparable_annualization",
        )
    )

    result = doctor_lifecycle(
        "us_equity", store=store, collector=FixedCollector(), require_snapshot=True
    )

    assert result["ok"] is False
    assert any("observation status" in issue for issue in result["issues"])
    assert any("annualization" in issue for issue in result["issues"])
    assert any("reference performance window" in issue for issue in result["issues"])


def test_doctor_accepts_complete_snapshot_with_reference_window(tmp_path: Path):
    from quant_platform_kit.strategy_lifecycle.contracts import WindowPerformance

    store = PerformanceStore(local_root=tmp_path)
    window = WindowPerformance(
        window_name="trailing_6m",
        window_days=126,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 6, 30),
        observation_count=126,
        total_return=0.1,
        cagr=0.2,
        volatility=0.1,
        sharpe_ratio=1.0,
        sortino_ratio=1.0,
        calmar_ratio=1.0,
        max_drawdown=-0.05,
        win_rate=0.5,
    )
    store.save_snapshot(_snapshot(windows={126: window}, observation_status="ok"))

    result = doctor_lifecycle(
        "us_equity", store=store, collector=FixedCollector(), require_snapshot=True
    )

    assert result["ok"] is True


def test_doctor_flags_empty_windows_without_requiring_drift(tmp_path: Path):
    store = PerformanceStore(local_root=tmp_path)
    store.save_snapshot(_snapshot(windows={}, observation_status="ok"))

    result = doctor_lifecycle(
        "us_equity",
        store=store,
        collector=FixedCollector(),
        require_snapshot=True,
        require_drift=False,
    )

    assert result["ok"] is False
    assert any("reference performance window" in issue for issue in result["issues"])
    assert not any("missing lifecycle drift" in issue for issue in result["issues"])
