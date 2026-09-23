"""Unit tests for note capture and intake with provenance parameters."""

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

from abby.core.intake import capture_note
from abby.mcp.handlers import handle_note_capture
from abby.services.okf_parser import parse_okf_frontmatter


class TestIntakeProvenance(IsolatedVaultTestCase):
    """Tests for intake provenance stamping via core, CLI, and MCP."""

    def setUp(self) -> None:
        super().setUp()
        self.init_vault()

    def test_capture_note_with_generated(self) -> None:
        gen = {"by": "abby/agent:synthesizer", "at": "2026-09-18T12:00:00Z"}
        note = capture_note(
            self.vault_root,
            "Synthesized Concepts",
            body="Decomposed atomic note.",
            generated=gen,
        )
        self.assertEqual(note.frontmatter.generated, gen)

        disk_content = note.absolute_path.read_text(encoding="utf-8")
        parsed = parse_okf_frontmatter(disk_content, default_title="Synthesized Concepts")
        self.assertEqual(parsed.get("generated"), gen)

    def test_capture_note_with_verified_and_sources(self) -> None:
        verified = [{"by": "human:bookian", "at": "2026-09-18T13:00:00Z"}]
        sources = [
            {
                "resource": "https://example.com/rfc.pdf",
                "id": "rfc123",
                "title": "Protocol RFC",
                "author": "Network WG",
            }
        ]
        note = capture_note(
            self.vault_root,
            "Verified Protocol",
            body="Verified protocol details.",
            verified=verified,
            sources=sources,
        )
        self.assertEqual(note.frontmatter.verified, verified)
        self.assertEqual(note.frontmatter.sources, sources)

        disk_content = note.absolute_path.read_text(encoding="utf-8")
        parsed = parse_okf_frontmatter(disk_content, default_title="Verified Protocol")
        self.assertEqual(parsed.get("trust_tier"), "human-reviewed")
        self.assertEqual(len(parsed.get("sources", [])), 1)

    def test_cli_new_with_generated_by(self) -> None:
        code, out, err = CliRunner.invoke(
            [
                "new",
                "Triage Note",
                "--generated-by",
                "abby/agent:triage",
                "--json",
            ]
        )
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertTrue(data.get("success"))

        note_file = self.vault_root / data["path"]
        content = note_file.read_text(encoding="utf-8")
        self.assertIn("generated:", content)
        self.assertIn("by: abby/agent:triage", content)

    def test_mcp_note_capture_with_provenance(self) -> None:
        res = handle_note_capture(
            {
                "title": "Agent Created Note",
                "body": "Note body.",
                "generated": {"by": "agent:curator", "at": "2026-09-18T14:00:00Z"},
                "verified": [{"by": "process:ci", "at": "2026-09-18T14:05:00Z"}],
                "sources": [{"resource": "https://doi.org/10.1000/182"}],
            },
            self.vault_root,
        )
        self.assertFalse(res.isError)

        note_file = self.vault_root / "00 - Inbox" / "Agent Created Note.md"
        self.assertTrue(note_file.exists())
        content = note_file.read_text(encoding="utf-8")
        parsed = parse_okf_frontmatter(content, default_title="Agent Created Note")
        self.assertEqual(parsed.get("trust_tier"), "machine-confirmed")
        self.assertEqual(len(parsed.get("sources", [])), 1)


if __name__ == "__main__":
    import unittest

    unittest.main()

