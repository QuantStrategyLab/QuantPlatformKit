from __future__ import annotations

from quant_platform_kit.common.runtime_logging import (
    RuntimeLogContext,
    build_run_id,
    emit_runtime_log,
    extract_cloud_trace,
)


def test_runtime_log_context_emits_runtime_target_and_extra_fields():
    lines: list[str] = []
    context = RuntimeLogContext(
        platform="longbridge",
        deploy_target="cloud_run",
        service_name="longbridge-platform",
        strategy_profile="soxl_soxx_trend_income",
        runtime_target={"platform_id": "longbridge", "strategy_profile": "soxl_soxx_trend_income"},
        extra_fields={"account_prefix": "HK"},
    ).with_run("run-001")

    payload = emit_runtime_log(
        context,
        "runtime_test",
        message="testing",
        printer=lines.append,
    )

    assert payload["runtime_target"]["platform_id"] == "longbridge"
    assert payload["account_prefix"] == "HK"
    assert lines and "\"runtime_target\"" in lines[0]


def test_build_run_id_and_trace_helpers_still_work():
    assert build_run_id().endswith("Z")
    assert extract_cloud_trace("demo-project", "abc123/1;o=1") == "projects/demo-project/traces/abc123"
