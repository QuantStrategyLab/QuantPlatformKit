"""Immutable platform/channel bindings for non-live lifecycle evidence.

Forward-observation receipts prove that a frozen candidate was observed.
Strategy-release identities prove which strategy, risk, evidence and plugin
bundle a runtime loaded.  This module joins those two facts with a *single*
platform runtime scope and a non-live channel.  It deliberately contains no
account identifier, broker client, runtime target, storage implementation or
execution instruction.

The generic binding stores an evidence identity only, so later paper adapters
can use their own verified evidence schema.  The paired-shadow helper validates
the currently available ``paired_shadow_evidence.v1`` object before building
the generic binding.
"""

from __future__ import annotations

from collections.abc import Mapping
from hashlib import sha256
import json
import re

from quant_platform_kit.common.strategy_release import (
    StrategyReleaseIdentity,
    build_strategy_release_identity,
)
from quant_platform_kit.common.runtime_target import (
    RuntimeExecutionEnvironment,
    RuntimeTarget,
)

from .forward_observation import ForwardObservationPolicy
from .forward_observation_receipt import (
    forward_observation_receipt_sha256,
    validate_forward_observation_receipt,
)
from .paired_shadow_evidence import (
    PAIRED_SHADOW_EVIDENCE_SCHEMA_VERSION,
    paired_shadow_evidence_sha256,
    validate_paired_shadow_evidence,
)


NON_LIVE_EXECUTION_EVIDENCE_BINDING_SCHEMA_VERSION = (
    "non_live_execution_evidence_binding.v1"
)
NON_LIVE_RUNTIME_SCOPE_SCHEMA_VERSION = "non_live_runtime_scope.v1"
NON_LIVE_CANDIDATE_SUBJECTS = frozenset(
    {"strategy", "portfolio", "plugin_composite"}
)
NON_LIVE_EXECUTION_CHANNELS = frozenset({"shadow", "paper"})

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_PLATFORM_ID = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$")
_EVIDENCE_SCHEMA_VERSION = re.compile(r"^[a-z][a-z0-9_.-]{0,127}$")
_TOP_LEVEL_FIELDS = frozenset(
    {
        "schema_version",
        "candidate_id",
        "candidate_subject",
        "candidate_revision_sha256",
        "platform_id",
        "runtime_scope_sha256",
        "platform_adapter_sha256",
        "execution_channel",
        "strategy_release",
        "forward_observation_receipt_sha256",
        "non_live_evidence_ref",
        "no_order",
        "live_authority_granted",
        "binding_sha256",
    }
)
_EVIDENCE_REF_FIELDS = frozenset({"schema_version", "sha256"})


class InvalidNonLiveExecutionEvidenceBinding(ValueError):
    """Raised when a non-live evidence binding cannot be trusted."""


def _invalid(message: str) -> None:
    raise InvalidNonLiveExecutionEvidenceBinding(message)


def _canonical_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise InvalidNonLiveExecutionEvidenceBinding(
            "binding must contain only canonical JSON values"
        ) from exc


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        _invalid(f"{field} must be a non-empty string")
    if any(ord(character) < 0x20 or ord(character) == 0x7F for character in value):
        _invalid(f"{field} contains a control character")
    return value.strip()


def _digest(value: object, field: str) -> str:
    text = _text(value, field)
    if _SHA256.fullmatch(text) is None:
        _invalid(f"{field} must be a lowercase SHA-256 digest")
    return text


def _platform(value: object) -> str:
    platform = _text(value, "platform_id").lower()
    if _PLATFORM_ID.fullmatch(platform) is None:
        _invalid("platform_id must be a lowercase scoped identifier")
    return platform


def _candidate_subject(value: object) -> str:
    subject = _text(value, "candidate_subject").lower()
    if subject not in NON_LIVE_CANDIDATE_SUBJECTS:
        _invalid("candidate_subject must be strategy, portfolio, or plugin_composite")
    return subject


def _channel(value: object) -> str:
    channel = _text(value, "execution_channel").lower()
    if channel not in NON_LIVE_EXECUTION_CHANNELS:
        _invalid("execution_channel must be shadow or paper")
    return channel


def _scope_component(value: object, field: str) -> str | None:
    if value is None:
        return None
    text = _text(value, field)
    return text


def non_live_runtime_scope_sha256(
    *, runtime_target: RuntimeTarget, execution_channel: str
) -> str:
    """Derive an opaque scope identity from one non-live runtime target.

    The returned digest is the only value suitable for a durable non-live
    evidence binding.  Selectors are deliberately used only as hash material:
    the function never returns them, logs them, or attaches them to a report.
    A funded ``live`` target cannot be converted into non-live evidence.
    """

    if not isinstance(runtime_target, RuntimeTarget):
        _invalid("runtime_target must be a RuntimeTarget")
    channel = _channel(execution_channel)
    environment = runtime_target.execution_environment
    if environment is RuntimeExecutionEnvironment.LIVE:
        _invalid("non-live runtime scope cannot use a live execution target")
    if (
        channel == "shadow"
        and environment is not RuntimeExecutionEnvironment.DRY_RUN
    ):
        _invalid("shadow runtime scope requires a dry_run execution target")
    platform = _platform(runtime_target.platform_id)
    account_selector = tuple(
        _scope_component(value, "runtime_target.account_selector[]")
        for value in runtime_target.account_selector
    )
    material = {
        "schema_version": NON_LIVE_RUNTIME_SCOPE_SCHEMA_VERSION,
        "platform_id": platform,
        "execution_channel": channel,
        "execution_environment": environment.value,
        "deployment_selector": _scope_component(
            runtime_target.deployment_selector,
            "runtime_target.deployment_selector",
        ),
        "account_scope": _scope_component(
            runtime_target.account_scope, "runtime_target.account_scope"
        ),
        "account_selector": list(account_selector),
        "service_name": _scope_component(
            runtime_target.service_name, "runtime_target.service_name"
        ),
    }
    if not any(
        (
            material["deployment_selector"],
            material["account_scope"],
            material["account_selector"],
            material["service_name"],
        )
    ):
        _invalid("runtime_target needs an explicit non-live scope selector")
    return sha256(_canonical_bytes(material)).hexdigest()


def _strategy_release(value: object) -> StrategyReleaseIdentity:
    if isinstance(value, StrategyReleaseIdentity):
        return value
    if not isinstance(value, Mapping):
        _invalid("strategy_release must be a closed release identity")
    expected = {
        "release_id",
        "manifest_sha256",
        "strategy_revision",
        "config_sha256",
        "risk_policy_sha256",
        "evidence_sha256",
        "plugin_bundle_sha256",
        "effective_session",
    }
    if set(value) != expected:
        _invalid("strategy_release must be a closed release identity")
    try:
        return build_strategy_release_identity(value)
    except ValueError as exc:
        raise InvalidNonLiveExecutionEvidenceBinding(
            "strategy_release is invalid"
        ) from exc


def _evidence_ref(value: object) -> dict[str, str]:
    if not isinstance(value, Mapping) or set(value) != _EVIDENCE_REF_FIELDS:
        _invalid("non_live_evidence_ref must be a closed evidence identity")
    schema_version = _text(value.get("schema_version"), "non_live_evidence_ref.schema_version")
    if _EVIDENCE_SCHEMA_VERSION.fullmatch(schema_version) is None:
        _invalid("non_live_evidence_ref.schema_version is invalid")
    return {
        "schema_version": schema_version,
        "sha256": _digest(value.get("sha256"), "non_live_evidence_ref.sha256"),
    }


def _binding_core(value: Mapping[str, object]) -> dict[str, object]:
    return {
        key: value[key]
        for key in sorted(_TOP_LEVEL_FIELDS - {"binding_sha256"})
    }


def _validate_release_dependencies(
    receipt: Mapping[str, object], release: StrategyReleaseIdentity
) -> None:
    dependencies = receipt["dependency_digests"]
    assert isinstance(dependencies, Mapping)  # validated receipt invariant
    expected = {
        "p2_config": release.config_sha256,
        "p3_evidence": release.evidence_sha256,
        "risk_policy": release.risk_policy_sha256,
        "strategy_release": release.manifest_sha256,
        "plugin_bundle": release.plugin_bundle_sha256,
    }
    if any(dependencies[key] != digest for key, digest in expected.items()):
        _invalid("strategy_release does not match frozen receipt dependencies")


def _validate_channel_receipt_evidence(
    *, channel: str, policy: ForwardObservationPolicy, receipt: Mapping[str, object]
) -> None:
    modes = set(receipt["evidence_modes"])
    if channel not in policy.automatic_non_live_modes:
        _invalid("execution_channel is not enabled by the forward-observation policy")
    if channel == "shadow" and "shadow_decision" not in modes:
        _invalid("shadow binding requires shadow_decision receipt evidence")
    if channel == "paper" and not (
        {"simulated_replay", "broker_paper"} & modes
    ):
        _invalid("paper binding requires configured paper receipt evidence")


def build_non_live_execution_evidence_binding(
    *,
    policy: ForwardObservationPolicy,
    forward_observation_receipt: Mapping[str, object],
    candidate_subject: str,
    candidate_revision_sha256: str,
    platform_id: str,
    runtime_scope_sha256: str,
    platform_adapter_sha256: str,
    execution_channel: str,
    strategy_release: StrategyReleaseIdentity | Mapping[str, object],
    non_live_evidence_schema_version: str,
    non_live_evidence_sha256: str,
) -> dict[str, object]:
    """Build a no-order evidence binding for one platform and non-live channel.

    ``runtime_scope_sha256`` is an opaque digest owned by the platform.  Raw
    account selectors, service names and broker identifiers must not enter this
    artifact.  The generic evidence reference can represent a future paper
    evidence schema; callers must validate that schema before passing its
    identity here.  Use the paired-shadow helper below when the evidence is a
    ``paired_shadow_evidence.v1`` artifact.
    """

    receipt = validate_forward_observation_receipt(
        forward_observation_receipt, policy=policy
    )
    release = _strategy_release(strategy_release)
    channel = _channel(execution_channel)
    _validate_channel_receipt_evidence(channel=channel, policy=policy, receipt=receipt)
    _validate_release_dependencies(receipt, release)
    evidence_ref = _evidence_ref(
        {
            "schema_version": non_live_evidence_schema_version,
            "sha256": non_live_evidence_sha256,
        }
    )
    binding: dict[str, object] = {
        "schema_version": NON_LIVE_EXECUTION_EVIDENCE_BINDING_SCHEMA_VERSION,
        "candidate_id": policy.candidate_id,
        "candidate_subject": _candidate_subject(candidate_subject),
        "candidate_revision_sha256": _digest(
            candidate_revision_sha256, "candidate_revision_sha256"
        ),
        "platform_id": _platform(platform_id),
        "runtime_scope_sha256": _digest(runtime_scope_sha256, "runtime_scope_sha256"),
        "platform_adapter_sha256": _digest(
            platform_adapter_sha256, "platform_adapter_sha256"
        ),
        "execution_channel": channel,
        "strategy_release": release.to_dict(),
        "forward_observation_receipt_sha256": receipt["receipt_sha256"],
        "non_live_evidence_ref": evidence_ref,
        "no_order": True,
        "live_authority_granted": False,
        "binding_sha256": "",
    }
    binding["binding_sha256"] = sha256(_canonical_bytes(_binding_core(binding))).hexdigest()
    return validate_non_live_execution_evidence_binding(
        binding,
        policy=policy,
        forward_observation_receipt=forward_observation_receipt,
        strategy_release=strategy_release,
    )


def build_paired_shadow_execution_evidence_binding(
    *,
    policy: ForwardObservationPolicy,
    forward_observation_receipt: Mapping[str, object],
    paired_shadow_evidence: Mapping[str, object],
    candidate_subject: str,
    candidate_revision_sha256: str,
    platform_id: str,
    runtime_scope_sha256: str,
    platform_adapter_sha256: str,
    strategy_release: StrategyReleaseIdentity | Mapping[str, object],
) -> dict[str, object]:
    """Build a shadow binding after verifying a paired-shadow evidence object."""

    receipt = validate_forward_observation_receipt(
        forward_observation_receipt, policy=policy
    )
    evidence = validate_paired_shadow_evidence(
        paired_shadow_evidence,
        policy=policy,
        forward_observation_receipt=receipt,
    )
    return build_non_live_execution_evidence_binding(
        policy=policy,
        forward_observation_receipt=receipt,
        candidate_subject=candidate_subject,
        candidate_revision_sha256=candidate_revision_sha256,
        platform_id=platform_id,
        runtime_scope_sha256=runtime_scope_sha256,
        platform_adapter_sha256=platform_adapter_sha256,
        execution_channel="shadow",
        strategy_release=strategy_release,
        non_live_evidence_schema_version=PAIRED_SHADOW_EVIDENCE_SCHEMA_VERSION,
        non_live_evidence_sha256=str(evidence["paired_shadow_evidence_sha256"]),
    )


def validate_non_live_execution_evidence_binding(
    value: Mapping[str, object],
    *,
    policy: ForwardObservationPolicy | None = None,
    forward_observation_receipt: Mapping[str, object] | None = None,
    strategy_release: StrategyReleaseIdentity | Mapping[str, object] | None = None,
    paired_shadow_evidence: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Validate a binding and optional primary artifacts supplied by its owner.

    Validation stays pure and cannot resolve storage.  Therefore callers must
    supply the receipt/release/evidence objects they resolved from their
    create-only stores when proving an end-to-end runtime observation.
    """

    if not isinstance(value, Mapping) or set(value) != _TOP_LEVEL_FIELDS:
        _invalid("binding must be a closed object")
    if value.get("schema_version") != NON_LIVE_EXECUTION_EVIDENCE_BINDING_SCHEMA_VERSION:
        _invalid(
            "schema_version must equal "
            f"{NON_LIVE_EXECUTION_EVIDENCE_BINDING_SCHEMA_VERSION}"
        )
    candidate_id = _text(value.get("candidate_id"), "candidate_id")
    subject = _candidate_subject(value.get("candidate_subject"))
    candidate_revision = _digest(
        value.get("candidate_revision_sha256"), "candidate_revision_sha256"
    )
    platform = _platform(value.get("platform_id"))
    scope_digest = _digest(value.get("runtime_scope_sha256"), "runtime_scope_sha256")
    adapter_digest = _digest(
        value.get("platform_adapter_sha256"), "platform_adapter_sha256"
    )
    channel = _channel(value.get("execution_channel"))
    release = _strategy_release(value.get("strategy_release"))
    receipt_digest = _digest(
        value.get("forward_observation_receipt_sha256"),
        "forward_observation_receipt_sha256",
    )
    evidence_ref = _evidence_ref(value.get("non_live_evidence_ref"))
    if value.get("no_order") is not True:
        _invalid("no_order must be true")
    if value.get("live_authority_granted") is not False:
        _invalid("live_authority_granted must be false")
    claimed_digest = _digest(value.get("binding_sha256"), "binding_sha256")
    if claimed_digest != sha256(_canonical_bytes(_binding_core(value))).hexdigest():
        _invalid("binding_sha256 does not match canonical binding content")

    if forward_observation_receipt is not None:
        receipt = validate_forward_observation_receipt(
            forward_observation_receipt, policy=policy
        )
        if receipt_digest != forward_observation_receipt_sha256(receipt):
            _invalid("forward_observation_receipt_sha256 does not match receipt")
        if candidate_id != receipt["candidate_id"]:
            _invalid("candidate_id does not match forward-observation receipt")
        _validate_release_dependencies(receipt, release)
        if policy is not None:
            _validate_channel_receipt_evidence(
                channel=channel, policy=policy, receipt=receipt
            )
    elif policy is not None:
        _invalid("policy validation requires forward_observation_receipt")

    if strategy_release is not None:
        expected_release = _strategy_release(strategy_release)
        if release != expected_release:
            _invalid("strategy_release does not match expected release identity")

    if paired_shadow_evidence is not None:
        if forward_observation_receipt is None or policy is None:
            _invalid("paired-shadow validation requires policy and forward_observation_receipt")
        evidence = validate_paired_shadow_evidence(
            paired_shadow_evidence,
            policy=policy,
            forward_observation_receipt=forward_observation_receipt,
        )
        if channel != "shadow":
            _invalid("paired-shadow evidence can bind only to the shadow channel")
        if evidence_ref["schema_version"] != PAIRED_SHADOW_EVIDENCE_SCHEMA_VERSION:
            _invalid("paired-shadow evidence schema does not match evidence reference")
        if evidence_ref["sha256"] != paired_shadow_evidence_sha256(evidence):
            _invalid("paired-shadow evidence digest does not match evidence reference")
        if candidate_id != evidence["candidate_id"]:
            _invalid("candidate_id does not match paired-shadow evidence")

    return {
        "schema_version": NON_LIVE_EXECUTION_EVIDENCE_BINDING_SCHEMA_VERSION,
        "candidate_id": candidate_id,
        "candidate_subject": subject,
        "candidate_revision_sha256": candidate_revision,
        "platform_id": platform,
        "runtime_scope_sha256": scope_digest,
        "platform_adapter_sha256": adapter_digest,
        "execution_channel": channel,
        "strategy_release": release.to_dict(),
        "forward_observation_receipt_sha256": receipt_digest,
        "non_live_evidence_ref": evidence_ref,
        "no_order": True,
        "live_authority_granted": False,
        "binding_sha256": claimed_digest,
    }


def canonical_non_live_execution_evidence_binding_bytes(
    value: Mapping[str, object]
) -> bytes:
    """Return canonical bytes for a schema-valid non-live evidence binding."""

    return _canonical_bytes(validate_non_live_execution_evidence_binding(value))


def non_live_execution_evidence_binding_sha256(value: Mapping[str, object]) -> str:
    """Return the deterministic identity of a validated non-live binding."""

    return str(
        validate_non_live_execution_evidence_binding(value)["binding_sha256"]
    )


def build_non_live_execution_evidence_report_artifacts(
    binding: Mapping[str, object],
    **validation_context: object,
) -> dict[str, object]:
    """Return a platform-neutral runtime-report attachment for one binding.

    The helper is intentionally serialization-only: it does not resolve a
    runtime target, persist data, submit orders, or grant any live authority.
    """

    validated = validate_non_live_execution_evidence_binding(
        binding,
        **validation_context,  # type: ignore[arg-type]
    )
    return {
        "non_live_execution_evidence_binding_json": (
            canonical_non_live_execution_evidence_binding_bytes(validated).decode("utf-8")
        ),
        "non_live_execution_evidence_binding_sha256": validated["binding_sha256"],
        "non_live_execution_evidence_binding_schema_version": (
            NON_LIVE_EXECUTION_EVIDENCE_BINDING_SCHEMA_VERSION
        ),
        "non_live_execution_evidence_binding_no_order": True,
        "non_live_execution_evidence_binding_live_authority_granted": False,
    }


__all__ = [
    "NON_LIVE_CANDIDATE_SUBJECTS",
    "NON_LIVE_EXECUTION_CHANNELS",
    "NON_LIVE_EXECUTION_EVIDENCE_BINDING_SCHEMA_VERSION",
    "NON_LIVE_RUNTIME_SCOPE_SCHEMA_VERSION",
    "InvalidNonLiveExecutionEvidenceBinding",
    "build_non_live_execution_evidence_binding",
    "build_non_live_execution_evidence_report_artifacts",
    "build_paired_shadow_execution_evidence_binding",
    "canonical_non_live_execution_evidence_binding_bytes",
    "non_live_execution_evidence_binding_sha256",
    "non_live_runtime_scope_sha256",
    "validate_non_live_execution_evidence_binding",
]
