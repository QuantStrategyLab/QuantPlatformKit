"""Synthetic-only checks; no cloud, credentials, or market inputs are accessed."""

import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch


SPEC = importlib.util.spec_from_file_location(
    "fetch_hosted_inputs", Path(__file__).parents[1] / "scripts/fetch_hosted_inputs.py",
)
fetcher = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fetcher)


class CloudInputTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.payload = b"synthetic input, never real market data"
        self.env = {
            "HOSTED_INPUT_FETCH_ENABLED": "true", "GITHUB_ACTIONS": "true",
            "RUNNER_ENVIRONMENT": "github-hosted", "GITHUB_REF": "refs/heads/main",
            "HOSTED_INPUT_URI": "gs://example-inputs/approved/bundle.zip",
            "HOSTED_INPUT_GENERATION": "123", "HOSTED_INPUT_ASSET": "fixture.zip",
            "HOSTED_INPUT_SHA256": hashlib.sha256(self.payload).hexdigest(),
            "RUNNER_TEMP": self.temporary.name,
        }
        self.archive = Path(self.temporary.name) / "approved-input/fixture.zip"

    def fake_cloud(self, arguments, **overrides):
        if arguments[0] == "objects":
            return json.dumps({"size": len(self.payload), "generation": "123", **overrides})
        Path(arguments[2]).write_bytes(self.payload)
        return ""

    def test_disabled_does_nothing(self):
        for value in (None, "false", "TRUE", ""):
            with self.subTest(value=value), patch.object(fetcher, "_gcloud") as cloud:
                env = {} if value is None else {"HOSTED_INPUT_FETCH_ENABLED": value}
                self.assertFalse(fetcher.fetch(env))
                cloud.assert_not_called()

    def test_rejects_non_hosted_or_non_main_execution_before_cloud(self):
        for key, value in (("GITHUB_ACTIONS", "false"), ("RUNNER_ENVIRONMENT", "self-hosted"),
                           ("GITHUB_REF", "refs/pull/1/merge")):
            with self.subTest(key=key), patch.object(fetcher, "_gcloud") as cloud:
                with self.assertRaises(ValueError):
                    fetcher.fetch({**self.env, key: value})
                cloud.assert_not_called()

    def test_requires_exact_object_generation_digest_and_safe_destination(self):
        cases = [("HOSTED_INPUT_URI", "gs://example-inputs/approved/*"),
                 ("HOSTED_INPUT_URI", "https://example.invalid/input"),
                 ("HOSTED_INPUT_URI", "gs://example-inputs/input.zip?token=synthetic"),
                 ("HOSTED_INPUT_GENERATION", ""), ("HOSTED_INPUT_GENERATION", "0"),
                 ("HOSTED_INPUT_SHA256", ""), ("HOSTED_INPUT_ASSET", "../bad.zip"),
                 ("RUNNER_TEMP", "relative")]
        for key, value in cases:
            with self.subTest(key=key, value=value), patch.object(fetcher, "_gcloud") as cloud:
                with self.assertRaises(ValueError):
                    fetcher.fetch({**self.env, key: value})
                cloud.assert_not_called()

    def test_exact_generation_get_and_verified_archive(self):
        with patch.object(fetcher, "_gcloud", side_effect=self.fake_cloud) as cloud:
            self.assertTrue(fetcher.fetch(self.env))
        self.assertEqual(self.archive.read_bytes(), self.payload)
        self.assertEqual(cloud.call_count, 2)
        for call in cloud.call_args_list:
            self.assertEqual(call.args[0][2 if call.args[0][0] == "objects" else 1],
                             "gs://example-inputs/approved/bundle.zip#123")
            self.assertNotIn("ls", call.args[0])

    def test_rejects_metadata_before_download(self):
        for overrides in ({"generation": "124"}, {"size": 0},
                          {"size": fetcher.MAX_ARCHIVE_BYTES + 1}):
            with self.subTest(overrides=overrides), patch.object(
                fetcher, "_gcloud", side_effect=lambda args: self.fake_cloud(args, **overrides),
            ) as cloud:
                with self.assertRaises(ValueError):
                    fetcher.fetch(self.env)
                self.assertEqual(cloud.call_count, 1)
                self.assertFalse(self.archive.exists())

    def test_digest_or_size_mismatch_never_publishes_partial(self):
        for mismatch in ("digest", "size"):
            with self.subTest(mismatch=mismatch):
                def fake(arguments):
                    if arguments[0] == "objects":
                        return json.dumps({"size": len(self.payload) + (mismatch == "size"), "generation": "123"})
                    return self.fake_cloud(arguments)
                env = {**self.env, "HOSTED_INPUT_SHA256": "0" * 64} if mismatch == "digest" else self.env
                with patch.object(fetcher, "_gcloud", side_effect=fake):
                    with self.assertRaises(ValueError):
                        fetcher.fetch(env)
                self.assertFalse(self.archive.exists())
                self.assertEqual(list(self.archive.parent.iterdir()), [])

    def test_cloud_failure_has_no_fallback_or_private_error_text(self):
        result = subprocess.CompletedProcess([], 1, "", "private object and authentication details")
        with patch.object(fetcher.subprocess, "run", return_value=result) as run:
            with self.assertRaisesRegex(ValueError, r"^approved cloud input command failed \(exit 1\)$"):
                fetcher.fetch(self.env)
            self.assertEqual(run.call_count, 1)
        self.assertFalse(self.archive.exists())

    def test_existing_destination_is_not_overwritten(self):
        self.archive.parent.mkdir()
        self.archive.write_bytes(b"prior verified input")
        with patch.object(fetcher, "_gcloud", side_effect=self.fake_cloud) as cloud:
            with self.assertRaises(ValueError):
                fetcher.fetch(self.env)
            self.assertEqual(cloud.call_count, 1)
        self.assertEqual(self.archive.read_bytes(), b"prior verified input")


if __name__ == "__main__":
    unittest.main()
