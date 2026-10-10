"""Shared fail-closed input validation for research_stats (stdlib only)."""

from __future__ import annotations

import math
from typing import Iterable


class ResearchInputError(ValueError):
    """Raised internally when an input cannot be used; callers map it to a status."""


def finite_float(value: object, label: str) -> float:
    """Accept int/float (and numpy scalars); reject bool, str and non-finite."""
    if isinstance(value, (bool, str, bytes)) or not hasattr(value, "__float__"):
        raise ResearchInputError(f"{label} must be a finite number")
    if type(value).__name__ in {"bool_", "bool"}:  # numpy.bool_
        raise ResearchInputError(f"{label} must be a finite number")
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise ResearchInputError(f"{label} must be a finite number") from exc
    if not math.isfinite(number):
        raise ResearchInputError(f"{label} must be finite")
    return number


def simple_returns(values: Iterable[object], label: str = "returns") -> tuple[float, ...]:
    """Validate ordinary compounding simple returns: finite and strictly > -1.

    Missing values are never filled with zero; any non-finite entry rejects the
    whole series.
    """
    if isinstance(values, (str, bytes)):
        raise ResearchInputError(f"{label} must be a sequence of numbers")
    try:
        items = list(values)
    except TypeError as exc:
        raise ResearchInputError(f"{label} must be a sequence of numbers") from exc
    out: list[float] = []
    for index, item in enumerate(items):
        number = finite_float(item, f"{label}[{index}]")
        if number <= -1.0:
            raise ResearchInputError(f"{label}[{index}] must be greater than -1")
        out.append(number)
    return tuple(out)


def positive_int(value: object, label: str, *, minimum: int = 1) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ResearchInputError(f"{label} must be an integer")
    if value < minimum:
        raise ResearchInputError(f"{label} must be >= {minimum}")
    return value
