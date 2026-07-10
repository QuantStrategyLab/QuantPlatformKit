#!/usr/bin/env python3
"""Validate a versioned ResearchSpec or OptimizationSpec JSON artifact."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from quant_platform_kit.strategy_spec.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
