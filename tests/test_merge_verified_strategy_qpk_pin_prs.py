from __future__ import annotations

from scripts.merge_verified_strategy_qpk_pin_prs import (
    ALLOWED_CHANGED_FILES,
    candidate_reason,
    expected_branch,
    process_repo,
    superseded_pr_reason,
    wait_for_current_candidate,
)
from scripts.open_downstream_qpk_pin_prs import RepoSpec


TARGET = "8378e939d9324ea63a0f45c9f21ba0e2eeb1cfff"


def _pr(*, checks: list[dict[str, str]] | None = None) -> dict[str, object]:
    return {
        "author": {"login": "Pigbibi"},
        "baseRefName": "main",
        "isCrossRepository": False,
        "isDraft": False,
        "headRefName": "auto/qpk-pin-sync-8378e939d932-usequitystrategies",
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


def test_wait_for_current_candidate_rechecks_only_pending_ci(monkeypatch) -> None:
    repo = RepoSpec("UsEquityStrategies")
    pending = _pr(checks=[{"status": "IN_PROGRESS", "conclusion": ""}])
    pending["number"] = 400
    pending["headRefOid"] = "a" * 40
    green = _pr()
    green["number"] = 400
    green["headRefOid"] = "a" * 40
    candidates = iter([pending, green])
    monkeypatch.setattr(
        "scripts.merge_verified_strategy_qpk_pin_prs.open_pr_payload",
        lambda *_args, **_kwargs: next(candidates),
    )
    monkeypatch.setattr(
        "scripts.merge_verified_strategy_qpk_pin_prs.changed_files",
        lambda *_args, **_kwargs: sorted(ALLOWED_CHANGED_FILES),
    )
    monkeypatch.setattr(
        "scripts.merge_verified_strategy_qpk_pin_prs.pyproject_text",
        lambda *_args, **_kwargs: _pyproject(),
    )
    sleeps: list[float] = []
    ticks = iter([0.0, 1.0])

    pr, reason = wait_for_current_candidate(
        repo,
        branch=expected_branch(repo, TARGET),
        qpk_sha=TARGET,
        env={"GH_TOKEN": "test"},
        wait_for_ci_seconds=10,
        poll_interval_seconds=5,
        monotonic=lambda: next(ticks),
        sleep=sleeps.append,
    )

    assert pr == green
    assert reason is None
    assert sleeps == [5]


def test_only_a_recognized_older_generated_pr_can_be_closed() -> None:
    current_branch = "auto/qpk-pin-sync-8378e939d932-usequitystrategies"
    older = _pr()
    older["headRefName"] = "auto/qpk-pin-sync-37c81901160c-usequitystrategies"
    assert superseded_pr_reason(pr=older, current_branch=current_branch) is None

    assert superseded_pr_reason(pr=_pr(), current_branch=current_branch) == "current_branch"
    manual = _pr()
    manual["headRefName"] = "codex/manual-dependency-change"
    assert superseded_pr_reason(pr=manual, current_branch=current_branch) == "unexpected_branch"


def test_cleanup_runs_after_current_pin_has_already_merged(monkeypatch, capsys) -> None:
    repo = RepoSpec("UsEquityStrategies")
    monkeypatch.setattr(
        "scripts.merge_verified_strategy_qpk_pin_prs.open_pr_payload",
        lambda *_args, **_kwargs: None,
    )
    observed: dict[str, object] = {}

    def close(repo_arg, *, current_branch, qpk_sha, env):
        observed.update(
            repo=repo_arg,
            current_branch=current_branch,
            qpk_sha=qpk_sha,
            env=env,
        )
        return ["123"]

    monkeypatch.setattr(
        "scripts.merge_verified_strategy_qpk_pin_prs.close_superseded_candidates",
        close,
    )

    process_repo(
        repo,
        qpk_sha=TARGET,
        close_superseded=True,
        env={"GH_TOKEN": "test"},
    )

    assert observed["repo"] == repo
    assert observed["current_branch"] == expected_branch(repo, TARGET)
    assert observed["qpk_sha"] == TARGET
    assert capsys.readouterr().out.splitlines() == [
        "UsEquityStrategies: no current generated PR",
        "UsEquityStrategies: closed_superseded:123",
    ]
