"""Tier 2 integration tests for Abby MCP tool registry and service delegation.

Validates that all 9 MCP tools execute within a sandboxed vault, correctly delegate
to Abby core services, and return standard MCPToolCallResult structures.
"""

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


class TestMCPToolsIntegration(Tier2FilesystemTestCase):
    """Tier 2 tests for MCP tool execution and core service parity."""

    def setUp(self) -> None:
        super().setUp()
        self.init_vault()

    def test_tool_registry_contains_nine_tools(self) -> None:
        names = get_tool_names()
        expected = [
            "vault_check",
            "vault_init",
            "note_capture",
            "domain_list",
            "note_move",
            "note_archive",
            "note_verify",
            "vault_search",
            "vault_links",
            "vault_lint",
            "note_read",
            "note_refactor",
        ]
        self.assertEqual(len(names), 12)
        for name in expected:
            self.assertIn(name, names)

        tools = get_tool_definitions()
        self.assertEqual(len(tools), 12)
        for tool in tools:
            self.assertIn("name", tool)
            self.assertIn("description", tool)
            self.assertIn("inputSchema", tool)
            self.assertEqual(tool["inputSchema"]["type"], "object")

        vault_search_tool = next(t for t in tools if t["name"] == "vault_search")
        self.assertIn("snippets", vault_search_tool["inputSchema"]["properties"])
        self.assertEqual(
            vault_search_tool["inputSchema"]["properties"]["snippets"]["type"],
            "boolean",
        )

    def test_tool_vault_check(self) -> None:
        result = execute_tool("vault_check", {}, self.vault_root)
        self.assertFalse(result.isError)
        self.assertTrue(len(result.content) > 0)
        self.assertIn("Health", result.content[0].text)

    def test_tool_vault_init(self) -> None:
        # Remove a directory
        inbox = self.vault_root / "00 - Inbox"
        inbox.rmdir()
        self.assertFalse(inbox.exists())

        result = execute_tool("vault_init", {}, self.vault_root)
        self.assertFalse(result.isError)
        self.assertTrue(inbox.exists())
        self.assertIn("00 - Inbox", result.content[0].text)

    def test_tool_note_capture(self) -> None:
        args = {
            "title": "Captured via MCP",
            "body": "MCP note capture test body.",
            "tags": ["testing", "mcp"],
        }
        result = execute_tool("note_capture", args, self.vault_root)
        self.assertFalse(result.isError)
        self.assertIn("Captured via MCP", result.content[0].text)

        captured_file = self.vault_root / "00 - Inbox" / "Captured via MCP.md"
        self.assertTrue(captured_file.exists())
        content = captured_file.read_text(encoding="utf-8")
        self.assertIn('title: "Captured via MCP"', content)
        self.assertIn("testing", content)
        self.assertIn("mcp", content)

    def test_tool_domain_list(self) -> None:
        self.create_note(title="Item One", filename="Item One.md", domain="00 - Inbox")
        self.create_note(title="Item Two", filename="Item Two.md", domain="00 - Inbox")

        result = execute_tool("domain_list", {"domain": "inbox"}, self.vault_root)
        self.assertFalse(result.isError)
        self.assertIn("Item One", result.content[0].text)
        self.assertIn("Item Two", result.content[0].text)

    def test_tool_note_move(self) -> None:
        note_path = self.create_note(
            title="Active Sprint", filename="Active Sprint.md", domain="00 - Inbox"
        )
        result = execute_tool(
            "note_move",
            {"note": "Active Sprint", "target": "projects/Sprint 42"},
            self.vault_root,
        )
        self.assertFalse(result.isError)
        dest_file = self.vault_root / "01 - Projects" / "Sprint 42" / "Active Sprint.md"
        self.assertTrue(dest_file.exists())
        self.assertFalse(note_path.exists())

    def test_tool_note_archive(self) -> None:
        note_path = self.create_note(
            title="Old Project", filename="Old Project.md", domain="01 - Projects"
        )
        result = execute_tool(
            "note_archive",
            {"note": "Old Project"},
            self.vault_root,
        )
        self.assertFalse(result.isError)
        archived_file = self.vault_root / "04 - Archives" / "Old Project.md"
        self.assertTrue(archived_file.exists())
        self.assertFalse(note_path.exists())

    def test_tool_note_move_dry_run(self) -> None:
        note_path = self.create_note(
            title="Dry Run Note", filename="Dry Run Note.md", domain="00 - Inbox"
        )
        result = execute_tool(
            "note_move",
            {"note": "Dry Run Note", "target": "projects/Sprint 99", "dry_run": True},
            self.vault_root,
        )
        self.assertFalse(result.isError)
        self.assertIn("[DRY-RUN] Planned move.", result.content[0].text)
        self.assertIn("01 - Projects/Sprint 99/Dry Run Note.md", result.content[0].text)
        # Verify 0 disk changes
        self.assertTrue(note_path.exists())
        dest_file = self.vault_root / "01 - Projects" / "Sprint 99" / "Dry Run Note.md"
        self.assertFalse(dest_file.exists())

    def test_tool_note_archive_dry_run(self) -> None:
        note_path = self.create_note(
            title="Dry Run Archive",
            filename="Dry Run Archive.md",
            domain="01 - Projects",
        )
        result = execute_tool(
            "note_archive",
            {"note": "Dry Run Archive", "dry_run": True},
            self.vault_root,
        )
        self.assertFalse(result.isError)
        self.assertIn("[DRY-RUN] Planned archive.", result.content[0].text)
        self.assertIn("04 - Archives/Dry Run Archive.md", result.content[0].text)
        # Verify 0 disk changes
        self.assertTrue(note_path.exists())
        archived_file = self.vault_root / "04 - Archives" / "Dry Run Archive.md"
        self.assertFalse(archived_file.exists())

    def test_tool_vault_search(self) -> None:
        self.create_note(
            title="Searchable Architecture Note",
            filename="Searchable Architecture Note.md",
            domain="03 - Resources",
            body="Contains quantum encryption reference.",
        )
        result = execute_tool(
            "vault_search",
            {"query": "quantum", "domain": "resources"},
            self.vault_root,
        )
        self.assertFalse(result.isError)
        self.assertIn("Searchable Architecture Note", result.content[0].text)

    def test_tool_vault_search_snippets(self) -> None:
        self.create_note(
            title="Searchable Architecture Note",
            filename="Searchable Architecture Note.md",
            domain="03 - Resources",
            body="Contains quantum encryption reference.",
        )
        # Search without snippets - no snippet quotation line
        res_no_snip = execute_tool(
            "vault_search",
            {"query": "quantum", "domain": "resources"},
            self.vault_root,
        )
        self.assertFalse(res_no_snip.isError)
        self.assertIn("Searchable Architecture Note", res_no_snip.content[0].text)
        self.assertNotIn('    "', res_no_snip.content[0].text)

        # Search with snippets: true - indented quote with highlighted term
        res_snip = execute_tool(
            "vault_search",
            {"query": "quantum", "domain": "resources", "snippets": True},
            self.vault_root,
        )
        self.assertFalse(res_snip.isError)
        text = res_snip.content[0].text
        self.assertIn("Searchable Architecture Note", text)
        self.assertIn('    "', text)
        self.assertIn("**quantum**", text)
    def test_tool_invalid_name(self) -> None:
        result = execute_tool("nonexistent_tool", {}, self.vault_root)
        self.assertTrue(result.isError)
        self.assertIn("Unrecognized tool", result.content[0].text)

    def test_tool_missing_required_args(self) -> None:
        result = execute_tool("note_capture", {}, self.vault_root)
        self.assertTrue(result.isError)
        self.assertIn("Missing required argument", result.content[0].text)

    def test_tool_vault_init_already_initialized(self) -> None:
        # Vault is already initialized in setUp()
        result = execute_tool("vault_init", {}, self.vault_root)
        self.assertFalse(result.isError)
        self.assertIn(
            "Verified 7 existing required directories.", result.content[0].text
        )

    def test_tool_domain_list_formatting_and_empty(self) -> None:
        self.create_note(
            title="Item Alpha", filename="Item Alpha.md", domain="00 - Inbox"
        )
        result = execute_tool("domain_list", {"domain": "inbox"}, self.vault_root)
        self.assertFalse(result.isError)
        self.assertIn("- Item Alpha (00 - Inbox/Item Alpha.md)", result.content[0].text)
        self.assertNotIn("TriageNoteItem", result.content[0].text)

        # Empty domain
        res_empty = execute_tool("domain_list", {"domain": "projects"}, self.vault_root)
        self.assertFalse(res_empty.isError)
        self.assertIn(
            "Domain 'projects' queue is empty (0 notes).", res_empty.content[0].text
        )

if __name__ == "__main__":
    import unittest
    unittest.main()

