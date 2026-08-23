"""Build the read-only daily lifecycle matrix from existing JSON artifacts.

This entry point intentionally only reads producer artifacts.  It never starts
a strategy, fetches data, retries a run, sends a notification, or authorizes a
promotion/trade.  A scheduled job may call it after upstream jobs have
published their terminal artifacts.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from quant_platform_kit.strategy_lifecycle.lifecycle_matrix_runtime import (
    LifecycleMatrixInputError,
    build_lifecycle_matrix,
)


def _artifact_paths(inputs: list[str]) -> list[Path]:
    paths: list[Path] = []
    for raw in inputs:
        path = Path(raw)
        if path.is_file():
            paths.append(path)
        elif path.is_dir():
            paths.extend(sorted(path.rglob("*.json")))
        else:
            raise LifecycleMatrixInputError(f"{path}: artifact path does not exist")
    return paths


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Aggregate existing lifecycle terminal artifacts (read-only)."
    )
    parser.add_argument("inputs", nargs="+", help="JSON artifacts or directories containing them")
    parser.add_argument("--output", type=Path, help="write the matrix JSON to this path")
    parser.add_argument("--generated-at", default=date.today().isoformat())
    args = parser.parse_args(argv)

    try:
        matrix = build_lifecycle_matrix(
            _artifact_paths(args.inputs), generated_at=args.generated_at
        )
    except LifecycleMatrixInputError as exc:
        print(f"lifecycle matrix build failed: {exc}", file=sys.stderr)
        return 2

    rendered = json.dumps(matrix, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
