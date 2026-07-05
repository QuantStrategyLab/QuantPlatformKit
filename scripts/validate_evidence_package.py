#!/usr/bin/env python3
"""Validate a strategy promotion evidence package."""

from __future__ import annotations

import sys

from quant_platform_kit.strategy_lifecycle.cli import main


if __name__ == "__main__":
    raise SystemExit(main(["evidence", "--file", *sys.argv[1:]]) if len(sys.argv) > 1 else 2)
