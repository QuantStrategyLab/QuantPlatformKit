"""Fetch one pinned cloud object on an approved GitHub-hosted runner only."""

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile


MAX_ARCHIVE_BYTES = 512 * 1024**2


def _gcloud(arguments):
    try:
        result = subprocess.run(
            ["gcloud", "storage", *arguments, "--quiet"],
            capture_output=True, text=True, timeout=180, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise ValueError("approved cloud input command unavailable or timed out") from None
    if result.returncode:
        # CLI errors can contain private object names or authentication details.
        raise ValueError(f"approved cloud input command failed (exit {result.returncode})")
    return result.stdout


def fetch(environ=None):
    env = os.environ if environ is None else environ
    if env.get("HOSTED_INPUT_FETCH_ENABLED", "false") != "true":
        return False
    if (env.get("GITHUB_ACTIONS") != "true"
            or env.get("RUNNER_ENVIRONMENT") != "github-hosted"
            or env.get("GITHUB_REF") != "refs/heads/main"):
        raise ValueError("cloud inputs require an approved main-branch GitHub-hosted run")

    uri = env.get("HOSTED_INPUT_URI", "")
    generation = env.get("HOSTED_INPUT_GENERATION", "")
    expected_digest = env.get("HOSTED_INPUT_SHA256", "")
    asset = env.get("HOSTED_INPUT_ASSET", "")
    runner_temp = env.get("RUNNER_TEMP", "")
    if not re.fullmatch(r"gs://[a-z0-9][a-z0-9._-]{1,220}[a-z0-9]/[A-Za-z0-9_./-]+", uri):
        raise ValueError("HOSTED_INPUT_URI must name one exact GCS object without wildcards")
    if not re.fullmatch(r"[1-9][0-9]*", generation):
        raise ValueError("HOSTED_INPUT_GENERATION must pin a positive object generation")
    if not re.fullmatch(r"[0-9a-f]{64}", expected_digest):
        raise ValueError("HOSTED_INPUT_SHA256 must pin the approved archive digest")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+\.zip", asset):
        raise ValueError("HOSTED_INPUT_ASSET must be a ZIP basename")
    if not runner_temp or not Path(runner_temp).is_absolute():
        raise ValueError("RUNNER_TEMP must be an absolute hosted-runner directory")

    source = f"{uri}#{generation}"
    try:
        metadata = json.loads(_gcloud([
            "objects", "describe", source, "--format=json(size,generation)",
        ]))
        size = int(metadata["size"])
        actual_generation = str(metadata["generation"])
    except (KeyError, TypeError, json.JSONDecodeError):
        raise ValueError("approved cloud input metadata is invalid") from None
    if actual_generation != generation or not 0 < size <= MAX_ARCHIVE_BYTES:
        raise ValueError("approved cloud input generation or size rejected")

    destination = Path(runner_temp) / "approved-input"
    destination.mkdir(exist_ok=True)
    archive = destination / asset
    if destination.is_symlink() or archive.exists() or archive.is_symlink():
        raise ValueError("approved cloud input destination must be fresh")
    with tempfile.TemporaryDirectory(prefix="cloud-input-", dir=destination) as temporary:
        partial = Path(temporary) / "bundle.zip"
        _gcloud(["cp", source, str(partial)])
        if partial.stat().st_size != size:
            raise ValueError("approved cloud input size mismatch")
        digest = hashlib.sha256()
        with partial.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        if digest.hexdigest() != expected_digest:
            raise ValueError("approved cloud input digest mismatch")
        partial.rename(archive)
    return True


def main():
    try:
        enabled = fetch()
    except (OSError, ValueError) as error:
        # Do not expose exception strings from file/CLI/JSON operations.
        message = str(error) if isinstance(error, ValueError) else "approved cloud input file operation failed"
        if not message.startswith(("approved cloud input", "cloud inputs require", "HOSTED_INPUT_", "RUNNER_TEMP")):
            message = "approved cloud input validation failed"
        raise SystemExit(message) from None
    print("Approved cloud input verified" if enabled else "Cloud input fetch disabled")


if __name__ == "__main__":
    main()
