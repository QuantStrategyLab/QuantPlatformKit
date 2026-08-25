from __future__ import annotations

from scripts.merge_verified_strategy_qpk_pin_prs import ALLOWED_CHANGED_FILES, candidate_reason, expected_branch
from scripts.open_downstream_qpk_pin_prs import RepoSpec


TARGET = "8378e939d9324ea63a0f45c9f21ba0e2eeb1cfff"


def _pr(*, checks: list[dict[str, str]] | None = None) -> dict[str, object]:
    return {
        "author": {"login": "Pigbibi"},
        "baseRefName": "main",
        "isCrossRepository": False,
        "isDraft": False,
        "title": f"chore(deps): align QPK pin to {TARGET[:12]}",
        "statusCheckRollup": checks
        if checks is not None
        else [{"status": "COMPLETED", "conclusion": "SUCCESS"}],
    }


def _pyproject(qpk_sha: str = TARGET) -> str:
    return (
        'quant-platform-kit @ '
        f'git+https://github.com/QuantStrategyLab/QuantPlatformKit.git@{qpk_sha}\n'
    )


def test_expected_branch_is_scoped_to_the_current_pin_and_strategy_repo() -> None:
    assert expected_branch(RepoSpec("UsEquityStrategies"), TARGET) == (
        "auto/qpk-pin-sync-8378e939d932-usequitystrategies"
    )


def test_generated_green_strategy_pin_pr_is_eligible() -> None:
    assert candidate_reason(
        pr=_pr(),
        changed_files=sorted(ALLOWED_CHANGED_FILES),
        pyproject_text=_pyproject(),
        qpk_sha=TARGET,
    ) is None


def test_strategy_pin_pr_fails_closed_for_unexpected_changes_or_ci() -> None:
    assert candidate_reason(
        pr=_pr(),
        changed_files=["pyproject.toml"],
        pyproject_text=_pyproject(),
        qpk_sha=TARGET,
    ) == "unexpected_changed_files"
    assert candidate_reason(
        pr=_pr(checks=[{"status": "IN_PROGRESS", "conclusion": ""}]),
        changed_files=sorted(ALLOWED_CHANGED_FILES),
        pyproject_text=_pyproject(),
        qpk_sha=TARGET,
    ) == "ci_not_green"
    assert candidate_reason(
        pr=_pr(),
        changed_files=sorted(ALLOWED_CHANGED_FILES),
        pyproject_text=_pyproject("37c81901160c5b31127a27dba1c63944933fb6bf"),
        qpk_sha=TARGET,
    ) == "qpk_pin_mismatch"
