"""CLI integration tests for abby find command (Tier 3)."""

from __future__ import annotations

import json
import os
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
    from tests.support import CliRunner, IsolatedVaultTestCase, Tier3CliTestCase
except ModuleNotFoundError:
    from support import CliRunner, IsolatedVaultTestCase, Tier3CliTestCase


class TestCliFindSnippetsAndTextSearch(IsolatedVaultTestCase):
    """Tier 3 integration tests for abby find text search and snippets using a shared indexed vault."""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        import tempfile
        cls._class_temp_dir = tempfile.TemporaryDirectory()
        cls.vault_root = Path(cls._class_temp_dir.name).resolve()
        cls._old_vault_root = os.environ.get("ABBY_VAULT_ROOT")
        cls._old_cwd = os.getcwd()
        os.environ["ABBY_VAULT_ROOT"] = str(cls.vault_root)
        os.chdir(cls.vault_root)

        for d in [
            "00 - Inbox",
            "01 - Projects",
            "02 - Areas",
            "03 - Resources",
            "04 - Archives",
            "05 - Assets",
        ]:
            (cls.vault_root / d).mkdir(parents=True, exist_ok=True)

        cls.create_note_at(
            cls.vault_root,
            "01 - Projects",
            "Apollo.md",
            title="Project Apollo",
            status="active",
            type_="project-note",
            tags=["space"],
            body="Planning moon landing with Saturn V rocket.",
        )
        cls.create_note_at(
            cls.vault_root,
            "00 - Inbox",
            "Retro.md",
            title="Sprint Retro",
            body="We discussed architecture. We discussed PostgreSQL performance.",
        )
        cls.create_note_at(
            cls.vault_root,
            "01 - Projects",
            "Arch.md",
            title="Architecture Review",
            body="Deep dive notes.",
        )
        cls.create_note_at(
            cls.vault_root,
            "01 - Projects",
            "Postgres.md",
            content=(
                "---\n"
                'title: "PostgreSQL Setup"\n'
                'created: "2026-09-17T12:00:00"\n'
                "type: project-note\n"
                "status: active\n"
                "tags: []\n"
                "---\n"
                "Installation steps without repeating the title keyword.\n"
            ),
        )
        cls.create_note_at(
            cls.vault_root,
            "01 - Projects",
            "Auth2026.md",
            title="Auth 2026",
            body="Content",
        )
        cls.create_note_at(
            cls.vault_root,
            "01 - Projects",
            "Speed.md",
            title="Fast-Paced Innovation",
            body="Agile delivery in a fast-paced team.",
            tags=["infra", "devops"],
        )
        cls.create_note_at(
            cls.vault_root,
            "01 - Projects",
            "NoteA.md",
            tags=["tag1"],
        )
        cls.create_note_at(
            cls.vault_root,
            "01 - Projects",
            "NoteB.md",
            tags=["tag2"],
        )

        from abby.core.cache import sync_cache

        sync_cache(cls.vault_root)

    @classmethod
    def tearDownClass(cls) -> None:
        if cls._old_vault_root is not None:
            os.environ["ABBY_VAULT_ROOT"] = cls._old_vault_root
        elif "ABBY_VAULT_ROOT" in os.environ:
            del os.environ["ABBY_VAULT_ROOT"]
        os.chdir(cls._old_cwd)
        cls._class_temp_dir.cleanup()
        super().tearDownClass()

    def setUp(self) -> None:
        pass

    def tearDown(self) -> None:
        pass

    def test_find_invalid_domain_exits_1(self) -> None:
        code, out, err = self.invoke_cli(["find", "--domain", "unknown_realm"])
        self.assertEqual(code, 1)
        self.assertIn("Unrecognized domain: 'unknown_realm'", err)

    def test_find_snippets_text_mode(self) -> None:
        code, out, err = self.invoke_cli(["find", "Saturn", "--snippets"])
        self.assertEqual(code, 0)
        self.assertEqual(err, "")
        lines = out.strip().split("\n")
        self.assertEqual(len(lines), 2)
        self.assertEqual(
            lines[0],
            "01 - Projects/Apollo.md [01 - Projects | active | unverified | 0 links]",
        )
        self.assertTrue(lines[1].startswith("  "))
        self.assertIn("**Saturn**", lines[1])

    def test_find_snippets_flag_position_invariance(self) -> None:
        code1, out1, _ = self.invoke_cli(["find", "Saturn", "--snippets"])
        code2, out2, _ = self.invoke_cli(["--snippets", "find", "Saturn"])
        code3, out3, _ = self.invoke_cli(["find", "--snippets", "Saturn"])
        self.assertEqual(code1, 0)
        self.assertEqual(code2, 0)
        self.assertEqual(code3, 0)
        self.assertEqual(out1, out2)
        self.assertEqual(out1, out3)

    def test_find_snippets_json_mode(self) -> None:
        code, out_snip, err = self.invoke_cli(
            ["find", "Saturn", "--snippets", "--json"]
        )
        self.assertEqual(code, 0)
        self.assertEqual(err, "")
        data_snip = json.loads(out_snip)
        self.assertEqual(len(data_snip["notes"]), 1)
        item = data_snip["notes"][0]
        self.assertIsNotNone(item["snippet"])
        self.assertIn("**Saturn**", item["snippet"])

        # Flag position invariance with --json and --snippets
        code_prefix, out_prefix, _ = self.invoke_cli(
            ["--json", "find", "Saturn", "--snippets"]
        )
        self.assertEqual(code_prefix, 0)
        self.assertEqual(json.loads(out_prefix), data_snip)

        # Without --snippets (JSON mode)
        code_no_snip, out_no_snip, err_no_snip = self.invoke_cli(
            ["find", "Saturn", "--json"]
        )
        self.assertEqual(code_no_snip, 0)
        self.assertEqual(err_no_snip, "")
        data_no_snip = json.loads(out_no_snip)
        self.assertEqual(len(data_no_snip["notes"]), 1)
        self.assertIsNone(data_no_snip["notes"][0]["snippet"])

    def test_find_query_ranking(self) -> None:
        code, out, err = self.invoke_cli(["find", "Architecture"])
        self.assertEqual(code, 0)
        self.assertEqual(err, "")
        lines = out.strip().split("\n")
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0], "01 - Projects/Arch.md")
        self.assertEqual(lines[1], "00 - Inbox/Retro.md")

    def test_find_title_and_content_flags(self) -> None:
        # -t / --title-only
        code, out, _ = self.invoke_cli(["find", "-t", "PostgreSQL"])
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), "01 - Projects/Postgres.md")

        # -c / --content-only
        code, out, _ = self.invoke_cli(["find", "--content-only", "PostgreSQL"])
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), "00 - Inbox/Retro.md")

    def test_find_regex_and_malformed_syntax_exits_2(self) -> None:
        code, out, _ = self.invoke_cli(["find", r"^Auth \d{4}$"])
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), "01 - Projects/Auth2026.md")

        # Malformed regex exits with 2
        code, out, err = self.invoke_cli(["find", r"^[unterminated"])
        self.assertEqual(code, 2)
        self.assertIn("Malformed regular expression", err)

    def test_find_no_matches_exits_0(self) -> None:
        code, out, err = self.invoke_cli(["find", "NonExistentKeywordXYZ"])
        self.assertEqual(code, 0)
        self.assertEqual(out, "")
        self.assertEqual(err, "")

    def test_find_hyphenated_and_duplicate_tags_cli(self) -> None:
        # Hyphenated search via CLI
        code, out, err = self.invoke_cli(["find", "fast-paced"])
        self.assertEqual(code, 0)
        self.assertEqual(err, "")
        self.assertEqual(out.strip(), "01 - Projects/Speed.md")

        # Duplicate tags in CLI args should still match note
        code_tag, out_tag, err_tag = self.invoke_cli(
            ["find", "--tag", "infra", "--tag", "infra"]
        )
        self.assertEqual(code_tag, 0)
        self.assertEqual(err_tag, "")
        self.assertEqual(out_tag.strip(), "01 - Projects/Speed.md")

    def test_find_any_tag_cli(self) -> None:
        # Default AND yields empty
        code, out_and, _ = self.invoke_cli(["find", "--tag", "tag1", "--tag", "tag2"])
        self.assertEqual(code, 0)
        self.assertEqual(out_and, "")

        # --any-tag yields both
        code, out_or, _ = self.invoke_cli(
            ["find", "--tag", "tag1", "--tag", "tag2", "--any-tag"]
        )
        self.assertEqual(code, 0)
        lines = [l for l in out_or.strip().split("\n") if l]
        self.assertEqual(len(lines), 2)
        self.assertIn("01 - Projects/NoteA.md", lines)
        self.assertIn("01 - Projects/NoteB.md", lines)

if __name__ == "__main__":
    unittest.main()
