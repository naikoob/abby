"""Tier 2 integration tests for Abby MCP link inspection and linting tools.

Validates that vault_links and vault_lint MCP tools correctly delegate to Abby core
services and return standard MCPToolCallResult structures.
"""

from __future__ import annotations

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

from abby.mcp.tools import execute_tool


class TestMCPLinksAndLintTools(Tier2FilesystemTestCase):
    """Tier 2 tests for MCP vault_links and vault_lint tools."""

    def setUp(self) -> None:
        super().setUp()
        self.init_vault()

    def test_tool_vault_links(self) -> None:
        self.create_note(
            title="Target Note",
            filename="Target Note.md",
            domain="03 - Resources",
            body="I am target.",
        )
        self.create_note(
            title="Source Note",
            filename="Source Note.md",
            domain="01 - Projects",
            body="Check out [[Target Note]].",
        )
        result = execute_tool(
            "vault_links",
            {"note": "Source Note", "mode": "outbound"},
            self.vault_root,
        )
        self.assertFalse(result.isError)
        self.assertIn("Target Note", result.content[0].text)

    def test_tool_vault_links_modes(self) -> None:
        # Missing note for outbound and backlinks
        res_err_outbound = execute_tool(
            "vault_links", {"mode": "outbound"}, self.vault_root
        )
        self.assertTrue(res_err_outbound.isError)
        self.assertIn(
            "Mode 'outbound' requires 'note' argument.",
            res_err_outbound.content[0].text,
        )

        res_err_backlinks = execute_tool(
            "vault_links", {"mode": "backlinks"}, self.vault_root
        )
        self.assertTrue(res_err_backlinks.isError)
        self.assertIn(
            "Mode 'backlinks' requires 'note' argument.",
            res_err_backlinks.content[0].text,
        )

        # Invalid mode
        res_err_mode = execute_tool(
            "vault_links", {"mode": "invalid_mode"}, self.vault_root
        )
        self.assertTrue(res_err_mode.isError)
        self.assertIn("Invalid mode 'invalid_mode'", res_err_mode.content[0].text)

        # Target and Source notes
        self.create_note(
            title="Target Note",
            filename="Target Note.md",
            domain="03 - Resources",
            body="I am target.",
            type_="resource-note",
            status="evergreen",
        )
        self.create_note(
            title="Source Note",
            filename="Source Note.md",
            domain="01 - Projects",
            body="Link to [[Target Note]] and broken [[Nonexistent Note]].",
            type_="project-note",
            status="active",
        )
        self.create_note(
            title="Isolated Orphan",
            filename="Isolated Orphan.md",
            domain="03 - Resources",
            body="No links inbound or outbound.",
            type_="resource-note",
            status="evergreen",
        )

        # Backlinks mode
        res_bl = execute_tool(
            "vault_links", {"mode": "backlinks", "note": "Target Note"}, self.vault_root
        )
        self.assertFalse(res_bl.isError)
        self.assertIn("Source Note", res_bl.content[0].text)

        # Broken mode (unfiltered and domain filtered)
        res_broken = execute_tool("vault_links", {"mode": "broken"}, self.vault_root)
        self.assertFalse(res_broken.isError)
        self.assertIn("Nonexistent Note", res_broken.content[0].text)

        res_broken_domain = execute_tool(
            "vault_links", {"mode": "broken", "domain": "projects"}, self.vault_root
        )
        self.assertFalse(res_broken_domain.isError)
        self.assertIn("Nonexistent Note", res_broken_domain.content[0].text)

        res_broken_clean_domain = execute_tool(
            "vault_links", {"mode": "broken", "domain": "resources"}, self.vault_root
        )
        self.assertFalse(res_broken_clean_domain.isError)
        self.assertIn(
            "No broken links found across vault.",
            res_broken_clean_domain.content[0].text,
        )

        # Orphans mode
        res_orphans = execute_tool("vault_links", {"mode": "orphans"}, self.vault_root)
        self.assertFalse(res_orphans.isError)
        self.assertIn("Isolated Orphan.md", res_orphans.content[0].text)

        # Unreferenced mode
        res_unref = execute_tool(
            "vault_links", {"mode": "unreferenced"}, self.vault_root
        )
        self.assertFalse(res_unref.isError)
        self.assertIn("Source Note.md", res_unref.content[0].text)

    def test_tool_vault_lint(self) -> None:
        self.create_note(
            title="Clean Note", filename="Clean Note.md", domain="00 - Inbox"
        )
        result = execute_tool(
            "vault_lint",
            {"domain": "inbox"},
            self.vault_root,
        )
        self.assertFalse(result.isError)
        self.assertIn("clean", result.content[0].text.lower())

    def test_tool_vault_lint_single_note_audit_and_fix(self) -> None:
        dirty_content = (
            "---\n"
            "title: Unquoted Title Note\n"
            "created: 2026-09-17\n"
            "type: inbox\n"
            "status: active\n"
            "tags:\n"
            "  - #invalid\n"
            "---\n"
            "# Unquoted Title Note\n\nSome body."
        )
        self.create_note(
            domain="00 - Inbox",
            filename="Unquoted Title Note.md",
            content=dirty_content,
        )

        res_audit = execute_tool(
            "vault_lint", {"note": "Unquoted Title Note"}, self.vault_root
        )
        self.assertFalse(res_audit.isError)
        self.assertIn("Unquoted Title Note", res_audit.content[0].text)
        self.assertIn("violations", res_audit.content[0].text.lower())

        res_dry = execute_tool(
            "vault_lint",
            {"note": "Unquoted Title Note", "fix": True, "dry_run": True},
            self.vault_root,
        )
        self.assertFalse(res_dry.isError)
        self.assertIn("DRY-RUN", res_dry.content[0].text)
        note_file = self.vault_root / "00 - Inbox" / "Unquoted Title Note.md"
        self.assertEqual(note_file.read_text(encoding="utf-8"), dirty_content)

        res_fix = execute_tool(
            "vault_lint",
            {"note": "Unquoted Title Note", "fix": True, "dry_run": False},
            self.vault_root,
        )
        self.assertFalse(res_fix.isError)
        fixed_content = note_file.read_text(encoding="utf-8")
        self.assertIn("status: unprocessed", fixed_content)
        self.assertIn("- invalid", fixed_content)

    def test_tool_vault_lint_vault_wide_fix(self) -> None:
        dirty_content = (
            "---\n"
            "title: Vault Wide Dirty Note\n"
            "created: 2026-09-17\n"
            "type: inbox\n"
            "status: active\n"
            "---\n"
            "# Vault Wide Dirty Note\n\nBody."
        )
        self.create_note(
            domain="00 - Inbox",
            filename="Vault Wide Dirty Note.md",
            content=dirty_content,
        )
        res_fix = execute_tool(
            "vault_lint", {"domain": "inbox", "fix": True}, self.vault_root
        )
        self.assertFalse(res_fix.isError)
        note_file = self.vault_root / "00 - Inbox" / "Vault Wide Dirty Note.md"
        fixed_content = note_file.read_text(encoding="utf-8")
        self.assertIn("status: unprocessed", fixed_content)


if __name__ == "__main__":
    import unittest
    unittest.main()

