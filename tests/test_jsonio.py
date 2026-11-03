from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from quant_platform_kit.common.jsonio import (
    atomic_write_json,
    canonical_json_bytes,
    load_strict_json,
    sha256_hex,
    strict_json_loads,
    utc_now_iso,
)


def test_canonical_json_bytes_orders_keys_and_uses_compact_separators() -> None:
    payload = {"b": [1, 2], "a": {"c": True}}

    assert canonical_json_bytes(payload) == b'{"a":{"c":true},"b":[1,2]}'


def test_canonical_json_bytes_keeps_unicode_and_rejects_non_finite() -> None:
    assert canonical_json_bytes({"label": "策略"}) == '{"label":"策略"}'.encode("utf-8")

    with pytest.raises(ValueError):
        canonical_json_bytes({"value": float("nan")})


@pytest.mark.parametrize(
    "text",
    [
        '{"a": 1, "a": 2}',
        '{"nested": {"k": 1, "k": 2}}',
    ],
)
def test_strict_json_loads_rejects_duplicate_keys(text: str) -> None:
    with pytest.raises(ValueError, match="duplicate"):
        strict_json_loads(text)


@pytest.mark.parametrize("constant", ["NaN", "Infinity", "-Infinity"])
def test_strict_json_loads_rejects_non_finite_constants(constant: str) -> None:
    with pytest.raises(ValueError, match="non-finite"):
        strict_json_loads(f'{{"value": {constant}}}')


def test_strict_json_loads_accepts_valid_json() -> None:
    assert strict_json_loads('{"b": 2, "a": [1, null]}') == {"b": 2, "a": [1, None]}


def test_load_strict_json_reads_utf8(tmp_path: Path) -> None:
    path = tmp_path / "payload.json"
    path.write_text('{"label": "策略"}', encoding="utf-8")

    assert load_strict_json(path) == {"label": "策略"}


def test_atomic_write_json_matches_json_dumps_indentation(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "payload.json"
    payload = {"z": 1, "a": {"b": [1, 2]}}

    result = atomic_write_json(path, payload, indent=2)

    assert result == path
    assert path.read_text(encoding="utf-8") == json.dumps(
        payload, ensure_ascii=False, sort_keys=True, indent=2
    )
    assert [entry.name for entry in path.parent.iterdir()] == ["payload.json"]


def test_atomic_write_json_replaces_existing_file(tmp_path: Path) -> None:
    path = tmp_path / "payload.json"
    path.write_text('{"old": true}', encoding="utf-8")

    atomic_write_json(path, {"new": True})

    assert json.loads(path.read_text(encoding="utf-8")) == {"new": True}
    assert [entry.name for entry in tmp_path.iterdir()] == ["payload.json"]


def test_atomic_write_json_leaves_no_temp_file_on_failure(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        atomic_write_json(tmp_path / "payload.json", {"value": float("nan")})

    assert list(tmp_path.iterdir()) == []


def test_utc_now_iso_returns_aware_utc_timestamp() -> None:
    parsed = datetime.fromisoformat(utc_now_iso())

    assert parsed.utcoffset() == timedelta(0)


def test_sha256_hex_matches_hashlib() -> None:
    assert sha256_hex(b"abc") == (
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    )
