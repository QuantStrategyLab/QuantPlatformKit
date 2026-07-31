"""Validation helpers for the frozen research-input manifest v1 contract."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from hashlib import sha256
import json
from math import isfinite
import re
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


class InvalidResearchInputEvidence(ValueError):
    """Raised when a research-input manifest or its JSON readback is invalid."""


_BLANK_CODE_POINTS = frozenset(
    (*range(0x0009, 0x000E), *range(0x001C, 0x0020), 0x0020, 0x0085, 0x00A0,
     0x1680, *range(0x2000, 0x200B), 0x2028, 0x2029, 0x202F, 0x205F, 0x3000, 0xFEFF)
)
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_TIMESTAMP_RE = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T(?:[01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9](?:\.[0-9]+)?(?:Z|[+-](?:[01][0-9]|2[0-3]):[0-5][0-9])$"
)
_DATE_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
_TOP_LEVEL_KEYS = frozenset(
    {
        "schema_version", "manifest_id", "research_input_contract_id", "domain", "profile",
        "artifact_type", "observed_at", "effective_at", "as_of", "producer", "calendar",
        "adjustment", "sources", "members", "parent_manifest_sha256",
    }
)
_REQUIRED_TOP_LEVEL_KEYS = _TOP_LEVEL_KEYS - {"parent_manifest_sha256"}

__all__ = [
    "InvalidResearchInputEvidence",
    "validate_research_input_manifest",
    "canonical_research_input_manifest_bytes",
    "research_input_manifest_sha256",
    "read_research_input_manifest_json",
]


def _invalid() -> None:
    raise InvalidResearchInputEvidence("invalid research-input manifest")


def _is_nonblank(value: str) -> bool:
    return bool(value) and any(ord(character) not in _BLANK_CODE_POINTS for character in value)


def _require_nonblank_string(value: object) -> str:
    if (
        not isinstance(value, str)
        or not _is_nonblank(value)
        or any(0xD800 <= ord(character) <= 0xDFFF for character in value)
    ):
        _invalid()
    return value


def _require_exact_keys(value: object, required: frozenset[str], optional: frozenset[str] = frozenset()) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(not isinstance(key, str) for key in value):
        _invalid()
    keys = set(value)
    if not required <= keys or keys - required - optional:
        _invalid()
    return dict(value)


def _require_sha256(value: object) -> str:
    value = _require_nonblank_string(value)
    if not _SHA256_RE.fullmatch(value):
        _invalid()
    return value


def _require_git_sha(value: object) -> str:
    value = _require_nonblank_string(value)
    if not _GIT_SHA_RE.fullmatch(value):
        _invalid()
    return value


def _parse_timestamp(value: object) -> tuple[int, int, int]:
    value = _require_nonblank_string(value)
    if not _TIMESTAMP_RE.fullmatch(value) or value.endswith("-00:00"):
        _invalid()
    try:
        date_part, time_part = value.split("T", maxsplit=1)
        year, month, day = map(int, date_part.split("-"))
        hour, minute, second = map(int, time_part[:8].split(":"))
        day_number = date(year, month, day).toordinal()
    except ValueError:
        _invalid()
    remainder = time_part[8:]
    fraction = ""
    if remainder.startswith("."):
        fraction, remainder = remainder.split("Z" if remainder.endswith("Z") else remainder[-6:], maxsplit=1)
    if value.endswith("Z"):
        offset_seconds = 0
    else:
        sign = 1 if value[-6] == "+" else -1
        offset_seconds = sign * (int(value[-5:-3]) * 3600 + int(value[-2:]) * 60)
    numerator = int(fraction[1:]) if fraction else 0
    denominator = 10 ** (len(fraction) - 1) if fraction else 1
    return day_number * 86400 + hour * 3600 + minute * 60 + second - offset_seconds, numerator, denominator


def _not_after(left: tuple[int, int, int], right: tuple[int, int, int]) -> bool:
    if left[0] != right[0]:
        return left[0] < right[0]
    return left[1] * right[2] <= right[1] * left[2]


def _require_date(value: object) -> str:
    value = _require_nonblank_string(value)
    if not _DATE_RE.fullmatch(value):
        _invalid()
    try:
        date.fromisoformat(value)
    except ValueError:
        _invalid()
    return value


def _validate_json_value(value: object) -> None:
    if value is None or isinstance(value, (str, bool)):
        return
    if type(value) is int:
        return
    if type(value) is float:
        if not isfinite(value):
            _invalid()
        return
    if isinstance(value, list):
        for item in value:
            _validate_json_value(item)
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str):
                _invalid()
            _validate_json_value(item)
        return
    _invalid()


def _validate_member_path(value: object) -> str:
    value = _require_nonblank_string(value)
    if "\\" in value or "\x00" in value:
        _invalid()
    components = value.split("/")
    if any(component in {"", ".", ".."} for component in components):
        _invalid()
    return value


def _validate_producer(value: object) -> dict[str, object]:
    value = _require_exact_keys(
        value,
        frozenset({"repository", "commit_sha", "tree_sha", "tool", "tool_version"}),
    )
    value["repository"] = _require_nonblank_string(value["repository"])
    value["commit_sha"] = _require_git_sha(value["commit_sha"])
    value["tree_sha"] = _require_git_sha(value["tree_sha"])
    value["tool"] = _require_nonblank_string(value["tool"])
    value["tool_version"] = _require_nonblank_string(value["tool_version"])
    return value


def _validate_calendar(value: object) -> dict[str, object]:
    value = _require_exact_keys(
        value,
        frozenset({"calendar_id", "timezone", "session_date", "source", "source_revision"}),
    )
    value["calendar_id"] = _require_nonblank_string(value["calendar_id"])
    timezone = _require_nonblank_string(value["timezone"])
    try:
        ZoneInfo(timezone)
    except ZoneInfoNotFoundError:
        _invalid()
    if timezone in {"Factory", "posixrules"}:
        _invalid()
    value["timezone"] = timezone
    value["session_date"] = _require_date(value["session_date"])
    value["source"] = _require_nonblank_string(value["source"])
    value["source_revision"] = _require_nonblank_string(value["source_revision"])
    return value


def _validate_adjustment(value: object) -> dict[str, object]:
    value = _require_exact_keys(value, frozenset({"policy", "source", "source_revision"}))
    if value["policy"] not in {"raw", "split_adjusted", "total_return_adjusted"}:
        _invalid()
    value["source"] = _require_nonblank_string(value["source"])
    value["source_revision"] = _require_nonblank_string(value["source_revision"])
    return value


def _validate_sources(value: object, *, as_of: tuple[int, int, int]) -> list[dict[str, object]]:
    if not isinstance(value, list) or not value:
        _invalid()
    sources: list[dict[str, object]] = []
    previous = ""
    for source in value:
        source = _require_exact_keys(
            source,
            frozenset({"source_id", "revision", "observed_at", "content_sha256"}),
        )
        source_id = _require_nonblank_string(source["source_id"])
        if source_id <= previous or not _not_after(_parse_timestamp(source["observed_at"]), as_of):
            _invalid()
        previous = source_id
        source["source_id"] = source_id
        source["revision"] = _require_nonblank_string(source["revision"])
        source["observed_at"] = _require_nonblank_string(source["observed_at"])
        source["content_sha256"] = _require_sha256(source["content_sha256"])
        sources.append(source)
    return sources


def _validate_members(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list) or not value:
        _invalid()
    members: list[dict[str, object]] = []
    previous = ""
    for member in value:
        member = _require_exact_keys(member, frozenset({"path", "media_type", "size_bytes", "sha256"}))
        path = _validate_member_path(member["path"])
        if path <= previous or type(member["size_bytes"]) is not int or member["size_bytes"] < 0:
            _invalid()
        previous = path
        member["path"] = path
        member["media_type"] = _require_nonblank_string(member["media_type"])
        member["sha256"] = _require_sha256(member["sha256"])
        members.append(member)
    return members


def validate_research_input_manifest(manifest: Mapping[str, object]) -> dict[str, object]:
    """Validate and return an independent canonical-order manifest dictionary."""
    try:
        _validate_json_value(manifest)
        result = _require_exact_keys(manifest, _REQUIRED_TOP_LEVEL_KEYS, frozenset({"parent_manifest_sha256"}))
        if result["schema_version"] != "research_input_manifest.v1":
            _invalid()
        for field in ("schema_version", "manifest_id", "research_input_contract_id", "domain", "profile", "artifact_type"):
            result[field] = _require_nonblank_string(result[field])
        observed_at = _parse_timestamp(result["observed_at"])
        effective_at = _parse_timestamp(result["effective_at"])
        as_of = _parse_timestamp(result["as_of"])
        if not _not_after(observed_at, as_of) or not _not_after(effective_at, as_of):
            _invalid()
        result["observed_at"] = _require_nonblank_string(result["observed_at"])
        result["effective_at"] = _require_nonblank_string(result["effective_at"])
        result["as_of"] = _require_nonblank_string(result["as_of"])
        result["producer"] = _validate_producer(result["producer"])
        result["calendar"] = _validate_calendar(result["calendar"])
        result["adjustment"] = _validate_adjustment(result["adjustment"])
        result["sources"] = _validate_sources(result["sources"], as_of=as_of)
        result["members"] = _validate_members(result["members"])
        if "parent_manifest_sha256" in result:
            result["parent_manifest_sha256"] = _require_sha256(result["parent_manifest_sha256"])
        return json.loads(json.dumps(result, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False))
    except (InvalidResearchInputEvidence, TypeError, ValueError, KeyError, json.JSONDecodeError):
        raise InvalidResearchInputEvidence("invalid research-input manifest") from None


def canonical_research_input_manifest_bytes(manifest: Mapping[str, object]) -> bytes:
    """Return validated canonical UTF-8 JSON bytes without a trailing newline."""
    validated = validate_research_input_manifest(manifest)
    return json.dumps(
        validated,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def research_input_manifest_sha256(manifest: Mapping[str, object]) -> str:
    """Return the SHA-256 digest of validated canonical manifest bytes."""
    return sha256(canonical_research_input_manifest_bytes(manifest)).hexdigest()


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            _invalid()
        result[key] = value
    return result


def _reject_nonfinite_constant(_: str) -> None:
    _invalid()


def read_research_input_manifest_json(payload: bytes | str) -> dict[str, object]:
    """Strictly parse and validate an in-memory research-input manifest JSON payload."""
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
        if not isinstance(parsed, dict):
            _invalid()
        return validate_research_input_manifest(parsed)
    except (InvalidResearchInputEvidence, UnicodeDecodeError, TypeError, ValueError, json.JSONDecodeError):
        raise InvalidResearchInputEvidence("invalid research-input manifest JSON") from None
