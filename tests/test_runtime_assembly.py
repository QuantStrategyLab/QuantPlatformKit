from __future__ import annotations

from quant_platform_kit.common import RuntimeAssembly, build_runtime_target


def test_runtime_assembly_builds_log_context_and_report_kwargs():
    target = build_runtime_target(
        platform_id="longbridge",
        strategy_profile="soxl_soxx_trend_income",
        dry_run_only=True,
        deployment_selector="HK",
        account_scope="HK",
        service_name="longbridge-platform",
    )
    assembly = RuntimeAssembly(
        platform="longbridge",
        deploy_target="cloud_run",
        service_name="longbridge-platform",
        strategy_profile="soxl_soxx_trend_income",
        runtime_target=target,
        account_scope="HK",
        account_region="HK",
        project_id="project-1",
        extra_context_fields={"account_prefix": "HK"},
    )

    log_context = assembly.build_log_context(run_id="run-001")
    report_kwargs = assembly.build_report_base_kwargs(
        run_id="run-001",
        dry_run=True,
        strategy_domain="us_equity",
    )

    assert log_context.runtime_target is target
    assert log_context.extra_fields["account_prefix"] == "HK"
    assert report_kwargs["runtime_target"] is target
    assert report_kwargs["extra_context_fields"]["account_prefix"] == "HK"


def test_runtime_assembly_with_overrides_merges_extra_context_and_runtime_target():
    base_target = build_runtime_target(
        platform_id="longbridge",
        strategy_profile="soxl_soxx_trend_income",
        dry_run_only=True,
        deployment_selector="HK",
        account_scope="HK",
        service_name="longbridge-platform",
    )
    override_target = build_runtime_target(
        platform_id="longbridge",
        strategy_profile="soxl_soxx_trend_income",
        dry_run_only=False,
        deployment_selector="SG",
        account_scope="SG",
        service_name="longbridge-platform",
    )
    assembly = RuntimeAssembly(
        platform="longbridge",
        deploy_target="cloud_run",
        service_name="longbridge-platform",
        strategy_profile="soxl_soxx_trend_income",
        runtime_target=base_target,
        extra_context_fields={"account_prefix": "HK", "strategy": "original"},
    )

    merged = assembly.with_overrides(
        runtime_target=override_target,
        extra_context_fields={"strategy": "override", "env": "paper"},
    )

    assert merged.runtime_target is override_target
    assert merged.extra_context_fields == {
        "account_prefix": "HK",
        "strategy": "override",
        "env": "paper",
    }
    assert assembly.runtime_target is base_target
    assert assembly.extra_context_fields == {"account_prefix": "HK", "strategy": "original"}
