"""Integration test suite for abby links refactor command.

Adheres strictly to Constitution Principle VI (Verifiable Technical Quality & Testing Discipline).
"""

from __future__ import annotations

import json
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
    from tests.support import CliRunner, IsolatedVaultTestCase
except ModuleNotFoundError:
    from support import CliRunner, IsolatedVaultTestCase


class TestLinksRefactor(IsolatedVaultTestCase):
    """Tier 3: Link refactoring engine, file renames, frontmatter updates, and dry-run safety."""

    def setUp(self) -> None:
        super().setUp()
        self.init_vault()

        # Seed target note
        self.create_note(
            domain="01 - Projects",
            filename="Roadmap 2025.md",
            title="Roadmap 2025",
            body="Our 2025 roadmap.",
        )
        # Referencing note 1 with alias
        self.create_note(
            domain="01 - Projects",
            filename="Kickoff.md",
            title="Kickoff",
            body="Review [[Roadmap 2025|Our Plan]] today.",
        )
        # Referencing note 2 with heading, markdown link, and code block
        self.create_note(
            domain="02 - Areas",
            filename="Strategy.md",
            title="Strategy",
            body=(
                "See [[Roadmap 2025#Q3]] in detail.\n"
                "Also check [Roadmap](../01%20-%20Projects/Roadmap%202025.md).\n\n"
                "```python\n"
                "# This code link must NOT be rewritten:\n"
                "ref = '[[Roadmap 2025]]'\n"
                "```\n"
            ),
        )

    def test_refactor_dry_run_text_and_json(self) -> None:
        code, out, err = CliRunner.invoke(
            ["links", "refactor", "Roadmap 2025", "Roadmap 2026", "--dry-run"]
        )
        self.assertEqual(code, 0)
        self.assertIn(
            '[DRY-RUN] Planned refactor: "Roadmap 2025" -> "Roadmap 2026"', out
        )
        self.assertIn(
            "01 - Projects/Roadmap 2025.md -> 01 - Projects/Roadmap 2026.md", out
        )
        self.assertIn("Total occurrences: 3 across 2 files", out)

        # Assert disk is NOT modified
        self.assertTrue((self.vault_root / "01 - Projects/Roadmap 2025.md").is_file())
        self.assertFalse((self.vault_root / "01 - Projects/Roadmap 2026.md").exists())
        kickoff_content = (self.vault_root / "01 - Projects/Kickoff.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("[[Roadmap 2025|Our Plan]]", kickoff_content)

        # JSON dry run
        code, out, err = CliRunner.invoke(
            ["--json", "links", "refactor", "Roadmap 2025", "Roadmap 2026", "--dry-run"]
        )
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertTrue(data["is_dry_run"])
        self.assertEqual(data["total_occurrences"], 3)
        self.assertEqual(data["file_renamed"], "01 - Projects/Roadmap 2026.md")

    def test_refactor_live_execution(self) -> None:
        code, out, err = CliRunner.invoke(
            ["links", "refactor", "Roadmap 2025", "Roadmap 2026"]
        )
        self.assertEqual(code, 0)
        self.assertIn('Refactored: "Roadmap 2025" -> "Roadmap 2026"', out)
        self.assertIn("Renamed file: 01 - Projects/Roadmap 2026.md", out)

        # Verify on-disk file rename
        self.assertFalse((self.vault_root / "01 - Projects/Roadmap 2025.md").exists())
        new_file = self.vault_root / "01 - Projects/Roadmap 2026.md"
        self.assertTrue(new_file.is_file())

        # Verify frontmatter update
        new_file_content = new_file.read_text(encoding="utf-8")
        self.assertIn('title: "Roadmap 2026"', new_file_content)
        self.assertIn("updated:", new_file_content)

        # Verify links rewritten in referencing notes
        kickoff_content = (self.vault_root / "01 - Projects/Kickoff.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("[[Roadmap 2026|Our Plan]]", kickoff_content)
        self.assertNotIn("Roadmap 2025", kickoff_content)

        strat_content = (self.vault_root / "02 - Areas/Strategy.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("[[Roadmap 2026#Q3]]", strat_content)
        self.assertIn(
            "[Roadmap](../01%20-%20Projects/Roadmap%202026.md)", strat_content
        )

        # Verify code block immunity: code fence link is NOT modified
        self.assertIn(
            "# This code link must NOT be rewritten:\nref = '[[Roadmap 2025]]'",
            strat_content,
        )

    def test_refactor_links_only(self) -> None:
        self.create_note(
            domain="01 - Projects",
            filename="Doc.md",
            title="Doc",
            body="Follow [[Guide]].",
        )
        self.create_note(
            domain="03 - Resources",
            filename="Guide.md",
            title="Guide",
            body="Guide body.",
        )

        code, out, err = CliRunner.invoke(
            ["links", "refactor", "Guide", "NewGuide", "--links-only"]
        )
        self.assertEqual(code, 0)
        self.assertIn("File rename: skipped (--links-only)", out)

        # File was NOT renamed
        self.assertTrue((self.vault_root / "03 - Resources/Guide.md").is_file())
        # Link WAS rewritten
        doc_content = (self.vault_root / "01 - Projects/Doc.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("[[NewGuide]]", doc_content)

    def test_refactor_ambiguous_target_rejection_and_force(self) -> None:
        self.create_note(
            domain="01 - Projects",
            filename="Overview.md",
            title="Overview",
            body="Project overview.",
        )
        self.create_note(
            domain="02 - Areas",
            filename="Overview.md",
            title="Overview",
            body="Area overview.",
        )

        # Ambiguous title rejection
        code, out, err = CliRunner.invoke(
            ["links", "refactor", "Overview", "RenamedOverview"]
        )
        self.assertEqual(code, 1)
        self.assertIn("ambiguous refactor target", err.lower())

        # Disambiguated with path qualification
        code, out, err = CliRunner.invoke(
            [
                "links",
                "refactor",
                "01 - Projects/Overview.md",
                "RenamedOverview",
                "--dry-run",
            ]
        )
        self.assertEqual(code, 0)

        # Disambiguated with --force
        code, out, err = CliRunner.invoke(
            ["links", "refactor", "Overview", "RenamedOverview", "--force", "--dry-run"]
        )
        self.assertEqual(code, 0)

    def test_refactor_argument_validation(self) -> None:
        # Missing new title
        code, out, err = CliRunner.invoke(["links", "refactor", "OldTitle"])
        self.assertEqual(code, 2)
        self.assertIn("usage", err.lower())

    def test_refactor_destination_collision_rejected(self) -> None:
        """Verify that refactoring into an existing filename is aborted without data corruption."""
        self.create_note(
            domain="01 - Projects",
            filename="FirstNote.md",
            title="FirstNote",
            body="Content of first note.",
        )
        self.create_note(
            domain="01 - Projects",
            filename="SecondNote.md",
            title="SecondNote",
            body="Content of second note.",
        )
        self.create_note(
            domain="01 - Projects",
            filename="ReferencingNote.md",
            title="ReferencingNote",
            body="Links to [[FirstNote]].",
        )

        # Attempt to rename FirstNote into SecondNote (which already exists in destination folder)
        code, out, err = CliRunner.invoke(
            ["links", "refactor", "01 - Projects/FirstNote.md", "SecondNote"]
        )
        self.assertEqual(code, 1)
        self.assertIn("already exists in destination folder", err)

        # Verify neither file was overwritten or destroyed
        first_path = self.vault_root / "01 - Projects" / "FirstNote.md"
        second_path = self.vault_root / "01 - Projects" / "SecondNote.md"
        ref_path = self.vault_root / "01 - Projects" / "ReferencingNote.md"

        self.assertTrue(first_path.is_file())
        self.assertTrue(second_path.is_file())
        self.assertIn("Content of first note.", first_path.read_text(encoding="utf-8"))
        self.assertIn(
            "Content of second note.", second_path.read_text(encoding="utf-8")
        )
        # Referencing note must remain unchanged
        self.assertIn("[[FirstNote]]", ref_path.read_text(encoding="utf-8"))

        # Verify in JSON mode
        code_json, out_json, _ = CliRunner.invoke(
            ["links", "refactor", "01 - Projects/FirstNote.md", "SecondNote", "--json"]
        )
        self.assertEqual(code_json, 1)
        data = json.loads(out_json)
        self.assertFalse(data["success"])
        self.assertIn("already exists", data["error"])

    def test_refactor_flag_invariance(self) -> None:
        # --dry-run after titles vs before titles
        code1, out1, _ = CliRunner.invoke(
            ["links", "refactor", "Roadmap 2025", "NewRoadmap", "--dry-run"]
        )
        code2, out2, _ = CliRunner.invoke(
            ["links", "refactor", "--dry-run", "Roadmap 2025", "NewRoadmap"]
        )
        self.assertEqual(code1, 0)
        self.assertEqual(code2, 0)
        self.assertEqual(out1, out2)


if __name__ == "__main__":
    unittest.main()

