from __future__ import annotations

from scripts.open_downstream_qpk_pin_prs import (
    classify_pin_relation,
    collect_qpk_workflow_pins,
    paths_affect_runtime,
    should_open_upgrade_pr,
    update_drift_workflow_file,
)


def test_classify_pin_relation_equal_behind_ahead_diverged() -> None:
    def is_ancestor(ancestor: str, descendant: str) -> bool:
        order = {
            "aaa0000000000000000000000000000000000001": 1,
            "bbb0000000000000000000000000000000000002": 2,
            "ccc0000000000000000000000000000000000003": 3,
        }
        if ancestor == descendant:
            return True
        if ancestor not in order or descendant not in order:
            return False
        return order[ancestor] < order[descendant]

    a = "aaa0000000000000000000000000000000000001"
    b = "bbb0000000000000000000000000000000000002"
    c = "ccc0000000000000000000000000000000000003"
    side = "ddd0000000000000000000000000000000000004"

    assert classify_pin_relation(a, a, is_ancestor=is_ancestor) == "equal"
    assert classify_pin_relation(a, c, is_ancestor=is_ancestor) == "behind"
    assert classify_pin_relation(c, a, is_ancestor=is_ancestor) == "ahead"
    assert classify_pin_relation(b, side, is_ancestor=is_ancestor) == "diverged"


def test_should_open_upgrade_pr_blocks_equal_ahead_and_diverged() -> None:
    assert should_open_upgrade_pr("equal", mode="upgrade-affected") is False
    assert should_open_upgrade_pr("ahead", mode="upgrade-affected") is False
    assert should_open_upgrade_pr("diverged", mode="upgrade-affected") is False
    assert should_open_upgrade_pr("behind", mode="upgrade-affected") is True
    assert should_open_upgrade_pr("behind", mode="cohort-all") is True
    assert should_open_upgrade_pr("ahead", mode="cohort-all") is False


def test_paths_affect_runtime_ignores_docs_only_changes() -> None:
    assert paths_affect_runtime(["docs/adr/0003.md", "README.md"]) is False
    assert paths_affect_runtime(["docs/x.md", "src/quant_platform_kit/risk.py"]) is True
    assert paths_affect_runtime([".github/workflows/ci.yml"]) is False
    assert paths_affect_runtime(["scripts/open_downstream_qpk_pin_prs.py"]) is True


def test_update_drift_workflow_file_rewrites_qpk_pins(tmp_path) -> None:
    workflow = tmp_path / ".github" / "workflows"
    workflow.mkdir(parents=True)
    old = "aae333fe8b3fe5aeb32e1ff135ab14ea7db32420"
    new = "c812ed70f83d61bdf1816fa5ca112b0f6976c6b6"
    (workflow / "drift-check.yml").write_text(
        "repository: QuantStrategyLab/QuantPlatformKit\n"
        f"          ref: {old}\n"
        f"    uses: QuantStrategyLab/QuantPlatformKit/.github/workflows/reusable-drift-check.yml@{old}\n"
        f"      quant_platform_kit_ref: {old}\n",
        encoding="utf-8",
    )
    assert update_drift_workflow_file(
        tmp_path,
        qpk_sha=new,
        previous_qpk_refs={old},
    )
    body = (workflow / "drift-check.yml").read_text(encoding="utf-8")
    assert old not in body
    assert body.count(new) == 3


def test_collect_qpk_workflow_pins_ignores_checkout_and_snapshot_shas() -> None:
    old = "aae333fe8b3fe5aeb32e1ff135ab14ea7db32420"
    checkout = "11bd71901bbe5bc399482e927229509a74240172"
    snapshot = "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef"
    text = (
        f"    - uses: actions/checkout@{checkout}\n"
        "      with:\n"
        f"        snapshot_sha: {snapshot}\n"
        "repository: QuantStrategyLab/QuantPlatformKit\n"
        f"          ref: {old}\n"
        f"    uses: QuantStrategyLab/QuantPlatformKit/.github/workflows/reusable-drift-check.yml@{old}\n"
        f"      quant_platform_kit_ref: {old}\n"
    )
    assert collect_qpk_workflow_pins(text) == {old}


def test_update_drift_workflow_file_preserves_non_qpk_shas(tmp_path) -> None:
    workflow = tmp_path / ".github" / "workflows"
    workflow.mkdir(parents=True)
    old = "aae333fe8b3fe5aeb32e1ff135ab14ea7db32420"
    new = "c812ed70f83d61bdf1816fa5ca112b0f6976c6b6"
    checkout = "11bd71901bbe5bc399482e927229509a74240172"
    snapshot = "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef"
    (workflow / "drift-check.yml").write_text(
        f"    - uses: actions/checkout@{checkout}\n"
        "      with:\n"
        f"        snapshot_sha: {snapshot}\n"
        "repository: QuantStrategyLab/QuantPlatformKit\n"
        f"          ref: {old}\n"
        f"    uses: QuantStrategyLab/QuantPlatformKit/.github/workflows/reusable-drift-check.yml@{old}\n"
        f"      quant_platform_kit_ref: {old}\n",
        encoding="utf-8",
    )
    # Even a polluted previous set must not rewrite checkout/snapshot SHAs.
    assert update_drift_workflow_file(
        tmp_path,
        qpk_sha=new,
        previous_qpk_refs={old, checkout, snapshot},
    )
    body = (workflow / "drift-check.yml").read_text(encoding="utf-8")
    assert checkout in body
    assert snapshot in body
    assert old not in body
    assert body.count(new) == 3
