"""Integration tests for abby move --description and note_move description injection."""

from __future__ import annotations

import json
import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent.parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

TESTS_DIR = Path(__file__).resolve().parent.parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

try:
    from tests.support import CliRunner, Tier2FilesystemTestCase
except ModuleNotFoundError:
    from support import CliRunner, Tier2FilesystemTestCase

from abby.core.lifecycle import move_note
from abby.mcp.tools import execute_tool
from abby.services.lint.rules import audit_note_content


class TestMoveDescriptionIntegration(Tier2FilesystemTestCase):
    """Integration tests for moving notes with --description into curated PARA domains."""

    def setUp(self) -> None:
        super().setUp()
        self.init_vault()

    def test_core_move_note_with_description(self) -> None:
        # Create an inbox note lacking a description
        self.create_note(
            domain="00 - Inbox",
            filename="Raw Telemetry.md",
            title="Raw Telemetry",
            body="Raw telemetry data from sensors.",
        )

        desc = "High-throughput telemetry ingestion pipeline using SQLite WAL mode."
        res = move_note(
            self.vault_root,
            "Raw Telemetry.md",
            "projects/Telemetry",
            description=desc,
        )
        self.assertTrue(res.success)
        self.assertEqual(res.description, desc)

        dest_file = (
            self.vault_root
            / "01 - Projects"
            / "Telemetry"
            / "Raw Telemetry.md"
        )
        self.assertTrue(dest_file.exists())
        content = dest_file.read_text(encoding="utf-8")
        self.assertIn(f'description: "{desc}"', content)

        # Assert no lint violations for missing description
        audit_res = audit_note_content(
            content,
            "01 - Projects/Telemetry/Raw Telemetry.md",
            domain="01 - Projects",
        )
        desc_violations = [
            v for v in audit_res.violations if v.field == "description"
        ]
        self.assertEqual(len(desc_violations), 0)

    def test_cli_move_with_description_flag(self) -> None:
        self.create_note(
            domain="00 - Inbox",
            filename="Draft Proposal.md",
            title="Draft Proposal",
            body="Proposal body.",
        )

        desc = "Executive strategy proposal for quarterly resource allocation."
        code, out, err = CliRunner.invoke(
            [
                "move",
                "Draft Proposal.md",
                "resources/Strategy",
                "--description",
                desc,
                "--json",
            ]
        )
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("description"), desc)

        dest_file = (
            self.vault_root
            / "03 - Resources"
            / "Strategy"
            / "Draft Proposal.md"
        )
        self.assertTrue(dest_file.exists())
        self.assertIn(desc, dest_file.read_text(encoding="utf-8"))

    def test_mcp_note_move_with_description(self) -> None:
        self.create_note(
            domain="00 - Inbox",
            filename="Sprint Notes.md",
            title="Sprint Notes",
            body="Sprint retrospective points.",
        )

        desc = "Summary of sprint velocity, blocker resolution, and retro action items."
        res = execute_tool(
            "note_move",
            {
                "note": "Sprint Notes.md",
                "target": "projects/Sprint",
                "description": desc,
            },
            self.vault_root,
        )
        self.assertFalse(res.isError)

        dest_file = (
            self.vault_root
            / "01 - Projects"
            / "Sprint"
            / "Sprint Notes.md"
        )
        self.assertTrue(dest_file.exists())
        self.assertIn(desc, dest_file.read_text(encoding="utf-8"))


if __name__ == "__main__":
    import unittest

    unittest.main()

