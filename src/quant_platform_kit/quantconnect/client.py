from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Callable

from .models import QuantConnectCredentials, QuantConnectLiveDeployment, redact_sensitive_payload


DEFAULT_QUANTCONNECT_API_BASE_URL = "https://www.quantconnect.com/api/v2"


class QuantConnectApiError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        payload: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.payload = dict(payload or {})


@dataclass(frozen=True)
class QuantConnectRestClient:
    credentials: QuantConnectCredentials
    api_base_url: str = DEFAULT_QUANTCONNECT_API_BASE_URL
    timeout: float = 15.0
    opener: Any = None
    clock: Callable[[], float] = field(default=time.time, repr=False)

    def authenticate(self) -> dict[str, Any]:
        return self.post_json("/authenticate", {})

    def create_live_algorithm(self, deployment: QuantConnectLiveDeployment | Mapping[str, Any]) -> dict[str, Any]:
        payload = deployment.to_payload() if hasattr(deployment, "to_payload") else dict(deployment)
        return self.post_json("/live/create", payload)

    def read_live_algorithm(self, *, project_id: int, deploy_id: str) -> dict[str, Any]:
        return self.post_json(
            "/live/read",
            {
                "projectId": int(project_id),
                "deployId": str(deploy_id).strip(),
            },
        )

    def list_live_algorithms(
        self,
        *,
        project_id: int | None = None,
        status: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        if project_id is not None:
            payload["projectId"] = int(project_id)
        text_status = str(status or "").strip()
        if text_status:
            payload["status"] = text_status
        return self.post_json("/live/list", payload)

    def stop_live_algorithm(self, *, project_id: int) -> dict[str, Any]:
        return self.post_json("/live/update/stop", {"projectId": int(project_id)})

    def liquidate_live_algorithm(self, *, project_id: int) -> dict[str, Any]:
        return self.post_json("/live/update/liquidate", {"projectId": int(project_id)})

    def post_json(self, path: str, payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
        request_payload = dict(payload or {})
        request = urllib.request.Request(
            self._endpoint(path),
            data=json.dumps(request_payload, ensure_ascii=False).encode("utf-8"),
            headers={
                **self.credentials.build_auth_headers(clock=self.clock),
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with self._opener()(request, timeout=self.timeout) as response:
                status_code = _response_status(response)
                raw_body = response.read()
        except urllib.error.HTTPError as exc:
            status_code = int(exc.code)
            raw_body = exc.read()
            parsed_error = _parse_response_body(raw_body)
            raise QuantConnectApiError(
                f"QuantConnect API request failed with HTTP {status_code}",
                status_code=status_code,
                payload=redact_sensitive_payload(parsed_error),
            ) from exc

        result = _parse_response_body(raw_body)
        if status_code < 200 or status_code >= 300:
            raise QuantConnectApiError(
                f"QuantConnect API request failed with HTTP {status_code}",
                status_code=status_code,
                payload=redact_sensitive_payload(result),
            )
        if result.get("success") is False:
            errors = result.get("errors")
            message = "QuantConnect API request failed"
            if errors:
                message = f"{message}: {errors}"
            raise QuantConnectApiError(
                message,
                status_code=status_code,
                payload=redact_sensitive_payload(result),
            )
        return result

    def _endpoint(self, path: str) -> str:
        base_url = str(self.api_base_url or DEFAULT_QUANTCONNECT_API_BASE_URL).rstrip("/")
        endpoint_path = str(path or "").strip().lstrip("/")
        if not endpoint_path:
            raise ValueError("path must not be empty.")
        return f"{base_url}/{endpoint_path}"

    def _opener(self) -> Any:
        return self.opener or urllib.request.urlopen


@dataclass(frozen=True)
class QuantConnectLiveConnector:
    client: QuantConnectRestClient

    def deploy(self, deployment: QuantConnectLiveDeployment) -> dict[str, Any]:
        return self.client.create_live_algorithm(deployment)

    def running_deployments(self, *, project_id: int | None = None) -> tuple[dict[str, Any], ...]:
        result = self.client.list_live_algorithms(project_id=project_id, status="Running")
        live = result.get("live") or ()
        if not isinstance(live, list):
            return ()
        return tuple(dict(item) for item in live if isinstance(item, Mapping))

    def stop_project(self, *, project_id: int, liquidate: bool = False) -> dict[str, Any]:
        if liquidate:
            return self.client.liquidate_live_algorithm(project_id=project_id)
        return self.client.stop_live_algorithm(project_id=project_id)


def _response_status(response: Any) -> int:
    status = getattr(response, "status", None)
    if status is None:
        status = response.getcode()
    return int(status)


def _parse_response_body(raw_body: bytes | str | None) -> dict[str, Any]:
    if raw_body is None or raw_body == b"" or raw_body == "":
        return {}
    if isinstance(raw_body, bytes):
        body_text = raw_body.decode("utf-8")
    else:
        body_text = raw_body
    parsed = json.loads(body_text)
    if not isinstance(parsed, dict):
        raise QuantConnectApiError("QuantConnect API response must decode to an object.")
    return parsed
