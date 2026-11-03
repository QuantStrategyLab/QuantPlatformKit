"""QRT console synchronization, pull and decision reconciliation."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

from .models import (
    ResearchPromotionState,
    ResearchPromotionTicket,
    _TERMINAL,
    apply_human_promotion_decision,
)
from .store import _research_directory_lock, load_research_promotion_ticket


def _resolve_pull_factory() -> Callable[..., Any]:
    """Resolve the pull factory through the compatibility facade."""
    from quant_platform_kit.strategy_lifecycle import research_promotion_cycle as _compat

    return _compat.make_console_research_promotion_pull


def _save_ticket_via_facade(ticket: ResearchPromotionTicket, path: str | Path) -> Path:
    """Save through the compatibility facade so module-level patches still apply."""
    from quant_platform_kit.strategy_lifecycle import research_promotion_cycle as _compat

    return _compat.save_research_promotion_ticket(ticket, path)


def make_console_research_promotion_sync(
    *,
    endpoint_url: str | None = None,
    sync_token: str | None = None,
    timeout_seconds: float = 5.0,
    printer: Any = print,
    post_json: Callable[..., Any] | None = None,
    pull_console: Callable[[str], Mapping[str, Any] | None] | None = None,
) -> Callable[[ResearchPromotionTicket], bool]:
    """Confirm an awaiting ticket by reading it back from the QRT console.

    Env defaults:
    - RESEARCH_PROMOTION_SYNC_URL
    - RESEARCH_PROMOTION_SYNC_TOKEN (must match QRT RESEARCH_PROMOTION_SYNC_TOKEN)

    Read before writing; only a confirmed absence permits one POST. A POST with
    an unknown outcome is followed by GET, never another POST. An injected pull
    must return None only for a confirmed 404 and raise for unavailable reads.
    Failures return False; HTTP success alone is not delivery confirmation.
    """
    import os
    import urllib.request

    url = str(
        endpoint_url or os.environ.get("RESEARCH_PROMOTION_SYNC_URL") or ""
    ).strip()
    token = str(
        sync_token or os.environ.get("RESEARCH_PROMOTION_SYNC_TOKEN") or ""
    ).strip()

    def _default_post_json(
        *,
        endpoint: str,
        bearer_token: str,
        payload: Mapping[str, Any],
        timeout: float,
    ) -> int:
        body = json.dumps(payload, sort_keys=True).encode("utf-8")
        request = urllib.request.Request(
            endpoint,
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {bearer_token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return int(getattr(response, "status", 200) or 200)

    sender = post_json or _default_post_json
    reader = pull_console or _resolve_pull_factory()(
        endpoint_url=_default_research_promotion_pull_url(url),
        sync_token=token, timeout_seconds=timeout_seconds, printer=printer,
        raise_on_unavailable=True,
    )
    attempted_ticket_ids: set[str] = set()

    def confirmed(ticket: ResearchPromotionTicket, remote: Mapping[str, Any]) -> bool:
        _require_matching_console_promotion_candidate(ticket, remote)
        return all(
            key in remote and _canonical_ticket_value(remote[key]) == _canonical_ticket_value(value)
            for key, value in ticket.to_dict().items()
        )

    def sync_console(ticket: ResearchPromotionTicket) -> bool:
        if not url or not token:
            printer(
                "research promotion console sync skipped: url/token not configured",
                flush=True,
            )
            return False
        if ticket.state != ResearchPromotionState.AWAITING_HUMAN:
            printer(
                "research promotion console sync skipped: ticket is not awaiting_human",
                flush=True,
            )
            return False
        if ticket.live_authority_granted:
            printer(
                "research promotion console sync refused: live_authority_granted=true",
                flush=True,
            )
            return False
        try:
            existing = reader(ticket.ticket_id)
            if existing is not None:
                return confirmed(ticket, existing)
        except Exception:
            printer("research promotion console sync soft-failed: readback_unavailable", flush=True)
            return False
        if ticket.ticket_id in attempted_ticket_ids:
            printer("research promotion console sync soft-failed: readback_unconfirmed", flush=True)
            return False
        payload = ticket.to_dict()
        payload["live_authority_granted"] = False
        attempted_ticket_ids.add(ticket.ticket_id)
        try:
            sender(
                endpoint=url,
                bearer_token=token,
                payload=payload,
                timeout=float(timeout_seconds),
            )
        except Exception:
            # A transport failure can occur after the server persisted the ticket.
            # Reconcile by reading, without automatically repeating this write.
            pass
        try:
            remote = reader(ticket.ticket_id)
            if remote is not None and confirmed(ticket, remote):
                return True
        except Exception:
            pass
        printer("research promotion console sync soft-failed: readback_unconfirmed", flush=True)
        return False

    return sync_console


def _default_research_promotion_pull_url(sync_url: str) -> str:
    base = str(sync_url or "").strip().rstrip("/")
    suffix = "/api/internal/sync-research-promotion-ticket"
    if base.endswith(suffix):
        return base[: -len(suffix)] + "/api/internal/research-promotion-ticket"
    if base.endswith("/sync-research-promotion-ticket"):
        return base[: -len("/sync-research-promotion-ticket")] + "/research-promotion-ticket"
    return ""


def make_console_research_promotion_pull(
    *,
    endpoint_url: str | None = None,
    sync_token: str | None = None,
    timeout_seconds: float = 5.0,
    printer: Any = print,
    get_json: Callable[..., Any] | None = None,
    raise_on_unavailable: bool = False,
) -> Callable[[str], Mapping[str, Any] | None]:
    """GET a console ticket by id; soft-skip if unconfigured.

    Env defaults:
    - RESEARCH_PROMOTION_PULL_URL (or derived from RESEARCH_PROMOTION_SYNC_URL)
    - RESEARCH_PROMOTION_SYNC_TOKEN

    Returns the remote ticket mapping, or None on soft-skip/soft-fail. With
    raise_on_unavailable, None means a confirmed 404; all other failures raise
    a sanitized ValueError so callers cannot mistake uncertainty for absence.
    Never grants live authority.
    """
    import os
    import urllib.error
    import urllib.parse
    import urllib.request

    sync_url = str(os.environ.get("RESEARCH_PROMOTION_SYNC_URL") or "").strip()
    url = str(
        endpoint_url
        or os.environ.get("RESEARCH_PROMOTION_PULL_URL")
        or _default_research_promotion_pull_url(sync_url)
        or ""
    ).strip()
    token = str(
        sync_token or os.environ.get("RESEARCH_PROMOTION_SYNC_TOKEN") or ""
    ).strip()

    def _default_get_json(
        *,
        endpoint: str,
        bearer_token: str,
        ticket_id: str,
        timeout: float,
    ) -> Mapping[str, Any]:
        query = urllib.parse.urlencode({"ticket_id": ticket_id})
        request = urllib.request.Request(
            f"{endpoint}?{query}",
            method="GET",
            headers={
                "Authorization": f"Bearer {bearer_token}",
                "Accept": "application/json",
            },
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if not isinstance(payload, Mapping):
            raise ValueError("console pull response must be a JSON object")
        return payload

    fetcher = get_json or _default_get_json

    def unavailable(reason: str) -> None:
        if raise_on_unavailable:
            raise ValueError(reason) from None
        printer(f"research promotion console pull soft-failed: {reason}", flush=True)
        return None

    def pull_console(ticket_id: str) -> Mapping[str, Any] | None:
        tid = str(ticket_id or "").strip()
        if not tid:
            return unavailable("empty_ticket_id")
        if not url or not token:
            return unavailable("url/token not configured")
        try:
            payload = fetcher(
                endpoint=url,
                bearer_token=token,
                ticket_id=tid,
                timeout=float(timeout_seconds),
            )
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return None
            return unavailable("console_read_unavailable")
        except Exception:
            return unavailable("console_read_unavailable")
        if (not isinstance(payload, Mapping) or payload.get("ok") is not True
                or payload.get("live_authority_granted") is not False):
            return unavailable("console_response_invalid")
        ticket = payload.get("ticket")
        if (not isinstance(ticket, Mapping) or ticket.get("ticket_id") != tid
                or ticket.get("live_authority_granted") is not False):
            return unavailable("console_ticket_invalid")
        return dict(ticket)

    return pull_console


def _canonical_ticket_value(value: Any) -> str:
    """Compare JSON material across Python/JS, with booleans distinct from numbers."""
    def normalize(item: Any) -> Any:
        if isinstance(item, float) and item.is_integer():
            return int(item)
        if isinstance(item, Mapping):
            return {key: normalize(child) for key, child in item.items()}
        if isinstance(item, (list, tuple)):
            return [normalize(child) for child in item]
        return item

    return json.dumps(normalize(value), sort_keys=True, separators=(",", ":"), allow_nan=False)


def _require_matching_console_promotion_candidate(
    ticket: ResearchPromotionTicket,
    remote_ticket: Mapping[str, Any],
) -> None:
    """Match all fixed ticket material, including budget and shadow evidence."""
    if not isinstance(remote_ticket, Mapping) or remote_ticket.get("live_authority_granted") is not False:
        raise ValueError("console ticket must retain live_authority_granted=false")
    remote_id = str(remote_ticket.get("ticket_id") or "").strip()
    if not remote_id:
        raise ValueError("console ticket_id is required")
    if remote_id != ticket.ticket_id:
        raise ValueError(
            f"console ticket_id mismatch: local={ticket.ticket_id} remote={remote_id}"
        )
    remote_profile = str(remote_ticket.get("strategy_profile") or "").strip()
    if remote_profile != ticket.strategy_profile:
        raise ValueError(
            "console strategy_profile mismatch: "
            f"local={ticket.strategy_profile} remote={remote_profile}"
        )
    remote_domain = str(remote_ticket.get("domain") or "").strip()
    if remote_domain != ticket.domain:
        raise ValueError(
            f"console domain mismatch: local={ticket.domain} remote={remote_domain}"
        )
    remote_params = dict(remote_ticket.get("proposed_params") or {})
    local_params = dict(ticket.proposed_params)
    if _canonical_ticket_value(remote_params) != _canonical_ticket_value(local_params):
        raise ValueError(
            "console proposed_params mismatch with local ticket candidate"
        )
    decision_fields = {
        "state", "updated_at", "human_decision", "human_decided_at", "notes",
        "confirmation_target_platform", "confirmation_execution_mode", "confirmation_risk_profile",
    }
    for key, value in ticket.to_dict().items():
        if key not in decision_fields and (
            key not in remote_ticket
            or _canonical_ticket_value(remote_ticket[key]) != _canonical_ticket_value(value)
        ):
            raise ValueError(f"console candidate material mismatch: {key}")
    notes = remote_ticket.get("notes")
    if not isinstance(notes, (list, tuple)) or list(notes[:len(ticket.notes)]) != list(ticket.notes):
        raise ValueError("console candidate evidence notes mismatch")


def apply_console_research_promotion_decision(
    ticket: ResearchPromotionTicket,
    remote_ticket: Mapping[str, Any],
    *,
    decided_at: str | None = None,
) -> ResearchPromotionTicket:
    """Apply a console-stored decision onto a local awaiting ticket.

    Console is the intent ledger SoT for HITL accept/reject. Accept still never
    grants live authority. If the console already validated paper, trust that
    gate here (paper_supported follows remote execution_mode == paper).
    """
    if ticket.live_authority_granted or remote_ticket.get("live_authority_granted") is not False:
        raise ValueError("refusing to apply console decision with live_authority_granted=true")
    _require_matching_console_promotion_candidate(ticket, remote_ticket)
    state = str(remote_ticket.get("state") or "").strip()
    if state == ResearchPromotionState.AWAITING_HUMAN.value:
        raise ValueError("console ticket is still awaiting_human")
    if state == ResearchPromotionState.HUMAN_ACCEPTED.value:
        decision = "accept"
        confirmation = {
            "target_platform": str(remote_ticket.get("confirmation_target_platform") or ""),
            "execution_mode": str(remote_ticket.get("confirmation_execution_mode") or ""),
            "risk_profile": str(remote_ticket.get("confirmation_risk_profile") or ""),
        }
        paper_supported = confirmation["execution_mode"] == "paper"
    elif state == ResearchPromotionState.HUMAN_REJECTED.value:
        decision = "reject"
        confirmation = None
        paper_supported = False
    else:
        raise ValueError(f"unsupported console ticket state={state}")
    if remote_ticket.get("human_decision") != decision:
        raise ValueError("console decision/state mismatch")
    remote_decided_at = str(remote_ticket.get("human_decided_at") or "").strip()
    if not remote_decided_at:
        raise ValueError("console decision time unavailable")
    if datetime.fromisoformat(remote_decided_at.replace("Z", "+00:00")).tzinfo is None:
        raise ValueError("console decision time requires timezone")
    decided = apply_human_promotion_decision(
        ResearchPromotionTicket.from_dict(ticket.to_dict(include_progress=True)),
        decision=decision,
        confirmation=confirmation,
        paper_supported=paper_supported,
        decided_at=decided_at or remote_decided_at,
    )
    if list(remote_ticket["notes"]) != list(decided.notes):
        raise ValueError("console decision evidence notes mismatch")
    decided.notes = decided.notes + ("console_decision_applied",)
    decided.live_authority_granted = False
    return decided


def reconcile_saved_research_promotion_ticket(
    ticket_path: str | Path,
    *,
    pull_console: Callable[[str], Mapping[str, Any] | None] | None = None,
    output_path: str | Path | None = None,
    domain: str | None = None,
) -> dict[str, Any]:
    """Serialize decision recovery with research and manual decisions."""
    result = {"ticket_id": None, "strategy_profile": None, "state": None,
              "status": "unavailable", "reason": "local_ticket_unavailable",
              "live_authority_granted": False}
    try:
        with _research_directory_lock(Path(ticket_path).parent) as acquired:
            if not acquired:
                return {**result, "status": "deferred", "reason": "research_in_progress"}
            return _reconcile_saved_research_promotion_ticket(
                ticket_path, pull_console=pull_console, output_path=output_path, domain=domain,
            )
    except (OSError, TypeError, ValueError):
        return result


def _reconcile_saved_research_promotion_ticket(
    ticket_path: str | Path,
    *,
    pull_console: Callable[[str], Mapping[str, Any] | None] | None = None,
    output_path: str | Path | None = None,
    domain: str | None = None,
) -> dict[str, Any]:
    """Recover one saved human decision without starting research or applying it.

    Terminal local tickets are idempotent no-ops. Callers retain each returned
    status and serialize work for the same ticket. No POST, model or platform
    action is performed; failures leave the original ticket unchanged.
    """
    result: dict[str, Any] = {"ticket_id": None, "strategy_profile": None,
        "status": "rejected", "state": None, "reason": "local_ticket_invalid",
        "live_authority_granted": False}
    try:
        ticket = load_research_promotion_ticket(ticket_path)
    except (OSError, ValueError, TypeError, KeyError, OverflowError):
        return result
    result.update(ticket_id=ticket.ticket_id, strategy_profile=ticket.strategy_profile, state=ticket.state.value)
    if domain is not None and ticket.domain != domain:
        return {**result, "status": "skipped", "reason": "ticket_domain_mismatch"}
    if ticket.live_authority_granted:
        return {**result, "reason": "local_live_authority_rejected"}
    if ticket.state in _TERMINAL:
        return {**result, "status": "already_terminal", "reason": "local_ticket_terminal"}
    if ticket.state is not ResearchPromotionState.AWAITING_HUMAN:
        return {**result, "status": "skipped", "reason": "ticket_not_awaiting_human"}
    result["delivery_unstarted"] = (
        isinstance(ticket.research_progress.get("identity"), Mapping)
        and "console_delivery" not in ticket.research_progress
    )
    try:
        remote = (pull_console or _resolve_pull_factory()())(ticket.ticket_id)
    except Exception:
        return {**result, "status": "unavailable", "reason": "console_read_unavailable"}
    if remote is None:
        return {**result, "status": "unavailable", "reason": "console_ticket_unavailable"}
    try:
        _require_matching_console_promotion_candidate(ticket, remote)
        if remote.get("state") == ResearchPromotionState.AWAITING_HUMAN.value:
            if any(key not in remote or _canonical_ticket_value(remote[key]) != _canonical_ticket_value(value)
                   for key, value in ticket.to_dict().items()):
                raise ValueError("awaiting ticket mismatch")
            return {**result, "status": "awaiting_human", "reason": "human_decision_pending"}
        decided = apply_console_research_promotion_decision(ticket, remote)
    except (ValueError, TypeError, KeyError):
        return {**result, "reason": "console_candidate_or_decision_mismatch"}
    try:
        _save_ticket_via_facade(decided, output_path or ticket_path)
    except (OSError, ValueError, TypeError):
        return {**result, "status": "unavailable", "reason": "local_ticket_save_failed"}
    return {**result, "status": "updated", "state": decided.state.value, "reason": "human_intent_reconciled"}
