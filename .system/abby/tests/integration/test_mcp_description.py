"""Integration tests for MCP tools handling note descriptions."""

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

from abby.mcp.tools import execute_tool, get_tool_definitions


class TestMcpDescription(Tier2FilesystemTestCase):
    """Integration test suite verifying description handling in MCP tools."""

    def setUp(self) -> None:
        super().setUp()
        self.init_vault()

    def test_vault_search_with_description_summary(self) -> None:
        """Verify vault_search outputs Summary: <description> when snippets=True."""
        res_dir = self.vault_root / "03 - Resources"
        res_note = res_dir / "Consensus Algorithm.md"
        res_note.write_text(
            "---\n"
            'title: "Consensus Algorithm"\n'
            'description: "Distributed Paxos consensus state machine implementation."\n'
            'created: "2026-09-18T10:00:00"\n'
            "type: resource-note\n"
            "status: evergreen\n"
            "tags:\n"
            "  - consensus\n"
            "---\n\n"
            "# Consensus Algorithm\n\nLeader election details.\n",
            encoding="utf-8",
        )

        # Search without snippets
        result_no_snip = execute_tool(
            "vault_search",
            {"query": "Paxos", "snippets": False},
            self.vault_root,
        )
        self.assertFalse(result_no_snip.isError)
        self.assertIn("Consensus Algorithm", result_no_snip.content[0].text)
        self.assertNotIn("Summary:", result_no_snip.content[0].text)

        # Search with snippets: True
        result_snip = execute_tool(
            "vault_search",
            {"query": "Paxos", "snippets": True},
            self.vault_root,
        )
        self.assertFalse(result_snip.isError)
        text = result_snip.content[0].text
        self.assertIn("Consensus Algorithm", text)
        self.assertIn("Summary: Distributed Paxos consensus state machine implementation.", text)

    def test_note_capture_schema_contains_description(self) -> None:
        """Verify note_capture tool schema exposes optional description property."""
        tools = get_tool_definitions()
        capture_tool = next(t for t in tools if t["name"] == "note_capture")
        props = capture_tool["inputSchema"]["properties"]
        self.assertIn("description", props)
        self.assertEqual(props["description"]["type"], "string")

    def test_note_capture_with_description(self) -> None:
        """Verify note_capture populates description in OKF frontmatter."""
        result = execute_tool(
            "note_capture",
            {
                "title": "Quantum Cryptography",
                "description": "Post-quantum lattice encryption standards.",
                "tags": ["cryptography", "quantum"],
            },
            self.vault_root,
        )
        self.assertFalse(result.isError)
        self.assertIn("Quantum Cryptography", result.content[0].text)
        self.assertIn("Post-quantum lattice encryption standards.", result.content[0].text)

        created_file = self.vault_root / "00 - Inbox" / "Quantum Cryptography.md"
        self.assertTrue(created_file.exists())
        content = created_file.read_text(encoding="utf-8")
        self.assertIn('description: "Post-quantum lattice encryption standards."', content)


if __name__ == "__main__":
    unittest.main()
