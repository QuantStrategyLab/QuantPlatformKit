"""Multi-AI adversarial proposal reviewer.

Review chain (SAFETY pattern via AiServiceClient):
  L1: Rule-based (5 dims) — instant, deterministic, always available
  L2: Claude — adversarial statistical analysis
  L3: GPT — second opinion from different provider
  L4: Codex VPS — advisory claims, not independently verified execution
  L5: Consensus — all must agree, or escalate to human

All LLM/Codex calls delegate to AiServiceClient (ai_provider.py).
The unified provider supports two patterns:
  RELIABILITY — Codex primary → API fallback (CodexAuditBridge style)
  SAFETY — adversarial consensus (strategy_lifecycle style)
"""

from __future__ import annotations

import json
import math
from numbers import Real
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import numpy as np

from quant_platform_kit.strategy_lifecycle.contracts import (
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
    confidence: float = 0.5          # AI confidence (0.0–1.0), default neutral
    recommended_action: str = ""     # "candidate_ready" | "notify" | "escalate"

    def to_dict(self) -> dict[str, Any]:
        return {"verdict": self.verdict, "overall_score": self.overall_score,
                "dimensions": [d.to_dict() for d in self.dimensions],
                "summary": self.summary, "requires_human": self.requires_human,
                "reviewed_at": self.reviewed_at, "confidence": self.confidence,
                "recommended_action": self.recommended_action}


# ── Provider labels (for consensus display) ──────────────────────────

_PRIMARY_LLM = "Claude"
_SECONDARY_LLM = "GPT"
_CODEX_VPS = "Codex VPS"


def _finite_number(value: Any) -> bool:
    try:
        return isinstance(value, Real) and not isinstance(value, bool) and math.isfinite(value)
    except OverflowError:
        return False


def _invalid_review_inputs(p: OptimizationProposal) -> list[str]:
    """Validate only inputs consumed by this advisory scorer, not promotion evidence."""
    errors = []
    m = p.proposed_metrics
    if m is None:
        errors.append("proposed_metrics")
    else:
        for name in ("sharpe_ratio", "max_drawdown", "observation_count"):
            if not _finite_number(getattr(m, name)):
                errors.append(name)
        if _finite_number(m.observation_count) and (
            m.observation_count <= 0 or m.observation_count != int(m.observation_count)
        ):
            errors.append("observation_count")
        # Missing OOS/WF metrics are allowed for learning; supplied values must be finite.
        for name in ("oos_sharpe", "walk_forward_stability", "calmar_ratio", "volatility"):
            value = getattr(m, name)
            if value is not None and not _finite_number(value):
                errors.append(name)
    if not _finite_number(p.confidence) or not 0 <= p.confidence <= 1:
        errors.append("confidence")
    if p.current_metrics:
        for name in ("sharpe_ratio", "volatility"):
            value = getattr(p.current_metrics, name)
            if value is not None and not _finite_number(value):
                errors.append("current_" + name)
    for name, value in p.proposed_params.items():
        previous = p.current_params.get(name)
        if (isinstance(previous, (int, float)) and not isinstance(previous, bool)
                and isinstance(value, (int, float)) and not isinstance(value, bool)):
            if not _finite_number(previous) or not _finite_number(value):
                errors.append("parameter " + name)
    return errors


# ── Level 1: Rule-based review ───────────────────────────────────────

def review_proposal(
    proposal: OptimizationProposal,
    *, drift: DriftResult | None = None,
    snapshot: StrategyPerformanceSnapshot | None = None,
    min_pass_dimensions: int = 3,
) -> AiReviewVerdict:
    """Deterministic 5-dimension review. No API call needed."""
    invalid = _invalid_review_inputs(proposal)
    if invalid:
        return AiReviewVerdict(
            proposal=proposal, verdict="escalate", overall_score=0.0, dimensions=(),
            summary="Invalid review inputs: " + ", ".join(invalid) + "; human review required.",
            requires_human=True, confidence=0.0, recommended_action="escalate",
        )
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
        v, h, s = "approve", True, "All dimensions passed with high confidence; human approval required."
    elif passed >= min_pass_dimensions and overall >= 0.55:
        v, h, s = "approve", True, f"{passed}/{len(dims)} passed. Human approval required."
    elif passed >= 2 and overall >= 0.35:
        v, h, s = "escalate", True, f"Only {passed}/{len(dims)} passed. Needs deeper review."
    else:
        v, h, s = "reject", False, f"Failed: {passed}/{len(dims)}."

    if v == "approve" and not dims[1].passed:
        v, h, s = "escalate", True, "Risk profile failed; human review required."

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
    if m.calmar_ratio is not None and m.calmar_ratio < 0.3: issues.append("Low Calmar"); s -= 0.2
    ok = s >= 0.5 and abs(m.max_drawdown) <= max_dd
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
#   Claude + GPT independently review → Codex advisory claims → consensus


def llm_enhanced_review(
    proposal: OptimizationProposal,
    *, drift: DriftResult | None = None, dry_run: bool = False,
) -> AiReviewVerdict:
    """Multi-AI review using unified AiServiceClient (SAFETY pattern)."""
    base = review_proposal(proposal, drift=drift)
    if (base.verdict != "escalate" or dry_run or _invalid_review_inputs(proposal)
            or any(d.name == "risk_profile" and not d.passed for d in base.dimensions)):
        return base

    from quant_platform_kit.strategy_lifecycle.ai_provider import AiServiceClient, AiServiceConfig

    config = AiServiceConfig.from_env()
    client = AiServiceClient(config)
    prompt = _build_review_prompt(proposal, drift)

    # L2+L3: Run all configured reviewers via AiServiceClient
    results = client.review(prompt)
    claude = _parse_reviewer_result(proposal, results, _PRIMARY_LLM)
    gpt = _parse_reviewer_result(proposal, results, _SECONDARY_LLM)

    # L4: Codex self-reported claims remain advisory, not execution evidence.
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
    """Confidence-driven consensus resolution.

    Decision logic (ordered):
    Research candidate readiness requires both independent LLM reviewers.
    Codex self-reports cannot verify execution or replace either reviewer;
    advisory disagreement still requires human inspection.
    """
    advisory = f" [{codex.summary}]" if codex else ""
    verdicts: list[tuple[str, AiReviewVerdict]] = []
    for l, v in [(_PRIMARY_LLM, claude), (_SECONDARY_LLM, gpt)]:
        if v: verdicts.append((l, v))

    if not verdicts:
        return AiReviewVerdict(proposal=proposal, verdict="escalate", overall_score=base.overall_score,
            dimensions=base.dimensions, summary="No AI available. " + base.summary + advisory,
            requires_human=True, confidence=0.0)

    missing_independent_reviewers = [
        label
        for label, verdict in [(_PRIMARY_LLM, claude), (_SECONDARY_LLM, gpt)]
        if verdict is None
    ]
    if missing_independent_reviewers:
        return AiReviewVerdict(
            proposal=proposal,
            verdict="escalate",
            overall_score=base.overall_score,
            dimensions=base.dimensions,
            summary=(
                "[DUAL_REVIEW_INCOMPLETE] missing independent reviewer(s): "
                + ", ".join(missing_independent_reviewers) + advisory
            ),
            requires_human=True,
            confidence=0.0,
            recommended_action="escalate",
        )

    if (_invalid_review_inputs(proposal)
            or any(d.name == "risk_profile" and not d.passed for d in base.dimensions)):
        return AiReviewVerdict(
            proposal=proposal, verdict="escalate", overall_score=base.overall_score,
            dimensions=base.dimensions, summary=base.summary + " AI opinions cannot override invalid inputs or failed risk review." + advisory,
            requires_human=True, confidence=0.0, recommended_action="escalate",
        )

    if codex and codex.recommended_action != "notify":
        return AiReviewVerdict(
            proposal=proposal, verdict="escalate", overall_score=base.overall_score,
            dimensions=base.dimensions, summary="Codex advisory disagreement; human inspection required." + advisory,
            requires_human=True, confidence=0.0, recommended_action="escalate",
        )
    apps = [l for l, v in verdicts if v.verdict == "approve"]
    rejs = [l for l, v in verdicts if v.verdict == "reject"]
    avg_conf = float(np.mean([v.confidence for _, v in verdicts]))
    avg_score = float(np.mean([v.overall_score for _, v in verdicts]))

    # Unanimous approve
    if len(apps) == len(verdicts):
        if avg_conf >= 0.85:
            note = " [candidate-ready: high confidence; human decision required]"
            action = "candidate_ready"
        elif avg_conf >= 0.60:
            note = " [candidate-ready: moderate confidence; human decision required]"
            action = "candidate_ready"
        else:
            note = " [ESCALATE: low confidence unanimous]"
            action = "escalate"
        return AiReviewVerdict(proposal=proposal, verdict="approve", overall_score=avg_score,
            dimensions=base.dimensions, summary=f"[Unanimous: {', '.join(apps)}]{note}{advisory}",
            requires_human=True, confidence=avg_conf, recommended_action=action)

    # Unanimous reject
    if len(rejs) == len(verdicts):
        return AiReviewVerdict(proposal=proposal, verdict="reject", overall_score=avg_score,
            dimensions=base.dimensions,
            summary=f"[Unanimous reject: {', '.join(rejs)}] confidence={avg_conf:.0%}{advisory}",
            requires_human=False, confidence=avg_conf, recommended_action="escalate")

    # Disagreement → escalate
    detail = "; ".join(f"{l}={v.verdict}(c={v.confidence:.0%})" for l, v in verdicts)
    return AiReviewVerdict(proposal=proposal, verdict="escalate", overall_score=base.overall_score,
        dimensions=base.dimensions, summary=f"[DISAGREE] {detail}{advisory}",
        requires_human=True, confidence=avg_conf, recommended_action="escalate")


# ── Result parsers (AiCallResult → AiReviewVerdict) ──────────────────

def _parse_reviewer_result(
    proposal: OptimizationProposal, results: list[Any], label: str,
) -> AiReviewVerdict | None:
    aliases = {"Claude": ("claude", "anthropic"), "GPT": ("gpt", "openai")}
    for r in results:
        provider = getattr(r, "provider", "")
        if isinstance(provider, str) and provider.lower() in aliases.get(label, (label.lower(),)) and getattr(r, "success", False):
            try:
                m = re.search(r"\{[\s\S]*\}", getattr(r, "output", ""))
                if m:
                    d = json.loads(m.group(0))
                    verdict = d.get("verdict", "escalate")
                    score, confidence = d.get("overall_score", 0.5), d.get("confidence", 0.5)
                    if verdict not in ("approve", "reject", "escalate"):
                        continue
                    if not all(_finite_number(v) and 0 <= v <= 1 for v in (score, confidence)):
                        continue
                    return AiReviewVerdict(proposal=proposal,
                        verdict=verdict,
                        overall_score=float(score), dimensions=(),
                        summary=str(d.get("summary", f"{label} done")),
                        requires_human=(verdict == "approve") or bool(d.get("requires_human", True)),
                        confidence=float(confidence))
            except (json.JSONDecodeError, ValueError, TypeError, AttributeError):
                pass
    return None


def _parse_codex_result(proposal: OptimizationProposal, result: Any) -> AiReviewVerdict | None:
    output = getattr(result, "output", "")
    if not isinstance(output, str): return None
    m = re.search(r"\{[\s\S]*\}", output)
    if not m: return None
    try: d = json.loads(m.group(0))
    except json.JSONDecodeError: return None
    v = d.get("verdict")
    if v not in ("verified", "mismatch"):
        return None
    invalid = any(name in d and not _finite_number(d[name])
                  for name in ("reproduced_sharpe", "reproduced_max_dd", "reproduced_cagr"))
    invalid |= any(name in d and not (_finite_number(d[name]) and 0 <= d[name] <= 1)
                   for name in ("confidence", "overall_score"))
    note = " Invalid numeric claims require human inspection." if invalid else ""
    return AiReviewVerdict(
        proposal=proposal, verdict="escalate", overall_score=0.0, dimensions=(),
        summary=f"Codex VPS advisory claim: {v}; execution and reproduced metrics are not independently verified." + note,
        requires_human=True, confidence=0.0,
        recommended_action="notify" if v == "verified" and not invalid else "escalate",
    )


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
