from __future__ import annotations

from scripts.report_consumer_qpk_pin_prs import (
    ci_status,
    classify_generated_prs,
    hygiene_label_for_pr,
    render_row,
)
from scripts.open_downstream_qpk_pin_prs import RepoSpec


TARGET = "8378e939d9324ea63a0f45c9f21ba0e2eeb1cfff"


def _pr(*, branch: str, number: int = 1) -> dict[str, object]:
    return {
        "author": {"login": "Pigbibi"},
        "baseRefName": "main",
        "headRefName": branch,
        "isCrossRepository": False,
        "isDraft": False,
        "number": number,
        "title": "chore(deps): align QPK pin to 8378e939d932",
        "url": f"https://example.test/pr/{number}",
        "statusCheckRollup": [],
    }


def test_classify_generated_consumer_prs_keeps_current_and_reports_only_recognized_stale() -> None:
    current_branch = "auto/qpk-pin-sync-8378e939d932-longbridgeplatform"
    current, stale = classify_generated_prs(
        [
            _pr(branch=current_branch, number=10),
            _pr(branch="auto/qpk-pin-sync-37c81901160c-longbridgeplatform", number=9),
            _pr(branch="codex/manual-update", number=8),
        ],
        current_branch=current_branch,
    )

    assert [item["number"] for item in current] == [10]
    assert [item["number"] for item in stale] == [9]


def test_render_row_includes_links_without_mutation_instruction() -> None:
    row = render_row(
        RepoSpec("LongBridgePlatform"),
        [_pr(branch="auto/qpk-pin-sync-8378e939d932-longbridgeplatform", number=10)],
        [_pr(branch="auto/qpk-pin-sync-37c81901160c-longbridgeplatform", number=9)],
        candidate_sha=TARGET,
    )

    assert "LongBridgePlatform" in row
    assert "[#10](https://example.test/pr/10)" in row
    assert "[#9](https://example.test/pr/9)" in row
    assert "close-as-superseded-or-downgrade" in row
    assert "MISSING" in row


def test_hygiene_label_for_pr_marks_older_targets() -> None:
    assert (
        hygiene_label_for_pr(
            branch="auto/qpk-pin-sync-8378e939d932-longbridgeplatform",
            candidate_sha=TARGET,
        )
        == "current-target"
    )
    assert (
        hygiene_label_for_pr(
            branch="auto/qpk-pin-sync-37c81901160c-longbridgeplatform",
            candidate_sha=TARGET,
        )
        == "close-as-superseded-or-downgrade"
    )
    assert hygiene_label_for_pr(branch="codex/manual-update", candidate_sha=TARGET) == "unrecognized"


def test_ci_status_distinguishes_green_pending_failed_and_non_green() -> None:
    pr = _pr(branch="auto/qpk-pin-sync-8378e939d932-longbridgeplatform")

    assert ci_status(pr) == "MISSING"
    pr["statusCheckRollup"] = [{"status": "IN_PROGRESS", "conclusion": ""}]
    assert ci_status(pr) == "PENDING"
    pr["statusCheckRollup"] = [{"status": "COMPLETED", "conclusion": "SUCCESS"}]
    assert ci_status(pr) == "GREEN"
    pr["statusCheckRollup"] = [{"status": "COMPLETED", "conclusion": "FAILURE"}]
    assert ci_status(pr) == "FAILED"
    pr["statusCheckRollup"] = [{"status": "COMPLETED", "conclusion": "SKIPPED"}]
    assert ci_status(pr) == "NON_GREEN"
