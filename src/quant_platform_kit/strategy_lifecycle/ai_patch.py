"""Bounded candidate edits; the caller supplies exact paths and domain validation."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path, PurePosixPath


class PatchError(ValueError):
    pass


def parse_patch(text: str, *, max_changes: int = 20, max_edits: int = 20,
                max_replacement_bytes: int = 128 * 1024):
    if not isinstance(text, str):
        raise PatchError("patch must be JSON text")
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise PatchError("duplicate patch key")
            result[key] = value
        return result
    try:
        payload = json.loads(text, object_pairs_hook=pairs,
                             parse_constant=lambda _: (_ for _ in ()).throw(PatchError("nonfinite patch value")))
        if not isinstance(payload, dict) or set(payload) != {"final_message", "changes"}:
            raise PatchError("invalid patch fields")
        if not isinstance(payload["final_message"], str) or not isinstance(payload["changes"], list):
            raise PatchError("invalid patch values")
        if len(payload["changes"]) > max_changes:
            raise PatchError("too many changed files")
        replacement_bytes = 0
        paths = set()
        for change in payload["changes"]:
            if not isinstance(change, dict) or set(change) != {"path", "base_sha256", "edits"}:
                raise PatchError("targeted edits required")
            path = change["path"]
            if (not isinstance(path, str) or not path or "\\" in path
                    or PurePosixPath(path).is_absolute() or PurePosixPath(path).as_posix() != path
                    or any(p in {".", "..", ".git"} for p in PurePosixPath(path).parts)):
                raise PatchError("invalid patch path")
            if path in paths:
                raise PatchError("duplicate changed file")
            paths.add(path)
            if not isinstance(change["base_sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", change["base_sha256"]):
                raise PatchError("invalid base digest")
            edits = change["edits"]
            if not isinstance(edits, list) or not 1 <= len(edits) <= max_edits:
                raise PatchError("invalid edit count")
            for edit in edits:
                if (not isinstance(edit, dict) or set(edit) != {"old", "new"}
                        or not isinstance(edit["old"], str) or not edit["old"]
                        or not isinstance(edit["new"], str) or edit["old"] == edit["new"]):
                    raise PatchError("invalid targeted edit")
                edit["old"].encode("utf-8")
                replacement_bytes += len(edit["new"].encode("utf-8"))
            if replacement_bytes > max_replacement_bytes:
                raise PatchError("replacement limit exceeded")
        return payload["final_message"].strip(), payload["changes"]
    except (TypeError, UnicodeError, json.JSONDecodeError):
        raise PatchError("invalid patch JSON") from None


def apply_patch(root: Path, changes: list[dict], *, allowed_paths: frozenset[str], validate_updated=None):
    # Revalidate callers' direct dictionaries, including all files before any write.
    _, changes = parse_patch(json.dumps({"final_message": "", "changes": changes}, allow_nan=False))
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise PatchError("candidate root must be a directory")
    root = root.resolve()
    prepared = []
    for change in changes:
        path = change["path"]
        if path not in allowed_paths:
            raise PatchError("path outside caller allowlist")
        target = root / path
        for part in (target, *target.parents):
            if part == root:
                break
            if part.is_symlink():
                raise PatchError("symlink in candidate path")
        if not target.is_file():
            raise PatchError("candidate file is missing")
        original = target.read_bytes()
        if hashlib.sha256(original).hexdigest() != change["base_sha256"]:
            raise PatchError("candidate base digest mismatch")
        try:
            source = original.decode("utf-8")
        except UnicodeError:
            raise PatchError("candidate must be UTF-8") from None
        locations = []
        for edit in change["edits"]:
            first = source.find(edit["old"])
            if first < 0 or source.find(edit["old"], first + 1) >= 0:
                raise PatchError("edit source must occur exactly once")
            locations.append((first, first + len(edit["old"]), edit["new"]))
        locations.sort()
        if any(right[0] < left[1] for left, right in zip(locations, locations[1:])):
            raise PatchError("overlapping candidate edits")
        updated = source
        for start, end, replacement in reversed(locations):
            updated = updated[:start] + replacement + updated[end:]
        if validate_updated is not None:
            validate_updated(path, source, updated)
        prepared.append((target, updated.encode("utf-8")))
    for target, content in prepared:
        target.write_bytes(content)
    return [change["path"] for change in changes]
