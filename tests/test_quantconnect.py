from __future__ import annotations

import base64
import hashlib
import json
import unittest

from quant_platform_kit.quantconnect import (
    BrokerageHolding,
    CashAmount,
    InteractiveBrokersBrokerageSettings,
    QuantConnectApiError,
    QuantConnectCredentials,
    QuantConnectLiveConnector,
    QuantConnectLiveDeployment,
    QuantConnectPaperBrokerageSettings,
    QuantConnectRestClient,
)


class _FakeResponse:
    def __init__(self, payload: dict[str, object], *, status: int = 200) -> None:
        self.payload = payload
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


class QuantConnectTests(unittest.TestCase):
    def test_credentials_build_quantconnect_auth_headers(self) -> None:
        credentials = QuantConnectCredentials(user_id="42", api_token="test-token")
        headers = credentials.build_auth_headers(clock=lambda: 1234567890)

        hashed_token = hashlib.sha256(b"test-token:1234567890").hexdigest()
        expected_auth = base64.b64encode(f"42:{hashed_token}".encode("utf-8")).decode("ascii")
        self.assertEqual(headers["Timestamp"], "1234567890")
        self.assertEqual(headers["Authorization"], f"Basic {expected_auth}")

    def test_credentials_load_from_env_style_mapping(self) -> None:
        credentials = QuantConnectCredentials.from_env(
            {
                "QUANTCONNECT_USER_ID": "42",
                "QUANTCONNECT_API_TOKEN": "test-token",
                "QUANTCONNECT_ORGANIZATION_ID": "org-1",
            }
        )

        self.assertEqual(credentials.user_id, "42")
        self.assertEqual(credentials.organization_id, "org-1")
        self.assertEqual(credentials.redacted()["api_token"], "***")

    def test_interactive_brokers_brokerage_payload_uses_quantconnect_keys(self) -> None:
        settings = InteractiveBrokersBrokerageSettings(
            user_name="ib-user",
            account="U00000000",
            password="ib-password",
            weekly_restart_utc_time="08:30:00",
        )

        self.assertEqual(
            settings.to_payload(),
            {
                "id": "InteractiveBrokersBrokerage",
                "ib-user-name": "ib-user",
                "ib-account": "U00000000",
                "ib-password": "ib-password",
                "ib-weekly-restart-utc-time": "08:30:00",
            },
        )
        self.assertEqual(settings.redacted_payload()["ib-password"], "***")

    def test_live_deployment_builds_create_payload(self) -> None:
        deployment = QuantConnectLiveDeployment(
            project_id=123,
            compile_id="compile-1",
            node_id="LN-1",
            brokerage=QuantConnectPaperBrokerageSettings(
                cash=(CashAmount(amount=25000.0, currency="USD"),),
                holdings=(
                    BrokerageHolding(
                        symbol_id="SPY R735QTJ8XC9X",
                        symbol="SPY",
                        quantity=1,
                        average_price=500,
                    ),
                ),
            ),
            data_providers={
                "QuantConnectBrokerage": {
                    "id": "QuantConnectBrokerage",
                },
            },
            parameters={"strategy": "tqqq_growth_income"},
        )

        payload = deployment.to_payload()

        self.assertEqual(payload["versionId"], "-1")
        self.assertEqual(payload["projectId"], 123)
        self.assertEqual(payload["compileId"], "compile-1")
        self.assertEqual(payload["nodeId"], "LN-1")
        self.assertEqual(payload["brokerage"]["id"], "QuantConnectBrokerage")
        self.assertEqual(payload["brokerage"]["cash"][0]["amount"], 25000.0)
        self.assertEqual(payload["parameters"]["strategy"], "tqqq_growth_income")

    def test_rest_client_posts_authenticated_json(self) -> None:
        requests = []

        def opener(request, timeout):
            requests.append((request, timeout))
            return _FakeResponse({"success": True, "deployId": "L-1"})

        client = QuantConnectRestClient(
            credentials=QuantConnectCredentials(user_id="42", api_token="test-token"),
            api_base_url="https://qc.example.test/api/v2/",
            timeout=3.0,
            opener=opener,
            clock=lambda: 1234567890,
        )

        result = client.create_live_algorithm(
            {
                "projectId": 123,
                "compileId": "compile-1",
                "nodeId": "LN-1",
                "versionId": "-1",
                "brokerage": {"id": "QuantConnectBrokerage"},
            }
        )

        self.assertEqual(result["deployId"], "L-1")
        request, timeout = requests[0]
        self.assertEqual(timeout, 3.0)
        self.assertEqual(request.full_url, "https://qc.example.test/api/v2/live/create")
        self.assertEqual(request.method, "POST")
        self.assertIn("Authorization", request.headers)
        self.assertEqual(json.loads(request.data.decode("utf-8"))["projectId"], 123)

    def test_rest_client_raises_for_unsuccessful_api_response(self) -> None:
        def opener(_request, timeout=None):
            del timeout
            return _FakeResponse({"success": False, "errors": ["invalid credentials"]})

        client = QuantConnectRestClient(
            credentials=QuantConnectCredentials(user_id="42", api_token="test-token"),
            opener=opener,
            clock=lambda: 1234567890,
        )

        with self.assertRaises(QuantConnectApiError) as context:
            client.authenticate()

        self.assertIn("invalid credentials", str(context.exception))

    def test_live_connector_filters_running_deployments(self) -> None:
        def opener(_request, timeout=None):
            del timeout
            return _FakeResponse(
                {
                    "success": True,
                    "live": [
                        {"projectId": 123, "deployId": "L-1", "status": "Running"},
                        "malformed",
                    ],
                }
            )

        connector = QuantConnectLiveConnector(
            QuantConnectRestClient(
                credentials=QuantConnectCredentials(user_id="42", api_token="test-token"),
                opener=opener,
                clock=lambda: 1234567890,
            )
        )

        self.assertEqual(
            connector.running_deployments(project_id=123),
            ({"projectId": 123, "deployId": "L-1", "status": "Running"},),
        )


if __name__ == "__main__":
    unittest.main()
