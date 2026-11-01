import hashlib
import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

from scripts import fetch_alpaca_public_market_data as fetcher

KEY = "synthetic-key-id"
SECRET = "synthetic-secret-value"
ENV = {fetcher.KEY_ENV: KEY, fetcher.SECRET_ENV: SECRET}


def _config(tmp_path: Path, queries=None, base_url="https://data.alpaca.markets") -> Path:
    queries = queries or [
        {"id": "bars-xyz", "path": "/v2/stocks/XYZ/bars", "params": {"timeframe": "1Day", "feed": "sip"}},
        {"id": "actions-xyz", "path": "/v1/corporate-actions", "params": {"symbols": "XYZ"}},
    ]
    path = tmp_path / "queries.json"
    path.write_text(json.dumps({"base_url": base_url, "queries": queries}), encoding="utf-8")
    return path


class FakeHttp:
    """Serves canned (status, body) responses per URL path and records every call."""

    def __init__(self, responses):
        self.responses = {key: list(value) for key, value in responses.items()}
        self.calls = []

    def __call__(self, url, headers):
        self.calls.append((url, dict(headers)))
        return self.responses[urlparse(url).path].pop(0)


def _page(token=None, **extra):
    return 200, json.dumps({"next_page_token": token, **extra}, separators=(",", ":")).encode()


def test_follows_pagination_and_writes_raw_pages_with_checksums(tmp_path):
    http = FakeHttp(
        {
            "/v2/stocks/XYZ/bars": [_page("t1", bars=[1]), _page("t2", bars=[2]), _page(None, bars=[3])],
            "/v1/corporate-actions": [_page(None, corporate_actions={})],
        }
    )
    out = tmp_path / "out"

    assert fetcher.run(_config(tmp_path), out, ENV, fetch=http, sleep=lambda _s: None) == 0

    tokens = [parse_qs(urlparse(url).query).get("page_token") for url, _ in http.calls]
    assert tokens == [None, ["t1"], ["t2"], None]
    assert all(call[1]["APCA-API-KEY-ID"] == KEY for call in http.calls)
    assert all(urlparse(url).hostname == "data.alpaca.markets" for url, _ in http.calls)
    first = (out / "bars-xyz" / "page-001.json").read_bytes()
    assert json.loads(first)["bars"] == [1]
    assert first == json.dumps({"next_page_token": "t1", "bars": [1]}, separators=(",", ":")).encode()
    assert (out / "bars-xyz" / "page-003.json").exists()
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["all_complete"] is True
    assert [len(q["pages"]) for q in manifest["queries"]] == [3, 1]
    sums = dict(
        line.split("  ", 1)[::-1] for line in (out / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
    )
    assert "SHA256SUMS" not in sums
    assert sums["bars-xyz/page-002.json"] == hashlib.sha256(
        (out / "bars-xyz" / "page-002.json").read_bytes()
    ).hexdigest()
    assert "manifest.json" in sums


def test_credentials_are_never_written_to_disk(tmp_path):
    leak = (400, f"bad key {KEY} secret {SECRET}".encode())
    http = FakeHttp({"/v2/stocks/XYZ/bars": [leak], "/v1/corporate-actions": [_page(None)]})
    out = tmp_path / "out"

    assert fetcher.run(_config(tmp_path), out, ENV, fetch=http, sleep=lambda _s: None) == 1

    for path in out.rglob("*"):
        if path.is_file():
            text = path.read_text(encoding="utf-8")
            assert KEY not in text and SECRET not in text


def test_http_error_marks_query_failed_but_other_queries_still_run(tmp_path):
    http = FakeHttp({"/v2/stocks/XYZ/bars": [(403, b"forbidden")], "/v1/corporate-actions": [_page(None)]})
    out = tmp_path / "out"

    assert fetcher.run(_config(tmp_path), out, ENV, fetch=http, sleep=lambda _s: None) == 1

    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["all_complete"] is False
    assert [q["complete"] for q in manifest["queries"]] == [False, True]
    assert (out / "bars-xyz" / "page-001.http-403.txt").read_bytes() == b"forbidden"


def test_retries_transient_status_then_succeeds(tmp_path):
    http = FakeHttp(
        {
            "/v2/stocks/XYZ/bars": [(429, b"slow"), (503, b"later"), _page(None)],
            "/v1/corporate-actions": [_page(None)],
        }
    )
    sleeps = []

    assert fetcher.run(_config(tmp_path), tmp_path / "out", ENV, fetch=http, sleep=sleeps.append) == 0
    assert len(http.calls) == 4
    assert len(sleeps) == 2


def test_repeated_page_token_fails_closed(tmp_path):
    http = FakeHttp(
        {"/v2/stocks/XYZ/bars": [_page("same"), _page("same")], "/v1/corporate-actions": [_page(None)]}
    )
    out = tmp_path / "out"

    assert fetcher.run(_config(tmp_path), out, ENV, fetch=http, sleep=lambda _s: None) == 1
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["queries"][0]["error"] == "repeated next_page_token"


def test_missing_credentials_fail_before_any_request(tmp_path):
    http = FakeHttp({})
    with pytest.raises(fetcher.ConfigError):
        fetcher.run(_config(tmp_path), tmp_path / "out", {fetcher.KEY_ENV: KEY}, fetch=http)
    assert http.calls == []
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize("base_url", ["http://data.alpaca.markets", "https://example.com", "https://data.alpaca.markets.evil.test"])
def test_config_rejects_other_hosts_or_plain_http(tmp_path, base_url):
    with pytest.raises(fetcher.ConfigError):
        fetcher.load_config(_config(tmp_path, base_url=base_url))


def test_config_rejects_page_token_and_duplicate_ids(tmp_path):
    bad = [{"id": "a", "path": "/v1/x", "params": {"page_token": "t"}}]
    with pytest.raises(fetcher.ConfigError):
        fetcher.load_config(_config(tmp_path, queries=bad))
    dup = [{"id": "a", "path": "/v1/x"}, {"id": "a", "path": "/v1/y"}]
    with pytest.raises(fetcher.ConfigError):
        fetcher.load_config(_config(tmp_path, queries=dup))


def test_checked_in_config_has_the_expected_read_only_queries():
    config = fetcher.load_config(fetcher.DEFAULT_CONFIG)
    queries = {q["id"]: q for q in config["queries"]}

    assert len(queries) == 21
    for symbol in ("schd", "dgro", "sgov", "spyi", "qqqi", "boxx", "qqqm"):
        bars = queries[f"bars-{symbol}"]
        assert bars["path"] == f"/v2/stocks/{symbol.upper()}/bars"
        assert bars["params"]["feed"] == "sip" and bars["params"]["adjustment"] == "raw"
        assert bars["params"]["start"].startswith("2026-07-28")
        assert queries[f"actions-{symbol}"]["path"] == "/v1/corporate-actions"
        supplemental = queries[f"actions-all-{symbol}"]
        assert supplemental["path"] == "/v1/corporate-actions"
        assert supplemental["params"] == {
            "symbols": symbol.upper(),
            "start": "2026-07-28",
            "end": "2026-10-30",
            "data_quality": "all",
        }
    assert queries["actions-schd"]["params"]["start"] == "2016-01-04"
    assert queries["actions-boxx"]["params"]["start"] == "2022-12-28"
    assert all(q["params"].get("end", "").startswith("2026-10-3") for q in queries.values())


def test_main_returns_2_on_configuration_error(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv(fetcher.KEY_ENV, raising=False)
    monkeypatch.delenv(fetcher.SECRET_ENV, raising=False)
    assert fetcher.main(["--out-dir", str(tmp_path / "out")]) == 2
    assert "must be set" in capsys.readouterr().err
