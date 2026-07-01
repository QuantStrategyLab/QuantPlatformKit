from __future__ import annotations

import sys
import types
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from quant_platform_kit.common.health import register_health_endpoint


@dataclass
class _FakeRule:
    rule: str


class _FakeUrlMap:
    def __init__(self, app: _FakeFlaskApp):
        self._app = app

    def iter_rules(self):
        return iter(self._app.rules)


class _FakeFlaskApp:
    def __init__(self):
        self.rules: list[_FakeRule] = []
        self.view_functions: dict[str, Callable[..., Any]] = {}
        self.url_map = _FakeUrlMap(self)

    def add_url_rule(
        self,
        rule: str,
        endpoint: str,
        view_func: Callable[..., Any],
        methods: list[str],
    ) -> None:
        if endpoint in self.view_functions:
            raise AssertionError(
                f"View function mapping is overwriting an existing endpoint function: {endpoint}"
            )
        self.rules.append(_FakeRule(rule))
        self.view_functions[endpoint] = view_func


def _install_fake_flask(monkeypatch):
    monkeypatch.setitem(sys.modules, "flask", types.SimpleNamespace(jsonify=lambda payload: payload))


def test_register_health_endpoint_uses_non_colliding_endpoint_names(monkeypatch):
    _install_fake_flask(monkeypatch)
    app = _FakeFlaskApp()
    register_health_endpoint(app)

    app.add_url_rule("/", endpoint="health", view_func=lambda: "service-info", methods=["GET"])

    assert {rule.rule for rule in app.rules} == {"/health", "/healthz", "/"}
    assert {"qpk_health", "qpk_healthz", "health"} <= set(app.view_functions)


def test_register_health_endpoint_preserves_existing_health_route(monkeypatch):
    _install_fake_flask(monkeypatch)
    app = _FakeFlaskApp()
    app.add_url_rule("/health", endpoint="platform_health", view_func=lambda: "platform-ok", methods=["GET"])

    register_health_endpoint(app)

    assert [rule.rule for rule in app.rules] == ["/health", "/healthz"]
    assert "platform_health" in app.view_functions
    assert "qpk_health" not in app.view_functions
    assert "qpk_healthz" in app.view_functions
