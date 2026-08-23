"""Batch research-only consumption of strategy risk inputs.

This module is intentionally a thin boundary around :mod:`risk.snapshot`.
Strategies publish terminal lifecycle metadata; the consumer never fetches
market data, changes a signal, or creates an execution instruction.  Missing
research evidence is represented as ``DEFERRED`` and invalid risk input is
represented by the existing fail-closed ``PARKED`` snapshot.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .snapshot import RiskSnapshot, build_risk_snapshot


DEFAULT_RESEARCH_STRATEGIES = (
    "soxl",
    "smart_dca",
    "tecl",
    "global_etf",
    "russell",
    "portfolio",
)


@dataclass(frozen=True)
class ResearchRiskObservation:
    """A safe, serializable risk result for one strategy."""

    strategy_id: str
    status: str
    snapshot: RiskSnapshot | None
    reason_codes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "status": self.status,
            "risk_snapshot": None if self.snapshot is None else self.snapshot.to_dict(),
            "reason_codes": list(self.reason_codes),
        }


def consume_research_risk(
    strategy_id: str,
    values: Mapping[str, Any] | None,
) -> ResearchRiskObservation:
    """Consume one terminal research record without execution side effects.

    A record lacking accepted P1/P3 evidence is deferred.  Once evidence is
    present, all numeric and circuit validation remains delegated to the
    canonical ``build_risk_snapshot`` contract.
    """

    identifier = str(strategy_id or "").strip().lower()
    if not identifier:
        return ResearchRiskObservation("unknown", "PARKED", None, ("invalid_strategy_id",))
    if not isinstance(values, Mapping):
        return ResearchRiskObservation(identifier, "DEFERRED", None, ("research_record_missing",))
    lifecycle = str(values.get("lifecycle_status", "")).strip().upper()
    if lifecycle in {"DEFERRED", "PARKED", "QUARANTINED"}:
        return ResearchRiskObservation(identifier, lifecycle, None, ("research_not_ready",))
    if lifecycle not in {"ACCEPTED", "READY", "SUCCESS"}:
        return ResearchRiskObservation(identifier, "DEFERRED", None, ("research_terminal_missing",))
    evidence = values.get("evidence_package_id")
    if not isinstance(evidence, str) or not evidence.strip():
        return ResearchRiskObservation(identifier, "DEFERRED", None, ("evidence_missing",))
    snapshot = build_risk_snapshot(values)
    return ResearchRiskObservation(identifier, snapshot.status, snapshot, snapshot.reason_codes)


def consume_research_risk_batch(
    records: Mapping[str, Mapping[str, Any] | None],
) -> tuple[ResearchRiskObservation, ...]:
    """Consume a deterministic batch for the standard strategy registry."""

    return tuple(
        consume_research_risk(strategy_id, records.get(strategy_id))
        for strategy_id in records
    )


__all__ = [
    "DEFAULT_RESEARCH_STRATEGIES",
    "ResearchRiskObservation",
    "consume_research_risk",
    "consume_research_risk_batch",
]
