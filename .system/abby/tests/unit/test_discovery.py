"""Unit tests for vault discovery (Tier 2)."""

from __future__ import annotations

import os
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
from abby.core.discovery import VaultNotFoundError, find_vault_root


class TestVaultDiscovery(Tier2FilesystemTestCase):
    def test_find_vault_root_from_root(self) -> None:
        (self.vault_root / ".system").mkdir()
        (self.vault_root / "00 - Inbox").mkdir()

        found = find_vault_root(start_path=self.vault_root)
        self.assertEqual(found, self.vault_root)

    def test_find_vault_root_from_nested_subdir(self) -> None:
        (self.vault_root / ".system").mkdir()
        (self.vault_root / "01 - Projects").mkdir()
        nested = self.vault_root / "01 - Projects" / "SubProject" / "Deep"
        nested.mkdir(parents=True)

        found = find_vault_root(start_path=nested)
        self.assertEqual(found, self.vault_root)

    def test_env_var_override(self) -> None:
        (self.vault_root / ".system").mkdir()
        os.environ["ABBY_VAULT_ROOT"] = str(self.vault_root)
        random_dir = Path("/tmp")
        found = find_vault_root(start_path=random_dir)
        self.assertEqual(found, self.vault_root)

    def test_invalid_env_var_override_raises_error(self) -> None:
        os.environ["ABBY_VAULT_ROOT"] = "/nonexistent/invalid/path/12345"
        with self.assertRaises(VaultNotFoundError):
            find_vault_root(start_path=self.vault_root)

    def test_uninitialized_vault_discovery(self) -> None:
        # Without .system, but at least two vault markers present
        (self.vault_root / ".specify").mkdir()
        (self.vault_root / "AGENTS.md").write_text("# Agents", encoding="utf-8")

        found = find_vault_root(start_path=self.vault_root)
        self.assertEqual(found, self.vault_root)

    def test_outside_vault_raises_error(self) -> None:
        empty_dir = self.vault_root / "empty"
        empty_dir.mkdir()
        # Remove environment variable to test true outside-vault traversal
        del os.environ["ABBY_VAULT_ROOT"]
        with self.assertRaises(VaultNotFoundError):
            find_vault_root(start_path=empty_dir)


if __name__ == "__main__":
    unittest.main()
