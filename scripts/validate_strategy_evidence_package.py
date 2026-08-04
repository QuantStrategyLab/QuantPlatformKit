#!/usr/bin/env python3
"""Compatibility CLI for the canonical strategy evidence package validator."""

from __future__ import annotations

import argparse
import sys

from quant_platform_kit.strategy_lifecycle.evidence_package_v2 import (
    STRATEGY_EVIDENCE_PACKAGE_SCHEMA_VERSION,
    canonical_evidence_package_v2_bytes,
    read_evidence_package_v2_json,
    validate_evidence_package_v2,
    validate_strategy_evidence_file,
    validate_strategy_evidence_payload,
)

validate_payload = validate_strategy_evidence_payload
validate_file = validate_strategy_evidence_file


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="validate_strategy_evidence_package")
    parser.add_argument("path", help="path to evidence package JSON")
    args = parser.parse_args(argv)

    issues = validate_file(args.path)
    if issues:
        for issue in issues:
            print(issue, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
