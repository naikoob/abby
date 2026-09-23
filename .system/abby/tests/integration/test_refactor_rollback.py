"""Integration tests for multi-file refactoring rollback and transaction safety."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

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

from abby.core.cache import get_cache_db_path, get_db_connection, sync_cache
from abby.core.graph.refactor import refactor_note
from abby.models.exceptions import RefactorError


class TestRefactorRollback(IsolatedVaultTestCase):
    """Verifies that refactor_note rolls back all file mutations if any phase fails."""

    def setUp(self) -> None:
        super().setUp()
        self.init_vault()

        # Create target note
        self.target_note = self.create_note(
            domain="03 - Resources",
            filename="Neural Networks.md",
            title="Neural Networks",
            body="Fundamental concepts of neural networks.",
        )

        # Create referencing notes across different domains
        self.project_note = self.create_note(
            domain="01 - Projects",
            filename="Vision Model.md",
            title="Vision Model",
            body="Depends on [[Neural Networks]] and [[Convolution]].",
        )

        self.area_note = self.create_note(
            domain="02 - Areas",
            filename="Machine Learning.md",
            title="Machine Learning",
            body="Review [[Neural Networks|Deep NN]] architecture.",
        )

        # Sync cache to populate link records
        self.db_path = get_cache_db_path(self.vault_root)
        sync_cache(self.vault_root, self.db_path)
        self.conn = get_db_connection(self.db_path)

    def tearDown(self) -> None:
        self.conn.close()
        super().tearDown()

    def test_successful_multi_file_refactor(self) -> None:
        """Verifies full refactoring renames note, updates frontmatter, and rewrites links."""
        res = refactor_note(
            self.vault_root,
            self.conn,
            "Neural Networks",
            "Deep Learning Systems",
            dry_run=False,
            cache_syncer=sync_cache,
        )

        self.assertEqual(res.total_occurrences, 2)
        new_target = self.vault_root / "03 - Resources" / "Deep Learning Systems.md"
        self.assertTrue(new_target.exists())
        self.assertFalse(self.target_note.exists())

        # Verify frontmatter updated
        content = new_target.read_text(encoding="utf-8")
        self.assertIn('title: "Deep Learning Systems"', content)

        # Verify links rewritten in referencing notes
        proj_content = self.project_note.read_text(encoding="utf-8")
        self.assertIn("[[Deep Learning Systems]]", proj_content)

        area_content = self.area_note.read_text(encoding="utf-8")
        self.assertIn("[[Deep Learning Systems|Deep NN]]", area_content)

    def test_rollback_when_note_rename_fails(self) -> None:
        """If target note rename fails, referencing note link rewrites must be restored."""
        orig_proj_content = self.project_note.read_text(encoding="utf-8")
        orig_area_content = self.area_note.read_text(encoding="utf-8")

        # Mock Path.rename on target file to simulate permission or disk failure
        def failing_rename(target: Path, *args, **kwargs) -> Path:
            raise OSError("Simulated permission denied on file rename")

        with patch.object(Path, "rename", side_effect=failing_rename):
            with self.assertRaises(RefactorError) as ctx:
                refactor_note(
                    self.vault_root,
                    self.conn,
                    "Neural Networks",
                    "Deep Learning Systems",
                    dry_run=False,
                )

        self.assertIn("Simulated permission denied", str(ctx.exception))
        self.assertIn("All changes rolled back", str(ctx.exception))

        # Target note must remain under original name
        self.assertTrue(self.target_note.exists())
        new_target = self.vault_root / "03 - Resources" / "Deep Learning Systems.md"
        self.assertFalse(new_target.exists())

        # Referencing notes must be restored to original content with original links
        self.assertEqual(
            self.project_note.read_text(encoding="utf-8"), orig_proj_content
        )
        self.assertEqual(
            self.area_note.read_text(encoding="utf-8"), orig_area_content
        )

    def test_rollback_when_frontmatter_mutation_fails(self) -> None:
        """If frontmatter mutation on renamed note fails, rename and links must be restored."""
        orig_proj_content = self.project_note.read_text(encoding="utf-8")
        orig_area_content = self.area_note.read_text(encoding="utf-8")
        orig_target_content = self.target_note.read_text(encoding="utf-8")

        with patch(
            "abby.core.graph.refactor.mutate_okf_frontmatter",
            side_effect=RuntimeError("Simulated frontmatter corruption error"),
        ):
            with self.assertRaises(RefactorError) as ctx:
                refactor_note(
                    self.vault_root,
                    self.conn,
                    "Neural Networks",
                    "Deep Learning Systems",
                    dry_run=False,
                )

        self.assertIn("Simulated frontmatter corruption", str(ctx.exception))
        self.assertIn("All changes rolled back", str(ctx.exception))

        # Target note must be renamed back to original name with original content
        self.assertTrue(self.target_note.exists())
        self.assertEqual(
            self.target_note.read_text(encoding="utf-8"), orig_target_content
        )
        new_target = self.vault_root / "03 - Resources" / "Deep Learning Systems.md"
        self.assertFalse(new_target.exists())

        # Referencing notes must be restored
        self.assertEqual(
            self.project_note.read_text(encoding="utf-8"), orig_proj_content
        )
        self.assertEqual(
            self.area_note.read_text(encoding="utf-8"), orig_area_content
        )


if __name__ == "__main__":
    unittest.main()
