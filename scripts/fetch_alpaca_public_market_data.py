"""Fetch public Alpaca market data with read-only GET requests.

The query list lives in a checked-in JSON config. Credentials come only from
the environment (``ALPACA_API_KEY_ID`` and ``ALPACA_API_SECRET_KEY``) and are
never written to disk or printed. Every response page is stored byte for byte,
``next_page_token`` is followed until it is empty, and a ``SHA256SUMS`` file
covers every written file.

Exit codes: 0 all queries complete, 1 at least one query failed, 2 usage or
configuration error.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

ALLOWED_HOST = "data.alpaca.markets"
KEY_ENV = "ALPACA_API_KEY_ID"
SECRET_ENV = "ALPACA_API_SECRET_KEY"
DEFAULT_CONFIG = Path(__file__).with_name("alpaca_public_market_data_queries.json")
MAX_PAGES = 1000
MAX_ATTEMPTS = 3
RETRY_STATUS = frozenset({429, 500, 502, 503, 504})
TIMEOUT_SECONDS = 40

Fetcher = Callable[[str, Mapping[str, str]], "tuple[int, bytes]"]


class ConfigError(ValueError):
    """The query config or the environment is unusable."""


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D401
        raise urllib.error.HTTPError(req.full_url, code, "redirect refused", headers, fp)


def http_get(url: str, headers: Mapping[str, str]) -> "tuple[int, bytes]":
    """Perform one GET without following redirects; return (status, body)."""
    request = urllib.request.Request(url, headers=dict(headers), method="GET")
    opener = urllib.request.build_opener(_NoRedirect())
    try:
        with opener.open(request, timeout=TIMEOUT_SECONDS) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.read()


def load_config(path: Path) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    base = urllib.parse.urlparse(str(config.get("base_url", "")))
    if base.scheme != "https" or base.hostname != ALLOWED_HOST or base.path not in ("", "/"):
        raise ConfigError(f"base_url must be https://{ALLOWED_HOST}")
    queries = config.get("queries")
    if not isinstance(queries, list) or not queries:
        raise ConfigError("queries must be a non-empty list")
    seen: set[str] = set()
    for query in queries:
        qid = query.get("id")
        if not isinstance(qid, str) or not qid or "/" in qid or qid.startswith("."):
            raise ConfigError(f"invalid query id: {qid!r}")
        if qid in seen:
            raise ConfigError(f"duplicate query id: {qid}")
        seen.add(qid)
        if not str(query.get("path", "")).startswith("/v"):
            raise ConfigError(f"query {qid}: path must start with /v")
        params = query.get("params", {})
        if not isinstance(params, dict) or "page_token" in params:
            raise ConfigError(f"query {qid}: params must be an object without page_token")
    return config


def build_url(base_url: str, path: str, params: Mapping[str, str]) -> str:
    return base_url.rstrip("/") + path + ("?" + urllib.parse.urlencode(params) if params else "")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _redact(data: bytes, secrets: Sequence[str]) -> bytes:
    for secret in secrets:
        if secret:
            data = data.replace(secret.encode(), b"[REDACTED]")
    return data


def _get_with_retry(
    fetch: Fetcher, url: str, headers: Mapping[str, str], sleep: Callable[[float], None]
) -> "tuple[int, bytes]":
    status, body = 0, b""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            status, body = fetch(url, headers)
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            status, body = 0, type(error).__name__.encode()
        if status not in RETRY_STATUS and status != 0:
            break
        if attempt < MAX_ATTEMPTS:
            sleep(2.0 * attempt)
    return status, body


def fetch_query(
    query: Mapping[str, Any],
    base_url: str,
    out_dir: Path,
    headers: Mapping[str, str],
    fetch: Fetcher,
    secrets: Sequence[str],
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    qid = query["id"]
    query_dir = out_dir / qid
    query_dir.mkdir(parents=True, exist_ok=False)
    params = {str(k): str(v) for k, v in query.get("params", {}).items()}
    pages: list[dict[str, Any]] = []
    receipt: dict[str, Any] = {
        "id": qid,
        "method": "GET",
        "path": query["path"],
        "params": params,
        "pages": pages,
        "complete": False,
    }
    token = ""
    seen_tokens: set[str] = set()
    for number in range(1, MAX_PAGES + 1):
        page_params = dict(params)
        if token:
            page_params["page_token"] = token
        url = build_url(base_url, query["path"], page_params)
        retrieved = datetime.now(timezone.utc).isoformat()
        status, body = _get_with_retry(fetch, url, headers, sleep)
        ok = status == 200
        body = body if ok else _redact(body, secrets)
        name = f"page-{number:03d}.json" if ok else f"page-{number:03d}.http-{status}.txt"
        (query_dir / name).write_bytes(body)
        pages.append(
            {
                "file": f"{qid}/{name}",
                "http_status": status,
                "page_token_sent": bool(token),
                "retrieved_at_utc": retrieved,
                "bytes": len(body),
                "sha256": _sha256(body),
            }
        )
        if not ok:
            receipt["error"] = f"HTTP status {status}"
            return receipt
        try:
            payload = json.loads(body)
        except ValueError:
            receipt["error"] = "response is not valid JSON"
            return receipt
        token = payload.get("next_page_token") if isinstance(payload, dict) else None
        if not token:
            receipt["complete"] = True
            return receipt
        if token in seen_tokens:
            receipt["error"] = "repeated next_page_token"
            return receipt
        seen_tokens.add(token)
    receipt["error"] = f"more than {MAX_PAGES} pages"
    return receipt


def write_checksums(out_dir: Path) -> None:
    lines = []
    for path in sorted(p for p in out_dir.rglob("*") if p.is_file() and p.name != "SHA256SUMS"):
        lines.append(f"{_sha256(path.read_bytes())}  {path.relative_to(out_dir).as_posix()}")
    (out_dir / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(
    config_path: Path,
    out_dir: Path,
    env: Mapping[str, str],
    fetch: Fetcher = http_get,
    sleep: Callable[[float], None] = time.sleep,
) -> int:
    config = load_config(config_path)
    key, secret = env.get(KEY_ENV, ""), env.get(SECRET_ENV, "")
    if not key or not secret:
        raise ConfigError(f"{KEY_ENV} and {SECRET_ENV} must be set")
    if out_dir.exists() and any(out_dir.iterdir()):
        raise ConfigError("output directory must be empty or absent")
    out_dir.mkdir(parents=True, exist_ok=True)
    headers = {
        "APCA-API-KEY-ID": key,
        "APCA-API-SECRET-KEY": secret,
        "Accept": "application/json",
    }
    receipts = []
    for query in config["queries"]:
        receipt = fetch_query(query, config["base_url"], out_dir, headers, fetch, (key, secret), sleep)
        receipts.append(receipt)
        status = "ok" if receipt["complete"] else f"FAILED ({receipt['error']})"
        print(f"{query['id']}: {len(receipt['pages'])} page(s), {status}", flush=True)
    manifest = {
        "schema": "alpaca-public-market-data-run/1",
        "config_sha256": _sha256(config_path.read_bytes()),
        "all_complete": all(r["complete"] for r in receipts),
        "queries": receipts,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    write_checksums(out_dir)
    return 0 if manifest["all_complete"] else 1


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        return run(args.config, args.out_dir, os.environ)
    except (ConfigError, OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
