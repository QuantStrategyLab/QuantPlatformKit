from __future__ import annotations

from hashlib import sha256

import pytest

from quant_platform_kit.data import (
    DECISION_DATA_ASSURANCE_VERIFIED,
    DECISION_DATA_MODE_ARTIFACT_REQUIRED,
    DECISION_PRICE_SERIES_MEMBER_PATH,
    DecisionDataBinding,
    InvalidDecisionDataArtifact,
    canonical_decision_price_series_artifact_bytes,
    read_decision_price_series_artifact_json,
    verify_decision_price_series_artifact_members,
)
from quant_platform_kit.data.research_input import (
    canonical_research_input_manifest_bytes,
    read_research_input_manifest_json,
    research_input_manifest_sha256,
)


def _artifact() -> dict[str, object]:
    return {
        "schema_version": "qpk.decision_price_series_artifact.v1",
        "strategy_scope": "tqqq_growth_income",
        "as_of": "2026-08-28",
        "adjustment_basis": "split_adjusted",
        "source_ids": ["twelve_data_daily", "yahoo_finance_daily"],
        "series": {
            "QQQ": {
                "currency": "USD",
                "points": [
                    {"as_of": "2026-08-27", "close": 100.0, "volume": 123.0},
                    {"as_of": "2026-08-28", "close": 101.5, "volume": None},
                ],
            }
        },
    }


def _manifest(projection: bytes) -> bytes:
    return canonical_research_input_manifest_bytes(
        {
            "schema_version": "research_input_manifest.v1",
            "manifest_id": "decision-price-series-test",
            "research_input_contract_id": "tqqq_daily_decision_input.v1",
            "domain": "us_equity",
            "profile": "tqqq_growth_income",
            "artifact_type": "immutable_assured_daily_decision_price_series",
            "observed_at": "2026-08-28T20:00:00Z",
            "effective_at": "2026-08-28T20:00:00Z",
            "as_of": "2026-08-28T20:00:00Z",
            "producer": {
                "repository": "QuantStrategyLab/UsEquitySnapshotPipelines",
                "commit_sha": "a" * 40,
                "tree_sha": "b" * 40,
                "tool": "daily_decision_projection",
                "tool_version": "v1",
            },
            "calendar": {
                "calendar_id": "XNYS",
                "timezone": "America/New_York",
                "session_date": "2026-08-28",
                "source": "exchange_calendars",
                "source_revision": "v1",
            },
            "adjustment": {
                "policy": "split_adjusted",
                "source": "two_source_assurance",
                "source_revision": "v1",
            },
            "sources": [
                {
                    "source_id": "twelve_data_daily:QQQ",
                    "revision": "v1",
                    "observed_at": "2026-08-28T20:00:00Z",
                    "content_sha256": "c" * 64,
                },
                {
                    "source_id": "yahoo_finance_daily:QQQ",
                    "revision": "v1",
                    "observed_at": "2026-08-28T20:00:00Z",
                    "content_sha256": "d" * 64,
                },
            ],
            "members": [
                {
                    "path": DECISION_PRICE_SERIES_MEMBER_PATH,
                    "media_type": "application/json",
                    "size_bytes": len(projection),
                    "sha256": sha256(projection).hexdigest(),
                }
            ],
        }
    )


def _binding(manifest: bytes) -> DecisionDataBinding:
    return DecisionDataBinding(
        binding_id="tqqq-daily-decision-data-v1",
        strategy_scope="tqqq_growth_income",
        mode=DECISION_DATA_MODE_ARTIFACT_REQUIRED,
        source_ids=("twelve_data_daily", "yahoo_finance_daily"),
        as_of="2026-08-28",
        adjustment_basis="split_adjusted",
        artifact_sha256=research_input_manifest_sha256(read_research_input_manifest_json(manifest)),
        assurance_status=DECISION_DATA_ASSURANCE_VERIFIED,
    )


def test_verified_projection_requires_matching_canonical_manifest_and_member() -> None:
    projection = canonical_decision_price_series_artifact_bytes(_artifact())
    manifest = _manifest(projection)

    series = verify_decision_price_series_artifact_members(
        binding=_binding(manifest),
        manifest_bytes=manifest,
        decision_price_series_bytes=projection,
    )

    assert list(series) == ["QQQ"]
    assert series["QQQ"].currency == "USD"
    assert series["QQQ"].latest.close == 101.5
    assert series["QQQ"].latest.volume is None
    assert series["QQQ"].latest.as_of.isoformat() == "2026-08-28T00:00:00+00:00"


def test_projection_rejects_binding_identity_or_member_integrity_mismatch() -> None:
    projection = canonical_decision_price_series_artifact_bytes(_artifact())
    manifest = _manifest(projection)
    binding = _binding(manifest)

    with pytest.raises(InvalidDecisionDataArtifact):
        verify_decision_price_series_artifact_members(
            binding=binding,
            manifest_bytes=manifest,
            decision_price_series_bytes=projection + b" ",
        )

    with pytest.raises(InvalidDecisionDataArtifact):
        verify_decision_price_series_artifact_members(
            binding=binding,
            manifest_bytes=manifest + b"\n",
            decision_price_series_bytes=projection,
        )

    mismatched = _artifact()
    mismatched["source_ids"] = ["twelve_data_daily"]
    with pytest.raises(InvalidDecisionDataArtifact):
        verify_decision_price_series_artifact_members(
            binding=binding,
            manifest_bytes=manifest,
            decision_price_series_bytes=canonical_decision_price_series_artifact_bytes(mismatched),
        )


def test_projection_rejects_duplicate_json_keys_and_incomplete_daily_series() -> None:
    with pytest.raises(InvalidDecisionDataArtifact):
        read_decision_price_series_artifact_json(
            b'{"schema_version":"qpk.decision_price_series_artifact.v1","schema_version":"x"}'
        )

    incomplete = _artifact()
    incomplete["series"] = {
        "QQQ": {"currency": "USD", "points": [{"as_of": "2026-08-27", "close": 1.0, "volume": None}]}
    }
    with pytest.raises(InvalidDecisionDataArtifact):
        canonical_decision_price_series_artifact_bytes(incomplete)
