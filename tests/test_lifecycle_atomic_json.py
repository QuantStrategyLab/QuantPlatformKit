"""Synthetic local persistence failures must not destroy the committed file."""
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from quant_platform_kit.strategy_lifecycle import performance_store as module


class AtomicLocalJsonTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.store = module.PerformanceStore(local_root=self.root)
        self.key = "daily/us_equity/synthetic/2026-10-18.json"
        self.path = self.root / self.key
        self.store._write_local_json(self.key, {"committed": "old"})
        self.path.chmod(0o640)
        self.old = self.path.read_bytes()

    def assert_old_preserved(self):
        self.assertEqual(self.path.read_bytes(), self.old)
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o640)
        self.assertEqual(list(self.path.parent.iterdir()), [self.path])

    def test_partial_stream_write_preserves_committed_bytes(self):
        actual_open = io.open

        class Interrupted:
            def __init__(self, handle):
                self.handle = handle

            def __enter__(self):
                return self

            def __exit__(self, *args):
                self.handle.close()

            def write(self, value):
                self.handle.write(value[:5])
                self.handle.flush()
                raise OSError("synthetic full disk during stream write")

            def __getattr__(self, name):
                return getattr(self.handle, name)

        def interrupt(file, mode="r", *args, **kwargs):
            handle = actual_open(file, mode, *args, **kwargs)
            if any(flag in mode for flag in "wx"):
                return Interrupted(handle)
            return handle

        with patch.object(io, "open", side_effect=interrupt), self.assertRaises(OSError):
            self.store._write_local_json(self.key, {"committed": "new"})
        self.assert_old_preserved()

    def test_serialization_failure_preserves_committed_bytes(self):
        with self.assertRaises(TypeError):
            self.store._write_local_json(self.key, {"invalid": object()})
        self.assert_old_preserved()

    def test_exclusive_create_collision_never_deletes_unowned_file(self):
        value = module.uuid.UUID("00000000-0000-4000-8000-000000000001")
        other = self.path.with_name(f".{self.path.name}.{value.hex}.tmp")
        other.write_text("another owner's temporary file")
        with patch.object(module.uuid, "uuid4", return_value=value):
            with self.assertRaises(FileExistsError):
                self.store._write_local_json(self.key, {"committed": "new"})
        self.assertEqual(self.path.read_bytes(), self.old)
        self.assertEqual(other.read_text(), "another owner's temporary file")

    def test_fsync_failure_preserves_committed_bytes(self):
        with patch.object(module.os, "fsync", side_effect=OSError("synthetic fsync failure")):
            with self.assertRaises(OSError):
                self.store._write_local_json(self.key, {"committed": "new"})
        self.assert_old_preserved()

    def test_replace_failure_preserves_committed_bytes(self):
        with patch.object(module.os, "replace", side_effect=OSError("synthetic replace failure")):
            with self.assertRaises(OSError):
                self.store._write_local_json(self.key, {"committed": "new"})
        self.assert_old_preserved()

    def test_failed_writer_does_not_restore_over_another_commit(self):
        current = b'{"committed":"other-writer"}\n'

        def concurrent_replace(source, destination):
            Path(destination).write_bytes(current)
            raise OSError("synthetic replacement failure after another commit")

        with patch.object(module.os, "replace", side_effect=concurrent_replace):
            with self.assertRaises(OSError):
                self.store._write_local_json(self.key, {"committed": "new"})
        self.assertEqual(self.path.read_bytes(), current)
        self.assertEqual(list(self.path.parent.iterdir()), [self.path])

    def test_success_preserves_wire_mode_and_new_file_umask(self):
        self.store._write_local_json(self.key, {"committed": "new"})
        self.assertEqual(json.loads(self.path.read_text()), {"committed": "new"})
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o640)
        new_key = "dashboard/aggregated_health.json"
        reference = self.root / "reference.json"
        reference.write_text("{}")
        self.store._write_local_json(new_key, {"synthetic": True})
        self.assertEqual((self.root / new_key).stat().st_mode & 0o777,
                         reference.stat().st_mode & 0o777)
        self.assertEqual(list(self.path.parent.iterdir()), [self.path])
