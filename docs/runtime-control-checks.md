# Offline dry-run migration checks

`quant_platform_kit.common.runtime_control_checks.validate_dry_run_consistency`
is an opt-in, pure helper. No platform imports it and no runtime parser,
deployment workflow, dependency pin or trading admission path changes.

```python
from quant_platform_kit.common.runtime_control_checks import validate_dry_run_consistency

validate_dry_run_consistency(
    declared_dry_run_only=True,
    env={"EXAMPLE_DRY_RUN_ONLY": "true"},
    flag_name="EXAMPLE_DRY_RUN_ONLY",
)
```

Supply an already-parsed target boolean and an explicit environment mapping.
Missing flags default to dry-run. Explicit empty/malformed flags raise
`RuntimeControlError`. If both `FLAG` and `QSL_FLAG` are present, they must agree;
the helper does not hide conflicts using precedence. The resulting flag must
match the target and, when supplied, `RuntimeControl.mode`.

`RuntimeControl.mode=paper` permits broker paper execution and therefore matches
`dry_run_only=False`. The historical `RuntimeTarget.execution_mode=paper` is a
different alias for `dry_run_only=True`; it must not be treated as the new mode.
Disabled controls are still checked, so a latent disagreement remains visible.

The return value reports consistency and grants no execution permission. It
does not validate target/platform/profile identity, policy binding, capabilities,
reserves or order admission. Each platform adoption needs a separate reviewed
change with a trading-diff note and tests of that platform's real call path.
Existing legacy parser precedence is unchanged by adding this module.

Validation: `PYTHONPATH=src python3 -m pytest -q tests/test_runtime_control_checks.py tests/test_runtime_control.py`.

[中文](runtime-control-checks.zh-CN.md)
