"""Evidence package validation for lifecycle promotion requests."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from quant_platform_kit.common.strategy_plugins import (
    STRATEGY_PLUGIN_DIRECT_POSITION_CONTROL_ALLOWED,
)

from .evidence_package_v2 import (
    SUPPORTED_STRATEGY_EVIDENCE_PACKAGE_SCHEMA_VERSIONS,
    read_evidence_package_v2_json,
    validate_strategy_evidence_payload,
)

ALLOWED_EVIDENCE_STAGES = (
    "research_active",
    "shadow_active",
    "paper_active",
    "live_enabled",
    "research_backtest_only",
    "ai_monitored_candidate",
    "shadow_candidate",
    "live_candidate",
    "runtime_enabled",
)
LIVE_EVIDENCE_STAGES = {"live_candidate", "live_enabled", "runtime_enabled"}
ALLOWED_PLUGIN_GATE_STATUSES = {
    "automation_approved",
    "deprecated_compatibility",
    "notification_only",
    "research_only",
    "shadow_observer",
}


@dataclass(frozen=True)
class EvidencePackage:
    strategy_profile: str
    domain: str
    requested_stage: str
    target_platforms: tuple[str, ...] = ()
    backtest_summary: Mapping[str, Any] = field(default_factory=dict)
    drift_notes: Any = None
    platform_compatibility: Mapping[str, Any] | None = None
    plugin_gate: Any = None
    rollout_notes: Any = None
    operator_notes: Any = None
    evidence_version: str = "evidence_package.v1"
    submitted_at: str = ""

    # Appended defaults preserve every legacy positional argument above.
    schema_version: str = ""
    promotion_eligible: bool = False
    live_ready: bool = False
    size_zero_required: bool = True
    no_order: bool = True
    promotion_status: str = "LEGACY_RESEARCH_ONLY"
    canonical_payload: Mapping[str, Any] = field(default_factory=dict, repr=False)

    def to_dict(self) -> dict[str, object]:
        if (
            self.schema_version in SUPPORTED_STRATEGY_EVIDENCE_PACKAGE_SCHEMA_VERSIONS
            and self.canonical_payload
        ):
            return dict(self.canonical_payload)
        return {
            "strategy_profile": self.strategy_profile,
            "domain": self.domain,
            "requested_stage": self.requested_stage,
            "target_platforms": list(self.target_platforms),
            "backtest_summary": dict(self.backtest_summary),
            "drift_notes": self.drift_notes,
            "platform_compatibility": self.platform_compatibility,
            "plugin_gate": self.plugin_gate,
            "rollout_notes": self.rollout_notes,
            "operator_notes": self.operator_notes,
            "evidence_version": self.evidence_version,
            "submitted_at": self.submitted_at,
        }


@dataclass(frozen=True)
class EvidenceGateResult:
    valid: bool
    package: EvidencePackage
    issues: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    # Appended defaults preserve every legacy positional argument above.
    promotion_eligible: bool = False
    live_ready: bool = False
    size_zero_required: bool = True
    no_order: bool = True
    promotion_status: str = "LEGACY_RESEARCH_ONLY"

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "valid": self.valid,
            "issues": list(self.issues),
            "warnings": list(self.warnings),
            "package": self.package.to_dict(),
        }
        if (
            self.package.schema_version
            in SUPPORTED_STRATEGY_EVIDENCE_PACKAGE_SCHEMA_VERSIONS
        ):
            payload.update(
                {
                    "promotion_eligible": self.promotion_eligible,
                    "live_ready": self.live_ready,
                    "size_zero_required": self.size_zero_required,
                    "no_order": self.no_order,
                    "promotion_status": self.promotion_status,
                }
            )
        return payload


def load_evidence_package(path: str | Path) -> dict[str, Any]:
    evidence_path = Path(path)
    suffix = evidence_path.suffix.lower()
    if suffix == ".json":
        payload = read_evidence_package_v2_json(evidence_path)
    elif suffix == ".toml":
        raw = evidence_path.read_text(encoding="utf-8")
        payload = tomllib.loads(raw)
    else:
        raise ValueError(
            f"Unsupported evidence package format: {evidence_path.suffix or '<none>'}"
        )
    if not isinstance(payload, dict):
        raise ValueError("Evidence package must decode to a mapping")
    return payload


def validate_evidence_package(
    raw: Mapping[str, Any], *, base_dir: str | Path | None = None
) -> EvidenceGateResult:
    if (
        raw.get("schema_version") != "strategy_evidence_package.v1"
        and str(raw.get("schema_version", "")).startswith("strategy_evidence_package.")
    ):
        return _validate_canonical_evidence_package(raw, base_dir=base_dir)

    issues: list[str] = []
    warnings: list[str] = []

    strategy_profile = _first_str(raw, "strategy_profile", "profile")
    domain = _first_str(raw, "domain", "market")
    requested_stage = _first_str(raw, "requested_stage", "stage")
    target_platforms = _normalize_platforms(
        _first_value(
            raw, "target_platforms", "platforms", "target_platform", "runtime_targets"
        )
    )
    backtest_summary = _first_mapping(raw, "backtest_summary", "backtest", "evidence")
    drift_notes = _first_value(raw, "drift_notes", "drift", "regime_notes")
    platform_compatibility = _first_mapping(
        raw,
        "platform_compatibility",
        "compatibility",
        "platform_evidence",
    )
    plugin_gate = _first_value(raw, "plugin_gate", "plugin_gates", "plugins")
    rollout_notes = _first_value(raw, "rollout_notes", "rollout", "operator_notes")
    evidence_version = str(
        _first_value(raw, "evidence_version", "schema", default="evidence_package.v1")
        or "evidence_package.v1"
    )
    submitted_at = str(
        _first_value(raw, "submitted_at", "generated_at", "created_at", default="")
        or ""
    )

    if not strategy_profile:
        issues.append("missing strategy_profile/profile")
    if not domain:
        issues.append("missing domain/market")
    if requested_stage not in ALLOWED_EVIDENCE_STAGES:
        issues.append(f"unsupported requested_stage: {requested_stage!r}")
    if not backtest_summary:
        issues.append("missing backtest_summary")
    elif not _backtest_summary_has_evidence(backtest_summary):
        issues.append("backtest_summary missing core metrics or observation count")

    if requested_stage in LIVE_EVIDENCE_STAGES:
        if not target_platforms:
            issues.append("live request requires target_platforms/platforms")
        if not _is_non_empty(drift_notes):
            issues.append("live request requires drift_notes")
        if not platform_compatibility:
            issues.append("live request requires platform_compatibility evidence")
        elif not _platform_compatibility_is_usable(platform_compatibility):
            issues.append("platform_compatibility evidence is incomplete")
        if plugin_gate is not None and not _plugin_gate_is_usable(plugin_gate):
            issues.append("plugin_gate evidence is incomplete or unsupported")

    if requested_stage in {
        "research_active",
        "research_backtest_only",
        "ai_monitored_candidate",
    } and not _is_non_empty(rollout_notes):
        warnings.append("rollout_notes is recommended for candidates")

    package = EvidencePackage(
        strategy_profile=str(strategy_profile or ""),
        domain=str(domain or ""),
        requested_stage=str(requested_stage or ""),
        target_platforms=target_platforms,
        backtest_summary=backtest_summary,
        drift_notes=drift_notes,
        platform_compatibility=platform_compatibility,
        plugin_gate=plugin_gate,
        rollout_notes=rollout_notes,
        operator_notes=_first_value(raw, "operator_notes", "notes"),
        evidence_version=evidence_version,
        submitted_at=submitted_at,
    )
    return EvidenceGateResult(
        valid=not issues,
        package=package,
        issues=tuple(issues),
        warnings=tuple(warnings),
        promotion_eligible=False,
        live_ready=False,
        size_zero_required=True,
        no_order=True,
        promotion_status="LEGACY_RESEARCH_ONLY",
    )


def validate_evidence_package_file(path: str | Path) -> EvidenceGateResult:
    evidence_path = Path(path)
    return validate_evidence_package(
        load_evidence_package(evidence_path), base_dir=evidence_path.parent
    )


def _validate_canonical_evidence_package(
    raw: Mapping[str, Any], *, base_dir: str | Path | None
) -> EvidenceGateResult:
    issues = validate_strategy_evidence_payload(
        raw, base_dir=Path(base_dir) if base_dir is not None else None
    )
    strategy = raw.get("strategy")
    claims = raw.get("lifecycle_claims")
    acceptance = raw.get("human_acceptance")
    strategy_mapping = strategy if isinstance(strategy, Mapping) else {}
    claims_mapping = claims if isinstance(claims, Mapping) else {}
    acceptance_mapping = acceptance if isinstance(acceptance, Mapping) else {}
    promotion_eligible = claims_mapping.get("promotion_eligible") is True and not issues
    learning_only = claims_mapping.get("learning_only") is True
    if issues:
        promotion_status = "INVALID"
    elif learning_only:
        promotion_status = "LEARNING_ONLY"
    elif promotion_eligible:
        promotion_status = "PROMOTION_ELIGIBLE"
    elif acceptance_mapping.get("decision") != "ACCEPTED":
        promotion_status = "HUMAN_REQUIRED"
    else:
        promotion_status = "STRUCTURALLY_COMPLETE"
    package = EvidencePackage(
        strategy_profile=str(strategy_mapping.get("profile") or ""),
        domain=str(strategy_mapping.get("domain") or ""),
        requested_stage=str(raw.get("requested_stage") or ""),
        backtest_summary=raw.get("metrics")
        if isinstance(raw.get("metrics"), Mapping)
        else {},
        operator_notes=acceptance,
        evidence_version=str(raw.get("schema_version") or ""),
        submitted_at=str(raw.get("generated_at") or ""),
        schema_version=str(raw.get("schema_version") or ""),
        promotion_eligible=promotion_eligible,
        live_ready=False,
        size_zero_required=True,
        no_order=True,
        promotion_status=promotion_status,
        canonical_payload=dict(raw),
    )
    return EvidenceGateResult(
        valid=not issues,
        package=package,
        issues=tuple(issues),
        promotion_eligible=promotion_eligible,
        live_ready=False,
        size_zero_required=True,
        no_order=True,
        promotion_status=promotion_status,
    )


def _first_value(raw: Mapping[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in raw and raw[key] is not None:
            return raw[key]
    return default


def _first_mapping(raw: Mapping[str, Any], *keys: str) -> Mapping[str, Any]:
    value = _first_value(raw, *keys)
    return value if isinstance(value, Mapping) else {}


def _first_str(raw: Mapping[str, Any], *keys: str) -> str:
    value = _first_value(raw, *keys)
    return str(value).strip() if value is not None else ""


def _normalize_platforms(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        items = [value]
    elif isinstance(value, (list, tuple, set, frozenset)):
        items = list(value)
    else:
        items = [value]
    return tuple(str(item).strip() for item in items if str(item).strip())


def _is_non_empty(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, Mapping):
        return bool(value)
    if isinstance(value, (list, tuple, set, frozenset)):
        return bool(value)
    return True


def _backtest_summary_has_evidence(summary: Mapping[str, Any]) -> bool:
    if not summary:
        return False
    if summary.get("observation_count") not in (None, "", 0):
        return True
    if _is_non_empty(summary.get("windows")):
        return True
    for key in ("cagr", "sharpe_ratio", "total_return", "max_drawdown"):
        if summary.get(key) not in (None, ""):
            return True
    return False


def _platform_compatibility_is_usable(compatibility: Mapping[str, Any]) -> bool:
    if not compatibility:
        return False
    if any(
        bool(compatibility.get(key))
        for key in ("verified", "compatible", "supported", "enabled")
    ):
        return True
    if _is_non_empty(compatibility.get("runtime_enabled_profiles")):
        return True
    if _is_non_empty(compatibility.get("target_platforms")):
        return True
    return False


def _plugin_gate_is_usable(plugin_gate: Any) -> bool:
    if isinstance(plugin_gate, Mapping):
        status = (
            str(plugin_gate.get("status") or plugin_gate.get("evidence_status") or "")
            .strip()
            .lower()
        )
        if status and status not in ALLOWED_PLUGIN_GATE_STATUSES:
            return False
        if status == "automation_approved":
            return bool(
                STRATEGY_PLUGIN_DIRECT_POSITION_CONTROL_ALLOWED
                and plugin_gate.get("position_control_allowed", False)
            )
        return True
    if isinstance(plugin_gate, (list, tuple)):
        return all(_plugin_gate_is_usable(item) for item in plugin_gate)
    return False
