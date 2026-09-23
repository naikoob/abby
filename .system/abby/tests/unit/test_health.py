"""Unit tests for vault health inspection (Tier 2)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent.parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
TESTS_DIR = Path(__file__).resolve().parent.parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

try:
    from tests.support import Tier2FilesystemTestCase
except ModuleNotFoundError:
    from support import Tier2FilesystemTestCase
from abby.constants import REQUIRED_DIRECTORIES
from abby.core.health import inspect_vault


class TestVaultHealth(Tier2FilesystemTestCase):
    def test_inspect_vault_missing_directories(self) -> None:
        # Empty folder
        report = inspect_vault(self.vault_root)
        self.assertFalse(report.healthy)
        self.assertIn("00 - Inbox", report.missing_directories)
        self.assertIn("01 - Projects", report.missing_directories)
        self.assertIn(".system", report.missing_directories)

    def test_inspect_vault_fully_healthy(self) -> None:
        self.init_vault()
        # Put an item in 00 - Inbox
        self.create_note(title="test", filename="test.md", content="content")

        report = inspect_vault(self.vault_root)
        self.assertTrue(report.healthy)
        self.assertEqual(len(report.missing_directories), 0)
        self.assertEqual(report.directories["00 - Inbox"].item_count, 1)
        self.assertEqual(report.directories["01 - Projects"].item_count, 0)

    def test_inspect_vault_non_directory_file_collision(self) -> None:
        # Create 00 - Inbox as a file instead of a directory
        (self.vault_root / "00 - Inbox").write_text(
            "I am a file, not a directory", encoding="utf-8"
        )
        report = inspect_vault(self.vault_root)
        self.assertFalse(report.healthy)
        self.assertIn("00 - Inbox", report.missing_directories)
        self.assertTrue(report.directories["00 - Inbox"].exists)
        self.assertFalse(report.directories["00 - Inbox"].is_dir)


if __name__ == "__main__":
    unittest.main()
