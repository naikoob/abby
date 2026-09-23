"""Integration tests for gap MCP tools: note_read and note_refactor."""

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
    from tests.support import Tier2FilesystemTestCase
except ModuleNotFoundError:
    from support import Tier2FilesystemTestCase

from abby.mcp.tools import execute_tool, get_tool_definitions, get_tool_names


class TestMCPGapToolsIntegration(Tier2FilesystemTestCase):
    """Integration tests for note_read and note_refactor tools executed via registry."""

    def setUp(self) -> None:
        super().setUp()
        self.init_vault()

    def test_gap_tools_registered(self) -> None:
        names = get_tool_names()
        self.assertIn("note_read", names)
        self.assertIn("note_refactor", names)

        tools = {t["name"]: t for t in get_tool_definitions()}
        self.assertIn("note_read", tools)
        self.assertIn("note", tools["note_read"]["inputSchema"]["properties"])

        self.assertIn("note_refactor", tools)
        self.assertIn("source", tools["note_refactor"]["inputSchema"]["properties"])
        self.assertIn("target", tools["note_refactor"]["inputSchema"]["properties"])
        self.assertIn("links_only", tools["note_refactor"]["inputSchema"]["properties"])
        self.assertIn("dry_run", tools["note_refactor"]["inputSchema"]["properties"])

    def test_note_read_integration(self) -> None:
        self.create_note(
            domain="01 - Projects",
            filename="Apollo Kickoff.md",
            title="Apollo Kickoff",
            description="Mission planning for Project Apollo.",
            status="active",
            type_="project-note",
            tags=["apollo", "space"],
            body="## Mission Goals\n\n1. Establish lunar base\n2. Gather telemetry",
        )

        res = execute_tool(
            "note_read",
            {"note": "Apollo Kickoff"},
            self.vault_root,
        )
        self.assertFalse(res.isError)
        data = json.loads(res.content[0].text)
        self.assertEqual(data["path"], "01 - Projects/Apollo Kickoff.md")
        self.assertEqual(data["title"], "Apollo Kickoff")
        self.assertEqual(data["frontmatter"]["status"], "active")
        self.assertEqual(data["frontmatter"]["type"], "project-note")
        self.assertIn("apollo", data["frontmatter"]["tags"])
        self.assertIn("## Mission Goals", data["body"])

    def test_note_refactor_dry_run(self) -> None:
        old_note = self.create_note(
            domain="01 - Projects",
            filename="Old Plan.md",
            title="Old Plan",
            body="Old plan contents.",
        )
        referrer = self.create_note(
            domain="02 - Areas",
            filename="Roadmap.md",
            title="Roadmap",
            body="Referencing [[Old Plan]] and [[Old Plan#Section|Alias]].",
        )

        res = execute_tool(
            "note_refactor",
            {
                "source": "Old Plan",
                "target": "New Plan",
                "dry_run": True,
            },
            self.vault_root,
        )
        self.assertFalse(res.isError)
        self.assertIn("[DRY-RUN]", res.content[0].text)
        self.assertIn("Refactor Complete", res.content[0].text)

        # Confirm nothing changed on disk
        self.assertTrue(old_note.exists())
        self.assertFalse((self.vault_root / "01 - Projects" / "New Plan.md").exists())
        self.assertIn("[[Old Plan]]", referrer.read_text(encoding="utf-8"))

    def test_note_refactor_execution(self) -> None:
        old_note = self.create_note(
            domain="01 - Projects",
            filename="Alpha Spec.md",
            title="Alpha Spec",
            body="Alpha specification body.",
        )
        ref1 = self.create_note(
            domain="02 - Areas",
            filename="Overview.md",
            title="Overview",
            body="See [[Alpha Spec]] and [[Alpha Spec#Architecture]].",
        )
        ref2 = self.create_note(
            domain="03 - Resources",
            filename="Docs.md",
            title="Docs",
            body="Link: [Alpha Spec](01%20-%20Projects/Alpha%20Spec.md).\nCode immunity: `[[Alpha Spec]]`.",
        )

        res = execute_tool(
            "note_refactor",
            {
                "source": "Alpha Spec",
                "target": "Beta Spec",
                "dry_run": False,
            },
            self.vault_root,
        )
        self.assertFalse(res.isError)
        self.assertIn("Refactor Complete", res.content[0].text)
        self.assertIn("Beta Spec.md", res.content[0].text)

        # Confirm old file renamed and new file exists
        new_path = self.vault_root / "01 - Projects" / "Beta Spec.md"
        self.assertFalse(old_note.exists())
        self.assertTrue(new_path.exists())

        # Check frontmatter in renamed file
        renamed_content = new_path.read_text(encoding="utf-8")
        self.assertIn('title: "Beta Spec"', renamed_content)

        # Check referencing files rewritten
        ref1_content = ref1.read_text(encoding="utf-8")
        self.assertIn("[[Beta Spec]]", ref1_content)
        self.assertIn("[[Beta Spec#Architecture]]", ref1_content)
        self.assertNotIn("[[Alpha Spec]]", ref1_content)

        # Check code fence immunity
        ref2_content = ref2.read_text(encoding="utf-8")
        self.assertIn("`[[Alpha Spec]]`", ref2_content)

    def test_note_refactor_links_only(self) -> None:
        source_note = self.create_note(
            domain="01 - Projects",
            filename="Target Project.md",
            title="Target Project",
            body="Target body.",
        )
        referrer = self.create_note(
            domain="02 - Areas",
            filename="Dashboard.md",
            title="Dashboard",
            body="Check [[Target Project]].",
        )

        res = execute_tool(
            "note_refactor",
            {
                "source": "Target Project",
                "target": "Updated Target",
                "links_only": True,
            },
            self.vault_root,
        )
        self.assertFalse(res.isError)

        # Source note file must NOT be renamed
        self.assertTrue(source_note.exists())
        self.assertFalse(
            (self.vault_root / "01 - Projects" / "Updated Target.md").exists()
        )

        # Links should still be rewritten
        self.assertIn(
            "[[Updated Target]]", referrer.read_text(encoding="utf-8")
        )

    def test_vault_links_depth_multihop(self) -> None:
        self.create_note(
            domain="01 - Projects",
            filename="First.md",
            title="First",
            body="Go to [[Second]].",
        )
        self.create_note(
            domain="01 - Projects",
            filename="Second.md",
            title="Second",
            body="Go to [[Third]].",
        )
        self.create_note(
            domain="03 - Resources",
            filename="Third.md",
            title="Third",
            body="End.",
        )
        # 1. MCP vault_links with depth=2
        res = execute_tool(
            "vault_links",
            {"note": "First", "mode": "outbound", "depth": 2},
            self.vault_root,
        )
        self.assertFalse(res.isError)
        self.assertIn("## Depth 1 (Direct)", res.content[0].text)
        self.assertIn("01 - Projects/Second.md", res.content[0].text)
        self.assertIn("## Depth 2 (Transitive)", res.content[0].text)
        self.assertIn("03 - Resources/Third.md", res.content[0].text)

        # 2. CLI abby links with --depth 2
        from tests.support import CliRunner
        code, out, err = CliRunner.invoke(["links", "First", "--depth", "2"])
        self.assertEqual(code, 0)
        self.assertIn("## Depth 1 (Direct)", out)
        self.assertIn("01 - Projects/Second.md", out)
        self.assertIn("## Depth 2 (Transitive)", out)
        self.assertIn("03 - Resources/Third.md", out)

        # 3. CLI abby links with --json and --depth 2
        code, out, err = CliRunner.invoke(["--json", "links", "First", "--depth", "2"])
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertEqual(len(data["links"]), 2)
        self.assertEqual(data["links"][0]["depth"], 1)
        self.assertEqual(data["links"][1]["depth"], 2)


if __name__ == "__main__":
    import unittest

    unittest.main()
