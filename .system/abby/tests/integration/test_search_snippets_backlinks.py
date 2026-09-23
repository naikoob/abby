"""Integration tests for backlink count exposure in CLI snippets and MCP tool responses.

Feature: 015-cognitive-graph-search
User Story 3: Backlink Exposure in Snippets & Search Payload (Priority: P2)
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
    from tests.support import CliRunner, IsolatedVaultTestCase
except ModuleNotFoundError:
    from support import CliRunner, IsolatedVaultTestCase

from abby.core.cache import sync_cache
from abby.mcp.tools import execute_tool


class TestSearchSnippetsBacklinksIntegration(IsolatedVaultTestCase):
    """Integration tests verifying backlink exposure across CLI snippets and MCP search."""

    def setUp(self) -> None:
        super().setUp()
        self.init_vault()

    def _seed_test_cluster(self) -> None:
        """Seed a central resource note and inbound project notes."""
        self.create_note(
            domain="03 - Resources",
            filename="Raft Consensus.md",
            content=(
                "---\n"
                "title: \"Raft Consensus\"\n"
                "description: \"Distributed consensus protocol utilizing leader election.\"\n"
                "type: resource-note\n"
                "status: evergreen\n"
                "tags:\n"
                "  - distributed-systems\n"
                "  - consensus\n"
                "verified:\n"
                "  - by: human:bookian\n"
                "    at: \"2026-09-18T12:00:00Z\"\n"
                "---\n\n"
                "Raft consensus guarantees replicated state machine consistency under async network partitions.\n"
            ),
        )

        self.create_note(
            domain="01 - Projects",
            filename="Project Alpha.md",
            content=(
                "---\n"
                "title: \"Project Alpha\"\n"
                "description: \"Core telemetry pipeline.\"\n"
                "type: project-note\n"
                "status: active\n"
                "---\n\n"
                "Implements replicated state via [[Raft Consensus]].\n"
            ),
        )

        self.create_note(
            domain="01 - Projects",
            filename="Project Beta.md",
            content=(
                "---\n"
                "title: \"Project Beta\"\n"
                "description: \"Secondary coordination service.\"\n"
                "type: project-note\n"
                "status: active\n"
                "---\n\n"
                "Coordinates node metadata using [[Raft Consensus]].\n"
            ),
        )

        self.create_note(
            domain="00 - Inbox",
            filename="Raw Note.md",
            content=(
                "---\n"
                "title: \"Raw Note\"\n"
                "type: inbox\n"
                "status: unprocessed\n"
                "---\n\n"
                "Quick thought about consensus algorithms.\n"
            ),
        )

        sync_cache(self.vault_root)

    def test_cli_snippets_backlink_header_formatting(self) -> None:
        """Verify CLI find --snippets displays [<Domain> | <Status> | <TrustTier> | <N> links]."""
        self._seed_test_cluster()
        code, out, err = CliRunner.invoke(["find", "Raft", "--snippets"])
        self.assertEqual(code, 0)
        self.assertEqual(err, "")

        # Target note has 2 active backlinks (Project Alpha + Project Beta)
        expected_header = (
            "03 - Resources/Raft Consensus.md "
            "[03 - Resources | evergreen | human-reviewed | 2 links]"
        )
        self.assertIn(expected_header, out)
        self.assertIn("Description: Distributed consensus protocol utilizing leader election.", out)
        self.assertIn("**Raft**", out)

    def test_cli_snippets_zero_backlinks(self) -> None:
        """Verify note with 0 backlinks formats as [0 links] without errors."""
        self._seed_test_cluster()
        code, out, _ = CliRunner.invoke(["find", "Raw", "--snippets"])
        self.assertEqual(code, 0)
        expected_header = "00 - Inbox/Raw Note.md [00 - Inbox | unprocessed | unverified | 0 links]"
        self.assertIn(expected_header, out)

    def test_cli_json_active_backlinks_payload(self) -> None:
        """Verify CLI find --json output contains active_backlinks integer field."""
        self._seed_test_cluster()
        code, out, _ = CliRunner.invoke(["find", "Raft", "--json"])
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertGreaterEqual(data["count"], 1)

        raft_note = next(n for n in data["notes"] if n["filename"] == "Raft Consensus.md")
        self.assertEqual(raft_note["active_backlinks"], 2)
        self.assertEqual(raft_note["trust_tier"], "human-reviewed")
        self.assertFalse(raft_note["is_stale"])

    def test_mcp_vault_search_backlink_visibility(self) -> None:
        """Verify MCP vault_search response surfaces active backlink counts."""
        self._seed_test_cluster()

        # 1. Text mode vault_search
        res_text = execute_tool(
            "vault_search",
            {"query": "Raft", "snippets": True},
            self.vault_root,
        )
        self.assertFalse(res_text.isError)
        text = res_text.content[0].text
        self.assertIn("Raft Consensus", text)
        self.assertIn("2 links", text)
        self.assertIn("human-reviewed", text)

        # 2. JSON mode vault_search
        res_json = execute_tool(
            "vault_search",
            {"query": "Raft", "json": True},
            self.vault_root,
        )
        self.assertFalse(res_json.isError)
        json_data = json.loads(res_json.content[0].text)
        raft_match = next(m for m in json_data["matches"] if m["filename"] == "Raft Consensus.md")
        self.assertEqual(raft_match["active_backlinks"], 2)
        self.assertEqual(raft_match["trust_tier"], "human-reviewed")


if __name__ == "__main__":
    import unittest
    unittest.main()

