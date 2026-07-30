from __future__ import annotations

import hashlib
import importlib
import inspect
import json
from pathlib import Path
import re
from types import MappingProxyType
import typing

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = (
    ROOT
    / "src"
    / "quant_platform_kit"
    / "schemas"
    / "research-input-manifest.v1.schema.json"
)
PUBLIC_SURFACE = {
    "InvalidResearchInputEvidence",
    "validate_research_input_manifest",
    "canonical_research_input_manifest_bytes",
    "research_input_manifest_sha256",
    "read_research_input_manifest_json",
}


# Frozen contract-to-test traceability matrix (contract sections 4-6):
# - exact Python surface and normalized failures: test_exact_python_surface,
#   test_all_public_functions_normalize_failures
# - complete fields / exact objects / no defaults: test_valid_manifest_and_deep_copy,
#   test_rejects_missing_or_unknown_fields
# - required non-blank strings and exact SHA shapes:
#   test_rejects_blank_strings, test_rejects_bad_hashes
# - timestamps, ordering, calendar timezone/date, adjustment policy:
#   test_rejects_bad_timestamps_and_time_order,
#   test_preserves_fractional_timestamp_precision,
#   test_rejects_bad_calendar_and_adjustment,
#   test_timezone_validation_fails_closed_without_tzdb
# - ordered unique source/member identities and safe POSIX paths:
#   test_rejects_bad_source_identity_order,
#   test_rejects_bad_member_identity_or_path
# - Unicode scalar strings and runtime-resolvable annotations:
#   test_rejects_lone_surrogates, test_public_annotations_resolve_at_runtime
# - JSON-compatible scalar discipline:
#   test_rejects_bad_size_or_non_json_values
# - canonical bytes and digest: test_canonical_bytes_and_digest_are_deterministic
# - canonical-order independent deep return:
#   test_valid_manifest_and_deep_copy,
#   test_mapping_key_order_does_not_change_canonical_output
# - strict JSON readback: test_strict_json_readback,
#   test_readback_rejects_duplicate_keys_at_every_depth
# - schema structural isomorphism / no fake semantic extensions:
#   test_schema_matches_frozen_structural_contract


def _module():
    return importlib.import_module("quant_platform_kit.data.research_input")


def _valid_manifest() -> dict[str, object]:
    return {
        "schema_version": "research_input_manifest.v1",
        "manifest_id": "pit-us-equity-20260730",
        "research_input_contract_id": "shared-us-equity-pit.v1",
        "domain": "us_equity",
        "profile": "shared_daily",
        "artifact_type": "immutable_pit_bundle",
        "observed_at": "2026-07-30T08:00:00+00:00",
        "effective_at": "2026-07-29T13:30:00-04:00",
        "as_of": "2026-07-30T09:00:00Z",
        "producer": {
            "repository": "QuantStrategyLab/UsEquitySnapshotPipelines",
            "commit_sha": "a" * 40,
            "tree_sha": "b" * 40,
            "tool": "build_shared_pit",
            "tool_version": "1.0.0",
        },
        "calendar": {
            "calendar_id": "XNYS",
            "timezone": "America/New_York",
            "session_date": "2026-07-29",
            "source": "exchange_calendars",
            "source_revision": "4.11.1",
        },
        "adjustment": {
            "policy": "split_adjusted",
            "source": "vendor-adjustments",
            "source_revision": "2026-07-30",
        },
        "sources": [
            {
                "source_id": "daily-bars",
                "revision": "2026-07-30T07:00:00Z",
                "observed_at": "2026-07-30T07:30:00Z",
                "content_sha256": "c" * 64,
            },
            {
                "source_id": "security-master",
                "revision": "2026-07-30",
                "observed_at": "2026-07-30T07:45:00+00:00",
                "content_sha256": "d" * 64,
            },
        ],
        "members": [
            {
                "path": "data/bars.parquet",
                "media_type": "application/vnd.apache.parquet",
                "size_bytes": 1024,
                "sha256": "e" * 64,
            },
            {
                "path": "metadata/universe.json",
                "media_type": "application/json",
                "size_bytes": 128,
                "sha256": "f" * 64,
            },
        ],
        "parent_manifest_sha256": "0" * 64,
    }


def _assert_invalid(manifest: object) -> None:
    module = _module()
    with pytest.raises(module.InvalidResearchInputEvidence):
        module.validate_research_input_manifest(manifest)


def _load_schema() -> dict[str, object]:
    def reject_duplicate_keys(pairs):
        result = {}
        for key, value in pairs:
            assert key not in result, f"duplicate schema key: {key}"
            result[key] = value
        return result

    return json.loads(
        SCHEMA_PATH.read_text(encoding="utf-8"),
        object_pairs_hook=reject_duplicate_keys,
    )


def _reverse_mapping_keys(value):
    if isinstance(value, dict):
        return {
            key: _reverse_mapping_keys(child)
            for key, child in reversed(tuple(value.items()))
        }
    if isinstance(value, list):
        return [_reverse_mapping_keys(child) for child in value]
    return value


def _assert_canonical_key_order(value: object) -> None:
    if isinstance(value, dict):
        assert list(value) == sorted(value)
        for child in value.values():
            _assert_canonical_key_order(child)
    elif isinstance(value, list):
        for child in value:
            _assert_canonical_key_order(child)


def test_exact_python_surface() -> None:
    module = _module()

    assert set(module.__all__) == PUBLIC_SURFACE
    assert {
        name for name in vars(module) if not name.startswith("_")
    } == PUBLIC_SURFACE
    assert issubclass(module.InvalidResearchInputEvidence, ValueError)
    assert list(inspect.signature(module.validate_research_input_manifest).parameters) == [
        "manifest"
    ]
    assert list(
        inspect.signature(module.canonical_research_input_manifest_bytes).parameters
    ) == ["manifest"]
    assert list(inspect.signature(module.research_input_manifest_sha256).parameters) == [
        "manifest"
    ]
    assert list(inspect.signature(module.read_research_input_manifest_json).parameters) == [
        "payload"
    ]


def test_public_annotations_resolve_at_runtime() -> None:
    module = _module()

    for function in (
        module.validate_research_input_manifest,
        module.canonical_research_input_manifest_bytes,
        module.research_input_manifest_sha256,
        module.read_research_input_manifest_json,
    ):
        assert typing.get_type_hints(function)


def test_valid_manifest_and_deep_copy() -> None:
    module = _module()
    original = _valid_manifest()
    validated = module.validate_research_input_manifest(MappingProxyType(original))

    assert validated == original
    assert type(validated) is dict
    _assert_canonical_key_order(validated)

    original["producer"]["tool"] = "mutated"
    original["sources"][0]["revision"] = "mutated"
    original["members"].append({"path": "mutated"})
    assert validated["producer"]["tool"] == "build_shared_pit"
    assert validated["sources"][0]["revision"] == "2026-07-30T07:00:00Z"
    assert len(validated["members"]) == 2

    validated["producer"]["tool"] = "returned-mutation"
    fresh = module.validate_research_input_manifest(_valid_manifest())
    assert fresh["producer"]["tool"] == "build_shared_pit"


@pytest.mark.parametrize(
    ("path", "key"),
    [
        *(((), key) for key in (
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
        )),
        *((("producer",), key) for key in (
            "repository",
            "commit_sha",
            "tree_sha",
            "tool",
            "tool_version",
        )),
        *((("calendar",), key) for key in (
            "calendar_id",
            "timezone",
            "session_date",
            "source",
            "source_revision",
        )),
        *((("adjustment",), key) for key in (
            "policy",
            "source",
            "source_revision",
        )),
        *((("sources", 0), key) for key in (
            "source_id",
            "revision",
            "observed_at",
            "content_sha256",
        )),
        *((("members", 0), key) for key in (
            "path",
            "media_type",
            "size_bytes",
            "sha256",
        )),
    ],
)
def test_rejects_every_missing_required_field(path, key) -> None:
    missing = _valid_manifest()
    target = missing
    for part in path:
        target = target[part]
    target.pop(key)
    _assert_invalid(missing)


@pytest.mark.parametrize(
    "path",
    [(), ("producer",), ("calendar",), ("adjustment",), ("sources", 0), ("members", 0)],
)
def test_rejects_unknown_fields_in_every_object(path) -> None:
    unknown = _valid_manifest()
    target = unknown
    for part in path:
        target = target[part]
    target["unknown"] = "forbidden"
    _assert_invalid(unknown)


@pytest.mark.parametrize(
    ("path", "key"),
    [
        ((), "manifest_id"),
        ((), "research_input_contract_id"),
        ((), "domain"),
        ((), "profile"),
        ((), "artifact_type"),
        (("producer",), "repository"),
        (("producer",), "tool"),
        (("producer",), "tool_version"),
        (("calendar",), "calendar_id"),
        (("calendar",), "source"),
        (("calendar",), "source_revision"),
        (("adjustment",), "source"),
        (("adjustment",), "source_revision"),
        (("sources", 0), "source_id"),
        (("sources", 0), "revision"),
        (("members", 0), "media_type"),
    ],
)
def test_rejects_blank_strings(path, key) -> None:
    manifest = _valid_manifest()
    target = manifest
    for part in path:
        target = target[part]
    target[key] = " \t\n"
    _assert_invalid(manifest)


@pytest.mark.parametrize(
    ("path", "key", "value"),
    [
        ((), "schema_version", "research_input_manifest.v2"),
        (("producer",), "commit_sha", "A" * 40),
        (("producer",), "commit_sha", "a" * 39),
        (("producer",), "tree_sha", "g" * 40),
        (("sources", 0), "content_sha256", "C" * 64),
        (("sources", 0), "content_sha256", "c" * 63),
        (("members", 0), "sha256", "z" * 64),
        ((), "parent_manifest_sha256", "0" * 65),
    ],
)
def test_rejects_bad_hashes(path, key, value) -> None:
    manifest = _valid_manifest()
    target = manifest
    for part in path:
        target = target[part]
    target[key] = value
    _assert_invalid(manifest)


@pytest.mark.parametrize(
    ("path", "key", "value"),
    [
        ((), "observed_at", "2026-07-30T08:00:00"),
        ((), "observed_at", "2026-07-30Q08:00:00Z"),
        ((), "effective_at", "not-a-timestamp"),
        ((), "as_of", "2026-07-30"),
        ((), "as_of", "2026-07-30T09:00:00-00:00"),
        (("sources", 0), "observed_at", "2026-07-30T07:30:00"),
        (("sources", 0), "observed_at", "2026-07-30T07:30:00-00:00"),
        ((), "observed_at", "2026-07-30T10:00:00Z"),
        ((), "effective_at", "2026-07-30T10:00:00Z"),
        (("sources", 0), "observed_at", "2026-07-30T10:00:00Z"),
    ],
)
def test_rejects_bad_timestamps_and_time_order(path, key, value) -> None:
    manifest = _valid_manifest()
    target = manifest
    for part in path:
        target = target[part]
    target[key] = value
    _assert_invalid(manifest)


@pytest.mark.parametrize(
    "path",
    [
        ("observed_at",),
        ("effective_at",),
        ("sources", 0, "observed_at"),
    ],
)
def test_preserves_fractional_timestamp_precision(path) -> None:
    manifest = _valid_manifest()
    manifest["as_of"] = "2026-07-30T09:00:00.00000001Z"
    target = manifest
    for part in path[:-1]:
        target = target[part]
    target[path[-1]] = "2026-07-30T09:00:00.00000009Z"

    _assert_invalid(manifest)


@pytest.mark.parametrize(
    ("path", "key", "value"),
    [
        (("calendar",), "timezone", "UTC+08:00"),
        (("calendar",), "timezone", "Not/A_Zone"),
        (("calendar",), "timezone", "posixrules"),
        (("calendar",), "timezone", "localtime"),
        (("calendar",), "session_date", "2026-02-30"),
        (("calendar",), "session_date", "20260730"),
        (("adjustment",), "policy", "back_adjusted"),
    ],
)
def test_rejects_bad_calendar_and_adjustment(path, key, value) -> None:
    manifest = _valid_manifest()
    target = manifest
    for part in path:
        target = target[part]
    target[key] = value
    _assert_invalid(manifest)


def test_timezone_validation_fails_closed_without_tzdb(monkeypatch) -> None:
    module = _module()
    monkeypatch.setattr(module, "_available_timezones", lambda: set())

    with pytest.raises(
        module.InvalidResearchInputEvidence,
        match="timezone database",
    ):
        module.validate_research_input_manifest(_valid_manifest())


def test_rejects_host_local_timezone_alias_even_when_exposed(monkeypatch) -> None:
    module = _module()
    monkeypatch.setattr(module, "_available_timezones", lambda: {"localtime"})
    monkeypatch.setattr(module, "_ZoneInfo", lambda _key: object())

    manifest = _valid_manifest()
    manifest["calendar"]["timezone"] = "localtime"
    _assert_invalid(manifest)


def test_rejects_bad_source_identity_order() -> None:
    empty = _valid_manifest()
    empty["sources"] = []
    _assert_invalid(empty)

    unsorted = _valid_manifest()
    unsorted["sources"].reverse()
    _assert_invalid(unsorted)

    duplicate = _valid_manifest()
    duplicate["sources"][1]["source_id"] = duplicate["sources"][0]["source_id"]
    _assert_invalid(duplicate)


@pytest.mark.parametrize(
    "path",
    [
        "",
        " \t",
        "/absolute/data.json",
        ".",
        "./data.json",
        "../data.json",
        "data/./bars.parquet",
        "data/../bars.parquet",
        "data//bars.parquet",
        "data/bars.parquet/",
        r"data\bars.parquet",
        "data/\x00bars.parquet",
    ],
)
def test_rejects_bad_member_identity_or_path(path) -> None:
    manifest = _valid_manifest()
    manifest["members"][0]["path"] = path
    _assert_invalid(manifest)


def test_rejects_empty_unsorted_or_duplicate_members() -> None:
    empty = _valid_manifest()
    empty["members"] = []
    _assert_invalid(empty)

    unsorted = _valid_manifest()
    unsorted["members"].reverse()
    _assert_invalid(unsorted)

    duplicate = _valid_manifest()
    duplicate["members"][1]["path"] = duplicate["members"][0]["path"]
    _assert_invalid(duplicate)


@pytest.mark.parametrize("value", [-1, True, False, 1.0, float("nan"), float("inf"), -float("inf"), set()])
def test_rejects_bad_size_or_non_json_values(value) -> None:
    manifest = _valid_manifest()
    manifest["members"][0]["size_bytes"] = value
    _assert_invalid(manifest)


@pytest.mark.parametrize(
    ("path", "key"),
    [
        ((), "manifest_id"),
        (("producer",), "tool"),
        (("calendar",), "source"),
        (("sources", 0), "revision"),
        (("members", 0), "media_type"),
    ],
)
def test_rejects_lone_surrogates(path, key) -> None:
    manifest = _valid_manifest()
    target = manifest
    for part in path:
        target = target[part]
    target[key] = "invalid\ud800text"

    _assert_invalid(manifest)


def test_canonical_bytes_and_digest_are_deterministic() -> None:
    module = _module()
    manifest = _valid_manifest()
    manifest["profile"] = "共享输入"
    expected = json.dumps(
        manifest,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")

    actual = module.canonical_research_input_manifest_bytes(manifest)
    assert actual == expected
    assert "共享输入".encode() in actual
    assert b"\\u" not in actual
    assert not actual.endswith(b"\n")
    assert module.research_input_manifest_sha256(manifest) == hashlib.sha256(
        expected
    ).hexdigest()
    assert "sha256" not in module.validate_research_input_manifest(manifest)


def test_mapping_key_order_does_not_change_canonical_output() -> None:
    module = _module()
    manifest = _valid_manifest()
    reordered = _reverse_mapping_keys(manifest)

    assert module.validate_research_input_manifest(reordered) == manifest
    assert module.canonical_research_input_manifest_bytes(
        reordered
    ) == module.canonical_research_input_manifest_bytes(manifest)


def test_optional_parent_and_untrimmed_values_are_preserved() -> None:
    module = _module()
    manifest = _valid_manifest()
    manifest.pop("parent_manifest_sha256")
    manifest["manifest_id"] = " stable identity "

    validated = module.validate_research_input_manifest(manifest)
    assert "parent_manifest_sha256" not in validated
    assert validated["manifest_id"] == " stable identity "


@pytest.mark.parametrize("path", [(), ("producer",), ("sources", 0), ("members", 0)])
def test_rejects_non_string_object_keys(path) -> None:
    manifest = _valid_manifest()
    target = manifest
    for part in path:
        target = target[part]
    target[1] = "not-json"
    _assert_invalid(manifest)


@pytest.mark.parametrize(
    "payload",
    [
        b"\xff",
        "[]",
        "null",
        '{"schema_version": NaN}',
        '{"schema_version": Infinity}',
        '{"schema_version": -Infinity}',
        '{"schema_version":"research_input_manifest.v1"} trailing',
        "{}{}",
    ],
)
def test_strict_json_readback_rejects_invalid_payload(payload) -> None:
    module = _module()
    with pytest.raises(module.InvalidResearchInputEvidence):
        module.read_research_input_manifest_json(payload)


def test_strict_json_readback_accepts_bytes_and_text() -> None:
    module = _module()
    manifest = _valid_manifest()
    payload = module.canonical_research_input_manifest_bytes(manifest)

    assert module.read_research_input_manifest_json(payload) == manifest
    assert module.read_research_input_manifest_json(payload.decode("utf-8")) == manifest


@pytest.mark.parametrize(
    "payload",
    [
        '{"manifest_id":"one","manifest_id":"two"}',
        '{"producer":{"tool":"one","tool":"two"}}',
        '{"sources":[{"source_id":"one","source_id":"two"}]}',
    ],
)
def test_readback_rejects_duplicate_keys_at_every_depth(payload) -> None:
    module = _module()
    with pytest.raises(module.InvalidResearchInputEvidence):
        module.read_research_input_manifest_json(payload)


def test_all_public_functions_normalize_failures() -> None:
    module = _module()
    invalid = {"schema_version": "research_input_manifest.v1"}

    for function in (
        module.validate_research_input_manifest,
        module.canonical_research_input_manifest_bytes,
        module.research_input_manifest_sha256,
    ):
        with pytest.raises(module.InvalidResearchInputEvidence) as exc_info:
            function(invalid)
        assert type(exc_info.value) is module.InvalidResearchInputEvidence

    for payload in (object(), b"\xff", "{"):
        with pytest.raises(module.InvalidResearchInputEvidence) as exc_info:
            module.read_research_input_manifest_json(payload)
        assert type(exc_info.value) is module.InvalidResearchInputEvidence


def test_schema_matches_frozen_structural_contract() -> None:
    schema = _load_schema()
    required = {
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

    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["type"] == "object"
    assert set(schema["required"]) == required
    assert schema["additionalProperties"] is False
    assert schema["properties"]["schema_version"] == {
        "const": "research_input_manifest.v1"
    }
    assert schema["properties"]["parent_manifest_sha256"]["pattern"] == "^[0-9a-f]{64}$"
    assert schema["$defs"]["nonemptyString"]["pattern"] == "\\S"

    producer = schema["$defs"]["producer"]
    assert set(producer["required"]) == {
        "repository",
        "commit_sha",
        "tree_sha",
        "tool",
        "tool_version",
    }
    assert producer["additionalProperties"] is False
    assert producer["properties"]["commit_sha"]["pattern"] == "^[0-9a-f]{40}$"
    assert producer["properties"]["tree_sha"]["pattern"] == "^[0-9a-f]{40}$"

    calendar = schema["$defs"]["calendar"]
    assert set(calendar["required"]) == {
        "calendar_id",
        "timezone",
        "session_date",
        "source",
        "source_revision",
    }
    assert calendar["additionalProperties"] is False
    assert calendar["properties"]["session_date"]["format"] == "date"

    adjustment = schema["$defs"]["adjustment"]
    assert set(adjustment["required"]) == {"policy", "source", "source_revision"}
    assert adjustment["additionalProperties"] is False
    assert adjustment["properties"]["policy"]["enum"] == [
        "raw",
        "split_adjusted",
        "total_return_adjusted",
    ]

    source = schema["$defs"]["source"]
    assert set(source["required"]) == {
        "source_id",
        "revision",
        "observed_at",
        "content_sha256",
    }
    assert source["additionalProperties"] is False
    assert source["properties"]["observed_at"]["format"] == "date-time"
    assert source["properties"]["content_sha256"]["pattern"] == "^[0-9a-f]{64}$"

    member = schema["$defs"]["member"]
    assert set(member["required"]) == {"path", "media_type", "size_bytes", "sha256"}
    assert member["additionalProperties"] is False
    assert member["properties"]["size_bytes"] == {"type": "integer", "minimum": 0}
    assert member["properties"]["sha256"]["pattern"] == "^[0-9a-f]{64}$"
    assert re.fullmatch(member["properties"]["path"]["pattern"], "data/\x00x") is None
    assert re.fullmatch(member["properties"]["path"]["pattern"], "data//x") is None
    assert re.fullmatch(member["properties"]["path"]["pattern"], "data/x/") is None

    assert schema["properties"]["sources"]["minItems"] == 1
    assert schema["properties"]["members"]["minItems"] == 1
    assert all(
        schema["properties"][name]["format"] == "date-time"
        for name in ("observed_at", "effective_at", "as_of")
    )
    assert "x-" not in json.dumps(schema)


def test_rejects_later_timestamp_beyond_ambient_decimal_precision() -> None:
    manifest = _valid_manifest()
    manifest["as_of"] = "2026-07-30T09:00:00." + "0" * 40 + "1Z"
    manifest["observed_at"] = "2026-07-30T09:00:00." + "0" * 40 + "9Z"

    _assert_invalid(manifest)


@pytest.mark.parametrize("fraction", ["1", "12", "1234567", "1234567890123456789012345678901234567890"])
def test_accepts_every_nonempty_rfc3339_fraction_length(fraction: str) -> None:
    manifest = _valid_manifest()
    manifest["observed_at"] = f"2026-07-30T08:00:00.{fraction}Z"
    manifest["effective_at"] = f"2026-07-29T13:30:00.{fraction}-04:00"
    manifest["sources"][0]["observed_at"] = f"2026-07-30T07:30:00.{fraction}Z"

    assert _module().validate_research_input_manifest(manifest) == manifest


@pytest.mark.parametrize("character", ["\n", "\r", "\u2028", "\u2029"])
def test_schema_member_path_pattern_matches_runtime_for_all_characters(
    character: str,
) -> None:
    path = f"data/{character}member.json"
    manifest = _valid_manifest()
    manifest["members"][0]["path"] = path
    manifest["members"][1]["path"] = f"metadata/{character}universe.json"
    schema = _load_schema()
    pattern = schema["$defs"]["member"]["properties"]["path"]["pattern"]

    assert re.fullmatch(pattern, path)
    assert _module().validate_research_input_manifest(manifest)["members"][0]["path"] == path


def test_rejects_non_ascii_rfc3339_fraction_digits() -> None:
    manifest = _valid_manifest()
    manifest["observed_at"] = "2026-07-30T08:00:00.١Z"

    _assert_invalid(manifest)


def test_schema_member_path_rejects_whitespace_only_like_runtime() -> None:
    manifest = _valid_manifest()
    manifest["members"][0]["path"] = " \t"
    schema = _load_schema()
    pattern = schema["$defs"]["member"]["properties"]["path"]["pattern"]

    assert re.fullmatch(pattern, " \t") is None
    _assert_invalid(manifest)
