"""Evidence-bound release readiness for every strategy package.

This control-plane helper deliberately has no broker, scheduler, or deployment
dependency. It turns reviewed evidence plus immutable local artifacts into a
``StrategyReleaseManifest`` only when every required check succeeds.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

from quant_platform_kit.common.strategy_release import StrategyReleaseManifest
from quant_platform_kit.data.multisource_assurance import MultiSourceDailyBarAssurance

from .evidence_gate import validate_evidence_package_file


RELEASE_READINESS_DIAGNOSTIC_SCHEMA_VERSION = "strategy_release_readiness.v1"


def _append_unique(items: list[str], value: str) -> None:
    if value not in items:
        items.append(value)


def _sha256_file(path: Path, *, missing_finding: str, findings: list[str]) -> str | None:
    try:
        if not path.is_file():
            raise OSError("not a regular file")
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        _append_unique(findings, missing_finding)
        return None


def _plugin_bundle_sha256(paths: Iterable[str | Path], findings: list[str]) -> str | None:
    digests: list[str] = []
    for raw_path in paths:
        path = Path(raw_path)
        digest = _sha256_file(path, missing_finding="plugin_bundle_invalid", findings=findings)
        if digest is not None:
            digests.append(digest)
    if not digests:
        _append_unique(findings, "plugin_bundle_missing")
        return None
    # The release identity must remain stable when the identical approved
    # bundle is materialized in a different workspace or runtime filesystem.
    # Paths also have no place in a content identity and can reveal topology.
    payload = json.dumps(sorted(digests), ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class StrategyReleaseReadiness:
    """Redacted result of preparing a promotion-capable strategy release."""

    release_id: str
    strategy_profile: str
    strategy_revision: str
    effective_session: str
    target_set_id: str
    targets: tuple[str, ...]
    config_sha256: str | None
    risk_policy_sha256: str | None
    evidence_sha256: str | None
    plugin_bundle_sha256: str | None
    findings: tuple[str, ...] = ()
    data_assurance_sha256: str | None = None

    @property
    def is_ready(self) -> bool:
        return not self.findings

    def to_diagnostic(self) -> dict[str, object]:
        """Return safe monitoring data without paths, content, or raw evidence."""

        diagnostic = {
            "schema_version": RELEASE_READINESS_DIAGNOSTIC_SCHEMA_VERSION,
            "release_id": self.release_id,
            "strategy_profile": self.strategy_profile,
            "strategy_revision": self.strategy_revision,
            "effective_session": self.effective_session,
            "target_set_id": self.target_set_id,
            "targets": list(self.targets),
            "ready": self.is_ready,
            "findings": list(self.findings),
        }
        if self.data_assurance_sha256 is not None:
            diagnostic["data_assurance_sha256"] = self.data_assurance_sha256
        return diagnostic

    def build_manifest(self) -> StrategyReleaseManifest:
        """Return an immutable manifest, or refuse to create one when blocked."""

        if not self.is_ready:
            raise ValueError("strategy release is not ready: " + ", ".join(self.findings))
        if None in (
            self.config_sha256,
            self.risk_policy_sha256,
            self.evidence_sha256,
            self.plugin_bundle_sha256,
        ):
            raise ValueError("strategy release is not ready: artifact digest missing")
        return StrategyReleaseManifest(
            release_id=self.release_id,
            strategy_profile=self.strategy_profile,
            strategy_revision=self.strategy_revision,
            config_sha256=self.config_sha256,
            risk_policy_sha256=self.risk_policy_sha256,
            evidence_sha256=self.evidence_sha256,
            plugin_bundle_sha256=self.plugin_bundle_sha256,
            effective_session=self.effective_session,
            target_set_id=self.target_set_id,
            targets=self.targets,
            data_assurance_sha256=self.data_assurance_sha256,
        )


def assess_strategy_release_readiness(
    *,
    release_id: object,
    strategy_profile: object,
    strategy_revision: object,
    effective_session: object,
    target_set_id: object,
    targets: tuple[str, ...] | list[str],
    config_path: str | Path,
    risk_policy_path: str | Path,
    evidence_path: str | Path,
    plugin_bundle_paths: Iterable[str | Path],
    data_assurance: MultiSourceDailyBarAssurance | None = None,
    require_data_assurance: bool = False,
) -> StrategyReleaseReadiness:
    """Assess whether a strategy can receive a loadable release identity.

    The evidence package must be structurally valid, explicitly promotion
    eligible, and bound to the same strategy profile and source revision. A
    failed assessment is useful monitoring output but cannot create a manifest.
    Source-sensitive profiles can additionally require a verified multi-source
    data report; existing profiles stay compatible until they opt in.
    """

    findings: list[str] = []
    release_text = str(release_id or "").strip()
    profile_text = str(strategy_profile or "").strip()
    revision_text = str(strategy_revision or "").strip()
    session_text = str(effective_session or "").strip()
    target_set_text = str(target_set_id or "").strip()
    target_values = tuple(str(target).strip() for target in targets)

    config_sha256 = _sha256_file(
        Path(config_path),
        missing_finding="config_artifact_missing",
        findings=findings,
    )
    risk_policy_sha256 = _sha256_file(
        Path(risk_policy_path),
        missing_finding="risk_policy_artifact_missing",
        findings=findings,
    )
    plugin_bundle_sha256 = _plugin_bundle_sha256(plugin_bundle_paths, findings)
    data_assurance_sha256: str | None = None
    if data_assurance is None:
        if require_data_assurance:
            _append_unique(findings, "data_assurance_missing")
    elif not isinstance(data_assurance, MultiSourceDailyBarAssurance):
        _append_unique(findings, "data_assurance_invalid")
    elif not data_assurance.can_publish_research_input:
        _append_unique(findings, "data_assurance_not_verified")
    else:
        data_assurance_sha256 = data_assurance.report_sha256

    evidence_file = Path(evidence_path)
    evidence_sha256 = _sha256_file(
        evidence_file,
        missing_finding="evidence_package_missing",
        findings=findings,
    )
    if evidence_sha256 is not None:
        try:
            evidence = validate_evidence_package_file(evidence_file)
        except ValueError:
            _append_unique(findings, "evidence_package_invalid")
        else:
            if not evidence.valid:
                _append_unique(findings, "evidence_package_invalid")
            if not evidence.promotion_eligible:
                _append_unique(findings, "evidence_not_promotion_eligible")
            if evidence.package.strategy_profile != profile_text:
                _append_unique(findings, "evidence_profile_mismatch")
            canonical = evidence.package.canonical_payload
            strategy = canonical.get("strategy") if isinstance(canonical, Mapping) else None
            evidence_revision = strategy.get("source_revision") if isinstance(strategy, Mapping) else None
            if str(evidence_revision or "").strip() != revision_text:
                _append_unique(findings, "evidence_revision_mismatch")

    # Constructing a provisional manifest validates release metadata and target
    # shape without ever returning it when evidence or artifact checks fail.
    try:
        StrategyReleaseManifest(
            release_id=release_text,
            strategy_profile=profile_text,
            strategy_revision=revision_text,
            config_sha256=config_sha256 or "0" * 64,
            risk_policy_sha256=risk_policy_sha256 or "0" * 64,
            evidence_sha256=evidence_sha256 or "0" * 64,
            plugin_bundle_sha256=plugin_bundle_sha256 or "0" * 64,
            effective_session=session_text,
            target_set_id=target_set_text,
            targets=target_values,
            data_assurance_sha256=data_assurance_sha256,
        )
    except ValueError:
        _append_unique(findings, "release_metadata_invalid")

    return StrategyReleaseReadiness(
        release_id=release_text,
        strategy_profile=profile_text,
        strategy_revision=revision_text,
        effective_session=session_text,
        target_set_id=target_set_text,
        targets=target_values,
        config_sha256=config_sha256,
        risk_policy_sha256=risk_policy_sha256,
        evidence_sha256=evidence_sha256,
        plugin_bundle_sha256=plugin_bundle_sha256,
        findings=tuple(findings),
        data_assurance_sha256=data_assurance_sha256,
    )


__all__ = [
    "RELEASE_READINESS_DIAGNOSTIC_SCHEMA_VERSION",
    "StrategyReleaseReadiness",
    "assess_strategy_release_readiness",
]
