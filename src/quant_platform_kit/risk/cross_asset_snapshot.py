"""Cross-asset daily risk observation envelope.

This is a research/shadow aggregation contract only.  It deliberately does
not produce target weights, order intents, or broker instructions.
"""

from __future__ import annotations

from typing import Any, Mapping

from quant_platform_kit.risk.snapshot import RiskSnapshot


def build_cross_asset_snapshot(
    snapshots: Mapping[str, RiskSnapshot],
    *,
    as_of: str,
    run_mode: str = "research_active",
) -> dict[str, Any]:
    """Build a deterministic CN/HK/US/Crypto daily observation envelope.

    Individual asset snapshots retain their own provenance and expiry.  The
    envelope reports partial readiness instead of treating missing assets as
    zero risk.  ``no_order`` is fixed true by contract.
    """
    if not isinstance(as_of, str) or not as_of.strip():
        raise ValueError("as_of is required")
    if run_mode not in {"research_active", "shadow_active"}:
        raise ValueError("run_mode must be research_active or shadow_active")
    if not isinstance(snapshots, Mapping) or not snapshots:
        raise ValueError("at least one asset snapshot is required")
    if any(not isinstance(asset, str) or not asset.strip() for asset in snapshots):
        raise ValueError("asset keys must be non-empty strings")
    if any(not isinstance(snapshot, RiskSnapshot) for snapshot in snapshots.values()):
        raise ValueError("snapshots must contain RiskSnapshot values")

    ready = {asset: snapshot for asset, snapshot in snapshots.items() if snapshot.is_usable}
    parked = sorted(asset for asset, snapshot in snapshots.items() if not snapshot.is_usable)
    return {
        "contract_version": "cross_asset_risk_snapshot.v1",
        "as_of": as_of.strip(),
        "run_mode": run_mode,
        "no_order": True,
        "status": "READY" if len(ready) == len(snapshots) else "PARTIAL",
        "asset_count": len(snapshots),
        "ready_asset_count": len(ready),
        "parked_assets": parked,
        "effective_exposure": sum(snapshot.effective_exposure for snapshot in ready.values()),
        "max_loss_estimate": sum(snapshot.max_loss_estimate for snapshot in ready.values()),
        "assets": {asset: snapshot.to_dict() for asset, snapshot in sorted(snapshots.items())},
    }
