from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Any, Mapping

from .runtime_logging import RuntimeLogContext
from .runtime_target import RuntimeTarget


def build_runtime_assembly(
    *,
    platform: str,
    deploy_target: str,
    service_name: str,
    strategy_profile: str,
    runtime_target: RuntimeTarget | None = None,
    account_scope: str | None = None,
    account_group: str | None = None,
    account_region: str | None = None,
    project_id: str | None = None,
    instance_name: str | None = None,
    extra_context_fields: Mapping[str, Any] | None = None,
) -> "RuntimeAssembly":
    return RuntimeAssembly(
        platform=platform,
        deploy_target=deploy_target,
        service_name=service_name,
        strategy_profile=strategy_profile,
        runtime_target=runtime_target,
        account_scope=account_scope,
        account_group=account_group,
        account_region=account_region,
        project_id=project_id,
        instance_name=instance_name,
        extra_context_fields=dict(extra_context_fields or {}),
    )


@dataclass(frozen=True)
class RuntimeAssembly:
    platform: str
    deploy_target: str
    service_name: str
    strategy_profile: str
    runtime_target: RuntimeTarget | None = None
    account_scope: str | None = None
    account_group: str | None = None
    account_region: str | None = None
    project_id: str | None = None
    instance_name: str | None = None
    extra_context_fields: Mapping[str, Any] = field(default_factory=dict)

    def with_overrides(
        self,
        *,
        runtime_target: RuntimeTarget | None = None,
        extra_context_fields: Mapping[str, Any] | None = None,
    ) -> "RuntimeAssembly":
        merged_extra = dict(self.extra_context_fields)
        if extra_context_fields:
            merged_extra.update(dict(extra_context_fields))
        return replace(
            self,
            runtime_target=self.runtime_target if runtime_target is None else runtime_target,
            extra_context_fields=merged_extra,
        )

    def build_log_context(
        self,
        *,
        run_id: str,
        trace: str | None = None,
    ) -> RuntimeLogContext:
        return RuntimeLogContext(
            platform=self.platform,
            deploy_target=self.deploy_target,
            service_name=self.service_name,
            strategy_profile=self.strategy_profile,
            runtime_target=self.runtime_target,
            account_scope=self.account_scope,
            account_group=self.account_group,
            account_region=self.account_region,
            project_id=self.project_id,
            instance_name=self.instance_name,
            trace=trace,
            extra_fields=dict(self.extra_context_fields),
        ).with_run(run_id)

    def build_report_base_kwargs(
        self,
        *,
        run_id: str,
        run_source: str = "cloud_run",
        dry_run: bool = False,
        started_at: datetime | None = None,
        strategy_domain: str | None = None,
        extra_context_fields: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        merged_extra = dict(self.extra_context_fields)
        if extra_context_fields:
            merged_extra.update(dict(extra_context_fields))
        return {
            "platform": self.platform,
            "deploy_target": self.deploy_target,
            "service_name": self.service_name,
            "strategy_profile": self.strategy_profile,
            "runtime_target": self.runtime_target,
            "strategy_domain": strategy_domain,
            "account_scope": self.account_scope,
            "account_group": self.account_group,
            "account_region": self.account_region,
            "project_id": self.project_id,
            "instance_name": self.instance_name,
            "extra_context_fields": merged_extra,
            "run_id": run_id,
            "run_source": run_source,
            "dry_run": dry_run,
            "started_at": started_at,
        }
