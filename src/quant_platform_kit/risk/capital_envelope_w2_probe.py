"""W2 read-only capital envelope + account gate probe (no broker / no network).

Stdlib CLI for synthetic equity / peak / vol inputs. Does not grant live authority
or enable accounts.
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict
from typing import Any, Sequence

from quant_platform_kit.risk.account_new_risk_gate import (
    evaluate_new_risk_admission,
)
from quant_platform_kit.risk.capital_risk_envelope import (
    CapitalRiskEnvelope,
    evaluate_capital_risk_envelope,
)
from quant_platform_kit.risk.reconciliation_snapshot_binding import (
    ReconciliationEquitySummary,
    build_injected_snapshot_from_equity_summary,
)


def _derive_drawdown(
    equity_usd: float,
    peak_equity_usd: float | None,
    drawdown_from_peak: float | None,
) -> float | None:
    if drawdown_from_peak is not None:
        return drawdown_from_peak
    if peak_equity_usd is None or peak_equity_usd <= 0.0:
        return None
    return max(0.0, 1.0 - equity_usd / peak_equity_usd)


def probe_capital_envelope_w2(
    equity_usd: float,
    *,
    peak_equity_usd: float | None = None,
    realized_vol: float | None = None,
    drawdown_from_peak: float | None = None,
) -> dict[str, Any]:
    """Evaluate envelope + NEW_RISK gate disposition for injected equity inputs.

    Assumes healthy reconciliation axes (COMPLETE / VERIFIED / CLOSED). No broker
    read-back; not live-wired.
    """
    summary = ReconciliationEquitySummary(
        equity_usd=float(equity_usd),
        peak_equity_usd=peak_equity_usd,
        drawdown_from_peak=drawdown_from_peak,
        realized_vol=realized_vol,
    )
    snapshot = build_injected_snapshot_from_equity_summary(summary)
    drawdown = _derive_drawdown(
        float(snapshot.equity_usd or 0.0),
        snapshot.peak_equity_usd,
        snapshot.drawdown_from_peak,
    )
    envelope = evaluate_capital_risk_envelope(
        float(snapshot.equity_usd or 0.0),
        realized_vol=snapshot.realized_vol,
        drawdown_from_peak=drawdown,
    )
    gate = evaluate_new_risk_admission(snapshot)
    return {
        "envelope": _envelope_to_dict(envelope),
        "gate": {
            "disposition": gate.disposition.value,
            "reason_codes": list(gate.reason_codes),
            "live_authority_granted": gate.live_authority_granted,
        },
        "snapshot": {
            "observation_status": snapshot.observation_status,
            "reconciliation_status": snapshot.reconciliation_status,
            "circuit_breaker_state": snapshot.circuit_breaker_state,
            "equity_usd": snapshot.equity_usd,
            "peak_equity_usd": snapshot.peak_equity_usd,
            "drawdown_from_peak": snapshot.drawdown_from_peak,
            "realized_vol": snapshot.realized_vol,
        },
        "w2_probe": True,
        "live_wired": False,
    }


def _envelope_to_dict(envelope: CapitalRiskEnvelope) -> dict[str, Any]:
    payload = asdict(envelope)
    payload["reasons"] = list(envelope.reasons)
    return payload


def _parse_optional_float(value: str | None) -> float | None:
    if value is None:
        return None
    number = float(value)
    if isinstance(number, bool) or not math.isfinite(number):
        raise ValueError("must be a finite number")
    return number


def format_probe_report(result: dict[str, Any]) -> str:
    envelope = result["envelope"]
    gate = result["gate"]
    lines = [
        "capital_envelope_w2_probe (read-only; not live-wired)",
        f"disposition: {gate['disposition']}",
        f"reason_codes: {', '.join(gate['reason_codes']) or '(none)'}",
        f"band_id: {envelope['band_id']}",
        (
            "scales: capital={capital_scale:.4f} vol={vol_scale:.4f} "
            "dd={dd_scale:.4f} combined={combined_scale:.4f}"
        ).format(**envelope),
        f"new_risk_allowed: {envelope['new_risk_allowed']}",
        f"envelope_reasons: {', '.join(envelope['reasons'])}",
        f"live_authority_granted: {gate['live_authority_granted']}",
    ]
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "W2 read-only probe: equity/peak/vol → capital envelope + NEW_RISK gate "
            "(no broker, no network, no live authority)"
        )
    )
    parser.add_argument("--equity", required=True, type=float, help="equity_usd")
    parser.add_argument("--peak", type=float, default=None, help="optional peak_equity_usd")
    parser.add_argument("--vol", type=float, default=None, help="optional realized_vol")
    parser.add_argument(
        "--drawdown",
        type=float,
        default=None,
        help="optional drawdown_from_peak (overrides peak-derived DD)",
    )
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args(argv)

    result = probe_capital_envelope_w2(
        args.equity,
        peak_equity_usd=args.peak,
        realized_vol=args.vol,
        drawdown_from_peak=args.drawdown,
    )
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(format_probe_report(result))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
