"""Unit tests for vault initialization and directory scaffolding (Tier 2)."""

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
from abby.core.init import init_vault


class TestVaultInit(Tier2FilesystemTestCase):
    def test_init_scaffolds_all_directories(self) -> None:
        result = init_vault(self.vault_root)
        for d in REQUIRED_DIRECTORIES:
            self.assertIn(d, result["created"])
            self.assertTrue((self.vault_root / d).is_dir())
        self.assertEqual(
            len([d for d in result["existed"] if d in REQUIRED_DIRECTORIES]), 0
        )

    def test_init_is_idempotent_and_non_destructive(self) -> None:
        # Pre-create 00 - Inbox with a file
        inbox = self.vault_root / "00 - Inbox"
        inbox.mkdir(parents=True)
        test_file = inbox / "my-note.md"
        test_file.write_text("Hello World", encoding="utf-8")

        result = init_vault(self.vault_root)
        self.assertTrue(result["success"])
        self.assertIn("00 - Inbox", result["existed"])
        self.assertNotIn("00 - Inbox", result["created"])
        # File still exists untouched
        self.assertTrue(test_file.exists())
        self.assertEqual(test_file.read_text(encoding="utf-8"), "Hello World")

    def test_init_raises_on_existing_file_conflict(self) -> None:
        # If a required directory exists as a plain file, init must fail safely
        (self.vault_root / "00 - Inbox").write_text("file conflict", encoding="utf-8")
        with self.assertRaises(FileExistsError):
            init_vault(self.vault_root)


if __name__ == "__main__":
    unittest.main()
