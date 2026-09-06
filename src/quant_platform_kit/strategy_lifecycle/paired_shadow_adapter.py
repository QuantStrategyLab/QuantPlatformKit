"""Non-live paired-shadow observation adapter for research promotion.

Platforms supply same-timestamp baseline/candidate legs. This adapter only
assembles ``paired_shadow_evidence.v1`` and a promotion shadow record. It never
places orders, opens broker sessions, or grants live authority.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from quant_platform_kit.strategy_lifecycle.forward_observation import (
    ForwardObservationPolicy,
)
from quant_platform_kit.strategy_lifecycle.paired_shadow_evidence import (
    build_paired_shadow_evidence,
)
from quant_platform_kit.strategy_lifecycle.research_promotion_cycle import (
    shadow_record_from_paired_evidence,
)


@dataclass(frozen=True)
class PairedShadowObservation:
    """One same-input baseline/candidate observation from a non-live adapter."""

    policy: ForwardObservationPolicy
    forward_observation_receipt: Mapping[str, Any]
    baseline_id: str
    observed_at: str
    input_snapshot_sha256: str
    candidate: Mapping[str, Any]
    baseline: Mapping[str, Any]
    previous_evidence: Mapping[str, Any] | None = None
    previous_forward_observation_receipt: Mapping[str, Any] | None = None


PairedShadowCollector = Callable[..., PairedShadowObservation | Mapping[str, Any] | None]


def collect_paired_shadow_for_promotion(
    observation: PairedShadowObservation | Mapping[str, Any],
) -> dict[str, Any]:
    """Build validated paired-shadow evidence and a promotion shadow record."""
    if isinstance(observation, PairedShadowObservation):
        payload = {
            "policy": observation.policy,
            "forward_observation_receipt": observation.forward_observation_receipt,
            "baseline_id": observation.baseline_id,
            "observed_at": observation.observed_at,
            "input_snapshot_sha256": observation.input_snapshot_sha256,
            "candidate": observation.candidate,
            "baseline": observation.baseline,
            "previous_evidence": observation.previous_evidence,
            "previous_forward_observation_receipt": (
                observation.previous_forward_observation_receipt
            ),
        }
    else:
        payload = dict(observation)

    evidence = build_paired_shadow_evidence(
        policy=payload["policy"],
        forward_observation_receipt=payload["forward_observation_receipt"],
        baseline_id=str(payload["baseline_id"]),
        observed_at=str(payload["observed_at"]),
        input_snapshot_sha256=str(payload["input_snapshot_sha256"]),
        candidate=dict(payload["candidate"]),
        baseline=dict(payload["baseline"]),
        previous_evidence=payload.get("previous_evidence"),
        previous_forward_observation_receipt=payload.get(
            "previous_forward_observation_receipt"
        ),
    )
    if evidence.get("live_authority_granted") is True:
        raise ValueError("paired shadow adapter refused live_authority_granted=true")
    if evidence.get("no_order") is not True:
        raise ValueError("paired shadow adapter requires no_order=true")

    record = shadow_record_from_paired_evidence(
        evidence,
        policy=payload["policy"],
        forward_observation_receipt=payload["forward_observation_receipt"],
    )
    record["adapter"] = "paired_shadow_adapter.v1"
    record["live_authority_granted"] = False
    return record


def resolve_promotion_shadow_record(
    *,
    proposal: Any,
    drift: Any | None = None,
    collector: PairedShadowCollector | None = None,
    allow_proxy_fallback: bool = True,
) -> dict[str, Any]:
    """Prefer paired-shadow evidence; optionally fall back to explicit proxy.

    Proxy fallback is marked ``proxy_shadow_pending_paired`` and never implies
    live authority. When ``allow_proxy_fallback`` is False and no paired
    observation is available, returns a failing shadow record so the cycle parks.
    """
    observation = None
    if collector is not None:
        observation = collector(proposal=proposal, drift=drift)

    if observation is not None:
        return collect_paired_shadow_for_promotion(observation)

    if allow_proxy_fallback:
        return {
            "evidence_kind": "proxy_shadow_pending_paired",
            "passed": True,
            "live_authority_granted": False,
            "no_order": True,
            "adapter": "paired_shadow_adapter.v1",
            "notes": ("paired_observation_unavailable_used_proxy",),
        }

    return {
        "evidence_kind": "paired_shadow_missing",
        "passed": False,
        "live_authority_granted": False,
        "no_order": True,
        "adapter": "paired_shadow_adapter.v1",
        "notes": ("paired_observation_required",),
    }


__all__ = [
    "PairedShadowCollector",
    "PairedShadowObservation",
    "collect_paired_shadow_for_promotion",
    "resolve_promotion_shadow_record",
]
