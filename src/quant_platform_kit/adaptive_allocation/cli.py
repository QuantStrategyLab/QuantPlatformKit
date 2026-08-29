"""Command-line entry point for writing a Shadow-only selection record."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from quant_platform_kit.adaptive_allocation.io import build_shadow_selection, load_shadow_selection_input


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate a no-order adaptive Shadow selection record")
    parser.add_argument("--input", required=True, help="versioned selection-input JSON file")
    parser.add_argument("--output", required=True, help="destination JSON artifact path")
    args = parser.parse_args(argv)

    decision = build_shadow_selection(load_shadow_selection_input(args.input))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(decision.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
