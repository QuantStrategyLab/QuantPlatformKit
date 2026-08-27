"""Broker-neutral admission for an explicitly approved long-only reduction.

This is the final pure boundary before a platform execution adapter. It does
not select a de-risking target, create an order, query a broker, or submit an
order. A platform must provide a fresh reconciliation and invoke this check
immediately before its broker write.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass
from typing import Any

from .execution_commands import (
    ExecutionCommand,
    ExecutionCommandState,
    validate_execution_command_release_binding,
)
from .long_only_reduce import (
    LongOnlyReduceOnlyValidation,
    validate_long_only_reduce_only_order,
)
from .models import OrderIntent
from .runtime_command_gate import (
    RuntimeCommandAction,
    RuntimeCommandExposureEffect,
    RuntimeCommandGateDecision,
    RuntimeCommandGateEnforcement,
    RuntimeCommandGateMode,
    RuntimeCommandGatePolicy,
    evaluate_runtime_command_gate,
)
from .strategy_release import StrategyReleaseIdentity, StrategyReleaseVerification


REDUCE_ONLY_ORDER_DIGEST_FIELD = "reduce_only_order_sha256"
_SHA256_RE = re.compile(r"^[a-f0-9]{64}$")
_DEFAULT_REDUCE_ONLY_POLICY = RuntimeCommandGatePolicy(
    mode=RuntimeCommandGateMode.REDUCING,
    enforcement=RuntimeCommandGateEnforcement.ENFORCE,
)


class ReduceOnlyCommandFinding:
    """Stable, redacted findings produced by this composite admission check."""

    COMMAND_ORDER_BINDING_MISSING = "reduce_only_command_order_binding_missing"
    COMMAND_ORDER_BINDING_MISMATCH = "reduce_only_command_order_binding_mismatch"
    INVALID_ORDER_DIGEST = "reduce_only_invalid_order_digest"


def _canonical_optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _finite_positive(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) and number > 0.0 else None


def _finite_optional(value: object) -> float | None:
    if value is None:
        return None
    return _finite_positive(value)


def build_reduce_only_order_digest(order: OrderIntent | object) -> str | None:
    """Return the immutable digest to embed in an approved command intent.

    The digest deliberately binds only order-routing fields. It never copies
    broker metadata into a command or a report, but account routing remains
    part of the fingerprint so a command cannot be replayed to another
    account.
    """

    if not isinstance(order, OrderIntent):
        return None
    symbol = _canonical_optional_text(order.symbol)
    side = _canonical_optional_text(order.side)
    order_type = _canonical_optional_text(order.order_type)
    quantity = _finite_positive(order.quantity)
    limit_price = _finite_optional(order.limit_price)
    if not symbol or not side or not order_type or quantity is None:
        return None
    if order.limit_price is not None and limit_price is None:
        return None
    payload = {
        "account_id": _canonical_optional_text(order.account_id),
        "limit_price": limit_price,
        "order_type": order_type.lower(),
        "quantity": quantity,
        "side": side.lower(),
        "symbol": symbol.upper(),
        "time_in_force": _canonical_optional_text(order.time_in_force),
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def _dedupe(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(value for value in values if value))


@dataclass(frozen=True)
class ReduceOnlyCommandAdmission:
    """Safe composite decision that a platform may enforce before a broker write."""

    approved: bool
    findings: tuple[str, ...]
    order_validation: LongOnlyReduceOnlyValidation
    command_release_verification: StrategyReleaseVerification | None
    runtime_command_gate: RuntimeCommandGateDecision

    def to_safe_dict(self) -> dict[str, object]:
        return {
            "approved": self.approved,
            "findings": list(self.findings),
            "order_validation": self.order_validation.to_safe_dict(),
            "command_release_verification": (
                None
                if self.command_release_verification is None
                else asdict(self.command_release_verification)
            ),
            "runtime_command_gate": self.runtime_command_gate.to_receipt(),
        }


def evaluate_reduce_only_command_admission(
    *,
    order: OrderIntent | object,
    long_quantities: Mapping[object, object],
    short_quantities: Mapping[object, object],
    sellable_quantities: Mapping[object, object],
    allowed_symbols: Iterable[object],
    command: ExecutionCommand | None,
    as_of_session: object,
    runtime_release_receipt: Mapping[str, Any] | None,
    expected_strategy_release: StrategyReleaseIdentity | Mapping[str, object] | None,
    command_state: ExecutionCommandState | str | None = None,
    integrity_findings: Iterable[object] = (),
    policy: RuntimeCommandGatePolicy | None = None,
) -> ReduceOnlyCommandAdmission:
    """Admit one reconciled long-only sell bound to a durable command.

    This is stricter than a generic runtime gate: it requires the gate's
    ``policy_allows`` result, so observation mode cannot let an invalid
    reduction fall through. The supplied policy may tighten the default but
    cannot turn an invalid reduction into an approved write.
    """

    order_validation = validate_long_only_reduce_only_order(
        order,
        long_quantities=long_quantities,
        short_quantities=short_quantities,
        sellable_quantities=sellable_quantities,
        allowed_symbols=allowed_symbols,
    )
    findings: list[str] = list(order_validation.findings)
    command_release_verification: StrategyReleaseVerification | None = None
    order_digest = build_reduce_only_order_digest(order)
    binding_valid = False

    if order_digest is None:
        findings.append(ReduceOnlyCommandFinding.INVALID_ORDER_DIGEST)
    if command is None:
        findings.append(ReduceOnlyCommandFinding.COMMAND_ORDER_BINDING_MISSING)
    else:
        command_release_verification = validate_execution_command_release_binding(
            command,
            expected_strategy_release=expected_strategy_release,
        )
        findings.extend(command_release_verification.findings)
        expected_digest = str(
            command.intent.get(REDUCE_ONLY_ORDER_DIGEST_FIELD) or ""
        ).strip().lower()
        if not _SHA256_RE.fullmatch(expected_digest):
            findings.append(ReduceOnlyCommandFinding.COMMAND_ORDER_BINDING_MISSING)
        elif order_digest is None or expected_digest != order_digest:
            findings.append(ReduceOnlyCommandFinding.COMMAND_ORDER_BINDING_MISMATCH)
        else:
            binding_valid = True

    gate_findings = tuple(integrity_findings) + tuple(
        () if command_release_verification is None else command_release_verification.findings
    )
    runtime_command_gate = evaluate_runtime_command_gate(
        action=RuntimeCommandAction.SUBMIT,
        exposure_effect=RuntimeCommandExposureEffect.REDUCES,
        command=command,
        command_state=command_state,
        as_of_session=as_of_session,
        runtime_release_receipt=runtime_release_receipt,
        expected_strategy_release=expected_strategy_release,
        integrity_findings=gate_findings,
        policy=policy or _DEFAULT_REDUCE_ONLY_POLICY,
    )
    findings.extend(runtime_command_gate.reasons)
    approved = bool(
        order_validation.approved
        and binding_valid
        and (command_release_verification is None or command_release_verification.is_valid)
        and runtime_command_gate.policy_allows
    )
    return ReduceOnlyCommandAdmission(
        approved=approved,
        findings=_dedupe(findings),
        order_validation=order_validation,
        command_release_verification=command_release_verification,
        runtime_command_gate=runtime_command_gate,
    )


__all__ = [
    "REDUCE_ONLY_ORDER_DIGEST_FIELD",
    "ReduceOnlyCommandAdmission",
    "ReduceOnlyCommandFinding",
    "build_reduce_only_order_digest",
    "evaluate_reduce_only_command_admission",
]
