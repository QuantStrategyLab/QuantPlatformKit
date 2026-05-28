from __future__ import annotations

import re
import tomllib
from pathlib import Path

import quant_platform_kit


ROOT = Path(__file__).resolve().parents[1]


def test_package_version_declarations_match() -> None:
    pyproject_version = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    setup_text = (ROOT / "setup.py").read_text(encoding="utf-8")
    setup_version = re.search(r'version="([^"]+)"', setup_text)

    assert setup_version is not None
    assert quant_platform_kit.__version__ == pyproject_version
    assert setup_version.group(1) == pyproject_version
