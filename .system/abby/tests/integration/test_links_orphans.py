"""Tier 3: Orphan and unreferenced leaf note detection across vault domains."""

from __future__ import annotations

import json
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
    from tests.support import CliRunner, IsolatedVaultTestCase
except ModuleNotFoundError:
    from support import CliRunner, IsolatedVaultTestCase


class TestUserStory3Orphans(IsolatedVaultTestCase):
    """Tier 3: Orphan and unreferenced leaf note detection across vault domains."""

    def setUp(self) -> None:
        super().setUp()
        self.init_vault()

    def test_orphans_detection_and_inbox_exclusion(self) -> None:
        # NoteA links to NoteB
        self.create_note(
            domain="01 - Projects",
            filename="NoteA.md",
            title="Note A",
            body="References [[Note B]].",
        )
        self.create_note(
            domain="01 - Projects",
            filename="NoteB.md",
            title="Note B",
            body="Destination note.",
        )
        # Leaf note with outgoing link but 0 incoming
        self.create_note(
            domain="03 - Resources",
            filename="Leaf.md",
            title="Leaf",
            body="References [[Note B]].",
        )
        # Isolated note (0 incoming, 0 outgoing)
        self.create_note(
            domain="02 - Areas",
            filename="Island.md",
            title="Island",
            body="Completely isolated note.",
        )
        # Inbox note (0 incoming, 0 outgoing)
        self.create_note(
            domain="00 - Inbox",
            filename="QuickCapture.md",
            title="Quick Capture",
            body="Inbox raw thought.",
        )

        # Default query: excludes 00 - Inbox
        code, out, err = CliRunner.invoke(["links", "--orphans"])
        self.assertEqual(code, 0)
        self.assertIn("02 - Areas/Island.md", out)
        self.assertNotIn("00 - Inbox/QuickCapture.md", out)
        self.assertNotIn("Leaf.md", out)
        self.assertNotIn("NoteA.md", out)
        self.assertNotIn("NoteB.md", out)

        # JSON mode without inbox
        code, out, err = CliRunner.invoke(["--json", "links", "--orphans"])
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertEqual(data["total_orphans"], 1)
        self.assertEqual(data["orphans"], ["02 - Areas/Island.md"])

        # Query with --include-inbox
        code, out, err = CliRunner.invoke(["links", "--orphans", "--include-inbox"])
        self.assertEqual(code, 0)
        self.assertIn("02 - Areas/Island.md", out)
        self.assertIn("00 - Inbox/QuickCapture.md", out)

    def test_unreferenced_leaf_notes_detection(self) -> None:
        self.create_note(
            domain="01 - Projects",
            filename="Parent.md",
            title="Parent",
            body="Links to [[Child]].",
        )
        self.create_note(
            domain="01 - Projects",
            filename="Child.md",
            title="Child",
            body="I am referenced.",
        )
        self.create_note(
            domain="02 - Areas",
            filename="Standalone.md",
            title="Standalone",
            body="No incoming or outgoing.",
        )

        code, out, err = CliRunner.invoke(["links", "--unreferenced"])
        self.assertEqual(code, 0)
        self.assertIn("01 - Projects/Parent.md", out)
        self.assertIn("02 - Areas/Standalone.md", out)
        self.assertNotIn("01 - Projects/Child.md", out)

        code, out, err = CliRunner.invoke(["--json", "links", "--unreferenced"])
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertEqual(data["total_unreferenced"], 2)

    def test_orphans_domain_filtering(self) -> None:
        self.create_note(
            domain="01 - Projects",
            filename="ProjOrphan.md",
            title="Proj Orphan",
            body="Isolated project note.",
        )
        self.create_note(
            domain="02 - Areas",
            filename="AreaOrphan.md",
            title="Area Orphan",
            body="Isolated area note.",
        )

        code, out, err = CliRunner.invoke(
            ["links", "--orphans", "--domain", "projects"]
        )
        self.assertEqual(code, 0)
        self.assertIn("01 - Projects/ProjOrphan.md", out)
        self.assertNotIn("02 - Areas/AreaOrphan.md", out)


if __name__ == "__main__":
    unittest.main()

