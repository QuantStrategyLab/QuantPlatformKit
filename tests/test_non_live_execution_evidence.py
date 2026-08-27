from __future__ import annotations

import copy
import json

import pytest

from quant_platform_kit.common.runtime_reports import build_runtime_report_base
from quant_platform_kit.common.runtime_target import (
    RuntimeExecutionEnvironment,
    build_runtime_target,
)
from quant_platform_kit.common.strategy_release import build_strategy_release_identity
from quant_platform_kit.strategy_lifecycle.forward_observation import (
    ForwardObservationPolicy,
)
from quant_platform_kit.strategy_lifecycle.forward_observation_receipt import (
    FORWARD_OBSERVATION_DEPENDENCY_DIGESTS,
    build_forward_observation_receipt,
)
from quant_platform_kit.strategy_lifecycle.non_live_execution_evidence import (
    NON_LIVE_EXECUTION_EVIDENCE_BINDING_SCHEMA_VERSION,
    InvalidNonLiveExecutionEvidenceBinding,
    build_non_live_execution_evidence_binding,
    build_non_live_execution_evidence_report_artifacts,
    build_paired_shadow_execution_evidence_binding,
    canonical_non_live_execution_evidence_binding_bytes,
    non_live_execution_evidence_binding_sha256,
    non_live_runtime_scope_sha256,
    validate_non_live_execution_evidence_binding,
)
from quant_platform_kit.strategy_lifecycle.paired_shadow_evidence import (
    build_paired_shadow_evidence,
)


def _policy(**changes: object) -> ForwardObservationPolicy:
    values: dict[str, object] = {
        "candidate_id": "soxl-v7-volatility-budget",
        "strategy_profile": "soxl_tactical",
        "domain": "us_equity",
        "benchmark_symbol": "SOXX",
        "required_trading_sessions": 63,
        "review_milestones": (15, 42),
        "automatic_non_live_modes": ("shadow", "paper"),
        "auto_resume_clean_sessions": 2,
        "observation_calendar": "XNYS",
        "observation_window_type": "fixed",
        "observation_start_session": "2026-08-26",
        "window_rationale_ref": "sha256:soxl-v7-forward-window-rationale",
        "non_live_evidence_modes": ("shadow_decision", "simulated_replay"),
    }
    values.update(changes)
    return ForwardObservationPolicy(**values)  # type: ignore[arg-type]


def _release() -> dict[str, str]:
    return {
        "release_id": "soxl-v7.20260826",
        "manifest_sha256": "a" * 64,
        "strategy_revision": "soxl-v7",
        "config_sha256": "b" * 64,
        "risk_policy_sha256": "c" * 64,
        "evidence_sha256": "d" * 64,
        "plugin_bundle_sha256": "e" * 64,
        "effective_session": "2026-08-26",
    }


def _dependencies() -> dict[str, str]:
    release = _release()
    dependencies = {
        "p1_manifest": "f" * 64,
        "p2_config": release["config_sha256"],
        "p3_evidence": release["evidence_sha256"],
        "risk_policy": release["risk_policy_sha256"],
        "strategy_release": release["manifest_sha256"],
        "plugin_bundle": release["plugin_bundle_sha256"],
    }
    assert set(dependencies) == FORWARD_OBSERVATION_DEPENDENCY_DIGESTS
    return dependencies


def _receipt(*, policy: ForwardObservationPolicy | None = None) -> dict[str, object]:
    active_policy = policy or _policy()
    return build_forward_observation_receipt(
        policy=active_policy,
        observation_session="2026-08-26",
        observation_index=1,
        dependency_digests=_dependencies(),
        evidence_modes=active_policy.non_live_evidence_modes,
    )


def _leg(source: str) -> dict[str, object]:
    return {
        "signal": {"source": source},
        "hypothetical_order": {"source": source},
        "position": {"source": source},
        "cost": {"source": source},
        "return": {"source": source},
    }


def _paired_evidence(*, receipt: dict[str, object] | None = None) -> dict[str, object]:
    active_receipt = receipt or _receipt()
    return build_paired_shadow_evidence(
        policy=_policy(),
        forward_observation_receipt=active_receipt,
        baseline_id="soxl-v6-baseline",
        observed_at="2026-08-26T20:00:00-04:00",
        input_snapshot_sha256="9" * 64,
        candidate=_leg("candidate"),
        baseline=_leg("baseline"),
    )


def _binding(**changes: object) -> dict[str, object]:
    receipt = _receipt()
    values: dict[str, object] = {
        "policy": _policy(),
        "forward_observation_receipt": receipt,
        "candidate_subject": "strategy",
        "candidate_revision_sha256": "7" * 64,
        "platform_id": "longbridge_sg",
        "runtime_scope_sha256": "8" * 64,
        "platform_adapter_sha256": "6" * 64,
        "execution_channel": "shadow",
        "strategy_release": _release(),
        "non_live_evidence_schema_version": "shadow_observation.v1",
        "non_live_evidence_sha256": "5" * 64,
    }
    values.update(changes)
    return build_non_live_execution_evidence_binding(**values)  # type: ignore[arg-type]


def test_generic_binding_joins_candidate_platform_channel_and_release_identity() -> None:
    binding = _binding()

    assert binding["schema_version"] == NON_LIVE_EXECUTION_EVIDENCE_BINDING_SCHEMA_VERSION
    assert binding["candidate_subject"] == "strategy"
    assert binding["platform_id"] == "longbridge_sg"
    assert binding["execution_channel"] == "shadow"
    assert binding["strategy_release"] == _release()
    assert binding["no_order"] is True
    assert binding["live_authority_granted"] is False
    assert non_live_execution_evidence_binding_sha256(binding) == binding["binding_sha256"]
    assert canonical_non_live_execution_evidence_binding_bytes(binding)
    assert (
        validate_non_live_execution_evidence_binding(
            binding,
            policy=_policy(),
            forward_observation_receipt=_receipt(),
            strategy_release=_release(),
        )
        == binding
    )
    serialized = json.dumps(binding, sort_keys=True)
    assert "account_selector" not in serialized
    assert "service_name" not in serialized


def test_generic_binding_accepts_the_shared_release_identity_object() -> None:
    binding = _binding(strategy_release=build_strategy_release_identity(_release()))

    assert binding["strategy_release"] == _release()


def test_runtime_scope_digest_is_opaque_stable_and_target_bound() -> None:
    target = build_runtime_target(
        platform_id="longbridge_sg",
        strategy_profile="soxl_tactical",
        dry_run_only=True,
        deployment_selector="sg",
        account_selector=("paper_scope",),
        account_scope="sg_paper",
        service_name="longbridge-shadow-observer",
    )
    changed_target = build_runtime_target(
        platform_id="longbridge_sg",
        strategy_profile="soxl_tactical",
        dry_run_only=True,
        deployment_selector="sg",
        account_selector=("different_scope",),
        account_scope="sg_paper",
        service_name="longbridge-shadow-observer",
    )

    first = non_live_runtime_scope_sha256(
        runtime_target=target, execution_channel="shadow"
    )
    assert first == non_live_runtime_scope_sha256(
        runtime_target=target, execution_channel="shadow"
    )
    assert first != non_live_runtime_scope_sha256(
        runtime_target=changed_target, execution_channel="shadow"
    )
    assert len(first) == 64
    assert "paper_scope" not in first


def test_runtime_scope_rejects_live_or_ambiguous_shadow_targets() -> None:
    live_target = build_runtime_target(
        platform_id="longbridge_sg",
        strategy_profile="soxl_tactical",
        dry_run_only=False,
        deployment_selector="sg",
    )
    paper_target = build_runtime_target(
        platform_id="longbridge_sg",
        strategy_profile="soxl_tactical",
        dry_run_only=False,
        deployment_selector="sg",
        execution_environment=RuntimeExecutionEnvironment.PAPER,
    )
    unscoped_shadow_target = build_runtime_target(
        platform_id="longbridge_sg",
        strategy_profile="soxl_tactical",
        dry_run_only=True,
    )

    with pytest.raises(InvalidNonLiveExecutionEvidenceBinding, match="live execution"):
        non_live_runtime_scope_sha256(
            runtime_target=live_target, execution_channel="paper"
        )
    with pytest.raises(InvalidNonLiveExecutionEvidenceBinding, match="dry_run"):
        non_live_runtime_scope_sha256(
            runtime_target=paper_target, execution_channel="shadow"
        )
    assert len(
        non_live_runtime_scope_sha256(
            runtime_target=paper_target, execution_channel="paper"
        )
    ) == 64
    with pytest.raises(InvalidNonLiveExecutionEvidenceBinding, match="scope selector"):
        non_live_runtime_scope_sha256(
            runtime_target=unscoped_shadow_target, execution_channel="shadow"
        )


@pytest.mark.parametrize("candidate_subject", ("strategy", "portfolio", "plugin_composite"))
def test_generic_binding_supports_each_candidate_shape(candidate_subject: str) -> None:
    assert _binding(candidate_subject=candidate_subject)["candidate_subject"] == candidate_subject


def test_paired_shadow_helper_verifies_current_evidence_and_report_attachment() -> None:
    receipt = _receipt()
    evidence = _paired_evidence(receipt=receipt)
    binding = build_paired_shadow_execution_evidence_binding(
        policy=_policy(),
        forward_observation_receipt=receipt,
        paired_shadow_evidence=evidence,
        candidate_subject="plugin_composite",
        candidate_revision_sha256="7" * 64,
        platform_id="longbridge_sg",
        runtime_scope_sha256="8" * 64,
        platform_adapter_sha256="6" * 64,
        strategy_release=_release(),
    )
    artifacts = build_non_live_execution_evidence_report_artifacts(
        binding,
        policy=_policy(),
        forward_observation_receipt=receipt,
        strategy_release=_release(),
        paired_shadow_evidence=evidence,
    )
    report = build_runtime_report_base(
        platform="longbridge",
        deploy_target="non-live",
        service_name="shadow-observer",
        strategy_profile="soxl_tactical",
        run_id="shadow-001",
        run_source="shadow",
        dry_run=True,
        artifacts=artifacts,
    )

    assert binding["execution_channel"] == "shadow"
    assert binding["non_live_evidence_ref"]["sha256"] == evidence[
        "paired_shadow_evidence_sha256"
    ]
    assert json.loads(artifacts["non_live_execution_evidence_binding_json"]) == binding
    assert artifacts["non_live_execution_evidence_binding_no_order"] is True
    assert artifacts["non_live_execution_evidence_binding_live_authority_granted"] is False
    assert report["runtime_target"] == {}


def test_binding_fails_closed_for_release_or_channel_mismatches() -> None:
    changed_release = copy.deepcopy(_release())
    changed_release["config_sha256"] = "0" * 64
    with pytest.raises(InvalidNonLiveExecutionEvidenceBinding, match="frozen receipt"):
        _binding(strategy_release=changed_release)

    shadow_only = _policy(
        automatic_non_live_modes=("shadow",),
        non_live_evidence_modes=("shadow_decision",),
    )
    with pytest.raises(InvalidNonLiveExecutionEvidenceBinding, match="not enabled"):
        _binding(
            policy=shadow_only,
            forward_observation_receipt=_receipt(policy=shadow_only),
            execution_channel="paper",
        )


def test_paired_shadow_proof_rejects_an_unrelated_evidence_digest() -> None:
    receipt = _receipt()
    evidence = _paired_evidence(receipt=receipt)
    binding = _binding(
        forward_observation_receipt=receipt,
        non_live_evidence_schema_version="paired_shadow_evidence.v1",
        non_live_evidence_sha256="0" * 64,
    )

    with pytest.raises(InvalidNonLiveExecutionEvidenceBinding, match="does not match evidence reference"):
        validate_non_live_execution_evidence_binding(
            binding,
            policy=_policy(),
            forward_observation_receipt=receipt,
            strategy_release=_release(),
            paired_shadow_evidence=evidence,
        )
