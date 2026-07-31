from __future__ import annotations

import copy
import json
import subprocess
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from quant_platform_kit.data.research_input import (
    InvalidResearchInputEvidence,
    canonical_research_input_manifest_bytes,
    read_research_input_manifest_json,
    research_input_manifest_sha256,
    validate_research_input_manifest,
)


SCHEMA_PATH = (
    Path(__file__).parents[1]
    / "src/quant_platform_kit/schemas/research-input-manifest.v1.schema.json"
)


def valid_manifest(*, path: str = "data/file.json") -> dict[str, object]:
    return {
        "schema_version": "research_input_manifest.v1",
        "manifest_id": "manifest-001",
        "research_input_contract_id": "contract-001",
        "domain": "us_equity",
        "profile": "daily",
        "artifact_type": "research_input",
        "observed_at": "2026-07-30T09:00:00Z",
        "effective_at": "2026-07-30T09:30:00+00:00",
        "as_of": "2026-07-30T10:00:00+00:00",
        "producer": {
            "repository": "QuantStrategyLab/QuantPlatformKit",
            "commit_sha": "a" * 40,
            "tree_sha": "b" * 40,
            "tool": "pytest",
            "tool_version": "1.0",
        },
        "calendar": {
            "calendar_id": "XNYS",
            "timezone": "America/New_York",
            "session_date": "2026-07-30",
            "source": "NYSE",
            "source_revision": "2026-07-30",
        },
        "adjustment": {
            "policy": "split_adjusted",
            "source": "official",
            "source_revision": "2026-07-30",
        },
        "sources": [
            {
                "source_id": "source-a",
                "revision": "rev-1",
                "observed_at": "2026-07-30T09:00:00Z",
                "content_sha256": "c" * 64,
            }
        ],
        "members": [
            {
                "path": path,
                "media_type": "application/json",
                "size_bytes": 1,
                "sha256": "d" * 64,
            }
        ],
    }


ACCEPTED_MEMBER_PATHS = (
    "a",
    "file.json",
    ".hidden",
    "..hidden",
    "a...",
    "a/b",
    "data/file.json",
    "a/b/c",
    " a ",
    "\ufeffa\u0085",
    "a/ b ",
    "a/ ",
    "\n/a",
    "a/\ufeff/b",
    "\x01",
    "\x7f",
    "\u200b",
    "a\x01b",
    "a\nb",
    "a\rb",
    "a\u2028b",
    "a\u2029b",
    "a\nb\rc\u2028d\u2029e",
    "a/\n",
    "\r/a",
    "a\u2028/b\u2029",
    "é",
    "e\u0301",
    "a:b",
    "a-b_c",
    "~name",
)

REJECTED_MEMBER_PATHS = (
    "",
    " ",
    "\n",
    "\r",
    "\u2028",
    "\u2029",
    "\ufeff",
    " \u00a0\ufeff",
    "/a",
    "/",
    "//a",
    "a/",
    "a/b/",
    "a//b",
    "a///b",
    "//",
    ".",
    "a/.",
    "./a",
    "a/./b",
    "..",
    "a/..",
    "../a",
    "a/../b",
    "\\",
    "a\\b",
    "a/\\b",
    "\x00",
    "a\x00b",
    "a/\x00",
)


def schema_validator() -> Draft202012Validator:
    return Draft202012Validator(json.loads(SCHEMA_PATH.read_text(encoding="utf-8")))


def schema_accepts(path: str) -> bool:
    return not list(schema_validator().iter_errors(valid_manifest(path=path)))


def ecma_accepts(path: str) -> bool:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    script = """
const [definition, value] = JSON.parse(process.argv[1]);
const matches = (pattern) => new RegExp(pattern, "u").test(value);
let accepted = value.length >= definition.minLength;
for (const rule of definition.allOf) {
  if (rule.pattern && !matches(rule.pattern)) accepted = false;
  if (rule.not?.pattern && matches(rule.not.pattern)) accepted = false;
}
process.stdout.write(String(accepted));
"""
    completed = subprocess.run(
        ["node", "-e", script, json.dumps([schema["$defs"]["member_path"], path])],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout == "true"


@pytest.mark.parametrize("path", ACCEPTED_MEMBER_PATHS)
def test_member_path_v3_acceptance_and_preservation(path: str) -> None:
    validated = validate_research_input_manifest(valid_manifest(path=path))
    assert validated["members"][0]["path"] == path


@pytest.mark.parametrize("path", REJECTED_MEMBER_PATHS)
def test_member_path_v3_rejections(path: str) -> None:
    with pytest.raises(InvalidResearchInputEvidence):
        validate_research_input_manifest(valid_manifest(path=path))


@pytest.mark.parametrize("path, expected", [(path, True) for path in ACCEPTED_MEMBER_PATHS] + [(path, False) for path in REJECTED_MEMBER_PATHS])
def test_member_path_v3_python_schema_and_ecma_parity(path: str, expected: bool) -> None:
    try:
        validate_research_input_manifest(valid_manifest(path=path))
        python_accepts = True
    except InvalidResearchInputEvidence:
        python_accepts = False

    assert python_accepts is expected
    assert schema_accepts(path) is expected
    assert ecma_accepts(path) is expected


def test_member_path_wrong_type_and_missing_path_are_rejected() -> None:
    for path in (None, 1, [], {}):
        manifest = valid_manifest()
        manifest["members"][0]["path"] = path
        with pytest.raises(InvalidResearchInputEvidence):
            validate_research_input_manifest(manifest)

    manifest = valid_manifest()
    del manifest["members"][0]["path"]
    with pytest.raises(InvalidResearchInputEvidence):
        validate_research_input_manifest(manifest)


def test_manifest_contract_canonical_bytes_digest_and_copy_isolation() -> None:
    manifest = valid_manifest()
    validated = validate_research_input_manifest(manifest)
    assert validated is not manifest
    assert validated["members"] is not manifest["members"]
    assert canonical_research_input_manifest_bytes(manifest) == (
        b'{"adjustment":{"policy":"split_adjusted","source":"official","source_revision":"2026-07-30"},'
        b'"artifact_type":"research_input","as_of":"2026-07-30T10:00:00+00:00",'
        b'"calendar":{"calendar_id":"XNYS","session_date":"2026-07-30","source":"NYSE",'
        b'"source_revision":"2026-07-30","timezone":"America/New_York"},'
        b'"domain":"us_equity","effective_at":"2026-07-30T09:30:00+00:00",'
        b'"manifest_id":"manifest-001","members":[{"media_type":"application/json","path":"data/file.json",'
        b'"sha256":"dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd","size_bytes":1}],'
        b'"observed_at":"2026-07-30T09:00:00Z","producer":{"commit_sha":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",'
        b'"repository":"QuantStrategyLab/QuantPlatformKit","tool":"pytest","tool_version":"1.0",'
        b'"tree_sha":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"},"profile":"daily",'
        b'"research_input_contract_id":"contract-001","schema_version":"research_input_manifest.v1",'
        b'"sources":[{"content_sha256":"cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",'
        b'"observed_at":"2026-07-30T09:00:00Z","revision":"rev-1","source_id":"source-a"}]}'
    )
    assert research_input_manifest_sha256(manifest) == "39e5109a4089a94fac7c88584cf8581eb538ae18518a4d5da949e5e6474da1c1"


def test_manifest_rejects_unsorted_sources_and_members() -> None:
    manifest = valid_manifest()
    source_b = copy.deepcopy(manifest["sources"][0])
    source_b["source_id"] = "source-b"
    manifest["sources"] = [source_b, manifest["sources"][0]]
    with pytest.raises(InvalidResearchInputEvidence):
        validate_research_input_manifest(manifest)

    manifest = valid_manifest()
    member_b = copy.deepcopy(manifest["members"][0])
    member_b["path"] = "z"
    manifest["members"] = [member_b, manifest["members"][0]]
    with pytest.raises(InvalidResearchInputEvidence):
        validate_research_input_manifest(manifest)


@pytest.mark.parametrize("timestamp", ["2026-07-30T09:00:00", "2026-07-30T09:00:00-00:00", "2026-07-30T09:00:00+24:00", "2026-07-30T09:00:00+00:60"])
def test_manifest_rejects_invalid_timestamps(timestamp: str) -> None:
    manifest = valid_manifest()
    manifest["observed_at"] = timestamp
    with pytest.raises(InvalidResearchInputEvidence):
        validate_research_input_manifest(manifest)


@pytest.mark.parametrize("payload", [b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":1} trailing', b'\xff'])
def test_strict_json_readback_rejects_invalid_payloads(payload: bytes) -> None:
    with pytest.raises(InvalidResearchInputEvidence):
        read_research_input_manifest_json(payload)


def test_prepublication_regressions_fail_closed() -> None:
    for field in ("manifest_id", "members"):
        manifest = valid_manifest()
        if field == "members":
            manifest[field][0]["path"] = "\ud800"
        else:
            manifest[field] = "\ud800"
        with pytest.raises(InvalidResearchInputEvidence):
            validate_research_input_manifest(manifest)
        with pytest.raises(InvalidResearchInputEvidence):
            canonical_research_input_manifest_bytes(manifest)

    for timezone in ("Factory", "posixrules"):
        manifest = valid_manifest()
        manifest["calendar"]["timezone"] = timezone
        with pytest.raises(InvalidResearchInputEvidence):
            validate_research_input_manifest(manifest)

    manifest = valid_manifest()
    manifest["observed_at"] = "2026-07-30T10:00:00.0000001Z"
    with pytest.raises(InvalidResearchInputEvidence):
        validate_research_input_manifest(manifest)

    manifest = valid_manifest()
    manifest["sources"][0]["observed_at"] = "2026-07-30T10:00:00.0000001Z"
    with pytest.raises(InvalidResearchInputEvidence):
        validate_research_input_manifest(manifest)


def test_frozen_public_surface() -> None:
    import quant_platform_kit.data.research_input as research_input

    assert research_input.__all__ == [
        "InvalidResearchInputEvidence",
        "validate_research_input_manifest",
        "canonical_research_input_manifest_bytes",
        "research_input_manifest_sha256",
        "read_research_input_manifest_json",
    ]

@pytest.mark.parametrize(
    "timestamp",
    (
        "2026-07-30T24:00:00Z",
        "2026-07-30T99:00:00Z",
        "2026-07-30T23:60:00Z",
        "٢٠٢٦-٠٧-٣٠T٠٩:٠٠:٠٠Z",
        "2026-07-30T09:00:00.١Z",
    ),
)
def test_rfc3339_exception_rejects_invalid_fields_and_non_ascii_digits(timestamp: str) -> None:
    manifest = valid_manifest()
    manifest["observed_at"] = timestamp
    with pytest.raises(InvalidResearchInputEvidence):
        validate_research_input_manifest(manifest)

@pytest.mark.parametrize("suffix", ("\n", "\r", "\u2028", "\u2029"))
def test_timestamp_schema_python_trailing_terminator_parity(suffix: str) -> None:
    manifest = valid_manifest()
    manifest["observed_at"] += suffix
    assert list(schema_validator().iter_errors(manifest))
    with pytest.raises(InvalidResearchInputEvidence):
        validate_research_input_manifest(manifest)
