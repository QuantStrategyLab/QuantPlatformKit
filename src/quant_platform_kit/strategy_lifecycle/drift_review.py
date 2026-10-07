"""Advisory review of caller-owned critical drift observations."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from typing import Any
from .task_review import review_material

def _critical_drifts(domain: str) -> list[dict[str, Any]]:
    from quant_platform_kit.strategy_lifecycle.drift_detector import run_drift_detection

    results = run_drift_detection(domain)
    payloads: list[dict[str, Any]] = []
    for item in results:
        status = getattr(getattr(item, "status", None), "value", "")
        if status != "critical":
            continue
        payloads.append(
            {
                "trigger": "drift",
                "strategy_profile": item.strategy_profile,
                "domain": item.domain,
                "drift_score": item.drift_score,
                "context": {
                    "domain": item.domain,
                    "drift_score": item.drift_score,
                    "repository": os.environ.get("GITHUB_REPOSITORY", ""),
                },
            }
        )
    return payloads



def review_critical_drifts(domain, observations, *, roles, revision, reviewer=review_material):
    if domain not in {"cn_equity", "hk_equity", "us_equity", "crypto"} or not revision:
        raise ValueError("caller identity required")
    results = []
    for item in observations:
        material = {"repository": os.environ.get("GITHUB_REPOSITORY", ""), "revision": revision,
                    "observation": item, "advisory_only": True, "execution_authority_granted": False}
        identity = hashlib.sha256(json.dumps(material, sort_keys=True, allow_nan=False).encode()).hexdigest()
        try:
            result = reviewer(material, operation_id="drift:" + identity, required_roles=roles)
        except Exception:
            result = {"status": "unavailable", "reason": "review_unavailable", "advisory_only": True}
        results.append(result)
    pending = any(r.get("status") != "completed" for r in results)
    blocked = any(r.get("outcome") != "agree_approve" for r in results)
    return {"schema": "qsl.drift_review.v2", "ok": not pending and not blocked,
            "domain": domain, "count": len(results), "results": results,
            "state": "PARKED" if pending or blocked else "REVIEWED",
            "degraded": pending, "advisory_only": True, "execution_authority_granted": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--domain", required=True)
    args = parser.parse_args(argv)
    try:
        observations = _critical_drifts(args.domain)
        roles = json.loads(os.environ.get("AI_SERVICE_REQUIRED_ROLES_JSON", '["primary", "secondary", "verification"]'))
        if not isinstance(roles, list) or len(roles) != 3 or len(set(roles)) != 3 or any(not isinstance(r, str) or not r for r in roles):
            raise ValueError("three distinct review roles required")
        result = review_critical_drifts(args.domain, observations, roles=roles, revision=os.environ.get("GITHUB_SHA", ""))
    except Exception:
        result = {"schema": "qsl.drift_review.v2", "state": "PARKED", "ok": False,
                  "reason": "review_inputs_unavailable", "advisory_only": True, "execution_authority_granted": False}
    print(json.dumps(result, sort_keys=True))
    return 0 if result.get("ok") else 3


if __name__ == "__main__":
    raise SystemExit(main())
