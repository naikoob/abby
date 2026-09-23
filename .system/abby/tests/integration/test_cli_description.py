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


class TestCliDescription(IsolatedVaultTestCase):
    """Integration test suite verifying description lifecycle across CLI commands."""

    def setUp(self) -> None:
        super().setUp()
        self.init_vault()

    def test_inbox_capture_without_description_passes_strict_lint(self):
        """Verify zero capture friction: raw inbox note passes standard and strict lint."""
        code, out, err = CliRunner.invoke(["new", "Raw Thought"])
        self.assertEqual(code, 0)
        inbox_note = self.vault_root / "00 - Inbox" / "Raw Thought.md"
        self.assertTrue(inbox_note.exists())

        # Standard lint
        code_lint, out_lint, _ = CliRunner.invoke(["lint", str(inbox_note)])
        self.assertEqual(code_lint, 0)

        # Strict lint
        code_strict, out_strict, _ = CliRunner.invoke(
            ["lint", str(inbox_note), "--strict"]
        )
        self.assertEqual(code_strict, 0)

    def test_curated_domain_without_description_warns_and_fails_strict(self):
        """Verify lifecycle gating: notes in 01-03 require description for strict lint."""
        proj_dir = self.vault_root / "01 - Projects"
        proj_note = proj_dir / "Alpha Project.md"
        proj_note.write_text(
            "---\n"
            'title: "Alpha Project"\n'
            'created: "2026-09-18T10:00:00"\n'
            "type: project-note\n"
            "status: active\n"
            "tags:\n"
            "  - alpha\n"
            "---\n\n"
            "# Alpha Project\n\nContent here.\n",
            encoding="utf-8",
        )

        # Standard lint issues a warning but exits 0
        code_lint, out_lint, _ = CliRunner.invoke(["lint", str(proj_note)])
        self.assertEqual(code_lint, 0)
        self.assertIn("description", out_lint.lower())

        # Strict lint fails with exit code 1
        code_strict, out_strict, _ = CliRunner.invoke(
            ["lint", str(proj_note), "--strict"]
        )
        self.assertEqual(code_strict, 1)
        self.assertIn("description", out_strict.lower())

    def test_curated_domain_with_description_passes_strict_lint(self):
        """Verify note with description in 01-03 passes strict lint."""
        proj_dir = self.vault_root / "01 - Projects"
        proj_note = proj_dir / "Beta Project.md"
        proj_note.write_text(
            "---\n"
            'title: "Beta Project"\n'
            'description: "Beta initiative overview."\n'
            'created: "2026-09-18T10:00:00"\n'
            "type: project-note\n"
            "status: active\n"
            "tags:\n"
            "  - beta\n"
            "---\n\n"
            "# Beta Project\n\nContent here.\n",
            encoding="utf-8",
        )

        code_strict, out_strict, _ = CliRunner.invoke(
            ["lint", str(proj_note), "--strict"]
        )
        self.assertEqual(code_strict, 0)

    def test_archive_without_description_passes_strict_lint(self):
        """Verify historical archive notes pass without description even under strict lint."""
        arch_dir = self.vault_root / "04 - Archives"
        arch_note = arch_dir / "Old Project.md"
        arch_note.write_text(
            "---\n"
            'title: "Old Project"\n'
            'created: "2024-01-01T10:00:00"\n'
            "type: archive-note\n"
            "status: archived\n"
            "tags:\n"
            "  - old\n"
            "---\n\n"
            "# Old Project\n",
            encoding="utf-8",
        )

        code_strict, _, _ = CliRunner.invoke(["lint", str(arch_note), "--strict"])
        self.assertEqual(code_strict, 0)

    def test_capture_with_description_flag(self):
        """Verify abby new --description populates OKF frontmatter."""
        code, _, _ = CliRunner.invoke(
            [
                "new",
                "Telemetry Guide",
                "--description",
                "Ingestion pipeline architecture.",
                "--tags",
                "telemetry",
            ]
        )
        self.assertEqual(code, 0)
        note = self.vault_root / "00 - Inbox" / "Telemetry Guide.md"
        self.assertTrue(note.exists())
        content = note.read_text(encoding="utf-8")
        self.assertIn(
            'description: "Ingestion pipeline architecture."',
            content,
        )

    def test_move_preserves_description(self):
        """Verify moving a note preserves its description without corruption."""
        inbox_note = self.vault_root / "00 - Inbox" / "Consensus Engine.md"
        inbox_note.write_text(
            "---\n"
            'title: "Consensus Engine"\n'
            'description: "Raft state replication protocol."\n'
            'created: "2026-09-18T10:00:00"\n'
            "type: inbox\n"
            "status: unprocessed\n"
            "tags:\n"
            "  - consensus\n"
            "---\n\n"
            "# Consensus Engine\n\nProtocol details.\n",
            encoding="utf-8",
        )
        code, out, err = CliRunner.invoke(["move", "Consensus Engine", "01 - Projects"])
        self.assertEqual(code, 0)

        moved = self.vault_root / "01 - Projects" / "Consensus Engine.md"
        self.assertTrue(moved.exists())
        content = moved.read_text(encoding="utf-8")
        self.assertIn(
            'description: "Raft state replication protocol."',
            content,
        )

    def test_find_with_description_matches_and_snippets(self):
        """Verify abby find indexes description and displays it with --snippets."""
        res_dir = self.vault_root / "03 - Resources"
        res_note = res_dir / "Storage Engine.md"
        res_note.write_text(
            "---\n"
            'title: "Storage Engine"\n'
            'description: "High-performance RocksDB key-value storage layer."\n'
            'created: "2026-09-18T10:00:00"\n'
            "type: resource-note\n"
            "status: evergreen\n"
            "tags:\n"
            "  - storage\n"
            "---\n\n"
            "# Storage Engine\n\nUnderlying persistent table format.\n",
            encoding="utf-8",
        )

        # Search for 'RocksDB' which is ONLY in description
        code, out, _ = CliRunner.invoke(["find", "RocksDB", "--snippets"])
        self.assertEqual(code, 0)
        self.assertIn("03 - Resources/Storage Engine.md", out)
        self.assertIn("Description:", out)
        self.assertIn("RocksDB", out)

        # Search with --json
        code_json, out_json, _ = CliRunner.invoke(["find", "RocksDB", "--json"])
        self.assertEqual(code_json, 0)
        payload = json.loads(out_json)
        self.assertEqual(payload["count"], 1)
        self.assertEqual(
            payload["notes"][0]["description"],
            "High-performance RocksDB key-value storage layer.",
        )


if __name__ == "__main__":
    unittest.main()
