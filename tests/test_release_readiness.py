from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from quant_platform_kit.strategy_lifecycle.evidence_gate import EvidenceGateResult, EvidencePackage
from quant_platform_kit.strategy_lifecycle.release_readiness import (
    RELEASE_READINESS_DIAGNOSTIC_SCHEMA_VERSION,
    assess_strategy_release_readiness,
)


def _evidence_result(*, profile: str = "soxl_soxx_trend_income", revision: str = "a" * 40) -> EvidenceGateResult:
    package = EvidencePackage(
        strategy_profile=profile,
        domain="us_equity",
        requested_stage="paper_active",
        schema_version="strategy_evidence_package.v2",
        promotion_eligible=True,
        canonical_payload={"strategy": {"profile": profile, "source_revision": revision}},
    )
    return EvidenceGateResult(
        valid=True,
        package=package,
        promotion_eligible=True,
        promotion_status="PROMOTION_ELIGIBLE",
    )


def _readiness_kwargs(root: Path) -> dict[str, object]:
    config = root / "config.json"
    risk = root / "risk.py"
    evidence = root / "evidence.json"
    plugin = root / "plugin.json"
    for path, content in (
        (config, b"config"),
        (risk, b"risk"),
        (evidence, b"evidence"),
        (plugin, b"plugin"),
    ):
        path.write_bytes(content)
    return {
        "release_id": "soxl-p2-v3.20260825",
        "strategy_profile": "soxl_soxx_trend_income",
        "strategy_revision": "a" * 40,
        "effective_session": "2026-08-25",
        "target_set_id": "us-equity-soxl-paper-v1",
        "targets": ("longbridge:SG",),
        "config_path": config,
        "risk_policy_path": risk,
        "evidence_path": evidence,
        "plugin_bundle_paths": (plugin,),
    }


def test_ready_evidence_and_artifacts_build_an_immutable_manifest(tmp_path: Path) -> None:
    kwargs = _readiness_kwargs(tmp_path)
    with patch(
        "quant_platform_kit.strategy_lifecycle.release_readiness.validate_evidence_package_file",
        return_value=_evidence_result(),
    ):
        readiness = assess_strategy_release_readiness(**kwargs)

    manifest = readiness.build_manifest()

    assert readiness.is_ready
    assert manifest.release_id == "soxl-p2-v3.20260825"
    assert manifest.strategy_profile == "soxl_soxx_trend_income"
    assert len(manifest.plugin_bundle_sha256) == 64


def test_missing_evidence_refuses_manifest_and_emits_redacted_finding(tmp_path: Path) -> None:
    kwargs = _readiness_kwargs(tmp_path)
    Path(kwargs["evidence_path"]).unlink()

    readiness = assess_strategy_release_readiness(**kwargs)

    assert not readiness.is_ready
    assert readiness.findings == ("evidence_package_missing",)
    assert readiness.to_diagnostic() == {
        "schema_version": RELEASE_READINESS_DIAGNOSTIC_SCHEMA_VERSION,
        "release_id": "soxl-p2-v3.20260825",
        "strategy_profile": "soxl_soxx_trend_income",
        "strategy_revision": "a" * 40,
        "effective_session": "2026-08-25",
        "target_set_id": "us-equity-soxl-paper-v1",
        "targets": ["longbridge:SG"],
        "ready": False,
        "findings": ["evidence_package_missing"],
    }
    with pytest.raises(ValueError, match="evidence_package_missing"):
        readiness.build_manifest()


def test_mismatched_evidence_profile_and_revision_cannot_be_published(tmp_path: Path) -> None:
    kwargs = _readiness_kwargs(tmp_path)
    with patch(
        "quant_platform_kit.strategy_lifecycle.release_readiness.validate_evidence_package_file",
        return_value=_evidence_result(profile="tqqq_growth_income", revision="b" * 40),
    ):
        readiness = assess_strategy_release_readiness(**kwargs)

    assert not readiness.is_ready
    assert readiness.findings == ("evidence_profile_mismatch", "evidence_revision_mismatch")


def test_plugin_bundle_identity_is_content_based_not_workspace_based(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    first_kwargs = _readiness_kwargs(first)
    second_kwargs = _readiness_kwargs(second)
    with patch(
        "quant_platform_kit.strategy_lifecycle.release_readiness.validate_evidence_package_file",
        return_value=_evidence_result(),
    ):
        first_readiness = assess_strategy_release_readiness(**first_kwargs)
        second_readiness = assess_strategy_release_readiness(**second_kwargs)

    assert first_readiness.is_ready
    assert second_readiness.is_ready
    assert first_readiness.plugin_bundle_sha256 == second_readiness.plugin_bundle_sha256
