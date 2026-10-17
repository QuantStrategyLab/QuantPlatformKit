"""Safe review disposition. Only issue records and an injected cycle pause may change."""
from __future__ import annotations

import hashlib
import json

SEVERE = frozenset({"data_integrity", "risk_limit", "missing_stale_inputs"})


def strict_json(text):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate field")
            result[key] = value
        return result
    return json.loads(text, object_pairs_hook=pairs)


def opinion(value):
    if isinstance(value, str):
        value = strict_json(value)
    if (not isinstance(value, dict) or set(value) != {"verdict", "severity", "summary"}
            or value["verdict"] not in {"approve", "flag"}
            or value["severity"] not in SEVERE | {"none"}
            or not isinstance(value["summary"], str) or not value["summary"].strip()
            or len(value["summary"]) > 6000
            or (value["verdict"] == "approve" and value["severity"] != "none")):
        raise ValueError("invalid review opinion")
    return value


def confirmation(value):
    if (not isinstance(value, dict) or set(value) != {"confirmed", "severity", "summary"}
            or type(value["confirmed"]) is not bool
            or value["severity"] not in SEVERE | {"none"}
            or not isinstance(value["summary"], str) or not value["summary"].strip()
            or len(value["summary"]) > 6000
            or (not value["confirmed"] and value["severity"] != "none")):
        raise ValueError("invalid deeper review")
    return value


def finish_review(reviews, *, identity, store, dot=None, pause_cycle=None):
    """Persist before submitting once; unknown submissions are never replaced.

    store is the caller's durable issue record, with load/save/post/close/notify.
    A pause callback must already bind the current cycle and existing actuator.
    No callback for code, configuration, orders, reruns or adoption exists.
    """
    parsed = {role: opinion(value) for role, value in reviews.items()}
    if not parsed or not identity:
        raise ValueError("complete reviews and cycle identity required")
    digest = hashlib.sha256(json.dumps(parsed, sort_keys=True).encode()).hexdigest()
    state = store.load(identity) or {"identity": identity, "reviews_sha256": digest}
    if state.get("identity") != identity or state.get("reviews_sha256") != digest:
        raise ValueError("review material changed under an existing cycle")
    if state.get("finished"):
        return state
    state["reviews"] = parsed
    if all(value["verdict"] == "approve" for value in parsed.values()):
        state.update(disposition="auto_verified")
        store.save(state)
        store.close(state)  # archives JSON and applies auto-verified before closing
        state["finished"] = True
        store.save(state)
        return state

    severities = {value["severity"] for value in parsed.values()}
    severe = (len(parsed) >= 2 and all(value["verdict"] == "flag" for value in parsed.values())
              and len(severities) == 1 and severities <= SEVERE)
    if severe and not state.get("severe_notice_started"):
        # The marker also prevents repeating an actuator with an unknown outcome.
        state["severe_notice_started"] = True
        state["pause"] = "not_available" if pause_cycle is None else "outcome_unknown"
        store.save(state)
        if pause_cycle is not None:
            try:
                state["pause"] = "paused" if pause_cycle(identity) is True else "not_confirmed"
            except Exception:
                state["pause"] = "outcome_unknown"
        store.save(state)
    if severe and not state.get("severe_notified"):
        store.notify("Severe review consensus; hold positions and submit no new orders. "
                     + ("Existing cycle pause confirmed." if state["pause"] == "paused"
                        else "Pause not confirmed: no bound existing cycle-pause mechanism; owner action required."))
        state["severe_notified"] = True
        store.save(state)

    if dot is None:
        state.update(disposition="escalation_unavailable", gap="approved_dot_route_unavailable")
        store.save(state)
        return state
    request = dot.request(parsed, identity)
    request_digest = hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest()
    if state.get("request_sha256", request_digest) != request_digest:
        raise ValueError("deeper review request changed")
    if not state.get("submission_started"):
        state.update(submission_started=True, request_sha256=request_digest,
                     disposition="outcome_unknown")
        store.save(state)
        try:
            receipt = dot.submit(request, "review-loop:" + identity)
            task_id = receipt["id"]
            if not isinstance(task_id, str) or not task_id:
                raise ValueError("missing task id")
            state["task_id"] = task_id
            store.save(state)
        except Exception:
            # Includes ambiguous submission and state-write failures. Never resubmit.
            return state
    if not state.get("task_id"):
        return state
    try:
        value = confirmation(dot.result(state["task_id"], request))
    except Exception:
        state["disposition"] = "review_unavailable"
        store.save(state)
        return state
    state["dot_review"] = value
    state.update(disposition="confirmed" if value["confirmed"] else "dismissed")
    # Persist the final receipt before posting it. No model output can grant actions.
    store.save(state)
    store.post("Deeper Dot review (advisory only):\n```json\n"
               + json.dumps(value, sort_keys=True) + "\n```")
    if value["confirmed"]:
        if not state.get("severe_notice_started"):
            store.notify("Dot confirmed a real review finding. See the archived verdict; no live changes made.")
    else:
        store.close(state)
    state["finished"] = True
    store.save(state)
    return state


def deadman(outcomes, threshold=3):
    """Newest cycle first; failures, skips and unavailable results break liveness."""
    if type(threshold) is not int or not 1 <= threshold <= 24:
        raise ValueError("invalid dead-man threshold")
    failed = 0
    for outcome in outcomes:
        if outcome == "success":
            break
        if outcome not in {"failure", "skipped", "cancelled", "timed_out", "missing", "unavailable"}:
            raise ValueError("invalid review outcome")
        failed += 1
    return failed >= threshold
