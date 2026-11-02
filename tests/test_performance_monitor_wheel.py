"""Test the installed wheel's core recorder and optional numeric boundary."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys
import venv

import pytest


_PROBE = '''
import importlib.util
import json
from pathlib import Path
import sys


def offline(event, args):
    if event in {"socket.connect", "socket.bind", "socket.getaddrinfo",
                 "subprocess.Popen", "os.system", "os.posix_spawn"}:
        raise AssertionError("unexpected external operation: " + event)


sys.addaudithook(offline)
import quant_platform_kit.strategy_lifecycle.performance_monitor as monitor
from quant_platform_kit.strategy_lifecycle.performance_store import PerformanceStore

origin = Path(monitor.__file__).resolve()
assert origin.is_relative_to(Path(sys.prefix).resolve()), origin
store = PerformanceStore(local_root=Path.cwd() / "records")
'''

_CORE_PROBE = _PROBE + '''
for name in ("numpy", "pandas"):
    assert importlib.util.find_spec(name) is None, name
    assert name not in sys.modules, name

recorder = monitor.PerformanceMonitor(store=store)
assert recorder.record("synthetic_profile", None, {"status": "dry_run"},
                       domain="crypto", stream_id="synthetic-stream")["ok"]
assert recorder.record_execution("synthetic_profile", {"status": "dry_run"},
                                 domain="crypto", stream_id="synthetic-stream")["ok"]
records = list(store.list_live_run_records("crypto", strategy_profile="synthetic_profile",
                                         stream_id="synthetic-stream"))
assert len(records) == 2, records
assert {record.get("record_kind", "decision") for record in records} == {"decision", "execution"}
assert all(record["execution_result"] == {"status": "dry_run"} for record in records)
assert monitor.infer_strategy_domain("crypto_synthetic") == "crypto"
assert monitor.resolve_monitor_source_revision("synthetic-revision") == "synthetic-revision"
monitor.try_record_platform_execution("synthetic_profile", {})
assert recorder.record("", None) == {"ok": False, "skipped": "empty_profile"}
for name in ("numpy", "pandas"):
    assert name not in sys.modules, name
try:
    monitor.run_monitor("crypto", store=store)
except ModuleNotFoundError as exc:
    assert exc.name == "pandas", exc
else:
    raise AssertionError("numeric monitoring must require the research dependencies")
assert not list(Path("records").glob("daily/**/*.json"))
print(json.dumps({"mode": "core", "origin": str(origin), "records": len(records),
                  "numeric_dependencies": "absent", "external_operations": 0}))
'''

_RESEARCH_PROBE = _PROBE + '''
import pandas as pd
from quant_platform_kit.strategy_lifecycle.performance_metrics import DEFAULT_WINDOWS
assert monitor.DEFAULT_WINDOWS == DEFAULT_WINDOWS == (21, 63, 126, 252, 756)
assert monitor.run_monitor.__kwdefaults__["windows"] == DEFAULT_WINDOWS


class SyntheticCollector:
    def collect(self, domain):
        assert domain == "crypto"
        return {"synthetic_profile": pd.Series(
            [0.01, -0.02], index=pd.to_datetime(["2026-01-01", "2026-01-02"]))}

    def collect_benchmark(self, domain, symbol):
        return pd.Series([0.005, -0.01], index=pd.to_datetime(["2026-01-01", "2026-01-02"]))


snapshots = monitor.run_monitor(
    "crypto", collector=SyntheticCollector(), store=store, windows=(2,),
    min_observations=2, source_revision="synthetic-revision")
assert len(snapshots) == 1
snapshot = snapshots[0]
metrics = snapshot.windows[2]
assert abs(metrics.total_return - (1.01 * 0.98 - 1)) < 1e-12
assert metrics.observation_count == 2
assert metrics.periods_per_year == 365.25
benchmark_cagr = (1.005 * 0.99) ** (365.25 / 2) - 1
assert abs(metrics.excess_cagr - (metrics.cagr - benchmark_cagr)) < 1e-12
assert snapshot.latest_return == -0.02
assert snapshot.source_revision == "synthetic-revision"
loaded = store.load_latest_snapshot("crypto", "synthetic_profile")
assert loaded is not None
assert loaded.windows[2].to_dict() == metrics.to_dict()
assert loaded.latest_return == snapshot.latest_return
assert loaded.source_revision == snapshot.source_revision
persisted = next(Path("records/daily").rglob("*.json"))
payload = json.loads(persisted.read_text())
assert payload.pop("schema_version") == "strategy_lifecycle.v1"
assert payload == snapshot.to_dict()
for name in ("numpy", "pandas"):
    module = sys.modules[name]
    assert Path(module.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
print(json.dumps({"mode": "research", "origin": str(origin),
                  "total_return": metrics.total_return, "periods_per_year": 365.25,
                  "external_operations": 0}))
'''


def _setup_env(root: Path) -> dict[str, str]:
    env = {"PATH": os.defpath, "HOME": str(root)}
    for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY",
                "http_proxy", "https_proxy", "all_proxy", "no_proxy",
                "SSL_CERT_FILE", "SSL_CERT_DIR", "REQUESTS_CA_BUNDLE", "PIP_CERT"):
        if key in os.environ:
            env[key] = os.environ[key]
    return env


def _run(args: list[str], cwd: Path, env: dict[str, str]) -> str:
    result = subprocess.run(args, cwd=cwd, env=env, text=True, capture_output=True, timeout=300)
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout


@pytest.fixture(scope="module")
def wheel(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("monitor-wheel")
    source = root / "source"
    source.mkdir()
    repo = Path(__file__).resolve().parents[1]
    shutil.copytree(repo / "src", source / "src", ignore=shutil.ignore_patterns(
        "__pycache__", "*.egg-info"))
    for name in ("pyproject.toml", "setup.py", "README.md", "LICENSE"):
        shutil.copy2(repo / name, source / name)
    _run([sys.executable, "-I", "-m", "pip", "--isolated", "wheel", "--no-deps",
          "--index-url", "https://pypi.org/simple", "--wheel-dir", str(root / "wheels"),
          str(source)], root, _setup_env(root))
    return next((root / "wheels").glob("*.whl"))


@pytest.mark.parametrize("extra,probe", [("", _CORE_PROBE), ("research", _RESEARCH_PROBE)],
                         ids=["core-no-extras", "research-numeric-unit"])
def test_installed_monitor_wheel(wheel: Path, tmp_path: Path, extra: str, probe: str) -> None:
    environment = tmp_path / "venv"
    venv.EnvBuilder(with_pip=True, system_site_packages=False).create(environment)
    python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    env = _setup_env(tmp_path)
    target = str(wheel) + (f"[{extra}]" if extra else "")
    _run([str(python), "-I", "-m", "pip", "--isolated", "install", "--no-cache-dir",
          "--index-url", "https://pypi.org/simple", target], tmp_path, env)
    _run([str(python), "-I", "-m", "pip", "check"], tmp_path, env)
    print(_run([str(python), "-I", "-c", probe], tmp_path, env).strip())
