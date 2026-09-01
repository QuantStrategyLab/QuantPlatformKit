"""Portable, verified daily decision-data projections.

This contract intentionally carries historical decision inputs only.  It does
not describe a storage location, a broker account, or a short-lived execution
quote.  Pipeline-specific P1 validators remain responsible for proving their
native input root; this module verifies the small portable projection that a
runtime may consume after that proof has been published immutably.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, date, datetime, time
from hashlib import sha256
import json
from math import isfinite
import re
from typing import Any

from quant_platform_kit.common.models import PricePoint, PriceSeries

from .decision_data_binding import (
    DECISION_DATA_ASSURANCE_VERIFIED,
    DECISION_DATA_MODE_ARTIFACT_OPTIONAL,
    DECISION_DATA_MODE_ARTIFACT_REQUIRED,
    DecisionDataBinding,
)
from .research_input import (
    canonical_research_input_manifest_bytes,
    read_research_input_manifest_json,
    research_input_manifest_sha256,
)


DECISION_PRICE_SERIES_ARTIFACT_SCHEMA_VERSION = "qpk.decision_price_series_artifact.v1"
DECISION_PRICE_SERIES_MEMBER_PATH = "decision-price-series.json"

_SYMBOL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_CURRENCY_RE = re.compile(r"^[A-Z]{2,8}$")


class InvalidDecisionDataArtifact(ValueError):
    """Raised when a portable decision-data projection fails closed."""


def _invalid() -> None:
    raise InvalidDecisionDataArtifact("invalid decision price-series artifact")


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            _invalid()
        result[key] = value
    return result


def _reject_nonfinite_constant(_: str) -> None:
    _invalid()


def _require_exact_mapping(value: object, keys: frozenset[str]) -> dict[str, object]:
    if not isinstance(value, Mapping) or set(value) != keys or any(
        not isinstance(key, str) for key in value
    ):
        _invalid()
    return dict(value)


def _require_date(value: object) -> str:
    if not isinstance(value, str):
        _invalid()
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        _invalid()
    if parsed.isoformat() != value:
        _invalid()
    return value


def _require_identifier(value: object) -> str:
    if not isinstance(value, str):
        _invalid()
    text = value.strip()
    if not text or text != value:
        _invalid()
    return text


def _require_number(value: object, *, positive: bool) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _invalid()
    number = float(value)
    if not isfinite(number) or (number <= 0 if positive else number < 0):
        _invalid()
    return number


def _require_source_ids(value: object) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        _invalid()
    source_ids = tuple(_require_identifier(item) for item in value)
    if len(source_ids) != len(set(source_ids)):
        _invalid()
    return source_ids


def validate_decision_price_series_artifact(value: object) -> dict[str, object]:
    """Validate one provider-neutral, daily historical price projection."""

    try:
        artifact = _require_exact_mapping(
            value,
            frozenset(
                {
                    "schema_version",
                    "strategy_scope",
                    "as_of",
                    "adjustment_basis",
                    "source_ids",
                    "series",
                }
            ),
        )
        if artifact["schema_version"] != DECISION_PRICE_SERIES_ARTIFACT_SCHEMA_VERSION:
            _invalid()
        strategy_scope = _require_identifier(artifact["strategy_scope"])
        as_of = _require_date(artifact["as_of"])
        adjustment_basis = _require_identifier(artifact["adjustment_basis"])
        source_ids = _require_source_ids(artifact["source_ids"])
        raw_series = artifact["series"]
        if not isinstance(raw_series, Mapping) or not raw_series:
            _invalid()

        normalized_series: dict[str, dict[str, object]] = {}
        for raw_symbol, raw_payload in raw_series.items():
            if not isinstance(raw_symbol, str) or not _SYMBOL_RE.fullmatch(raw_symbol):
                _invalid()
            symbol = raw_symbol.upper()
            if symbol != raw_symbol or symbol in normalized_series:
                _invalid()
            payload = _require_exact_mapping(raw_payload, frozenset({"currency", "points"}))
            currency = _require_identifier(payload["currency"])
            if not _CURRENCY_RE.fullmatch(currency):
                _invalid()
            raw_points = payload["points"]
            if not isinstance(raw_points, list) or not raw_points:
                _invalid()

            points: list[dict[str, object]] = []
            prior_session: str | None = None
            for raw_point in raw_points:
                point = _require_exact_mapping(raw_point, frozenset({"as_of", "close", "volume"}))
                session = _require_date(point["as_of"])
                if prior_session is not None and session <= prior_session:
                    _invalid()
                prior_session = session
                if session > as_of:
                    _invalid()
                volume_raw = point["volume"]
                volume = None if volume_raw is None else _require_number(volume_raw, positive=False)
                points.append(
                    {
                        "as_of": session,
                        "close": _require_number(point["close"], positive=True),
                        "volume": volume,
                    }
                )
            if prior_session != as_of:
                _invalid()
            normalized_series[symbol] = {"currency": currency, "points": points}

        return {
            "schema_version": DECISION_PRICE_SERIES_ARTIFACT_SCHEMA_VERSION,
            "strategy_scope": strategy_scope,
            "as_of": as_of,
            "adjustment_basis": adjustment_basis,
            "source_ids": list(source_ids),
            "series": normalized_series,
        }
    except (InvalidDecisionDataArtifact, TypeError, ValueError, KeyError):
        raise InvalidDecisionDataArtifact("invalid decision price-series artifact") from None


def canonical_decision_price_series_artifact_bytes(value: object) -> bytes:
    """Return canonical bytes after strict validation."""

    return _canonical(validate_decision_price_series_artifact(value))


def read_decision_price_series_artifact_json(payload: bytes | str) -> dict[str, object]:
    """Strictly parse a portable projection without accepting duplicate keys."""

    try:
        if isinstance(payload, bytes):
            payload = payload.decode("utf-8")
        if not isinstance(payload, str):
            _invalid()
        parsed = json.loads(
            payload,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_nonfinite_constant,
        )
        return validate_decision_price_series_artifact(parsed)
    except (InvalidDecisionDataArtifact, UnicodeDecodeError, TypeError, ValueError, json.JSONDecodeError):
        raise InvalidDecisionDataArtifact("invalid decision price-series artifact") from None


def _require_verified_artifact_binding(binding: DecisionDataBinding) -> None:
    if (
        binding.mode
        not in {
            DECISION_DATA_MODE_ARTIFACT_OPTIONAL,
            DECISION_DATA_MODE_ARTIFACT_REQUIRED,
        }
        or binding.assurance_status != DECISION_DATA_ASSURANCE_VERIFIED
    ):
        raise InvalidDecisionDataArtifact("decision data binding is not verified for artifact use")


def price_series_from_decision_price_series_artifact(
    artifact: object,
    *,
    binding: DecisionDataBinding,
) -> dict[str, PriceSeries]:
    """Translate a verified projection only when its public identity matches."""

    _require_verified_artifact_binding(binding)
    normalized = validate_decision_price_series_artifact(artifact)
    if (
        normalized["strategy_scope"] != binding.strategy_scope
        or normalized["as_of"] != binding.as_of
        or normalized["adjustment_basis"] != binding.adjustment_basis
        or tuple(normalized["source_ids"]) != binding.source_ids
    ):
        raise InvalidDecisionDataArtifact("decision price-series artifact does not match binding")

    result: dict[str, PriceSeries] = {}
    for symbol, raw_payload in normalized["series"].items():
        payload = _require_exact_mapping(raw_payload, frozenset({"currency", "points"}))
        points = tuple(
            PricePoint(
                as_of=datetime.combine(date.fromisoformat(point["as_of"]), time.min, tzinfo=UTC),
                close=float(point["close"]),
                volume=(None if point["volume"] is None else float(point["volume"])),
            )
            for point in payload["points"]
        )
        result[symbol] = PriceSeries(symbol=symbol, currency=str(payload["currency"]), points=points)
    return result


def verify_decision_price_series_artifact_members(
    *,
    binding: DecisionDataBinding,
    manifest_bytes: bytes,
    decision_price_series_bytes: bytes,
) -> dict[str, PriceSeries]:
    """Verify immutable manifest/member bytes, then return safe price series.

    A transport adapter resolves the private root.  This function deliberately
    receives only bytes, so storage paths and credentials cannot enter the
    public runtime target or its execution report.
    """

    try:
        _require_verified_artifact_binding(binding)
        manifest = read_research_input_manifest_json(manifest_bytes)
        if manifest_bytes != canonical_research_input_manifest_bytes(manifest):
            _invalid()
        if research_input_manifest_sha256(manifest) != binding.artifact_sha256:
            _invalid()
        members = {str(member["path"]): member for member in manifest["members"]}
        member = members.get(DECISION_PRICE_SERIES_MEMBER_PATH)
        if not isinstance(member, Mapping):
            _invalid()
        if (
            member.get("size_bytes") != len(decision_price_series_bytes)
            or member.get("sha256") != sha256(decision_price_series_bytes).hexdigest()
        ):
            _invalid()
        if decision_price_series_bytes != canonical_decision_price_series_artifact_bytes(
            read_decision_price_series_artifact_json(decision_price_series_bytes)
        ):
            _invalid()
        return price_series_from_decision_price_series_artifact(
            read_decision_price_series_artifact_json(decision_price_series_bytes),
            binding=binding,
        )
    except (InvalidDecisionDataArtifact, TypeError, ValueError, KeyError):
        raise InvalidDecisionDataArtifact("invalid decision price-series artifact") from None


__all__ = [
    "DECISION_PRICE_SERIES_ARTIFACT_SCHEMA_VERSION",
    "DECISION_PRICE_SERIES_MEMBER_PATH",
    "InvalidDecisionDataArtifact",
    "canonical_decision_price_series_artifact_bytes",
    "price_series_from_decision_price_series_artifact",
    "read_decision_price_series_artifact_json",
    "validate_decision_price_series_artifact",
    "verify_decision_price_series_artifact_members",
]
