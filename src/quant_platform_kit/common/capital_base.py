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

from .models import PortfolioSnapshot


CAPITAL_BASE_CONTRACT_VERSION = "qpk.capital_base.v2"
CAPITAL_BASE_LEGACY_CONTRACT_VERSION = "qpk.capital_base.v1"

_CURRENCY = re.compile(r"^[A-Z][A-Z0-9]{1,11}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class CapitalScope(str, Enum):
    """The ownership boundary of a value-target denominator."""

    ACCOUNT = "account"
    ALLOCATED_SLEEVE = "allocated_sleeve"


class CapitalValuationBasis(str, Enum):
    """The only valuation methods accepted by strict capital evidence."""

    BROKER_ACCOUNT_NET_LIQUIDATION = "broker_account_net_liquidation"
    FULL_ACCOUNT_MARK_TO_MARKET = "full_account_mark_to_market"
    ALLOCATED_SLEEVE_LEDGER = "allocated_sleeve_ledger"


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


def _capital_scope(value: object, *, field_name: str) -> CapitalScope:
    try:
        return value if isinstance(value, CapitalScope) else CapitalScope(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} must be a supported capital scope") from None


def _valuation_basis(value: object, *, field_name: str) -> CapitalValuationBasis:
    try:
        return (
            value
            if isinstance(value, CapitalValuationBasis)
            else CapitalValuationBasis(value)
        )
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} must be a supported capital valuation basis") from None


def _capital_semantics(
    *,
    capital_scope: CapitalScope,
    valuation_basis: CapitalValuationBasis,
    allocation_scope: object,
    component_coverage_digest_sha256: object,
    require_component_coverage: bool = True,
) -> tuple[str | None, str | None]:
    """Validate ownership/coverage before a denominator reaches a risk gate."""

    allocation = (
        None
        if allocation_scope is None
        else _canonical_text(allocation_scope, field_name="allocation_scope")
    )
    coverage = (
        None
        if component_coverage_digest_sha256 is None
        else _sha256(
            component_coverage_digest_sha256,
            field_name="component_coverage_digest_sha256",
        )
    )
    if capital_scope is CapitalScope.ACCOUNT:
        if allocation is not None:
            raise ValueError("account capital_scope must not set allocation_scope")
        if valuation_basis is CapitalValuationBasis.BROKER_ACCOUNT_NET_LIQUIDATION:
            if coverage is not None:
                raise ValueError(
                    "broker_account_net_liquidation must not set component_coverage_digest_sha256"
                )
        elif valuation_basis is CapitalValuationBasis.FULL_ACCOUNT_MARK_TO_MARKET:
            if require_component_coverage and coverage is None:
                raise ValueError(
                    "full_account_mark_to_market requires component_coverage_digest_sha256"
                )
        else:
            raise ValueError("account capital_scope requires an account valuation basis")
    elif capital_scope is CapitalScope.ALLOCATED_SLEEVE:
        if valuation_basis is not CapitalValuationBasis.ALLOCATED_SLEEVE_LEDGER:
            raise ValueError("allocated_sleeve requires allocated_sleeve_ledger valuation")
        if allocation is None:
            raise ValueError("allocated_sleeve requires allocation_scope")
        if require_component_coverage and coverage is None:
            raise ValueError(
                "allocated_sleeve_ledger requires component_coverage_digest_sha256"
            )
    return allocation, coverage


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
    capital_scope: CapitalScope | None = None
    valuation_basis: CapitalValuationBasis | None = None
    allocation_scope: str | None = None
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
        if (self.capital_scope is None) != (self.valuation_basis is None):
            raise ValueError("capital_scope and valuation_basis must be supplied together")
        capital_scope = (
            None
            if self.capital_scope is None
            else _capital_scope(self.capital_scope, field_name="capital_scope")
        )
        valuation_basis = (
            None
            if self.valuation_basis is None
            else _valuation_basis(self.valuation_basis, field_name="valuation_basis")
        )
        if capital_scope is None or valuation_basis is None:
            allocation_scope = None
            if self.allocation_scope is not None:
                raise ValueError("legacy capital base binding must not set allocation_scope")
        else:
            allocation_scope, _ = _capital_semantics(
                capital_scope=capital_scope,
                valuation_basis=valuation_basis,
                allocation_scope=self.allocation_scope,
                component_coverage_digest_sha256=None,
                require_component_coverage=False,
            )
        object.__setattr__(self, "capital_scope", capital_scope)
        object.__setattr__(self, "valuation_basis", valuation_basis)
        object.__setattr__(self, "allocation_scope", allocation_scope)
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
            "capital_scope",
            "valuation_basis",
            "allocation_scope",
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
            capital_scope=payload.get("capital_scope"),
            valuation_basis=payload.get("valuation_basis"),
            allocation_scope=payload.get("allocation_scope"),
            max_age_seconds=payload.get("max_age_seconds", 300.0),
        )

    @property
    def scope_digest_sha256(self) -> str:
        return _canonical_payload_digest(
            {
                "account_scope": self.account_scope,
                "runtime_scope": self.runtime_scope,
                "strategy_scope": self.strategy_scope,
                "capital_scope": None if self.capital_scope is None else self.capital_scope.value,
                "valuation_basis": (
                    None if self.valuation_basis is None else self.valuation_basis.value
                ),
                "allocation_scope": self.allocation_scope,
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
    capital_scope: CapitalScope | None = None
    valuation_basis: CapitalValuationBasis | None = None
    allocation_scope: str | None = None
    component_coverage_digest_sha256: str | None = None
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
        if (self.capital_scope is None) != (self.valuation_basis is None):
            raise ValueError("capital_scope and valuation_basis must be supplied together")
        capital_scope = (
            None
            if self.capital_scope is None
            else _capital_scope(self.capital_scope, field_name="capital_scope")
        )
        valuation_basis = (
            None
            if self.valuation_basis is None
            else _valuation_basis(self.valuation_basis, field_name="valuation_basis")
        )
        if capital_scope is None or valuation_basis is None:
            if self.allocation_scope is not None or self.component_coverage_digest_sha256 is not None:
                raise ValueError(
                    "legacy capital base snapshot must not set allocation or coverage evidence"
                )
            allocation_scope, coverage_digest = None, None
        else:
            allocation_scope, coverage_digest = _capital_semantics(
                capital_scope=capital_scope,
                valuation_basis=valuation_basis,
                allocation_scope=self.allocation_scope,
                component_coverage_digest_sha256=self.component_coverage_digest_sha256,
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
        object.__setattr__(self, "capital_scope", capital_scope)
        object.__setattr__(self, "valuation_basis", valuation_basis)
        object.__setattr__(self, "allocation_scope", allocation_scope)
        object.__setattr__(self, "component_coverage_digest_sha256", coverage_digest)
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
            "capital_scope",
            "valuation_basis",
            "allocation_scope",
            "component_coverage_digest_sha256",
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
            capital_scope=payload.get("capital_scope"),
            valuation_basis=payload.get("valuation_basis"),
            allocation_scope=payload.get("allocation_scope"),
            component_coverage_digest_sha256=payload.get(
                "component_coverage_digest_sha256"
            ),
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
                "capital_scope": None if self.capital_scope is None else self.capital_scope.value,
                "valuation_basis": (
                    None if self.valuation_basis is None else self.valuation_basis.value
                ),
                "allocation_scope": self.allocation_scope,
            }
        )

    def to_safe_dict(self) -> dict[str, object]:
        """Return redacted evidence appropriate for risk diagnostics/receipts."""
        return {
            "contract_version": self.contract_version,
            "as_of": self.as_of.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "reported_currency": self.reported_currency,
            "target_currency": self.target_currency,
            "capital_scope": None if self.capital_scope is None else self.capital_scope.value,
            "valuation_basis": (
                None if self.valuation_basis is None else self.valuation_basis.value
            ),
            "allocation_scope_digest_sha256": (
                None
                if self.allocation_scope is None
                else _canonical_payload_digest({"allocation_scope": self.allocation_scope})
            ),
            "component_coverage_digest_sha256": self.component_coverage_digest_sha256,
            "fx_applied": self.reported_currency != self.target_currency,
            "source_digest_sha256": self.source_digest_sha256,
            "fx_source_digest_sha256": self.fx_source_digest_sha256,
            "scope_digest_sha256": self.scope_digest_sha256,
        }

    @property
    def contract_version(self) -> str:
        """Expose v1 only for diagnostics; v2 is required for strict admission."""

        return (
            CAPITAL_BASE_LEGACY_CONTRACT_VERSION
            if self.capital_scope is None
            else CAPITAL_BASE_CONTRACT_VERSION
        )


def build_capital_base_snapshot(
    portfolio_snapshot: PortfolioSnapshot,
    *,
    account_scope: str,
    runtime_scope: str,
    strategy_scope: str,
    reported_currency: str,
    target_currency: str,
    fx_rate_to_target: float,
    source_digest_sha256: str,
    capital_scope: CapitalScope,
    valuation_basis: CapitalValuationBasis,
    allocation_scope: str | None = None,
    component_coverage_digest_sha256: str | None = None,
    fx_source_digest_sha256: str | None = None,
) -> CapitalBaseSnapshot:
    """Adapt a canonical portfolio snapshot into verified capital evidence.

    This is intentionally a small, pure adapter: it copies only
    ``total_equity`` and ``as_of`` from the already-normalized portfolio
    snapshot.  Account/runtime/strategy scopes, capital ownership,
    valuation basis, currency conversion and source digests remain explicit
    inputs.  It does not read environment variables, infer account identity
    from metadata, or fabricate a digest.
    """
    if not isinstance(portfolio_snapshot, PortfolioSnapshot):
        raise TypeError("portfolio_snapshot must be a PortfolioSnapshot")
    return CapitalBaseSnapshot(
        reported_equity=portfolio_snapshot.total_equity,
        reported_currency=reported_currency,
        target_currency=target_currency,
        fx_rate_to_target=fx_rate_to_target,
        as_of=portfolio_snapshot.as_of,
        account_scope=account_scope,
        runtime_scope=runtime_scope,
        strategy_scope=strategy_scope,
        source_digest_sha256=source_digest_sha256,
        capital_scope=capital_scope,
        valuation_basis=valuation_basis,
        allocation_scope=allocation_scope,
        component_coverage_digest_sha256=component_coverage_digest_sha256,
        fx_source_digest_sha256=fx_source_digest_sha256,
    )


class CapitalBaseFinding(str, Enum):
    MISSING = "missing_capital_base"
    LEGACY_CONTRACT = "legacy_capital_base_contract"
    INVALID = "invalid_capital_base"
    INVALID_BINDING = "invalid_capital_base_binding"
    INVALID_DENOMINATOR = "invalid_capital_base_denominator"
    ACCOUNT_SCOPE_MISMATCH = "capital_base_account_scope_mismatch"
    RUNTIME_SCOPE_MISMATCH = "capital_base_runtime_scope_mismatch"
    STRATEGY_SCOPE_MISMATCH = "capital_base_strategy_scope_mismatch"
    TARGET_CURRENCY_MISMATCH = "capital_base_target_currency_mismatch"
    CAPITAL_SCOPE_MISMATCH = "capital_base_scope_mismatch"
    VALUATION_BASIS_MISMATCH = "capital_base_valuation_basis_mismatch"
    ALLOCATION_SCOPE_MISMATCH = "capital_base_allocation_scope_mismatch"
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
            payload["expected_capital_scope"] = (
                None if self.binding.capital_scope is None else self.binding.capital_scope.value
            )
            payload["expected_valuation_basis"] = (
                None
                if self.binding.valuation_basis is None
                else self.binding.valuation_basis.value
            )
            payload["expected_allocation_scope_digest_sha256"] = (
                None
                if self.binding.allocation_scope is None
                else _canonical_payload_digest(
                    {"allocation_scope": self.binding.allocation_scope}
                )
            )
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
    if snapshot.contract_version != CAPITAL_BASE_CONTRACT_VERSION or (
        resolved_binding.capital_scope is None or resolved_binding.valuation_basis is None
    ):
        findings.append(CapitalBaseFinding.LEGACY_CONTRACT.value)
    else:
        if snapshot.capital_scope is not resolved_binding.capital_scope:
            findings.append(CapitalBaseFinding.CAPITAL_SCOPE_MISMATCH.value)
        if snapshot.valuation_basis is not resolved_binding.valuation_basis:
            findings.append(CapitalBaseFinding.VALUATION_BASIS_MISMATCH.value)
        if snapshot.allocation_scope != resolved_binding.allocation_scope:
            findings.append(CapitalBaseFinding.ALLOCATION_SCOPE_MISMATCH.value)
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
