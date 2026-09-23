"""Unit tests for atomic file I/O operations."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent.parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from abby.utils.io import atomic_write_stream, atomic_write_text


class TestAtomicWriteText(unittest.TestCase):
    """Verifies atomic file write replacement, error rollback, and UTF-8 encoding."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_dir = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_creates_new_file(self) -> None:
        file_path = self.test_dir / "test_new.md"
        content = "# New Note\n\nSome body text."
        atomic_write_text(file_path, content)

        self.assertTrue(file_path.exists())
        self.assertEqual(file_path.read_text(encoding="utf-8"), content)

    def test_replaces_existing_file_atomically(self) -> None:
        file_path = self.test_dir / "test_replace.md"
        initial_content = "# Old Note\n\nOld content."
        file_path.write_text(initial_content, encoding="utf-8")

        new_content = "# Updated Note\n\nUpdated content."
        atomic_write_text(file_path, new_content)

        self.assertEqual(file_path.read_text(encoding="utf-8"), new_content)

    def test_creates_missing_parent_directories(self) -> None:
        file_path = self.test_dir / "sub" / "nested" / "deep_note.md"
        content = "Deeply nested note."
        atomic_write_text(file_path, content)

        self.assertTrue(file_path.exists())
        self.assertEqual(file_path.read_text(encoding="utf-8"), content)

    def test_supports_utf8_cjk_characters(self) -> None:
        file_path = self.test_dir / "test_cjk.md"
        content = "# 知识库笔记\n\n这是一篇关于系统架构的中文笔记。"
        atomic_write_text(file_path, content)

        self.assertEqual(file_path.read_text(encoding="utf-8"), content)

    def test_cleans_up_temp_file_on_write_error(self) -> None:
        file_path = self.test_dir / "test_error.md"
        file_path.write_text("Original content", encoding="utf-8")

        # Mock NamedTemporaryFile write to fail
        class FailingWrite:
            def __init__(self, *args, **kwargs) -> None:
                self.name = str(self.test_dir / ".tmp_failing_file")
                self.fileno = lambda: 1
                Path(self.name).write_text("partial data", encoding="utf-8")

            def write(self, *args) -> None:
                raise OSError("Simulated disk full")

            def flush(self) -> None:
                pass

            def close(self) -> None:
                pass

        FailingWrite.test_dir = self.test_dir

        original_named_temp = tempfile.NamedTemporaryFile
        try:
            tempfile.NamedTemporaryFile = FailingWrite  # type: ignore
            with self.assertRaises(OSError):
                atomic_write_text(file_path, "New content")
        finally:
            tempfile.NamedTemporaryFile = original_named_temp

        # Verify original file untouched and temp file cleaned up
        self.assertEqual(file_path.read_text(encoding="utf-8"), "Original content")
        tmp_files = list(self.test_dir.glob(".tmp_*"))
        self.assertEqual(tmp_files, [], f"Leftover temp files found: {tmp_files}")


class TestAtomicWriteStream(unittest.TestCase):
    """Verifies atomic_write_stream context manager for streaming I/O."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_dir = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_stream_writes_and_replaces_atomically(self) -> None:
        file_path = self.test_dir / "stream_output.md"
        with atomic_write_stream(file_path) as stream:
            stream.write("Line 1\n")
            stream.write("Line 2\n")

        self.assertTrue(file_path.exists())
        self.assertEqual(file_path.read_text(encoding="utf-8"), "Line 1\nLine 2\n")

    def test_stream_cleans_up_on_exception(self) -> None:
        file_path = self.test_dir / "stream_abort.md"
        file_path.write_text("Pre-existing data", encoding="utf-8")

        with self.assertRaises(RuntimeError):
            with atomic_write_stream(file_path) as stream:
                stream.write("Partial data")
                raise RuntimeError("Aborted write mid-stream")

        # Destination file must remain untouched
        self.assertEqual(file_path.read_text(encoding="utf-8"), "Pre-existing data")
        tmp_files = list(self.test_dir.glob(".tmp_*"))
        self.assertEqual(tmp_files, [])


if __name__ == "__main__":
    unittest.main()


