"""Integration tests for 'abby verify' CLI command.

Covers User Story 2 (T014) of OKF 0.2 Trust Model.
Adheres to CLI Contracts and stream isolation principles.
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


class TestCliVerify(IsolatedVaultTestCase):
    """Integration tests for abby verify CLI command."""

    def setUp(self) -> None:
        super().setUp()
        self.init_vault()

    def test_cli_verify_text_mode_success(self) -> None:
        self.create_note(
            domain="03 - Resources",
            filename="Raft Consensus.md",
            title="Raft Consensus",
            body="Safety invariants in Raft.",
        )
        code, out, err = CliRunner.invoke(
            ["verify", "03 - Resources/Raft Consensus.md", "--by", "human:bookian"]
        )
        self.assertEqual(code, 0)
        self.assertIn("Verified: 03 - Resources/Raft Consensus.md", out)
        self.assertIn("Actor:      human:bookian", out)
        self.assertIn("Trust Tier: human-reviewed", out)

    def test_cli_verify_json_mode_success(self) -> None:
        self.create_note(
            domain="03 - Resources",
            filename="Paxos.md",
            title="Paxos",
            body="Single decree Paxos.",
        )
        code, out, err = CliRunner.invoke(
            ["verify", "03 - Resources/Paxos.md", "--by", "human:alice", "--json"]
        )
        self.assertEqual(code, 0)
        # Verify clean stdout parseable as JSON
        data = json.loads(out.strip())
        self.assertEqual(data["path"], "03 - Resources/Paxos.md")
        self.assertEqual(data["actor"], "human:alice")
        self.assertEqual(data["trust_tier"], "human-reviewed")
        self.assertFalse(data["dry_run"])

    def test_cli_verify_dry_run_mode(self) -> None:
        note_path = self.create_note(
            domain="03 - Resources",
            filename="Gossip Protocol.md",
            title="Gossip Protocol",
            body="Epidemic algorithms.",
        )
        content_before = note_path.read_text(encoding="utf-8")
        mtime_before = note_path.stat().st_mtime_ns

        code, out, err = CliRunner.invoke(
            ["verify", "03 - Resources/Gossip Protocol.md", "--by", "human:bob", "--dry-run"]
        )
        self.assertEqual(code, 0)
        self.assertIn("[DRY RUN] Verification preview for: 03 - Resources/Gossip Protocol.md", out)
        self.assertIn("Actor:          human:bob", out)
        self.assertIn("New Trust Tier: human-reviewed", out)
        self.assertIn("Zero files modified.", out)

        # Confirm 0 disk modifications
        self.assertEqual(note_path.read_text(encoding="utf-8"), content_before)
        self.assertEqual(note_path.stat().st_mtime_ns, mtime_before)

    def test_cli_verify_missing_note_arg_returns_exit_2(self) -> None:
        code, out, err = CliRunner.invoke(["verify"])
        self.assertEqual(code, 2)

    def test_cli_verify_malformed_actor_returns_exit_2(self) -> None:
        self.create_note(
            domain="03 - Resources",
            filename="Vector Clocks.md",
            title="Vector Clocks",
        )
        code, out, err = CliRunner.invoke(
            ["verify", "03 - Resources/Vector Clocks.md", "--by", "bad actor name with spaces"]
        )
        self.assertEqual(code, 2)

    def test_cli_verify_not_found_note_returns_exit_1(self) -> None:
        code, out, err = CliRunner.invoke(
            ["verify", "NonExistentNote.md", "--by", "human:tester"]
        )
        self.assertEqual(code, 1)
