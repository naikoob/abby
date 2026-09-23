"""Tier 2 Integration tests for link refactoring, file renaming, and link rewriting."""

import sys
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent.parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

try:
    from tests.support import Tier2FilesystemTestCase
except ModuleNotFoundError:
    from support import Tier2FilesystemTestCase

from abby.core.cache import get_cache_db_path, get_db_connection, sync_cache
from abby.core.graph import refactor_note, rewrite_note_links
from abby.models.exceptions import AmbiguousTargetError, DestinationCollisionError


class TestRefactorIntegration(Tier2FilesystemTestCase):
    """Integration test suite for note renaming and link graph refactoring."""

    def setUp(self) -> None:
        super().setUp()
        self.init_vault()
        self.db_path = get_cache_db_path(self.vault_root)

    def test_rewrite_note_links_unit(self) -> None:
        raw_text = (
            "Check out [[Old Title]] and [[Old Title#Section|Alias]].\n"
            "Also local [link](Old%20Title.md) and [sub](01%20-%20Projects/Old%20Title.md#heading).\n"
            "Inside code: `[[Old Title]]` and:\n"
            "```\n[[Old Title]]\n```\n"
        )
        new_text, occurrences = rewrite_note_links(raw_text, "Old Title", "New Title")
        self.assertEqual(len(occurrences), 4)
        self.assertIn("[[New Title]]", new_text)
        self.assertIn("[[New Title#Section|Alias]]", new_text)
        self.assertIn("`[[Old Title]]`", new_text)
        self.assertIn("```\n[[Old Title]]\n```", new_text)

    def test_refactor_note_live(self) -> None:
        # Create target note and referencing note
        target_path = self.create_note(
            domain="01 - Projects",
            filename="Alpha Project.md",
            title="Alpha Project",
            type_="project-note",
            status="active",
        )
        referrer_path = self.create_note(
            domain="01 - Projects",
            filename="Project Overview.md",
            title="Project Overview",
            body="Depends on [[Alpha Project]] heavily.",
            type_="project-note",
            status="active",
        )

        sync_cache(self.vault_root, db_path=self.db_path)
        conn = get_db_connection(self.db_path)
        try:
            result = refactor_note(
                self.vault_root,
                conn,
                "Alpha Project",
                "Omega Project",
                dry_run=False,
            )
        finally:
            conn.close()

        self.assertFalse(result.is_dry_run)
        self.assertEqual(len(result.files_modified), 1)

        # Target note should be renamed on disk
        new_file = self.vault_root / "01 - Projects" / "Omega Project.md"
        self.assertTrue(new_file.exists())
        self.assertFalse(target_path.exists())

        # Referencing note should be updated
        ref_content = referrer_path.read_text(encoding="utf-8")
        self.assertIn("[[Omega Project]]", ref_content)
        self.assertNotIn("[[Alpha Project]]", ref_content)

    def test_refactor_note_dry_run(self) -> None:
        target_path = self.create_note(
            domain="01 - Projects",
            filename="Beta.md",
            title="Beta",
            type_="project-note",
            status="active",
        )
        referrer_path = self.create_note(
            domain="01 - Projects",
            filename="Referrer.md",
            title="Referrer",
            body="Link to [[Beta]].",
            type_="project-note",
            status="active",
        )

        sync_cache(self.vault_root, db_path=self.db_path)
        conn = get_db_connection(self.db_path)
        try:
            result = refactor_note(
                self.vault_root,
                conn,
                "Beta",
                "Gamma",
                dry_run=True,
            )
        finally:
            conn.close()

        self.assertTrue(result.is_dry_run)
        # Verify no files were renamed or mutated
        self.assertTrue(target_path.exists())
        new_file = self.vault_root / "01 - Projects" / "Gamma.md"
        self.assertFalse(new_file.exists())
        self.assertIn("[[Beta]]", referrer_path.read_text(encoding="utf-8"))

    def test_refactor_destination_collision(self) -> None:
        self.create_note(
            domain="01 - Projects",
            filename="Source.md",
            title="Source",
        )
        self.create_note(
            domain="01 - Projects",
            filename="Existing.md",
            title="Existing",
        )

        sync_cache(self.vault_root, db_path=self.db_path)
        conn = get_db_connection(self.db_path)
        try:
            with self.assertRaises(DestinationCollisionError):
                refactor_note(
                    self.vault_root,
                    conn,
                    "Source",
                    "Existing",
                    dry_run=False,
                )
        finally:
            conn.close()

    def test_refactor_ambiguous_target(self) -> None:
        # Create identical titles in two domains
        self.create_note(domain="01 - Projects", filename="Meeting.md", title="Meeting")
        self.create_note(domain="02 - Areas", filename="Meeting.md", title="Meeting")

        sync_cache(self.vault_root, db_path=self.db_path)
        conn = get_db_connection(self.db_path)
        try:
            with self.assertRaises(AmbiguousTargetError):
                refactor_note(
                    self.vault_root,
                    conn,
                    "Meeting",
                    "New Meeting",
                    dry_run=False,
                    force=False,
                )
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
