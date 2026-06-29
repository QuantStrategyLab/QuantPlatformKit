"""Drift detection thresholds and escalation policy.

Configurable via platform-config.json under the ``monitoring.drift`` section.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class DriftThresholds:
    """Per-dimension drift thresholds."""

    cagr_deviation_pct: float = 0.50
    sharpe_deviation: float = 0.50
    max_drawdown_multiplier: float = 1.5
    volatility_deviation_pct: float = 0.30
    win_rate_deviation_pct: float = 0.20

    def to_dict(self) -> dict[str, float]:
        return {
            "cagr_deviation_pct": self.cagr_deviation_pct,
            "sharpe_deviation": self.sharpe_deviation,
            "max_drawdown_multiplier": self.max_drawdown_multiplier,
            "volatility_deviation_pct": self.volatility_deviation_pct,
            "win_rate_deviation_pct": self.win_rate_deviation_pct,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> "DriftThresholds":
        if not data:
            return cls()
        return cls(
            cagr_deviation_pct=float(data.get("cagr_deviation_pct", 0.50)),
            sharpe_deviation=float(data.get("sharpe_deviation", 0.50)),
            max_drawdown_multiplier=float(data.get("max_drawdown_multiplier", 1.5)),
            volatility_deviation_pct=float(data.get("volatility_deviation_pct", 0.30)),
            win_rate_deviation_pct=float(data.get("win_rate_deviation_pct", 0.20)),
        )


@dataclass(frozen=True)
class EscalationTiers:
    """Score thresholds for each escalation level."""

    watch: float = 0.25
    review: float = 0.50
    critical: float = 0.75

    def to_dict(self) -> dict[str, float]:
        return {"watch": self.watch, "review": self.review, "critical": self.critical}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> "EscalationTiers":
        if not data:
            return cls()
        return cls(
            watch=float(data.get("watch", 0.25)),
            review=float(data.get("review", 0.50)),
            critical=float(data.get("critical", 0.75)),
        )


@dataclass(frozen=True)
class DriftPolicy:
    """Complete drift detection policy."""

    thresholds: DriftThresholds = DriftThresholds()
    escalation: EscalationTiers = EscalationTiers()
    alert_cooldown_hours: int = 24
    max_alerts_per_strategy_per_week: int = 3
    notification_channels: tuple[str, ...] = ("telegram", "email")

    def to_dict(self) -> dict[str, Any]:
        return {
            "thresholds": self.thresholds.to_dict(),
            "escalation": self.escalation.to_dict(),
            "alert_cooldown_hours": self.alert_cooldown_hours,
            "max_alerts_per_strategy_per_week": self.max_alerts_per_strategy_per_week,
            "notification_channels": list(self.notification_channels),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> "DriftPolicy":
        if not data:
            return cls()
        return cls(
            thresholds=DriftThresholds.from_dict(data.get("thresholds")),
            escalation=EscalationTiers.from_dict(data.get("escalation") or data.get("escalation_policy")),
            alert_cooldown_hours=int(data.get("alert_cooldown_hours", 24)),
            max_alerts_per_strategy_per_week=int(data.get("max_alerts_per_strategy_per_week", 3)),
            notification_channels=tuple(
                str(c).strip()
                for c in (data.get("notification_channels") or ["telegram", "email"])
            ),
        )

    @classmethod
    def load_default(cls) -> "DriftPolicy":
        """Load from environment or return sensible defaults."""
        import json
        import os

        config_path = os.environ.get("DRIFT_POLICY_PATH")
        if config_path:
            try:
                raw = json.loads(open(config_path, encoding="utf-8").read())
                return cls.from_dict(raw.get("drift"))
            except Exception:
                pass
        return cls()
