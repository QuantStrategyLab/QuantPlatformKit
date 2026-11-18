"""Shared constants, key builders, and report-matching helpers for execution state."""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from typing import Any

DEFAULT_EXECUTION_STATE_DIR = "/tmp/quant_execution_state"
DEFAULT_EXECUTION_STATE_NAMESPACE = "execution_markers"
DEFAULT_EXECUTION_OUTCOME_NAMESPACE = "execution_outcomes"
EXECUTION_LEDGER_DIGEST_SCHEMA_VERSION = "execution_ledger_digest.v1"
DEFAULT_EXECUTION_LEDGER_DIGEST_RECORD_LIMIT = 256


def _first_non_empty(*values: object) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _env_bool(value: object, *, default: bool) -> bool:
    text = str(value or "").strip().lower()
    if not text:
        return default
    if text in {"1", "true", "t", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "f", "no", "n", "off"}:
        return False
    return default


def _parse_cloud_uri(uri: str) -> tuple[str, str]:
    text = str(uri or "").strip()
    if not text.startswith("gs://") and not text.startswith("s3://"):
        raise ValueError(f"cloud uri must start with gs:// or s3://, got: {uri!r}")
    remainder = text[5:]
    bucket, _, prefix = remainder.partition("/")
    if not bucket:
        raise ValueError(f"cloud uri must include a bucket, got: {uri!r}")
    return bucket, prefix.strip("/")


# Backward-compatible alias
_parse_gcs_uri = _parse_cloud_uri


def _read_cloud_env(
    env_reader: Callable[[str, str | None], str | None],
    *,
    new_key: str,
    old_key: str,
) -> str | None:
    """Read new env var name first, fall back to old name with deprecation warning."""
    val = env_reader(new_key, None)
    if val is not None:
        return val
    val = env_reader(old_key, None)
    if val is not None:
        import warnings
        warnings.warn(
            f"Env var '{old_key}' is deprecated, use '{new_key}'",
            DeprecationWarning,
            stacklevel=3,
        )
    return val


def _clean_key_part(value: object, *, fallback: str) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[^a-z0-9._=-]+", "-", text)
    text = re.sub(r"-{2,}", "-", text).strip("-.")
    return text or fallback


def _clean_relative_key(key: str) -> str:
    parts = [
        _clean_key_part(part, fallback="unknown")
        for part in str(key or "").replace("\\", "/").split("/")
        if str(part or "").strip()
    ]
    return "/".join(parts) or "unknown"


def build_execution_marker_key(
    *,
    platform: str,
    strategy_profile: str,
    account_scope: str,
    execution_mode: str,
    signal_date: object,
    effective_date: object,
    execution_timing_contract: object = None,
) -> str:
    """Build a stable marker key for one strategy signal execution."""
    signal = _first_non_empty(signal_date)
    effective = _first_non_empty(effective_date)
    if not signal and not effective:
        return ""
    return "/".join(
        (
            "v1",
            _clean_key_part(platform, fallback="platform"),
            _clean_key_part(account_scope, fallback="account"),
            _clean_key_part(strategy_profile, fallback="strategy"),
            _clean_key_part(execution_mode, fallback="mode"),
            _clean_key_part(signal or "no-signal-date", fallback="signal"),
            _clean_key_part(effective or "no-effective-date", fallback="effective"),
            _clean_key_part(execution_timing_contract or "no-contract", fallback="contract"),
        )
    )


def build_account_owner_marker_key(*, broker: str, account_id: str) -> str:
    """Build a durable account-owner fence key (strategy profile intentionally omitted)."""
    broker_part = _first_non_empty(broker)
    account_part = _first_non_empty(account_id)
    if not broker_part or not account_part:
        raise ValueError("account owner marker requires broker and account_id")
    return "/".join(
        (
            "v1",
            "account-owner",
            _clean_key_part(broker_part, fallback="broker"),
            _clean_key_part(account_part, fallback="account"),
        )
    )



def _is_paper_account_scope(value: object) -> bool:
    return str(value or "").strip().upper() == "PAPER"


def _runtime_report_segment(value: object) -> str:
    text = str(value or "").strip()
    safe = "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "_" for ch in text)
    return safe or "unknown"


def _month_segment(*values: object) -> str:
    for value in values:
        text = _optional_str(value)
        if len(text) >= 7 and text[4] == "-" and text[:4].isdigit() and text[5:7].isdigit():
            return text[:7]
    return ""


def _optional_str(value: object) -> str:
    return str(value or "").strip()


def _report_matches_execution(
    payload: Mapping[str, Any],
    *,
    platform: str,
    strategy_profile: str,
    account_scope: str,
    signal_date: str,
    effective_date: str,
    dry_run_only: bool,
) -> bool:
    report = dict(payload or {})
    if _optional_str(report.get("platform")).lower() != _optional_str(platform).lower():
        return False
    if _optional_str(report.get("strategy_profile")).lower() != _optional_str(strategy_profile).lower():
        return False
    if _optional_str(report.get("account_scope")).lower() != _optional_str(account_scope).lower():
        return False
    if bool(report.get("dry_run")) != bool(dry_run_only):
        return False
    summary = dict(report.get("summary") or {})
    if signal_date and _date_key(signal_date) not in _report_signal_date_keys(report, summary):
        return False
    if effective_date and _date_key(effective_date) not in _report_effective_date_keys(report, summary):
        return False
    return (
        bool(summary.get("action_done"))
        or int(float(summary.get("orders_previewed_count") or 0)) > 0
        or int(float(summary.get("order_events_count") or 0)) > 0
        or _is_successful_no_action_report(report, summary)
    )


def _is_successful_no_action_report(report: Mapping[str, Any], summary: Mapping[str, Any]) -> bool:
    if _optional_str(report.get("status")).lower() != "ok":
        return False
    if int(float(summary.get("orders_skipped_count") or 0)) > 0:
        return False
    return bool("action_done" in summary and not summary.get("action_done"))


def _report_signal_date_keys(report: Mapping[str, Any], summary: Mapping[str, Any]) -> set[str]:
    signal_snapshot = _report_signal_snapshot(report)
    return _date_keys(
        summary.get("signal_date"),
        signal_snapshot.get("signal_as_of"),
        signal_snapshot.get("market_date"),
        signal_snapshot.get("price_as_of"),
        signal_snapshot.get("snapshot_as_of"),
    )


def _report_effective_date_keys(report: Mapping[str, Any], summary: Mapping[str, Any]) -> set[str]:
    signal_snapshot = _report_signal_snapshot(report)
    return _date_keys(
        summary.get("effective_date"),
        signal_snapshot.get("effective_date"),
    )


def _report_signal_snapshot(report: Mapping[str, Any]) -> dict[str, Any]:
    diagnostics = report.get("diagnostics")
    if not isinstance(diagnostics, Mapping):
        return {}
    signal_snapshot = diagnostics.get("signal_snapshot")
    return dict(signal_snapshot) if isinstance(signal_snapshot, Mapping) else {}


def _date_keys(*values: object) -> set[str]:
    return {key for value in values if (key := _date_key(value))}


def _date_key(value: object) -> str:
    text = _optional_str(value)
    if len(text) >= 10 and text[4] == "-" and text[7] == "-":
        return text[:10]
    return text


