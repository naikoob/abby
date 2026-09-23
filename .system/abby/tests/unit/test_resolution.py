"""Unit tests for unified note resolution (abby.core.resolution)."""

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
    from tests.support import IsolatedVaultTestCase
except ModuleNotFoundError:
    from support import IsolatedVaultTestCase

from abby.core.resolution import (
    resolve_note_target,
    resolve_source_note,
    validate_note_boundary,
)
from abby.models.exceptions import NoteNotFoundError, PathBoundaryError


class TestResolution(IsolatedVaultTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.init_vault()

    def test_resolve_source_note_inbox_and_extension(self) -> None:
        self.create_note(
            domain="00 - Inbox",
            filename="Quick Thought.md",
            title="Quick Thought",
            body="Some content",
        )
        # By filename without extension
        p1 = resolve_source_note(self.vault_root, "Quick Thought")
        self.assertTrue(p1.is_file())
        self.assertEqual(p1.name, "Quick Thought.md")

        # By relative path
        p2 = resolve_source_note(self.vault_root, "00 - Inbox/Quick Thought.md")
        self.assertEqual(p1, p2)

    def test_resolve_source_note_empty_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            resolve_source_note(self.vault_root, "   ")

    def test_resolve_source_note_not_found(self) -> None:
        with self.assertRaises(NoteNotFoundError):
            resolve_source_note(self.vault_root, "Nonexistent Note")

    def test_resolve_source_note_boundary_error(self) -> None:
        # Create a file outside valid domains
        outside_file = self.vault_root / "outside.md"
        outside_file.write_text("# Outside", encoding="utf-8")

        with self.assertRaises(PathBoundaryError):
            resolve_source_note(self.vault_root, "outside.md")

    def test_resolve_note_target_sqlite(self) -> None:
        from abby.core.cache import get_cache_db_path, get_db_connection, sync_cache

        self.create_note(
            domain="01 - Projects",
            filename="Project Apollo.md",
            title="Project Apollo",
            body="Apollo space mission.",
        )
        sync_cache(self.vault_root)

        db_path = get_cache_db_path(self.vault_root)
        with get_db_connection(db_path) as conn:
            path, title, cands = resolve_note_target(conn, "Project Apollo")
            self.assertEqual(path, "01 - Projects/Project Apollo.md")
            self.assertEqual(title, "Project Apollo")
            self.assertEqual(cands, [])

            # Case-insensitive stem
            path_stem, _, _ = resolve_note_target(conn, "project apollo")
            self.assertEqual(path_stem, "01 - Projects/Project Apollo.md")


if __name__ == "__main__":
    unittest.main()
