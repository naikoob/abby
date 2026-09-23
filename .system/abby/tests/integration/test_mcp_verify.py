"""Tier 2 integration tests for 'note_verify' MCP tool.

Covers User Story 2 (T015) of OKF 0.2 Trust Model.
Verifies JSON-RPC tool schema, parameter handling, and core delegation.
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
    from tests.support import IsolatedVaultTestCase
except ModuleNotFoundError:
    from support import IsolatedVaultTestCase

from abby.mcp.tools import execute_tool, get_tool_definitions, get_tool_names


class TestMCPVerifyIntegration(IsolatedVaultTestCase):
    """Integration tests for note_verify MCP tool."""

    def setUp(self) -> None:
        super().setUp()
        self.init_vault()

    def test_note_verify_tool_registered(self) -> None:
        names = get_tool_names()
        self.assertIn("note_verify", names)

        tools = {t["name"]: t for t in get_tool_definitions()}
        self.assertIn("note_verify", tools)
        schema = tools["note_verify"]["inputSchema"]
        self.assertEqual(schema["type"], "object")
        self.assertIn("note_path", schema["properties"])
        self.assertIn("actor", schema["properties"])
        self.assertIn("dry_run", schema["properties"])
        self.assertIn("note_path", schema["required"])

    def test_note_verify_execution_success(self) -> None:
        self.create_note(
            domain="03 - Resources",
            filename="Byzantine Faults.md",
            title="Byzantine Faults",
            body="BFT consensus protocols.",
        )
        res = execute_tool(
            name="note_verify",
            arguments={
                "note_path": "03 - Resources/Byzantine Faults.md",
                "actor": "agent:synthesizer",
            },
            vault_root=self.vault_root,
        )
        self.assertFalse(res.isError)
        self.assertTrue(len(res.content) > 0)
        data = json.loads(res.content[0].text)
        self.assertEqual(data["path"], "03 - Resources/Byzantine Faults.md")
        self.assertEqual(data["actor"], "agent:synthesizer")
        self.assertEqual(data["trust_tier"], "machine-confirmed")
        self.assertFalse(data["dry_run"])

    def test_note_verify_with_note_alias_success(self) -> None:
        self.create_note(
            domain="03 - Resources",
            filename="Paxos Consensus.md",
            title="Paxos Consensus",
            body="State machine replication.",
        )
        res = execute_tool(
            name="note_verify",
            arguments={
                "note": "03 - Resources/Paxos Consensus.md",
                "actor": "abby/agent:triage",
            },
            vault_root=self.vault_root,
        )
        self.assertFalse(res.isError)
        self.assertTrue(len(res.content) > 0)
        data = json.loads(res.content[0].text)
        self.assertEqual(data["path"], "03 - Resources/Paxos Consensus.md")
        self.assertEqual(data["actor"], "abby/agent:triage")
        self.assertEqual(data["trust_tier"], "machine-confirmed")

    def test_note_verify_dry_run_does_not_modify_file(self) -> None:
        note_path = self.create_note(
            domain="03 - Resources",
            filename="Chubby Lock.md",
            title="Chubby Lock",
            body="Coarse-grained locking service.",
        )
        before_content = note_path.read_text(encoding="utf-8")

        res = execute_tool(
            name="note_verify",
            arguments={
                "note_path": "03 - Resources/Chubby Lock.md",
                "actor": "human:bookian",
                "dry_run": True,
            },
            vault_root=self.vault_root,
        )
        self.assertFalse(res.isError)
        data = json.loads(res.content[0].text)
        self.assertTrue(data["dry_run"])
        self.assertEqual(data["trust_tier"], "human-reviewed")
        self.assertEqual(note_path.read_text(encoding="utf-8"), before_content)

    def test_note_verify_missing_required_arg_fails(self) -> None:
        res = execute_tool(
            name="note_verify",
            arguments={},
            vault_root=self.vault_root,
        )
        self.assertTrue(res.isError)

    def test_note_verify_invalid_actor_fails(self) -> None:
        self.create_note(
            domain="03 - Resources",
            filename="Spanner.md",
            title="Spanner",
        )
        res = execute_tool(
            name="note_verify",
            arguments={
                "note_path": "03 - Resources/Spanner.md",
                "actor": "invalid spaces actor",
            },
            vault_root=self.vault_root,
        )
        self.assertTrue(res.isError)
