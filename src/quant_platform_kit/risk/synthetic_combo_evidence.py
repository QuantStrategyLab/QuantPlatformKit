"""Synthetic combo evidence for research-only correlated sleeve haircuts.

Module boundary
---------------
- Pure synthetic research helper; no broker/account I/O, no network, no policy
  writes, no live grants, and no order submission.
- Consumes member sleeves plus optional pairwise correlation estimates.
- Missing correlation coverage for a multi-member combo fails closed rather than
  pretending a haircut was evaluated.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Mapping, Sequence


DEFAULT_CORRELATION_THRESHOLD = 0.80
DEFAULT_CORRELATED_GROUP_CAP = 1.00


@dataclass(frozen=True)
class SyntheticComboMember:
    """One strategy member participating in a synthetic combo study."""

    strategy_id: str
    target_weight: float | None = None
    risk_sleeve: float | None = None
    combined_scale: float | None = None


@dataclass(frozen=True)
class PairwiseCorrelationEstimate:
    """Pairwise correlation estimate between two strategy members."""

    left_strategy_id: str
    right_strategy_id: str
    correlation: float


@dataclass(frozen=True)
class SyntheticComboMemberEvidence:
    """Per-member pre/post haircut sleeve evidence."""

    strategy_id: str
    target_weight: float | None
    combined_scale: float
    pre_haircut_risk_sleeve: float
    post_haircut_risk_sleeve: float
    haircut_applied: bool


@dataclass(frozen=True)
class CorrelatedGroupEvidence:
    """One correlated group summary after thresholding the correlation graph."""

    member_strategy_ids: tuple[str, ...]
    pre_haircut_sleeve: float
    post_haircut_sleeve: float
    group_cap: float
    haircut_scale: float
    haircut_applied: bool


@dataclass(frozen=True)
class SyntheticComboEvidence:
    """Research-only combo evidence; never promotion eligible or live ready."""

    members: tuple[SyntheticComboMemberEvidence, ...]
    correlated_groups: tuple[CorrelatedGroupEvidence, ...]
    assumptions: tuple[str, ...]
    reason_codes: tuple[str, ...]
    pre_haircut_combined_risk_sleeve: float
    combined_risk_sleeve: float
    correlation_threshold: float
    correlated_group_cap: float
    fail_closed: bool
    learning_only: bool = True
    promotion_eligible: bool = False
    live_ready: bool = False
    synthetic: bool = True
    live_authority_granted: bool = False


def _is_finite_number(value: object) -> bool:
    return (
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and math.isfinite(float(value))
    )


def _clamp_unit(value: float) -> float:
    if not math.isfinite(value) or value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value


def _canonical_strategy_id(raw: object) -> str:
    value = str(raw or "").strip()
    if not value:
        raise ValueError("strategy_id must be a non-empty canonical string")
    return value


def _resolve_member_sleeve(
    member: SyntheticComboMember,
) -> tuple[float, float | None, float]:
    if member.risk_sleeve is not None:
        if not _is_finite_number(member.risk_sleeve) or float(member.risk_sleeve) < 0.0:
            raise ValueError("risk_sleeve must be a finite non-negative float")
        scale = 1.0
        if member.combined_scale is not None:
            if not _is_finite_number(member.combined_scale):
                raise ValueError("combined_scale must be a finite float when provided")
            scale = _clamp_unit(float(member.combined_scale))
        return float(member.risk_sleeve), None, scale

    if member.target_weight is None:
        raise ValueError("member must provide target_weight or risk_sleeve")
    if not _is_finite_number(member.target_weight) or float(member.target_weight) < 0.0:
        raise ValueError("target_weight must be a finite non-negative float")
    scale = 1.0
    if member.combined_scale is not None:
        if not _is_finite_number(member.combined_scale):
            raise ValueError("combined_scale must be a finite float when provided")
        scale = _clamp_unit(float(member.combined_scale))
    return float(member.target_weight) * scale, float(member.target_weight), scale


def _normalize_members(
    members: Sequence[SyntheticComboMember],
) -> tuple[tuple[SyntheticComboMemberEvidence, ...], list[str]]:
    if not members:
        raise ValueError("members must not be empty")

    evidence: list[SyntheticComboMemberEvidence] = []
    assumptions: list[str] = []
    seen: set[str] = set()
    used_target_weight_path = False
    used_explicit_sleeve_path = False
    assumed_unit_scale = False

    for member in members:
        if not isinstance(member, SyntheticComboMember):
            raise ValueError("members must contain SyntheticComboMember values")
        strategy_id = _canonical_strategy_id(member.strategy_id)
        if strategy_id in seen:
            raise ValueError("strategy_id values must be unique")
        seen.add(strategy_id)

        pre_sleeve, original_target_weight, combined_scale = _resolve_member_sleeve(member)
        if member.risk_sleeve is not None:
            used_explicit_sleeve_path = True
        else:
            used_target_weight_path = True
        if member.combined_scale is None:
            assumed_unit_scale = True
        evidence.append(
            SyntheticComboMemberEvidence(
                strategy_id=strategy_id,
                target_weight=original_target_weight,
                combined_scale=combined_scale,
                pre_haircut_risk_sleeve=pre_sleeve,
                post_haircut_risk_sleeve=pre_sleeve,
                haircut_applied=False,
            )
        )

    if used_target_weight_path:
        assumptions.append("risk_sleeve uses target_weight x combined_scale when omitted")
    if used_explicit_sleeve_path:
        assumptions.append("explicit risk_sleeve is consumed as injected synthetic input")
    if assumed_unit_scale:
        assumptions.append("missing combined_scale defaults to 1.0")
    return tuple(evidence), assumptions


def _normalize_pairwise_correlations(
    pairwise_correlation: (
        Mapping[str, Mapping[str, object]]
        | Sequence[PairwiseCorrelationEstimate | Mapping[str, object]]
        | None
    ),
    *,
    strategy_ids: Sequence[str],
) -> dict[frozenset[str], float]:
    required_ids = set(strategy_ids)
    if len(required_ids) <= 1:
        return {}
    if pairwise_correlation is None:
        raise ValueError("pairwise_correlation is required for multi-member combos")

    estimates: dict[frozenset[str], float] = {}
    if isinstance(pairwise_correlation, Mapping):
        for left_raw, right_mapping in pairwise_correlation.items():
            left = _canonical_strategy_id(left_raw)
            if left not in required_ids:
                continue
            if not isinstance(right_mapping, Mapping):
                raise ValueError("pairwise_correlation matrix rows must be mappings")
            for right_raw, correlation_raw in right_mapping.items():
                right = _canonical_strategy_id(right_raw)
                if right not in required_ids or right == left:
                    continue
                if not _is_finite_number(correlation_raw):
                    raise ValueError("correlation must be a finite float")
                corr = float(correlation_raw)
                if corr < -1.0 or corr > 1.0:
                    raise ValueError("correlation must be within [-1, 1]")
                estimates[frozenset((left, right))] = corr
    else:
        for entry in pairwise_correlation:
            if isinstance(entry, PairwiseCorrelationEstimate):
                left = _canonical_strategy_id(entry.left_strategy_id)
                right = _canonical_strategy_id(entry.right_strategy_id)
                correlation_raw = entry.correlation
            elif isinstance(entry, Mapping):
                left = _canonical_strategy_id(
                    entry.get("left_strategy_id") or entry.get("strategy_id_left")
                )
                right = _canonical_strategy_id(
                    entry.get("right_strategy_id") or entry.get("strategy_id_right")
                )
                correlation_raw = entry.get("correlation")
            else:
                raise ValueError("pairwise_correlation entries must be dataclasses or mappings")
            if left not in required_ids or right not in required_ids or left == right:
                continue
            if not _is_finite_number(correlation_raw):
                raise ValueError("correlation must be a finite float")
            corr = float(correlation_raw)
            if corr < -1.0 or corr > 1.0:
                raise ValueError("correlation must be within [-1, 1]")
            estimates[frozenset((left, right))] = corr

    missing_pairs: list[str] = []
    ordered_ids = list(strategy_ids)
    for idx, left in enumerate(ordered_ids):
        for right in ordered_ids[idx + 1 :]:
            key = frozenset((left, right))
            if key not in estimates:
                missing_pairs.append(f"{left}:{right}")
    if missing_pairs:
        missing = ", ".join(missing_pairs)
        raise ValueError(f"missing pairwise correlation estimates: {missing}")
    return estimates


def _fail_closed(
    members: tuple[SyntheticComboMemberEvidence, ...],
    assumptions: Sequence[str],
    *,
    reason_codes: Sequence[str],
    correlation_threshold: float,
    correlated_group_cap: float,
) -> SyntheticComboEvidence:
    zeroed_members = tuple(
        SyntheticComboMemberEvidence(
            strategy_id=member.strategy_id,
            target_weight=member.target_weight,
            combined_scale=member.combined_scale,
            pre_haircut_risk_sleeve=member.pre_haircut_risk_sleeve,
            post_haircut_risk_sleeve=0.0,
            haircut_applied=False,
        )
        for member in members
    )
    pre_combined = sum(member.pre_haircut_risk_sleeve for member in members)
    return SyntheticComboEvidence(
        members=zeroed_members,
        correlated_groups=(),
        assumptions=tuple(assumptions),
        reason_codes=tuple(reason_codes),
        pre_haircut_combined_risk_sleeve=pre_combined,
        combined_risk_sleeve=0.0,
        correlation_threshold=correlation_threshold,
        correlated_group_cap=correlated_group_cap,
        fail_closed=True,
    )


def evaluate_synthetic_combo_evidence(
    members: Sequence[SyntheticComboMember],
    *,
    pairwise_correlation: (
        Mapping[str, Mapping[str, object]]
        | Sequence[PairwiseCorrelationEstimate | Mapping[str, object]]
        | None
    ) = None,
    correlation_threshold: float = DEFAULT_CORRELATION_THRESHOLD,
    correlated_group_cap: float = DEFAULT_CORRELATED_GROUP_CAP,
) -> SyntheticComboEvidence:
    """Evaluate a synthetic combo study with fail-closed correlation haircuts.

    A multi-member combo requires complete pairwise correlation coverage.
    Correlated groups are connected components formed by edges with
    correlation >= ``correlation_threshold``. When a group's aggregate sleeve
    exceeds ``correlated_group_cap``, all member sleeves in that group are cut
    proportionally so the group total equals the cap.
    """
    normalized_members, assumptions = _normalize_members(tuple(members))
    assumptions = list(assumptions)

    if not _is_finite_number(correlation_threshold):
        return _fail_closed(
            normalized_members,
            assumptions,
            reason_codes=("INVALID_CORRELATION_THRESHOLD_FAIL_CLOSED",),
            correlation_threshold=0.0,
            correlated_group_cap=correlated_group_cap if _is_finite_number(correlated_group_cap) else 0.0,
        )
    if not _is_finite_number(correlated_group_cap) or float(correlated_group_cap) < 0.0:
        return _fail_closed(
            normalized_members,
            assumptions,
            reason_codes=("INVALID_CORRELATED_GROUP_CAP_FAIL_CLOSED",),
            correlation_threshold=_clamp_unit(float(correlation_threshold)),
            correlated_group_cap=0.0,
        )

    threshold = _clamp_unit(float(correlation_threshold))
    group_cap = float(correlated_group_cap)
    assumptions.append(f"correlated groups use pairwise correlation threshold >= {threshold:.2f}")
    assumptions.append(f"correlated group sleeve cap = {group_cap:.4f}")

    strategy_ids = [member.strategy_id for member in normalized_members]
    if len(strategy_ids) == 1:
        return SyntheticComboEvidence(
            members=normalized_members,
            correlated_groups=(),
            assumptions=tuple(assumptions),
            reason_codes=("SINGLE_MEMBER_NO_CORRELATION_HAIRCUT",),
            pre_haircut_combined_risk_sleeve=normalized_members[0].pre_haircut_risk_sleeve,
            combined_risk_sleeve=normalized_members[0].pre_haircut_risk_sleeve,
            correlation_threshold=threshold,
            correlated_group_cap=group_cap,
            fail_closed=False,
        )

    try:
        pairwise = _normalize_pairwise_correlations(
            pairwise_correlation, strategy_ids=strategy_ids
        )
    except ValueError as exc:
        message = str(exc)
        if (
            "missing pairwise correlation estimates" in message
            or "pairwise_correlation is required" in message
        ):
            reason = "MISSING_CORRELATION_ESTIMATE_FAIL_CLOSED"
        else:
            reason = "INVALID_CORRELATION_ESTIMATE_FAIL_CLOSED"
        assumptions.append(f"correlation coverage failure: {message}")
        return _fail_closed(
            normalized_members,
            assumptions,
            reason_codes=(reason,),
            correlation_threshold=threshold,
            correlated_group_cap=group_cap,
        )

    adjacency: dict[str, set[str]] = {strategy_id: set() for strategy_id in strategy_ids}
    for pair, correlation in pairwise.items():
        if correlation < threshold:
            continue
        left, right = sorted(pair)
        adjacency[left].add(right)
        adjacency[right].add(left)

    pre_by_id = {
        member.strategy_id: member.pre_haircut_risk_sleeve for member in normalized_members
    }
    post_by_id = dict(pre_by_id)
    groups: list[CorrelatedGroupEvidence] = []
    visited: set[str] = set()
    haircut_applied_any = False

    for strategy_id in strategy_ids:
        if strategy_id in visited:
            continue
        stack = [strategy_id]
        component: list[str] = []
        while stack:
            current = stack.pop()
            if current in visited:
                continue
            visited.add(current)
            component.append(current)
            stack.extend(sorted(adjacency[current] - visited))

        ordered_component = tuple(sorted(component))
        if len(ordered_component) <= 1:
            continue
        pre_total = sum(pre_by_id[item] for item in ordered_component)
        haircut_scale = 1.0
        if pre_total > group_cap and pre_total > 0.0:
            haircut_scale = group_cap / pre_total
            for item in ordered_component:
                post_by_id[item] = pre_by_id[item] * haircut_scale
            haircut_applied_any = True
        groups.append(
            CorrelatedGroupEvidence(
                member_strategy_ids=ordered_component,
                pre_haircut_sleeve=pre_total,
                post_haircut_sleeve=sum(post_by_id[item] for item in ordered_component),
                group_cap=group_cap,
                haircut_scale=haircut_scale,
                haircut_applied=haircut_scale < 1.0,
            )
        )

    members_out = tuple(
        SyntheticComboMemberEvidence(
            strategy_id=member.strategy_id,
            target_weight=member.target_weight,
            combined_scale=member.combined_scale,
            pre_haircut_risk_sleeve=member.pre_haircut_risk_sleeve,
            post_haircut_risk_sleeve=post_by_id[member.strategy_id],
            haircut_applied=post_by_id[member.strategy_id] < member.pre_haircut_risk_sleeve,
        )
        for member in normalized_members
    )
    reasons = ["SYNTHETIC_COMBO_RESEARCH_ONLY"]
    if groups:
        reasons.append("CORRELATED_GROUPS_EVALUATED")
    if haircut_applied_any:
        reasons.append("CORRELATED_GROUP_CAP_APPLIED")
    combined_pre = sum(member.pre_haircut_risk_sleeve for member in members_out)
    combined_post = sum(member.post_haircut_risk_sleeve for member in members_out)
    return SyntheticComboEvidence(
        members=members_out,
        correlated_groups=tuple(groups),
        assumptions=tuple(assumptions),
        reason_codes=tuple(reasons),
        pre_haircut_combined_risk_sleeve=combined_pre,
        combined_risk_sleeve=combined_post,
        correlation_threshold=threshold,
        correlated_group_cap=group_cap,
        fail_closed=False,
    )


__all__ = [
    "DEFAULT_CORRELATED_GROUP_CAP",
    "DEFAULT_CORRELATION_THRESHOLD",
    "CorrelatedGroupEvidence",
    "PairwiseCorrelationEstimate",
    "SyntheticComboEvidence",
    "SyntheticComboMember",
    "SyntheticComboMemberEvidence",
    "evaluate_synthetic_combo_evidence",
]
