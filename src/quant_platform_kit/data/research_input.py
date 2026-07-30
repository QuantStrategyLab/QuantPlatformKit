"""Pure validation and canonicalization for research-input manifest v1.

The runtime must provide an IANA timezone database through the operating
system or the ``tzdata`` package; validation fails closed when it is absent.
"""

from __future__ import annotations

from collections.abc import Mapping as _Mapping
from datetime import date as _date
from datetime import datetime as _datetime
from datetime import timezone as _datetime_timezone
import hashlib as _hashlib
import json as _json
import re as _re
from zoneinfo import ZoneInfo as _ZoneInfo
from zoneinfo import available_timezones as _available_timezones

del annotations

__all__ = [
    "InvalidResearchInputEvidence",
    "validate_research_input_manifest",
    "canonical_research_input_manifest_bytes",
    "research_input_manifest_sha256",
    "read_research_input_manifest_json",
]


_TOP_LEVEL_REQUIRED = frozenset(
    {
        "schema_version",
        "manifest_id",
        "research_input_contract_id",
        "domain",
        "profile",
        "artifact_type",
        "observed_at",
        "effective_at",
        "as_of",
        "producer",
        "calendar",
        "adjustment",
        "sources",
        "members",
    }
)
_PRODUCER_REQUIRED = frozenset(
    {"repository", "commit_sha", "tree_sha", "tool", "tool_version"}
)
_CALENDAR_REQUIRED = frozenset(
    {"calendar_id", "timezone", "session_date", "source", "source_revision"}
)
_ADJUSTMENT_REQUIRED = frozenset({"policy", "source", "source_revision"})
_SOURCE_REQUIRED = frozenset(
    {"source_id", "revision", "observed_at", "content_sha256"}
)
_MEMBER_REQUIRED = frozenset({"path", "media_type", "size_bytes", "sha256"})
_ADJUSTMENT_POLICIES = frozenset(
    {"raw", "split_adjusted", "total_return_adjusted"}
)
_COMMIT_PATTERN = _re.compile(r"[0-9a-f]{40}")
_SHA256_PATTERN = _re.compile(r"[0-9a-f]{64}")
_DATE_PATTERN = _re.compile(r"\d{4}-\d{2}-\d{2}")
_TIMESTAMP_PATTERN = _re.compile(
    r"(?P<whole>[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2})"
    r"(?:\.(?P<fraction>[0-9]+))?"
    r"(?P<offset>Z|[+-][0-9]{2}:[0-9]{2})"
)
_HOST_LOCAL_TIMEZONE_KEYS = frozenset({"Factory", "localtime", "posixrules"})
_HOST_LOCAL_TIMEZONE_PREFIXES = ("posix/", "right/")


class InvalidResearchInputEvidence(ValueError):
    """The manifest is not strict, canonical research-input evidence."""


def _fail(message: str) -> None:
    raise InvalidResearchInputEvidence(message)


def _object(
    value: object,
    required: frozenset[str],
    optional: frozenset[str] = frozenset(),
) -> _Mapping[str, object]:
    if not isinstance(value, _Mapping):
        _fail("expected an object")
    if any(type(key) is not str for key in value):
        _fail("object keys must be strings")
    keys = frozenset(value)
    if not required <= keys or not keys <= required | optional:
        _fail("object fields do not match the frozen contract")
    return value


def _nonempty(value: object) -> str:
    if type(value) is not str or not value.strip():
        _fail("expected a non-empty string")
    if any("\ud800" <= character <= "\udfff" for character in value):
        _fail("strings must contain only Unicode scalar values")
    return value


def _matches(value: object, pattern: _re.Pattern[str]) -> str:
    text = _nonempty(value)
    if pattern.fullmatch(text) is None:
        _fail("string does not match the frozen format")
    return text


def _timestamp(value: object) -> tuple[str, tuple[_datetime, str]]:
    text = _nonempty(value)
    match = _TIMESTAMP_PATTERN.fullmatch(text)
    if match is None:
        _fail("timestamp must use strict ISO-8601 date-time syntax")
    offset = match.group("offset")
    if offset == "-00:00":
        _fail("timestamp must not use an unknown UTC offset")
    try:
        whole_utc = _datetime.fromisoformat(
            match.group("whole") + ("+00:00" if offset == "Z" else offset)
        ).astimezone(_datetime_timezone.utc)
    except Exception:
        _fail("timestamp must be valid ISO-8601")
    fraction = (match.group("fraction") or "").rstrip("0")
    return text, (whole_utc, fraction)


def _calendar_date(value: object) -> str:
    text = _nonempty(value)
    if _DATE_PATTERN.fullmatch(text) is None:
        _fail("session_date must use YYYY-MM-DD")
    try:
        _date.fromisoformat(text)
    except Exception:
        _fail("session_date must be a valid ISO date")
    return text


def _timezone(value: object) -> str:
    text = _nonempty(value)
    try:
        available = _available_timezones()
    except Exception:
        _fail("IANA timezone database is unavailable")
    if not available:
        _fail("IANA timezone database is unavailable")
    if (
        text in _HOST_LOCAL_TIMEZONE_KEYS
        or text.startswith(_HOST_LOCAL_TIMEZONE_PREFIXES)
        or text not in available
    ):
        _fail("timezone must be a valid IANA timezone")
    try:
        _ZoneInfo(text)
    except Exception:
        _fail("IANA timezone database cannot load the requested timezone")
    return text


def _member_path(value: object) -> str:
    path = _nonempty(value)
    if path.startswith("/") or "\\" in path or "\x00" in path:
        _fail("member path must be relative POSIX")
    if any(part in {"", ".", ".."} for part in path.split("/")):
        _fail("member path contains an unsafe segment")
    return path


def _canonical_order(value: object) -> object:
    if isinstance(value, dict):
        return {key: _canonical_order(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [_canonical_order(child) for child in value]
    return value


def _validate(manifest: _Mapping[str, object]) -> dict[str, object]:
    root = _object(
        manifest,
        _TOP_LEVEL_REQUIRED,
        frozenset({"parent_manifest_sha256"}),
    )
    if root["schema_version"] != "research_input_manifest.v1":
        _fail("schema_version is invalid")

    result: dict[str, object] = {
        "schema_version": "research_input_manifest.v1",
        "manifest_id": _nonempty(root["manifest_id"]),
        "research_input_contract_id": _nonempty(
            root["research_input_contract_id"]
        ),
        "domain": _nonempty(root["domain"]),
        "profile": _nonempty(root["profile"]),
        "artifact_type": _nonempty(root["artifact_type"]),
    }
    observed_text, observed_at = _timestamp(root["observed_at"])
    effective_text, effective_at = _timestamp(root["effective_at"])
    as_of_text, as_of = _timestamp(root["as_of"])
    if observed_at > as_of or effective_at > as_of:
        _fail("manifest timestamps exceed as_of")
    result.update(
        {
            "observed_at": observed_text,
            "effective_at": effective_text,
            "as_of": as_of_text,
        }
    )

    producer = _object(root["producer"], _PRODUCER_REQUIRED)
    result["producer"] = {
        "repository": _nonempty(producer["repository"]),
        "commit_sha": _matches(producer["commit_sha"], _COMMIT_PATTERN),
        "tree_sha": _matches(producer["tree_sha"], _COMMIT_PATTERN),
        "tool": _nonempty(producer["tool"]),
        "tool_version": _nonempty(producer["tool_version"]),
    }

    calendar = _object(root["calendar"], _CALENDAR_REQUIRED)
    result["calendar"] = {
        "calendar_id": _nonempty(calendar["calendar_id"]),
        "timezone": _timezone(calendar["timezone"]),
        "session_date": _calendar_date(calendar["session_date"]),
        "source": _nonempty(calendar["source"]),
        "source_revision": _nonempty(calendar["source_revision"]),
    }

    adjustment = _object(root["adjustment"], _ADJUSTMENT_REQUIRED)
    policy = _nonempty(adjustment["policy"])
    if policy not in _ADJUSTMENT_POLICIES:
        _fail("adjustment policy is invalid")
    result["adjustment"] = {
        "policy": policy,
        "source": _nonempty(adjustment["source"]),
        "source_revision": _nonempty(adjustment["source_revision"]),
    }

    sources_value = root["sources"]
    if type(sources_value) is not list or not sources_value:
        _fail("sources must be a non-empty array")
    sources: list[dict[str, object]] = []
    source_ids: list[str] = []
    for source_value in sources_value:
        source = _object(source_value, _SOURCE_REQUIRED)
        source_id = _nonempty(source["source_id"])
        source_observed_text, source_observed_at = _timestamp(
            source["observed_at"]
        )
        if source_observed_at > as_of:
            _fail("source observed_at exceeds as_of")
        source_ids.append(source_id)
        sources.append(
            {
                "source_id": source_id,
                "revision": _nonempty(source["revision"]),
                "observed_at": source_observed_text,
                "content_sha256": _matches(
                    source["content_sha256"], _SHA256_PATTERN
                ),
            }
        )
    if source_ids != sorted(source_ids) or len(source_ids) != len(set(source_ids)):
        _fail("sources must be strictly ordered and unique by source_id")
    result["sources"] = sources

    members_value = root["members"]
    if type(members_value) is not list or not members_value:
        _fail("members must be a non-empty array")
    members: list[dict[str, object]] = []
    member_paths: list[str] = []
    for member_value in members_value:
        member = _object(member_value, _MEMBER_REQUIRED)
        path = _member_path(member["path"])
        size_bytes = member["size_bytes"]
        if type(size_bytes) is not int or size_bytes < 0:
            _fail("size_bytes must be a non-negative integer")
        member_paths.append(path)
        members.append(
            {
                "path": path,
                "media_type": _nonempty(member["media_type"]),
                "size_bytes": size_bytes,
                "sha256": _matches(member["sha256"], _SHA256_PATTERN),
            }
        )
    if member_paths != sorted(member_paths) or len(member_paths) != len(
        set(member_paths)
    ):
        _fail("members must be strictly ordered and unique by path")
    result["members"] = members

    if "parent_manifest_sha256" in root:
        result["parent_manifest_sha256"] = _matches(
            root["parent_manifest_sha256"], _SHA256_PATTERN
        )
    return _canonical_order(result)


def validate_research_input_manifest(
    manifest: _Mapping[str, object],
) -> dict[str, object]:
    """Validate and return an independent canonical-order manifest.

    The runtime must provide a system tzdb or the ``tzdata`` package.
    """
    try:
        return _validate(manifest)
    except InvalidResearchInputEvidence:
        raise
    except Exception:
        raise InvalidResearchInputEvidence("invalid research-input manifest") from None


def canonical_research_input_manifest_bytes(
    manifest: _Mapping[str, object],
) -> bytes:
    """Return strict canonical UTF-8 JSON bytes without a trailing newline."""
    try:
        validated = validate_research_input_manifest(manifest)
        return _json.dumps(
            validated,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except InvalidResearchInputEvidence:
        raise
    except Exception:
        raise InvalidResearchInputEvidence("cannot canonicalize manifest") from None


def research_input_manifest_sha256(manifest: _Mapping[str, object]) -> str:
    """Return the SHA-256 digest of strict canonical manifest bytes."""
    try:
        return _hashlib.sha256(
            canonical_research_input_manifest_bytes(manifest)
        ).hexdigest()
    except InvalidResearchInputEvidence:
        raise
    except Exception:
        raise InvalidResearchInputEvidence("cannot digest manifest") from None


def _reject_duplicate_keys(
    pairs: list[tuple[str, object]],
) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            _fail("duplicate JSON object key")
        result[key] = value
    return result


def _reject_nonfinite(_value: str) -> object:
    _fail("non-finite JSON constants are forbidden")


def read_research_input_manifest_json(payload: bytes | str) -> dict[str, object]:
    """Strictly parse and validate one JSON object from bytes or text."""
    try:
        if type(payload) is bytes:
            text = payload.decode("utf-8")
        elif type(payload) is str:
            text = payload
        else:
            _fail("payload must be bytes or str")
        parsed = _json.loads(
            text,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_nonfinite,
        )
        if not isinstance(parsed, dict):
            _fail("manifest JSON root must be an object")
        return validate_research_input_manifest(parsed)
    except InvalidResearchInputEvidence:
        raise
    except Exception:
        raise InvalidResearchInputEvidence("invalid research-input JSON") from None
