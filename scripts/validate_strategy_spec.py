#!/usr/bin/env python3
"""Validate a versioned ResearchSpec or OptimizationSpec JSON artifact."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from quant_platform_kit.strategy_lifecycle.spec_validation import validate_strategy_spec_file


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="validate_strategy_spec")
    parser.add_argument("path", help="path to a research_spec.v1 or optimization_spec.v1 JSON file")
    args = parser.parse_args(argv)

    issues = validate_strategy_spec_file(args.path)
    if issues:
        for issue in issues:
            print(issue, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
