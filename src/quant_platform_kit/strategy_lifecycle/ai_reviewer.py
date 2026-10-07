"""Advisory proposal review with deterministic checks and configured task routes.

Two explicitly configured reviewer roles may supply opinions. An optional
verification assistant supplies advisory claims only; reproduced metrics and
execution still require independent evidence and human approval. Task failure
has no automatic provider fallback.
"""

from __future__ import annotations

import json
import math
from numbers import Real
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping

import numpy as np

from quant_platform_kit.strategy_lifecycle.contracts import (
    DriftResult,
    DriftStatus,
    OptimizationProposal,
    StrategyPerformanceSnapshot,
    interval_return_coverage_comparison_reason,
    normalize_interval_return_coverage,
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

_PRIMARY_LLM = "reviewer-primary"
_SECONDARY_LLM = "reviewer-secondary"
_REVIEW_COVERAGE_FIELDS = frozenset({
    "method", "timezone", "currency", "valuation_basis", "source_segment_start_at", "source_segment_end_at",
    "available_return_start_at", "available_return_end_at", "return_start_at", "return_end_at",
    "requested_start_at", "requested_end_at", "requested_window_complete", "coverage_status",
    "normalized_interval_count", "segment_interval_count", "return_count", "truncation_reasons",
})


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

def _interval_review_issue(
    proposal: OptimizationProposal, snapshot: StrategyPerformanceSnapshot | None,
    comparison_coverage: Mapping[str, Any] | None,
) -> str:
    if snapshot is None:
        return ""
    coverage = snapshot.interval_return_coverage
    if coverage is None:
        return ("interval_coverage_unavailable" if snapshot.observation_status not in
                {"", "ok", "complete", "COMPLETE"} else "")
    try:
        coverage = normalize_interval_return_coverage(coverage)
    except (TypeError, ValueError):
        return "interval_coverage_unavailable"
    if coverage["coverage_status"] == "unavailable" or not comparison_coverage:
        return "interval_comparison_coverage_unavailable"
    current = proposal.current_metrics
    chosen = next((w for w in snapshot.windows.values() if current is not None
                   and w.start_date == current.start_date and w.end_date == current.end_date
                   and w.observation_count == current.observation_count), None)
    if chosen is None or current is None:
        return "interval_current_metrics_not_bound"
    # The declared baseline must actually be this snapshot's measured values.
    # Matching date labels/counts is not evidence for an arbitrary Sharpe or DD.
    for name in ("sharpe_ratio", "volatility", "calmar_ratio", "sortino_ratio", "max_drawdown",
                 "cagr", "win_rate", "total_return", "benchmark_cagr", "benchmark_max_drawdown", "excess_cagr"):
        actual, expected = getattr(current, name, None), getattr(chosen, name, None)
        if actual is None and name not in {"sharpe_ratio", "volatility"}:
            continue
        if (not _finite_number(actual) or not _finite_number(expected)
                or not math.isclose(float(actual), float(expected), rel_tol=1e-12, abs_tol=1e-12)):
            return "interval_current_metrics_not_bound"
    if current.benchmark_symbol and current.benchmark_symbol != chosen.benchmark_symbol:
        return "interval_current_metrics_not_bound"
    for label, metrics in (("current", current), ("proposed", proposal.proposed_metrics)):
        reason = interval_return_coverage_comparison_reason(
            coverage, comparison_coverage.get(label), current_window=chosen, reference_metrics=metrics,
        )
        if reason:
            return reason
    return ""


def review_proposal(
    proposal: OptimizationProposal,
    *, drift: DriftResult | None = None,
    snapshot: StrategyPerformanceSnapshot | None = None,
    min_pass_dimensions: int = 3,
    comparison_coverage: Mapping[str, Any] | None = None,
) -> AiReviewVerdict:
    """Deterministic 5-dimension review. No API call needed."""
    coverage_issue = _interval_review_issue(proposal, snapshot, comparison_coverage)
    if coverage_issue:
        return AiReviewVerdict(
            proposal=proposal, verdict="escalate", overall_score=0.0, dimensions=(),
            summary="Interval coverage comparison unavailable: " + coverage_issue,
            requires_human=True, confidence=0.0, recommended_action="escalate",
        )
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
    if snapshot is not None and snapshot.interval_return_coverage is not None:
        coverage = snapshot.interval_return_coverage
        s += (f" Comparison is limited to supplied {coverage['method']} checkpoints "
              f"{coverage['return_start_at']} through {coverage['return_end_at']}; "
              "not native archive completeness or exact TWR.")

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
# All AI calls go through the project-scoped task service.
# The caller owns independent review roles and numerical evidence:
#   configured review routes → advisory verification → consensus


def llm_enhanced_review(
    proposal: OptimizationProposal,
    *, drift: DriftResult | None = None, dry_run: bool = False,
    snapshot: StrategyPerformanceSnapshot | None = None,
    comparison_coverage: Mapping[str, Any] | None = None,
) -> AiReviewVerdict:
    """Multi-AI review using unified AiServiceClient (configured reviewer roles)."""
    base = review_proposal(proposal, drift=drift, snapshot=snapshot,
                           comparison_coverage=comparison_coverage)
    if (base.verdict != "escalate" or dry_run or _interval_review_issue(proposal, snapshot, comparison_coverage)
            or _invalid_review_inputs(proposal)
            or any(d.name == "risk_profile" and not d.passed for d in base.dimensions)):
        return base

    from quant_platform_kit.strategy_lifecycle.ai_provider import AiServiceClient, AiServiceConfig

    try:
        config = AiServiceConfig.from_env()
        client = AiServiceClient(config)
    except (ValueError, TypeError):
        return base
    prompt = _build_review_prompt(proposal, drift)
    if snapshot is not None and snapshot.interval_return_coverage is not None:
        context = {k: v for k, v in snapshot.interval_return_coverage.items()
                   if k in _REVIEW_COVERAGE_FIELDS}
        prompt += ("\nQualified comparison context: " + json.dumps(context, sort_keys=True)
                   + "\nThis is a supplied checkpoint window, not complete account history or exact TWR.")

    # L2+L3: Run all configured reviewers via AiServiceClient
    results = client.review(prompt)
    primary = _parse_reviewer_result(proposal, results, _PRIMARY_LLM)
    secondary = _parse_reviewer_result(proposal, results, _SECONDARY_LLM)

    # L4: Assistant self-reported claims remain advisory, not execution evidence.
    verification = None
    if client.config.verifier is not None:
        vp = _build_verifier_prompt(proposal, drift)
        if snapshot is not None and snapshot.interval_return_coverage is not None:
            vp += ("\nComparison is limited to the supplied checkpoint window and method. "
                   "Do not claim complete account history or exact TWR.")
        cr = client.verify(vp)
        if cr and cr.success:
            verification = _parse_verifier_result(proposal, cr)

    # L5: Consensus
    return _resolve_multi_consensus(proposal, base, primary, secondary, verification)


# ── Consensus resolution ─────────────────────────────────────────────

def _resolve_multi_consensus(
    proposal: OptimizationProposal, base: AiReviewVerdict,
    primary: AiReviewVerdict | None, secondary: AiReviewVerdict | None,
    verification: AiReviewVerdict | None,
) -> AiReviewVerdict:
    """Confidence-driven consensus resolution.

    Decision logic (ordered):
    Research candidate readiness requires both independent LLM reviewers.
    Assistant self-reports cannot verify execution or replace either reviewer;
    advisory disagreement still requires human inspection.
    """
    advisory = f" [{verification.summary}]" if verification else ""
    verdicts: list[tuple[str, AiReviewVerdict]] = []
    for l, v in [(_PRIMARY_LLM, primary), (_SECONDARY_LLM, secondary)]:
        if v: verdicts.append((l, v))

    if not verdicts:
        return AiReviewVerdict(proposal=proposal, verdict="escalate", overall_score=base.overall_score,
            dimensions=base.dimensions, summary="No AI available. " + base.summary + advisory,
            requires_human=True, confidence=0.0)

    missing_independent_reviewers = [
        label
        for label, verdict in [(_PRIMARY_LLM, primary), (_SECONDARY_LLM, secondary)]
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

    if verification and verification.recommended_action != "notify":
        return AiReviewVerdict(
            proposal=proposal, verdict="escalate", overall_score=base.overall_score,
            dimensions=base.dimensions, summary="Verification assistant advisory disagreement; human inspection required." + advisory,
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
    for r in results:
        if getattr(r, "label", "") == label and getattr(r, "success", False):
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


def _parse_verifier_result(proposal: OptimizationProposal, result: Any) -> AiReviewVerdict | None:
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
        summary=f"Verification assistant advisory claim: {v}; execution and reproduced metrics are not independently verified." + note,
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


def _build_verifier_prompt(proposal: OptimizationProposal, drift: DriftResult | None = None) -> str:
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
