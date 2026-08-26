"""Verified denominator contract for value-target risk controls.

``target_value`` is only meaningful when the account value used as its
denominator is tied to the same account, runtime and strategy invocation.
This module deliberately carries no broker credentials or raw account facts;
the scope values are accepted only to compare them and are never emitted by
the safe evidence helpers.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
import math
import re
import unicodedata
from typing import Any


CAPITAL_BASE_CONTRACT_VERSION = "qpk.capital_base.v1"

_CURRENCY = re.compile(r"^[A-Z][A-Z0-9]{1,11}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _canonical_text(value: object, *, field_name: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f"{field_name} must be a non-empty canonical string")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ValueError(f"{field_name} must be valid UTF-8") from exc
    if unicodedata.normalize("NFC", value) != value:
        raise ValueError(f"{field_name} must use NFC normalization")
    return value


def _currency(value: object, *, field_name: str) -> str:
    raw_value = _canonical_text(value, field_name=field_name)
    normalized = raw_value.upper()
    if raw_value != normalized:
        raise ValueError(f"{field_name} must be an uppercase currency code")
    if not _CURRENCY.fullmatch(normalized):
        raise ValueError(f"{field_name} must be an uppercase currency code")
    return normalized


def _sha256(value: object, *, field_name: str) -> str:
    normalized = _canonical_text(value, field_name=field_name)
    if not _SHA256.fullmatch(normalized):
        raise ValueError(f"{field_name} must be a lowercase SHA-256 digest")
    return normalized


def _finite_positive(value: object, *, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field_name} must be a finite positive number")
    number = float(value)
    if not math.isfinite(number) or number <= 0.0:
        raise ValueError(f"{field_name} must be a finite positive number")
    return number


def _utc_timestamp(value: datetime, *, field_name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError(f"{field_name} must be a timezone-aware datetime")
    return value.astimezone(timezone.utc)


def _canonical_payload_digest(value: Mapping[str, object]) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class CapitalBaseBinding:
    """Expected scope and freshness of one value-target denominator.

    The three scope values are opaque canonical identifiers.  A platform
    should use a stable account scope, its deployed runtime scope, and the
    strategy profile as ``strategy_scope``.  They are compared exactly but
    redacted to a digest in all diagnostic payloads.
    """

    account_scope: str
    runtime_scope: str
    strategy_scope: str
    target_currency: str
    max_age_seconds: float = 300.0

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "account_scope",
            _canonical_text(self.account_scope, field_name="account_scope"),
        )
        object.__setattr__(
            self,
            "runtime_scope",
            _canonical_text(self.runtime_scope, field_name="runtime_scope"),
        )
        object.__setattr__(
            self,
            "strategy_scope",
            _canonical_text(self.strategy_scope, field_name="strategy_scope"),
        )
        object.__setattr__(
            self,
            "target_currency",
            _currency(self.target_currency, field_name="target_currency"),
        )
        object.__setattr__(
            self,
            "max_age_seconds",
            _finite_positive(self.max_age_seconds, field_name="max_age_seconds"),
        )

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "CapitalBaseBinding":
        payload = dict(value)
        allowed = {
            "account_scope",
            "runtime_scope",
            "strategy_scope",
            "target_currency",
            "max_age_seconds",
        }
        unknown = sorted(set(payload) - allowed)
        if unknown:
            raise ValueError("unsupported capital base binding fields: " + ", ".join(unknown))
        return cls(
            account_scope=payload.get("account_scope"),
            runtime_scope=payload.get("runtime_scope"),
            strategy_scope=payload.get("strategy_scope"),
            target_currency=payload.get("target_currency"),
            max_age_seconds=payload.get("max_age_seconds", 300.0),
        )

    @property
    def scope_digest_sha256(self) -> str:
        return _canonical_payload_digest(
            {
                "account_scope": self.account_scope,
                "runtime_scope": self.runtime_scope,
                "strategy_scope": self.strategy_scope,
            }
        )


@dataclass(frozen=True)
class CapitalBaseSnapshot:
    """Read-only capital evidence normalized to a target-value currency.

    ``reported_equity`` comes from the broker/account snapshot in
    ``reported_currency``.  ``fx_rate_to_target`` transforms it into
    ``target_currency``.  An FX digest is mandatory whenever a conversion is
    required, making a stale or unrelated FX quote impossible to hide behind a
    nominal account value.
    """

    reported_equity: float
    reported_currency: str
    target_currency: str
    fx_rate_to_target: float
    as_of: datetime
    account_scope: str
    runtime_scope: str
    strategy_scope: str
    source_digest_sha256: str
    fx_source_digest_sha256: str | None = None

    def __post_init__(self) -> None:
        reported_equity = _finite_positive(
            self.reported_equity,
            field_name="reported_equity",
        )
        reported_currency = _currency(
            self.reported_currency,
            field_name="reported_currency",
        )
        target_currency = _currency(
            self.target_currency,
            field_name="target_currency",
        )
        fx_rate = _finite_positive(
            self.fx_rate_to_target,
            field_name="fx_rate_to_target",
        )
        as_of = _utc_timestamp(self.as_of, field_name="as_of")
        account_scope = _canonical_text(self.account_scope, field_name="account_scope")
        runtime_scope = _canonical_text(self.runtime_scope, field_name="runtime_scope")
        strategy_scope = _canonical_text(self.strategy_scope, field_name="strategy_scope")
        source_digest = _sha256(
            self.source_digest_sha256,
            field_name="source_digest_sha256",
        )
        fx_digest = self.fx_source_digest_sha256
        if fx_digest is not None:
            fx_digest = _sha256(
                fx_digest,
                field_name="fx_source_digest_sha256",
            )
        if reported_currency == target_currency:
            if fx_rate != 1.0:
                raise ValueError("fx_rate_to_target must be 1.0 when currencies match")
        elif fx_digest is None:
            raise ValueError(
                "fx_source_digest_sha256 is required when reported and target currencies differ"
            )
        object.__setattr__(self, "reported_equity", reported_equity)
        object.__setattr__(self, "reported_currency", reported_currency)
        object.__setattr__(self, "target_currency", target_currency)
        object.__setattr__(self, "fx_rate_to_target", fx_rate)
        object.__setattr__(self, "as_of", as_of)
        object.__setattr__(self, "account_scope", account_scope)
        object.__setattr__(self, "runtime_scope", runtime_scope)
        object.__setattr__(self, "strategy_scope", strategy_scope)
        object.__setattr__(self, "source_digest_sha256", source_digest)
        object.__setattr__(self, "fx_source_digest_sha256", fx_digest)

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "CapitalBaseSnapshot":
        payload = dict(value)
        allowed = {
            "reported_equity",
            "reported_currency",
            "target_currency",
            "fx_rate_to_target",
            "as_of",
            "account_scope",
            "runtime_scope",
            "strategy_scope",
            "source_digest_sha256",
            "fx_source_digest_sha256",
        }
        unknown = sorted(set(payload) - allowed)
        if unknown:
            raise ValueError("unsupported capital base snapshot fields: " + ", ".join(unknown))
        as_of = payload.get("as_of")
        if isinstance(as_of, str):
            try:
                as_of = datetime.fromisoformat(as_of.replace("Z", "+00:00"))
            except ValueError as exc:
                raise ValueError("as_of must be an ISO-8601 timestamp") from exc
        return cls(
            reported_equity=payload.get("reported_equity"),
            reported_currency=payload.get("reported_currency"),
            target_currency=payload.get("target_currency"),
            fx_rate_to_target=payload.get("fx_rate_to_target"),
            as_of=as_of,
            account_scope=payload.get("account_scope"),
            runtime_scope=payload.get("runtime_scope"),
            strategy_scope=payload.get("strategy_scope"),
            source_digest_sha256=payload.get("source_digest_sha256"),
            fx_source_digest_sha256=payload.get("fx_source_digest_sha256"),
        )

    @property
    def target_equity(self) -> float:
        """Positive denominator expressed in ``target_currency``."""
        return self.reported_equity * self.fx_rate_to_target

    @property
    def scope_digest_sha256(self) -> str:
        return _canonical_payload_digest(
            {
                "account_scope": self.account_scope,
                "runtime_scope": self.runtime_scope,
                "strategy_scope": self.strategy_scope,
            }
        )

    def to_safe_dict(self) -> dict[str, object]:
        """Return redacted evidence appropriate for risk diagnostics/receipts."""
        return {
            "contract_version": CAPITAL_BASE_CONTRACT_VERSION,
            "as_of": self.as_of.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "reported_currency": self.reported_currency,
            "target_currency": self.target_currency,
            "fx_applied": self.reported_currency != self.target_currency,
            "source_digest_sha256": self.source_digest_sha256,
            "fx_source_digest_sha256": self.fx_source_digest_sha256,
            "scope_digest_sha256": self.scope_digest_sha256,
        }


class CapitalBaseFinding(str, Enum):
    MISSING = "missing_capital_base"
    INVALID = "invalid_capital_base"
    INVALID_BINDING = "invalid_capital_base_binding"
    INVALID_DENOMINATOR = "invalid_capital_base_denominator"
    ACCOUNT_SCOPE_MISMATCH = "capital_base_account_scope_mismatch"
    RUNTIME_SCOPE_MISMATCH = "capital_base_runtime_scope_mismatch"
    STRATEGY_SCOPE_MISMATCH = "capital_base_strategy_scope_mismatch"
    TARGET_CURRENCY_MISMATCH = "capital_base_target_currency_mismatch"
    STALE = "stale_capital_base"
    FUTURE = "future_capital_base"


@dataclass(frozen=True)
class CapitalBaseValidation:
    """Non-throwing result for a capital-base admission check."""

    snapshot: CapitalBaseSnapshot | None
    binding: CapitalBaseBinding | None
    findings: tuple[str, ...]

    @property
    def is_valid(self) -> bool:
        return self.snapshot is not None and self.binding is not None and not self.findings

    @property
    def target_equity(self) -> float | None:
        return self.snapshot.target_equity if self.is_valid and self.snapshot is not None else None

    def to_safe_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "contract_version": CAPITAL_BASE_CONTRACT_VERSION,
            "valid": self.is_valid,
            "findings": list(self.findings),
        }
        if self.binding is not None:
            payload["expected_target_currency"] = self.binding.target_currency
            payload["max_age_seconds"] = self.binding.max_age_seconds
            payload["expected_scope_digest_sha256"] = self.binding.scope_digest_sha256
        if self.snapshot is not None:
            payload["snapshot"] = self.snapshot.to_safe_dict()
        return payload


def _coerce_binding(value: CapitalBaseBinding | Mapping[str, Any] | None) -> CapitalBaseBinding | None:
    if isinstance(value, CapitalBaseBinding):
        return value
    if isinstance(value, Mapping):
        return CapitalBaseBinding.from_mapping(value)
    return None


def _coerce_snapshot(value: CapitalBaseSnapshot | Mapping[str, Any] | None) -> CapitalBaseSnapshot | None:
    if isinstance(value, CapitalBaseSnapshot):
        return value
    if isinstance(value, Mapping):
        return CapitalBaseSnapshot.from_mapping(value)
    return None


def validate_capital_base(
    capital_base: CapitalBaseSnapshot | Mapping[str, Any] | None,
    *,
    binding: CapitalBaseBinding | Mapping[str, Any] | None,
    now: datetime | None = None,
) -> CapitalBaseValidation:
    """Validate a value-target denominator without touching external state.

    Invalid values yield stable findings rather than exceptions so an execution
    gate can fail closed and emit a redacted explanation.  The snapshot must
    be freshly observed, exact-scope matched, and already converted to the
    target currency expected by the caller.
    """
    try:
        resolved_binding = _coerce_binding(binding)
    except Exception:
        return CapitalBaseValidation(
            snapshot=None,
            binding=None,
            findings=(CapitalBaseFinding.INVALID_BINDING.value,),
        )
    if resolved_binding is None:
        return CapitalBaseValidation(
            snapshot=None,
            binding=None,
            findings=(CapitalBaseFinding.INVALID_BINDING.value,),
        )
    if capital_base is None:
        return CapitalBaseValidation(
            snapshot=None,
            binding=resolved_binding,
            findings=(CapitalBaseFinding.MISSING.value,),
        )
    try:
        snapshot = _coerce_snapshot(capital_base)
    except Exception:
        return CapitalBaseValidation(
            snapshot=None,
            binding=resolved_binding,
            findings=(CapitalBaseFinding.INVALID.value,),
        )
    if snapshot is None:
        return CapitalBaseValidation(
            snapshot=None,
            binding=resolved_binding,
            findings=(CapitalBaseFinding.INVALID.value,),
        )
    target_equity = snapshot.target_equity
    if not math.isfinite(target_equity) or target_equity <= 0.0:
        return CapitalBaseValidation(
            snapshot=snapshot,
            binding=resolved_binding,
            findings=(CapitalBaseFinding.INVALID_DENOMINATOR.value,),
        )
    try:
        evaluated_at = _utc_timestamp(now or datetime.now(timezone.utc), field_name="now")
    except ValueError:
        return CapitalBaseValidation(
            snapshot=snapshot,
            binding=resolved_binding,
            findings=(CapitalBaseFinding.INVALID_BINDING.value,),
        )

    findings: list[str] = []
    if snapshot.account_scope != resolved_binding.account_scope:
        findings.append(CapitalBaseFinding.ACCOUNT_SCOPE_MISMATCH.value)
    if snapshot.runtime_scope != resolved_binding.runtime_scope:
        findings.append(CapitalBaseFinding.RUNTIME_SCOPE_MISMATCH.value)
    if snapshot.strategy_scope != resolved_binding.strategy_scope:
        findings.append(CapitalBaseFinding.STRATEGY_SCOPE_MISMATCH.value)
    if snapshot.target_currency != resolved_binding.target_currency:
        findings.append(CapitalBaseFinding.TARGET_CURRENCY_MISMATCH.value)
    age_seconds = (evaluated_at - snapshot.as_of).total_seconds()
    if age_seconds < 0.0:
        findings.append(CapitalBaseFinding.FUTURE.value)
    elif age_seconds > resolved_binding.max_age_seconds:
        findings.append(CapitalBaseFinding.STALE.value)
    return CapitalBaseValidation(
        snapshot=snapshot,
        binding=resolved_binding,
        findings=tuple(sorted(findings)),
    )
