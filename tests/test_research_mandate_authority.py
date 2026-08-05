from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import stat
import threading

import pytest

from quant_platform_kit.data.research_mandate import (
    ResearchMandate,
    ResearchMandateAuthorityError,
    ResearchMandateAuthorityGuard,
)


UTC = timezone.utc
ISSUED_AT = datetime(2026, 8, 6, 1, 2, 3, 456789, tzinfo=UTC)


class MutableClock:
    def __init__(self, value: datetime = ISSUED_AT):
        self.value = value

    def __call__(self) -> datetime:
        return self.value


def identities(*, mandate_id: str = "soxl-stage-a-001") -> dict[str, str]:
    return {
        "candidate_id": "soxl-stage-a",
        "mandate_id": mandate_id,
        "config_digest": "a" * 64,
        "input_digest": "b" * 64,
        "authority_id": "qsl-p3-stage-a-static-acceptance",
    }


def issue(
    database: Path,
    *,
    clock: MutableClock | None = None,
    mandate_id: str = "soxl-stage-a-001",
) -> tuple[ResearchMandateAuthorityGuard, ResearchMandate, MutableClock]:
    clock = clock or MutableClock()
    guard = ResearchMandateAuthorityGuard(database, clock=clock)
    return guard, guard.issue(**identities(mandate_id=mandate_id)), clock


def consume(
    guard: ResearchMandateAuthorityGuard,
    mandate: ResearchMandate,
    **overrides: str,
):
    expected = identities(mandate_id=mandate.mandate_id)
    expected.update(overrides)
    return guard.consume(mandate, **expected)


def test_issue_freezes_fresh_nonce_exact_two_hour_lifetime_and_private_store(
    tmp_path: Path,
) -> None:
    database = tmp_path / "authority.sqlite3"
    guard, first, _ = issue(database)
    second = guard.issue(**identities(mandate_id="soxl-stage-a-002"))

    assert first.schema_version == "research_mandate.v1"
    assert first.issued_at == "2026-08-06T01:02:03.456789Z"
    assert first.expires_at == "2026-08-06T03:02:03.456789Z"
    assert first.nonce != second.nonce
    assert len(first.nonce) == 64
    assert set(first.nonce) <= set("0123456789abcdef")
    assert len(first.mandate_digest) == 64
    assert stat.S_IMODE(database.stat().st_mode) == 0o600
    assert first == ResearchMandate.from_dict(first.to_dict())
    with pytest.raises(FrozenInstanceError):
        first.nonce = "0" * 64  # type: ignore[misc]

    assert first.nonce.encode() not in database.read_bytes()


def test_consume_returns_deterministic_sanitized_receipt_and_terminally_invalidates(
    tmp_path: Path,
) -> None:
    database = tmp_path / "authority.sqlite3"
    guard, mandate, clock = issue(database)
    clock.value += timedelta(minutes=5)

    receipt = consume(guard, mandate)
    payload = receipt.to_dict()
    digest_payload = dict(payload)
    receipt_digest = digest_payload.pop("receipt_digest")

    assert payload["schema_version"] == "research_mandate_consumption_receipt.v1"
    assert payload["terminal_state"] == "CONSUMED"
    assert payload["consumed_at"] == "2026-08-06T01:07:03.456789Z"
    assert receipt_digest == hashlib.sha256(
        json.dumps(
            digest_payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode()
    ).hexdigest()

    serialized = json.dumps(payload, sort_keys=True)
    for forbidden in (
        mandate.nonce,
        mandate.candidate_id,
        mandate.mandate_id,
        mandate.authority_id,
        "credential",
        "provider_response",
        "market_data",
    ):
        assert forbidden not in serialized

    for restarted_guard in (
        guard,
        ResearchMandateAuthorityGuard(database, clock=clock),
    ):
        with pytest.raises(ResearchMandateAuthorityError, match="authority denied"):
            consume(restarted_guard, ResearchMandate.from_dict(mandate.to_dict()))


@pytest.mark.parametrize(
    "field,value",
    (
        ("candidate_id", "tqqq-stage-a"),
        ("mandate_id", "different-mandate"),
        ("config_digest", "c" * 64),
        ("input_digest", "d" * 64),
        ("authority_id", "different-authority"),
    ),
)
def test_consume_rejects_every_frozen_identity_mismatch(
    tmp_path: Path,
    field: str,
    value: str,
) -> None:
    guard, mandate, _ = issue(tmp_path / "authority.sqlite3")

    with pytest.raises(ResearchMandateAuthorityError, match="authority denied"):
        consume(guard, mandate, **{field: value})


def test_expired_or_clock_inconsistent_mandate_fails_closed(tmp_path: Path) -> None:
    database = tmp_path / "authority.sqlite3"
    guard, mandate, clock = issue(database)

    clock.value = ISSUED_AT + timedelta(hours=2)
    with pytest.raises(ResearchMandateAuthorityError, match="authority denied"):
        consume(guard, mandate)

    other_database = tmp_path / "future.sqlite3"
    guard, mandate, clock = issue(other_database)
    clock.value = ISSUED_AT - timedelta(microseconds=1)
    with pytest.raises(ResearchMandateAuthorityError, match="authority denied"):
        consume(guard, mandate)


@pytest.mark.parametrize("mutation", ("missing", "damaged_digest", "damaged_status"))
def test_missing_or_damaged_state_fails_closed(
    tmp_path: Path,
    mutation: str,
) -> None:
    database = tmp_path / "authority.sqlite3"
    guard, mandate, _ = issue(database)
    with sqlite3.connect(database) as connection:
        if mutation == "missing":
            connection.execute("DELETE FROM mandates")
        elif mutation == "damaged_digest":
            connection.execute(
                "UPDATE mandates SET state_digest = ?",
                ("0" * 64,),
            )
        else:
            connection.execute("PRAGMA ignore_check_constraints = ON")
            connection.execute("UPDATE mandates SET status = 'DAMAGED'")

    with pytest.raises(ResearchMandateAuthorityError, match="authority denied"):
        consume(guard, mandate)


@pytest.mark.parametrize(
    "mutation",
    (
        lambda payload: payload.pop("nonce"),
        lambda payload: payload.update(candidate_id=""),
        lambda payload: payload.update(config_digest="A" * 64),
        lambda payload: payload.update(issued_at=float("nan")),
        lambda payload: payload.update(expires_at="2026-08-06T03:02:04.456789Z"),
        lambda payload: payload.update(nonce="0" * 63),
        lambda payload: payload.update(mandate_digest="0" * 64),
    ),
)
def test_malformed_missing_nonfinite_or_inconsistent_mandate_is_rejected(
    tmp_path: Path,
    mutation,
) -> None:
    _, mandate, _ = issue(tmp_path / "authority.sqlite3")
    payload = mandate.to_dict()
    mutation(payload)

    with pytest.raises(ResearchMandateAuthorityError, match="authority denied"):
        ResearchMandate.from_dict(payload)


def test_duplicate_mandate_identity_and_unsafe_existing_state_fail_closed(
    tmp_path: Path,
) -> None:
    database = tmp_path / "authority.sqlite3"
    guard, _, _ = issue(database)
    with pytest.raises(ResearchMandateAuthorityError, match="authority denied"):
        guard.issue(**identities())

    unsafe_database = tmp_path / "unsafe.sqlite3"
    unsafe_database.write_bytes(b"")
    os.chmod(unsafe_database, 0o644)
    with pytest.raises(ResearchMandateAuthorityError, match="authority denied"):
        ResearchMandateAuthorityGuard(unsafe_database).issue(**identities())


def test_concurrent_consumers_have_exactly_one_atomic_winner(tmp_path: Path) -> None:
    database = tmp_path / "authority.sqlite3"
    _, mandate, clock = issue(database)
    clock.value += timedelta(minutes=1)
    barrier = threading.Barrier(2)

    def attempt() -> str:
        guard = ResearchMandateAuthorityGuard(database, clock=clock)
        barrier.wait()
        try:
            return consume(guard, ResearchMandate.from_dict(mandate.to_dict())).terminal_state
        except ResearchMandateAuthorityError:
            return "DENIED"

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(attempt) for _ in range(2)]
        outcomes = sorted(future.result() for future in futures)

    assert outcomes == ["CONSUMED", "DENIED"]

    with pytest.raises(ResearchMandateAuthorityError, match="authority denied"):
        consume(ResearchMandateAuthorityGuard(database, clock=clock), mandate)
