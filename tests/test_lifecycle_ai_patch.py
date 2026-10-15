import hashlib
import json

import pytest

from quant_platform_kit.strategy_lifecycle.ai_patch import PatchError, apply_patch, parse_patch


def change(path="candidate.py", old="old", new="new", source="old"):
    return {"path": path, "base_sha256": hashlib.sha256(source.encode()).hexdigest(),
            "edits": [{"old": old, "new": new}]}


def test_rejects_all_files_before_writing_anything(tmp_path):
    (tmp_path / "candidate.py").write_text("old")
    (tmp_path / "other.py").write_text("another")
    with pytest.raises(PatchError):
        apply_patch(tmp_path, [change(), change("other.py")], allowed_paths=frozenset({"candidate.py", "other.py"}))
    assert (tmp_path / "candidate.py").read_text() == "old"
    with pytest.raises(ValueError):
        apply_patch(tmp_path, [change()], allowed_paths=frozenset({"candidate.py"}),
                    validate_updated=lambda *args: (_ for _ in ()).throw(ValueError("domain violation")))
    assert (tmp_path / "candidate.py").read_text() == "old"


@pytest.mark.parametrize("path", ["../outside.py", "/outside.py", "a/../outside.py", ".git/config", "a//b", "a/./b", "a\\b"])
def test_rejects_path_escape_or_normalization(path):
    with pytest.raises(PatchError):
        parse_patch(json.dumps({"final_message": "", "changes": [change(path)]}))


def test_rejects_even_in_root_symlinks_and_nonallowlisted_paths(tmp_path):
    (tmp_path / "real.py").write_text("old")
    (tmp_path / "candidate.py").symlink_to(tmp_path / "real.py")
    with pytest.raises(PatchError):
        apply_patch(tmp_path, [change()], allowed_paths=frozenset({"candidate.py"}))
    with pytest.raises(PatchError):
        apply_patch(tmp_path, [change("real.py")], allowed_paths=frozenset())
    assert (tmp_path / "real.py").read_text() == "old"


def test_rejects_overlapping_edits_and_ambiguous_source(tmp_path):
    (tmp_path / "candidate.py").write_text("abcd")
    patch = change(old="abc", source="abcd")
    patch["edits"].append({"old": "bcd", "new": "replacement"})
    with pytest.raises(PatchError):
        apply_patch(tmp_path, [patch], allowed_paths=frozenset({"candidate.py"}))
    (tmp_path / "candidate.py").write_text("old old")
    with pytest.raises(PatchError):
        apply_patch(tmp_path, [change(source="old old")], allowed_paths=frozenset({"candidate.py"}))


def test_changes_only_the_approved_candidate_and_runs_domain_validation(tmp_path):
    (tmp_path / "candidate.py").write_text("old")
    seen = []
    assert apply_patch(tmp_path, [change()], allowed_paths=frozenset({"candidate.py"}),
                       validate_updated=lambda *args: seen.append(args)) == ["candidate.py"]
    assert seen == [("candidate.py", "old", "new")]
    assert (tmp_path / "candidate.py").read_text() == "new"


def test_rejects_full_content_duplicate_keys_and_output_budget():
    for payload in ['{"final_message":"","changes":[],"changes":[]}',
                    json.dumps({"final_message": "", "changes": [{"path": "candidate.py", "content": "new"}]}),
                    json.dumps({"final_message": "", "changes": [change(), change()]})]:
        with pytest.raises(PatchError):
            parse_patch(payload)
    with pytest.raises(PatchError):
        parse_patch(json.dumps({"final_message": "", "changes": [change(new="long")]}), max_replacement_bytes=3)
