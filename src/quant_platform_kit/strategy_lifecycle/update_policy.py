"""Safe update policy — auto-approval rules, shadow validation config, cooldowns."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class UpdatePolicy:
    """Policy controlling the safe update lifecycle."""

    # Auto-approval: skip human review when param change is below this threshold
    # and all dimensions improved.
    auto_approve_threshold: float = 0.10

    # Shadow validation
    min_shadow_days: int = 5
    max_shadow_days: int = 10

    # Concurrency control
    max_parallel_updates: int = 2

    # Minimum days between updates to the same strategy
    cooldown_days: int = 7

    # Post-deployment monitoring before auto-rollback is allowed
    rollback_monitoring_days: int = 5

    # Rollback threshold: if sharpe drops by this much post-update, roll back
    rollback_sharpe_decline: float = 0.30

    # Rollback threshold: if max drawdown worsens by this multiplier, roll back
    rollback_drawdown_multiplier: float = 1.30

    def to_dict(self) -> dict[str, Any]:
        return {
            "auto_approve_threshold": self.auto_approve_threshold,
            "min_shadow_days": self.min_shadow_days,
            "max_shadow_days": self.max_shadow_days,
            "max_parallel_updates": self.max_parallel_updates,
            "cooldown_days": self.cooldown_days,
            "rollback_monitoring_days": self.rollback_monitoring_days,
            "rollback_sharpe_decline": self.rollback_sharpe_decline,
            "rollback_drawdown_multiplier": self.rollback_drawdown_multiplier,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> "UpdatePolicy":
        if not data:
            return cls()
        return cls(
            auto_approve_threshold=float(data.get("auto_approve_threshold", 0.10)),
            min_shadow_days=int(data.get("min_shadow_days", 5)),
            max_shadow_days=int(data.get("max_shadow_days", 10)),
            max_parallel_updates=int(data.get("max_parallel_updates", 2)),
            cooldown_days=int(data.get("cooldown_days", 7)),
            rollback_monitoring_days=int(data.get("rollback_monitoring_days", 5)),
            rollback_sharpe_decline=float(data.get("rollback_sharpe_decline", 0.30)),
            rollback_drawdown_multiplier=float(data.get("rollback_drawdown_multiplier", 1.30)),
        )

    @classmethod
    def load_default(cls) -> "UpdatePolicy":
        import json
        import os

        config_path = os.environ.get("UPDATE_POLICY_PATH")
        if config_path:
            try:
                raw = json.loads(open(config_path, encoding="utf-8").read())
                return cls.from_dict(raw.get("safe_update"))
            except Exception:
                pass
        return cls()
