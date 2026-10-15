"""Deployment identifiers are supplied explicitly before any cloud command."""

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

SPEC = importlib.util.spec_from_file_location(
    "sync_strategy_config", Path(__file__).resolve().parents[1] / "scripts/sync_strategy_config.py"
)
sync = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = sync
SPEC.loader.exec_module(sync)


@pytest.mark.parametrize("platform", ["schwab", "ibkr", "longbridge"])
def test_missing_identifiers_stop_before_cloud_commands(monkeypatch, platform):
    prefix = platform.upper()
    monkeypatch.delenv(f"{prefix}_GCP_PROJECT_ID", raising=False)
    monkeypatch.delenv(f"{prefix}_SCHEDULER_SERVICE_ACCOUNT", raising=False)
    command = Mock()
    monkeypatch.setattr(sync.subprocess, "run", command)
    with pytest.raises(ValueError, match=f"{prefix}_GCP_PROJECT_ID is required"):
        sync.get_service_url(platform)
    monkeypatch.setenv(f"{prefix}_GCP_PROJECT_ID", "example-project")
    with pytest.raises(ValueError, match=f"{prefix}_SCHEDULER_SERVICE_ACCOUNT is required"):
        sync.sync_scheduler_jobs("example", {}, platform)
    command.assert_not_called()


@pytest.mark.parametrize("platform,region", [
    ("schwab", "us-central1"), ("ibkr", "us-central1"), ("longbridge", "asia-east2"),
])
def test_configured_identifiers_reach_existing_commands(monkeypatch, platform, region):
    monkeypatch.setenv(f"{platform.upper()}_GCP_PROJECT_ID", "example-project")
    monkeypatch.setenv(f"{platform.upper()}_SCHEDULER_SERVICE_ACCOUNT", "scheduler@example-project.iam.gserviceaccount.com")
    command = Mock(side_effect=[
        SimpleNamespace(returncode=0, stdout="https://example.invalid\n"),
        *[result for _ in range(3) for result in (
            SimpleNamespace(returncode=1, stdout="", stderr="missing"),
            SimpleNamespace(returncode=0, stdout="", stderr=""),
        )],
    ])
    monkeypatch.setattr(sync.subprocess, "run", command)
    report = sync.sync_scheduler_jobs("example", {}, platform, apply=True)
    assert report.errors == []
    assert len(report.added) == 3
    for call in command.call_args_list:
        args = call.args[0]
        assert args[args.index("--project") + 1] == "example-project"
        if "create" in args:
            assert args[args.index("--location") + 1] == region
            assert args[args.index("--oidc-service-account-email") + 1] == "scheduler@example-project.iam.gserviceaccount.com"
