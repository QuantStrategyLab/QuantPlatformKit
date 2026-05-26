from __future__ import annotations

import base64
import hashlib
import json
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Callable


_SENSITIVE_KEY_PARTS = ("password", "token", "secret", "key")


def _required_text(value: object, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field_name} must not be empty.")
    return text


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _lookup(mapping: Mapping[str, object], *keys: str) -> object | None:
    for key in keys:
        value = mapping.get(key)
        if value is not None and str(value).strip() != "":
            return value
    return None


def _payload_from(value: Any) -> dict[str, Any]:
    if hasattr(value, "to_payload"):
        payload = value.to_payload()
    else:
        payload = value
    if not isinstance(payload, Mapping):
        raise TypeError("QuantConnect payload values must be mappings or expose to_payload().")
    return dict(payload)


def redact_sensitive_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Return a copy with common credential fields replaced by a redaction marker."""

    redacted: dict[str, Any] = {}
    for key, value in payload.items():
        key_text = str(key)
        lowered_key = key_text.lower()
        if any(part in lowered_key for part in _SENSITIVE_KEY_PARTS):
            redacted[key_text] = "***"
            continue
        if isinstance(value, Mapping):
            redacted[key_text] = redact_sensitive_payload(value)
        elif isinstance(value, list):
            redacted[key_text] = [
                redact_sensitive_payload(item) if isinstance(item, Mapping) else item
                for item in value
            ]
        else:
            redacted[key_text] = value
    return redacted


@dataclass(frozen=True)
class QuantConnectCredentials:
    user_id: str
    api_token: str = field(repr=False)
    organization_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "user_id", _required_text(self.user_id, "user_id"))
        object.__setattr__(self, "api_token", _required_text(self.api_token, "api_token"))
        object.__setattr__(
            self,
            "organization_id",
            _optional_text(self.organization_id),
        )

    @classmethod
    def from_env(
        cls,
        env: Mapping[str, str | None],
        *,
        prefix: str = "QUANTCONNECT",
    ) -> "QuantConnectCredentials":
        normalized_prefix = _required_text(prefix, "prefix").upper()
        return cls.from_mapping(
            env,
            user_id_key=f"{normalized_prefix}_USER_ID",
            api_token_key=f"{normalized_prefix}_API_TOKEN",
            organization_id_key=f"{normalized_prefix}_ORGANIZATION_ID",
        )

    @classmethod
    def from_mapping(
        cls,
        values: Mapping[str, object],
        *,
        user_id_key: str = "user_id",
        api_token_key: str = "api_token",
        organization_id_key: str = "organization_id",
    ) -> "QuantConnectCredentials":
        user_id = _lookup(values, user_id_key, "userId", "user_id")
        api_token = _lookup(values, api_token_key, "apiToken", "api_token")
        organization_id = _lookup(values, organization_id_key, "organizationId", "organization_id")
        return cls(
            user_id=_required_text(user_id, user_id_key),
            api_token=_required_text(api_token, api_token_key),
            organization_id=_optional_text(organization_id),
        )

    @classmethod
    def from_json_payload(cls, payload: str) -> "QuantConnectCredentials":
        values = json.loads(payload)
        if not isinstance(values, Mapping):
            raise ValueError("QuantConnect credential payload must decode to an object.")
        return cls.from_mapping(values)

    def build_auth_headers(
        self,
        *,
        clock: Callable[[], float] = time.time,
    ) -> dict[str, str]:
        timestamp = str(int(clock()))
        time_stamped_token = f"{self.api_token}:{timestamp}".encode("utf-8")
        hashed_token = hashlib.sha256(time_stamped_token).hexdigest()
        auth_payload = f"{self.user_id}:{hashed_token}".encode("utf-8")
        authentication = base64.b64encode(auth_payload).decode("ascii")
        return {
            "Authorization": f"Basic {authentication}",
            "Timestamp": timestamp,
        }

    def redacted(self) -> dict[str, str | None]:
        return {
            "user_id": self.user_id,
            "api_token": "***",
            "organization_id": self.organization_id,
        }


@dataclass(frozen=True)
class CashAmount:
    amount: float
    currency: str = "USD"

    def to_payload(self) -> dict[str, Any]:
        return {
            "amount": float(self.amount),
            "currency": _required_text(self.currency, "currency"),
        }


@dataclass(frozen=True)
class BrokerageHolding:
    symbol_id: str
    symbol: str
    quantity: float
    average_price: float

    def to_payload(self) -> dict[str, Any]:
        return {
            "symbolId": _required_text(self.symbol_id, "symbol_id"),
            "symbol": _required_text(self.symbol, "symbol"),
            "quantity": float(self.quantity),
            "averagePrice": float(self.average_price),
        }


@dataclass(frozen=True)
class QuantConnectPaperBrokerageSettings:
    cash: tuple[CashAmount, ...] = (CashAmount(amount=100000.0, currency="USD"),)
    holdings: tuple[BrokerageHolding, ...] = ()

    def to_payload(self) -> dict[str, Any]:
        return {
            "id": "QuantConnectBrokerage",
            "holdings": [holding.to_payload() for holding in self.holdings],
            "cash": [cash_amount.to_payload() for cash_amount in self.cash],
        }


@dataclass(frozen=True)
class InteractiveBrokersBrokerageSettings:
    user_name: str
    account: str
    password: str = field(repr=False)
    weekly_restart_utc_time: str = "09:30:00"
    financial_advisors_group_filter: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "user_name", _required_text(self.user_name, "user_name"))
        object.__setattr__(self, "account", _required_text(self.account, "account"))
        object.__setattr__(self, "password", _required_text(self.password, "password"))
        object.__setattr__(
            self,
            "weekly_restart_utc_time",
            _required_text(self.weekly_restart_utc_time, "weekly_restart_utc_time"),
        )
        object.__setattr__(
            self,
            "financial_advisors_group_filter",
            _optional_text(self.financial_advisors_group_filter),
        )

    @classmethod
    def from_env(
        cls,
        env: Mapping[str, str | None],
        *,
        prefix: str = "QUANTCONNECT_IB",
    ) -> "InteractiveBrokersBrokerageSettings":
        normalized_prefix = _required_text(prefix, "prefix").upper()
        return cls.from_mapping(
            env,
            user_name_key=f"{normalized_prefix}_USER_NAME",
            account_key=f"{normalized_prefix}_ACCOUNT",
            password_key=f"{normalized_prefix}_PASSWORD",
            weekly_restart_utc_time_key=f"{normalized_prefix}_WEEKLY_RESTART_UTC_TIME",
            financial_advisors_group_filter_key=f"{normalized_prefix}_FINANCIAL_ADVISORS_GROUP_FILTER",
        )

    @classmethod
    def from_mapping(
        cls,
        values: Mapping[str, object],
        *,
        user_name_key: str = "user_name",
        account_key: str = "account",
        password_key: str = "password",
        weekly_restart_utc_time_key: str = "weekly_restart_utc_time",
        financial_advisors_group_filter_key: str = "financial_advisors_group_filter",
    ) -> "InteractiveBrokersBrokerageSettings":
        return cls(
            user_name=_required_text(
                _lookup(values, user_name_key, "ib-user-name", "ib_user_name", "userName"),
                user_name_key,
            ),
            account=_required_text(
                _lookup(values, account_key, "ib-account", "ib_account", "account"),
                account_key,
            ),
            password=_required_text(
                _lookup(values, password_key, "ib-password", "ib_password", "password"),
                password_key,
            ),
            weekly_restart_utc_time=_required_text(
                _lookup(
                    values,
                    weekly_restart_utc_time_key,
                    "ib-weekly-restart-utc-time",
                    "ib_weekly_restart_utc_time",
                    "weeklyRestartUtcTime",
                ),
                weekly_restart_utc_time_key,
            ),
            financial_advisors_group_filter=_optional_text(
                _lookup(
                    values,
                    financial_advisors_group_filter_key,
                    "ib-financial-advisors-group-filter",
                    "ib_financial_advisors_group_filter",
                    "financialAdvisorsGroupFilter",
                )
            ),
        )

    @classmethod
    def from_json_payload(cls, payload: str) -> "InteractiveBrokersBrokerageSettings":
        values = json.loads(payload)
        if not isinstance(values, Mapping):
            raise ValueError("Interactive Brokers brokerage payload must decode to an object.")
        return cls.from_mapping(values)

    def to_payload(self) -> dict[str, Any]:
        payload = {
            "id": "InteractiveBrokersBrokerage",
            "ib-user-name": self.user_name,
            "ib-account": self.account,
            "ib-password": self.password,
            "ib-weekly-restart-utc-time": self.weekly_restart_utc_time,
        }
        if self.financial_advisors_group_filter is not None:
            payload["ib-financial-advisors-group-filter"] = self.financial_advisors_group_filter
        return payload

    def redacted_payload(self) -> dict[str, Any]:
        return redact_sensitive_payload(self.to_payload())


@dataclass(frozen=True)
class QuantConnectLiveDeployment:
    project_id: int
    compile_id: str
    node_id: str
    brokerage: Any
    version_id: str = "-1"
    data_providers: Mapping[str, Any] = field(default_factory=dict)
    parameters: Mapping[str, Any] = field(default_factory=dict)
    notification: Mapping[str, Any] = field(default_factory=dict)

    def to_payload(self) -> dict[str, Any]:
        return {
            "versionId": _required_text(self.version_id, "version_id"),
            "projectId": int(self.project_id),
            "compileId": _required_text(self.compile_id, "compile_id"),
            "nodeId": _required_text(self.node_id, "node_id"),
            "brokerage": _payload_from(self.brokerage),
            "dataProviders": {
                str(name): _payload_from(settings)
                for name, settings in self.data_providers.items()
            },
            "parameters": dict(self.parameters),
            "notification": dict(self.notification),
        }

    def redacted_payload(self) -> dict[str, Any]:
        return redact_sensitive_payload(self.to_payload())
