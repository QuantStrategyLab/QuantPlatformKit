"""Validated account identity and policy snapshots, without execution authority."""
from __future__ import annotations

from datetime import datetime, timedelta
import hashlib
import json
import re
from typing import Any, Mapping

_IDENTITY_FIELDS = frozenset({"environment", "platform_id", "server", "account_id_fingerprint", "lifecycle_id"})
_POLICY_FIELDS = frozenset({"capital_kind", "product", "phase", "account_type", "style", "preference", "currency", "source", "effective_at", "valid_until", "version"})


def _time(value: str) -> datetime:
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError) as exc:
        raise ValueError("account domain time must be ISO 8601 UTC") from exc
    if result.tzinfo is None or result.utcoffset() != timedelta(0):
        raise ValueError("account domain time must be timezone-aware UTC")
    return result


def validate_account_domain(value: Mapping[str, Any], *, platform_id: str | None = None) -> dict[str, dict[str, str]]:
    if not isinstance(value, Mapping) or set(value) != {"identity", "policy"}:
        raise ValueError("account_domain must contain identity and policy")
    identity, policy = value["identity"], value["policy"]
    if not isinstance(identity, Mapping) or set(identity) != _IDENTITY_FIELDS:
        raise ValueError("invalid account domain identity fields")
    if not isinstance(policy, Mapping) or set(policy) != _POLICY_FIELDS:
        raise ValueError("invalid account domain policy fields")
    if any(not isinstance(item, str) or not item.strip() or item != item.strip() for item in (*identity.values(), *policy.values())):
        raise ValueError("account domain fields must be nonempty strings")
    identity, policy = dict(identity), dict(policy)
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", identity["account_id_fingerprint"]):
        raise ValueError("invalid account fingerprint")
    if platform_id is not None and identity["platform_id"].lower() != platform_id.lower():
        raise ValueError("account domain platform mismatch")
    if policy["preference"] not in {"CAPITAL_PRESERVATION", "BALANCED_COMPOUNDING", "GROWTH_COMPOUNDING"}:
        raise ValueError("invalid risk preference")
    if not re.fullmatch(r"[A-Z]{3}", policy["currency"]):
        raise ValueError("invalid currency")
    if _time(policy["valid_until"]) <= _time(policy["effective_at"]):
        raise ValueError("invalid policy validity interval")
    if policy["capital_kind"] == "FTMO_SIMULATED":
        if (policy["product"], policy["phase"], policy["account_type"], identity["environment"]) not in {
            ("FTMO_CFD_2_STEP", "FREE_TRIAL", "STANDARD", "DEMO"),
            ("FTMO_CFD_2_STEP", "FREE_TRIAL", "SWING", "DEMO"),
        }:
            raise ValueError("unsupported FTMO account domain")
    elif policy["capital_kind"] == "OWN_REAL":
        if identity["environment"] != "LIVE" or policy["product"] != "BROKERAGE" or policy["phase"] != "LIVE" or policy["account_type"] not in {"CASH", "MARGIN"}:
            raise ValueError("unsupported real account domain")
    else:
        raise ValueError("invalid capital kind")
    return {"identity": identity, "policy": policy}


def account_domain_key(value: Mapping[str, Any]) -> str:
    identity = validate_account_domain(value)["identity"]
    canonical = json.dumps(identity, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def account_domain_matches_broker_identity(
    value: Mapping[str, Any], observation: object, *, observed_environment=None,
    observed_server=None, observed_currency=None, observed_lifecycle_id=None,
) -> bool:
    """Compare the configured domain with independently observed broker facts."""
    from .account_identity import BrokerAccountIdentity

    domain = validate_account_domain(value)
    if not isinstance(observation, BrokerAccountIdentity):
        return False
    identity, policy = domain["identity"], domain["policy"]
    return (
        observed_environment == identity["environment"]
        and observed_server == identity["server"]
        and observed_currency == policy["currency"]
        and observed_lifecycle_id == identity["lifecycle_id"]
        and observation.platform_id == identity["platform_id"].lower()
        and observation.account_id_fingerprint == identity["account_id_fingerprint"]
        and observation.account_types == (policy["account_type"].lower(),)
        and len(observation.account_modes) == 1
        and observation.account_modes[0] in ({"live"} if identity["environment"] == "LIVE" else {"demo", "paper"})
    )


def account_domain_policy_active(value: Mapping[str, Any], *, as_of: str) -> bool:
    """Evaluate validity against an explicit trusted UTC observation time."""
    policy = validate_account_domain(value)["policy"]
    moment = _time(as_of)
    return _time(policy["effective_at"]) <= moment < _time(policy["valid_until"])
