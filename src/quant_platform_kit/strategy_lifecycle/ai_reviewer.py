"""Multi-AI adversarial proposal reviewer.

Review chain (SAFETY pattern via AiServiceClient):
  L1: Rule-based (5 dims) — instant, deterministic, always available
  L2: Claude — adversarial statistical analysis
  L3: GPT — second opinion from different provider
  L4: Codex VPS — actually RUNS the backtest to verify numbers
  L5: Consensus — all must agree, or escalate to human

All LLM/Codex calls delegate to AiServiceClient (ai_provider.py).
The unified provider supports two patterns:
  RELIABILITY — Codex primary → API fallback (CodexAuditBridge style)
  SAFETY — adversarial consensus (strategy_lifecycle style)
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any

import numpy as np

from quant_platform_kit.strategy_lifecycle.contracts import (
    BacktestResult,
    DriftResult,
    DriftStatus,
    OptimizationProposal,
    StrategyPerformanceSnapshot,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Data models ──────────────────────────────────────────────────────

@dataclass(frozen=True)
class ReviewDimension:
    name: str; score: float; passed: bool; reasoning: str
    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "score": self.score, "passed": self.passed, "reasoning": self.reasoning}


@dataclass(frozen=True)
class AiReviewVerdict:
    proposal: OptimizationProposal
    verdict: str                     # "approve" | "reject" | "escalate"
    overall_score: float
    dimensions: tuple[ReviewDimension, ...]
    summary: str
    requires_human: bool
    reviewed_at: str = field(default_factory=_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return {"verdict": self.verdict, "overall_score": self.overall_score,
                "dimensions": [d.to_dict() for d in self.dimensions],
                "summary": self.summary, "requires_human": self.requires_human,
                "reviewed_at": self.reviewed_at}


# ── Provider labels (for consensus display) ──────────────────────────

_PRIMARY_LLM = "Claude"
_SECONDARY_LLM = "GPT"
_CODEX_VPS = "Codex VPS"


# ── Level 1: Rule-based review ───────────────────────────────────────

def review_proposal(
    proposal: OptimizationProposal,
    *, drift: DriftResult | None = None,
    snapshot: StrategyPerformanceSnapshot | None = None,
    min_pass_dimensions: int = 3,
) -> AiReviewVerdict:
    """Deterministic 5-dimension review. No API call needed."""
    dims = [
        _review_statistical_validity(proposal),
        _review_risk_profile(proposal),
        _review_regime_compatibility(proposal, drift=drift),
        _review_param_safety(proposal),
        _review_confidence(proposal),
    ]
    passed = sum(1 for d in dims if d.passed)
    overall = np.mean([d.score for d in dims])

    if passed >= 5 and overall >= 0.75:
        v, h, s = "approve", False, "All dimensions passed with high confidence."
    elif passed >= min_pass_dimensions and overall >= 0.55:
        v, h, s = "approve", False, f"{passed}/{len(dims)} passed. Auto-deploying."
    elif passed >= 2 and overall >= 0.35:
        v, h, s = "escalate", True, f"Only {passed}/{len(dims)} passed. Needs deeper review."
    else:
        v, h, s = "reject", False, f"Failed: {passed}/{len(dims)}."

    return AiReviewVerdict(proposal=proposal, verdict=v, overall_score=round(overall, 4),
                           dimensions=tuple(dims), summary=s, requires_human=h)


def _review_statistical_validity(p: OptimizationProposal, *, min_oos: float = 0.02) -> ReviewDimension:
    m = p.proposed_metrics
    if m is None: return ReviewDimension("statistical_validity", 0.0, False, "No metrics")
    issues, s = [], 1.0
    if m.observation_count < 60: issues.append(f"Few obs ({m.observation_count})"); s -= 0.4
    if m.oos_sharpe is not None and m.oos_sharpe < 0: issues.append("Neg OOS Sharpe"); s -= 0.3
    if m.walk_forward_stability is not None and m.walk_forward_stability < 0.5: issues.append("Low WF stability"); s -= 0.2
    if p.current_metrics and m.sharpe_ratio and p.current_metrics.sharpe_ratio:
        if (m.sharpe_ratio - p.current_metrics.sharpe_ratio) < min_oos: issues.append("Tiny improvement"); s -= 0.2
    ok = s >= 0.6
    return ReviewDimension("statistical_validity", max(s, 0.0), ok, "; ".join(issues) if issues else "OK")

def _review_risk_profile(p: OptimizationProposal, *, max_dd: float = 0.40) -> ReviewDimension:
    m = p.proposed_metrics
    if m is None: return ReviewDimension("risk_profile", 0.0, False, "No metrics")
    issues, s = [], 1.0
    if m.max_drawdown is not None and abs(m.max_drawdown) > max_dd: issues.append(f"MaxDD {m.max_drawdown:.1%}>{max_dd:.0%}"); s -= 0.5
    if p.current_metrics and m.volatility and p.current_metrics.volatility:
        if m.volatility / max(p.current_metrics.volatility, 0.001) > 1.5: issues.append("Vol spike"); s -= 0.3
    if m.calmar_ratio is not None and m.calmar_ratio < 0.3: issues.append(f"Low Calmar"); s -= 0.2
    ok = s >= 0.5
    return ReviewDimension("risk_profile", max(s, 0.0), ok, "; ".join(issues) if issues else "OK")

def _review_regime_compatibility(p: OptimizationProposal, drift: DriftResult | None = None) -> ReviewDimension:
    issues, s = [], 1.0
    if drift and drift.status == DriftStatus.CRITICAL and len(drift.breached_dimensions) >= 4:
        issues.append("4+ dims breached — may be regime"); s -= 0.3
    if p.regressing_dimensions:
        issues.append(f"Regressing: {', '.join(p.regressing_dimensions)}"); s -= 0.15 * len(p.regressing_dimensions)
    ok = s >= 0.4
    return ReviewDimension("regime_compatibility", max(s, 0.0), ok, "; ".join(issues) if issues else "OK")

def _review_param_safety(p: OptimizationProposal, *, max_change: float = 0.50) -> ReviewDimension:
    issues, s = [], 1.0
    for k, nv in p.proposed_params.items():
        ov = p.current_params.get(k)
        if ov is not None and isinstance(ov, (int, float)) and isinstance(nv, (int, float)):
            if abs(float(ov)) > 0.001:
                c = abs(float(nv) - float(ov)) / abs(float(ov))
                if c > max_change: issues.append(f"'{k}' {c:.0%}"); s -= 0.2
    ok = s >= 0.5
    return ReviewDimension("param_safety", max(s, 0.0), ok, "; ".join(issues) if issues else "OK")

def _review_confidence(p: OptimizationProposal) -> ReviewDimension:
    if p.confidence < 0.3: return ReviewDimension("confidence", 0.2, False, f"Low ({p.confidence:.2f})")
    if p.confidence < 0.6: return ReviewDimension("confidence", 0.6, True, f"Moderate ({p.confidence:.2f})")
    return ReviewDimension("confidence", 0.9, True, f"High ({p.confidence:.2f})")


# ── Level 2-5: Multi-AI adversarial review (via AiServiceClient) ─────
#
# All LLM/Codex calls go through AiServiceClient.
# This is the "双AI审计 + Codex执行回测" pattern:
#   Claude + GPT independently review → Codex runs backtest → consensus


def llm_enhanced_review(
    proposal: OptimizationProposal,
    *, drift: DriftResult | None = None, dry_run: bool = False,
) -> AiReviewVerdict:
    """Multi-AI review using unified AiServiceClient (SAFETY pattern)."""
    base = review_proposal(proposal, drift=drift)
    if base.verdict != "escalate" or dry_run:
        return base

    from quant_platform_kit.strategy_lifecycle.ai_provider import AiServiceClient, AiServiceConfig

    config = AiServiceConfig.from_env()
    client = AiServiceClient(config)
    prompt = _build_review_prompt(proposal, drift)

    # L2+L3: Run all configured reviewers via AiServiceClient
    results = client.review(prompt)
    claude = _parse_reviewer_result(proposal, results, _PRIMARY_LLM)
    gpt = _parse_reviewer_result(proposal, results, _SECONDARY_LLM)

    # Claude confident → early return
    if claude and claude.verdict in ("approve", "reject"):
        return AiReviewVerdict(proposal=proposal, verdict=claude.verdict,
            overall_score=claude.overall_score, dimensions=base.dimensions,
            summary=f"[{_PRIMARY_LLM}] {claude.summary}", requires_human=False)

    # L4: Codex VPS execution verification
    codex = None
    if client.config.verifier is not None:
        vp = _build_codex_verify_prompt(proposal, drift)
        cr = client.verify(vp)
        if cr and cr.success:
            codex = _parse_codex_result(proposal, cr)

    # L5: Consensus
    return _resolve_multi_consensus(proposal, base, claude, gpt, codex)


# ── Consensus resolution ─────────────────────────────────────────────

def _resolve_multi_consensus(
    proposal: OptimizationProposal, base: AiReviewVerdict,
    claude: AiReviewVerdict | None, gpt: AiReviewVerdict | None,
    codex: AiReviewVerdict | None,
) -> AiReviewVerdict:
    verdicts: list[tuple[str, AiReviewVerdict]] = []
    for l, v in [(_PRIMARY_LLM, claude), (_SECONDARY_LLM, gpt), (_CODEX_VPS, codex)]:
        if v: verdicts.append((l, v))

    if not verdicts:
        return AiReviewVerdict(proposal=proposal, verdict="escalate", overall_score=base.overall_score,
            dimensions=base.dimensions, summary="No AI available. " + base.summary, requires_human=True)

    apps = [l for l, v in verdicts if v.verdict == "approve"]
    rejs = [l for l, v in verdicts if v.verdict == "reject"]
    escs = [l for l, v in verdicts if v.verdict == "escalate"]
    cx_ok = codex and codex.verdict == "approve"
    cx_bad = codex and codex.verdict == "reject"

    def _avg(): return float(np.mean([v.overall_score for _, v in verdicts]))

    if len(apps) == len(verdicts):
        note = f" [{_CODEX_VPS} verified]" if cx_ok else ""
        return AiReviewVerdict(proposal=proposal, verdict="approve", overall_score=_avg(),
            dimensions=base.dimensions, summary=f"[Unanimous: {', '.join(apps)}]{note}", requires_human=False)
    if len(rejs) == len(verdicts):
        return AiReviewVerdict(proposal=proposal, verdict="reject", overall_score=_avg(),
            dimensions=base.dimensions, summary=f"[Unanimous reject: {', '.join(rejs)}]", requires_human=False)
    if cx_bad:
        llms = ", ".join(f"{l}={v.verdict}" for l, v in verdicts if l != _CODEX_VPS)
        return AiReviewVerdict(proposal=proposal, verdict="reject", overall_score=codex.overall_score,
            dimensions=base.dimensions, summary=f"[{_CODEX_VPS} MISMATCH] {codex.summary}. LLMs: {llms}", requires_human=False)
    if cx_ok and apps and not rejs:
        return AiReviewVerdict(proposal=proposal, verdict="approve", overall_score=_avg(),
            dimensions=base.dimensions, summary=f"[{_CODEX_VPS} verified] {', '.join(apps)} approve.", requires_human=False)
    if len(verdicts) == 1 and not codex:
        sl, sv = verdicts[0]
        if sv.verdict == "approve":
            return AiReviewVerdict(proposal=proposal, verdict="approve", overall_score=sv.overall_score,
                dimensions=base.dimensions, summary=f"[Single: {sl}] {sv.summary}", requires_human=False)

    detail = "; ".join(f"{l}={v.verdict}" for l, v in verdicts)
    return AiReviewVerdict(proposal=proposal, verdict="escalate", overall_score=base.overall_score,
        dimensions=base.dimensions, summary=f"[DISAGREE] {detail}", requires_human=True)


# ── Result parsers (AiCallResult → AiReviewVerdict) ──────────────────

def _parse_reviewer_result(
    proposal: OptimizationProposal, results: list[Any], label: str,
) -> AiReviewVerdict | None:
    for r in results:
        if getattr(r, "provider", "") == label and getattr(r, "success", False):
            try:
                m = re.search(r"\{[\s\S]*\}", getattr(r, "output", ""))
                if m:
                    d = json.loads(m.group(0))
                    return AiReviewVerdict(proposal=proposal,
                        verdict=str(d.get("verdict", "escalate")),
                        overall_score=float(d.get("overall_score", 0.5)), dimensions=(),
                        summary=str(d.get("summary", f"{label} done")),
                        requires_human=bool(d.get("requires_human", True)))
            except (json.JSONDecodeError, ValueError):
                pass
    return None


def _parse_codex_result(proposal: OptimizationProposal, result: Any) -> AiReviewVerdict | None:
    m = re.search(r"\{[\s\S]*\}", getattr(result, "output", ""))
    if not m: return None
    try: d = json.loads(m.group(0))
    except json.JSONDecodeError: return None
    v = str(d.get("verdict", "error")).strip().lower()
    if v == "verified":
        return AiReviewVerdict(proposal=proposal, verdict="approve", overall_score=1.0, dimensions=(),
            summary=f"Codex VPS verified: Sharpe={d.get('reproduced_sharpe')}, MaxDD={d.get('reproduced_max_dd')}",
            requires_human=False)
    if v == "mismatch":
        return AiReviewVerdict(proposal=proposal, verdict="reject", overall_score=0.0, dimensions=(),
            summary=f"Codex VPS MISMATCH: {d.get('summary', 'numbers differ')}", requires_human=False)
    return None


# ── Prompt builders ──────────────────────────────────────────────────

def _build_review_prompt(proposal: OptimizationProposal, drift: DriftResult | None) -> str:
    lines = [
        "You are an adversarial strategy reviewer. Find reasons this proposal might fail in live trading.", "",
        f"Strategy: {proposal.strategy_profile} | Domain: {proposal.domain}",
        f"Improvement: {proposal.improvement_score:.4f} | Confidence: {proposal.confidence:.4f}", "",
        "### Current Params", json.dumps(dict(proposal.current_params), indent=2),
        "### Proposed Params", json.dumps(dict(proposal.proposed_params), indent=2), "",
    ]
    if proposal.current_metrics:
        lines.append(f"Current: Sharpe={proposal.current_metrics.sharpe_ratio} MaxDD={proposal.current_metrics.max_drawdown}")
    if proposal.proposed_metrics:
        lines.append(f"Proposed: Sharpe={proposal.proposed_metrics.sharpe_ratio} MaxDD={proposal.proposed_metrics.max_drawdown}")
    if proposal.regressing_dimensions:
        lines.append(f"Regressing: {', '.join(proposal.regressing_dimensions)}")
    if drift:
        lines.extend(["", f"Drift: {drift.status.value} score={drift.drift_score:.3f}"])
    lines.extend(["", 'Respond JSON: {"verdict":"approve|reject|escalate","overall_score":0.5,"summary":"..."}'])
    return "\n".join(lines)


def _build_codex_verify_prompt(proposal: OptimizationProposal, drift: DriftResult | None = None) -> str:
    lines = [
        "# Role", "", "RUN the backtest with proposed parameters and verify the claimed metrics.", "",
        f"Strategy: {proposal.strategy_profile}", "",
        "### Proposed Parameters", "```json", json.dumps(dict(proposal.proposed_params), indent=2), "```", "",
        "### Claimed Metrics",
    ]
    if proposal.proposed_metrics:
        m = proposal.proposed_metrics
        lines.extend([f"- Sharpe: {m.sharpe_ratio}", f"- MaxDD: {m.max_drawdown}", f"- CAGR: {m.cagr}"])
    lines.extend([
        "", "# Rules", "- NO code changes", "- NO branches/PRs", "- Read-only backtest only", "",
        "Compare vs claimed (tolerance: Sharpe ±0.05, MaxDD ±0.02, CAGR ±0.02).",
        'Respond JSON: {"verdict":"verified|mismatch","reproduced_sharpe":0.0,"summary":"..."}',
    ])
    return "\n".join(lines)
