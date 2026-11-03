"""Pure, opt-in migration checks. No platform runtime imports this module.

Callers supply an already-parsed target boolean and an explicit environment
mapping. A successful check describes consistency only, never execution
authorization. Existing runtime parsers and their precedence are unchanged.
"""

from __future__ import annotations

import re
from typing import Mapping

from .runtime_control import RuntimeControl, RuntimeControlError, RuntimeMode, parse_strict_bool


def validate_dry_run_consistency(
    *,
    declared_dry_run_only: bool,
    env: Mapping[str, str | None],
    flag_name: str,
    control: RuntimeControl | None = None,
) -> bool:
    """Return the consistent dry-run value, or raise on ambiguity.

    An absent flag defaults to dry-run. An explicitly empty/malformed flag is
    rejected. Both the unprefixed flag and its ``QSL_`` alias are checked when
    present; precedence must not hide a disagreement during migration.

    ``RuntimeControl.mode=paper`` represents broker-side paper execution, so
    it requires ``dry_run_only=False`` just like ``live``. This is distinct
    from the historical RuntimeTarget ``execution_mode=paper`` alias, which
    describes ``dry_run_only=True``; do not pass that alias as a control mode.

    No environment is read implicitly and no input is modified. Target,
    platform, profile, policy binding and execution admission remain separate
    caller responsibilities. This helper is not wired into trading paths.
    """
    if type(declared_dry_run_only) is not bool:
        raise RuntimeControlError("declared_dry_run_only must be a bool")
    if (
        not isinstance(flag_name, str)
        or re.fullmatch(r"[A-Z][A-Z0-9_]*", flag_name) is None
        or flag_name.startswith("QSL_")
    ):
        raise RuntimeControlError("flag_name must be an unprefixed uppercase environment name")
    values: list[bool] = []
    for name in (flag_name, f"QSL_{flag_name}"):
        if name in env:
            raw = env[name]
            # Do not include arbitrary environment values in diagnostics.
            if not isinstance(raw, (str, bool)):
                raise RuntimeControlError(f"{name} must contain a boolean")
            try:
                values.append(parse_strict_bool(raw, name=name))
            except RuntimeControlError:
                raise RuntimeControlError(f"{name} must contain a non-empty boolean") from None
    if len(set(values)) > 1:
        raise RuntimeControlError(f"{flag_name} and QSL_{flag_name} aliases disagree")
    effective = values[0] if values else True
    if effective != declared_dry_run_only:
        raise RuntimeControlError(f"{flag_name} disagrees with the target dry_run_only")
    if control is not None and (control.mode is RuntimeMode.DRY_RUN) != effective:
        raise RuntimeControlError("RuntimeControl.mode disagrees with dry_run_only")
    return effective


__all__ = ["validate_dry_run_consistency"]
