"""Unit, filesystem sandbox, and integration test suite for abby links.

Adheres strictly to Constitution Principle VI (Verifiable Technical Quality & Testing Discipline).
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
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


class TestLinkCacheIntegration(IsolatedVaultTestCase):
    """Tier 2: SQLite note_links relational table creation and sync behavior."""

    def test_cache_indexes_and_resolves_links(self) -> None:
        from abby.core.cache import get_db_connection, sync_cache

        self.init_vault()

        # Seed target notes
        self.create_note(
            domain="03 - Resources",
            filename="Architecture Guide.md",
            title="Architecture Guide",
            body="Architecture specs.",
        )
        self.create_note(
            domain="01 - Projects",
            filename="Kickoff.md",
            title="Kickoff",
            body="Follow [[Architecture Guide|Our Architecture]] and [Arch Guide](../03%20-%20Resources/Architecture%20Guide.md).",
        )

        counts = sync_cache(self.vault_root)
        self.assertEqual(counts["indexed"], 2)

        db_path = self.vault_root / ".system/cache/vault.db"
        conn = get_db_connection(db_path)
        try:
            cursor = conn.execute(
                "SELECT source_path, target_title, target_alias, target_path, link_syntax FROM note_links ORDER BY id ASC;"
            )
            rows = cursor.fetchall()
            self.assertEqual(len(rows), 2)

            wikilinks = [r for r in rows if r[4] == "wikilink"]
            mdlinks = [r for r in rows if r[4] == "markdown"]

            self.assertEqual(len(wikilinks), 1)
            self.assertEqual(wikilinks[0][0], "01 - Projects/Kickoff.md")
            self.assertEqual(wikilinks[0][1], "Architecture Guide")
            self.assertEqual(wikilinks[0][2], "Our Architecture")
            self.assertEqual(wikilinks[0][3], "03 - Resources/Architecture Guide.md")

            self.assertEqual(len(mdlinks), 1)
            self.assertEqual(mdlinks[0][0], "01 - Projects/Kickoff.md")
            self.assertEqual(mdlinks[0][3], "03 - Resources/Architecture Guide.md")
        finally:
            conn.close()

    def test_cache_link_invalidation_on_note_edit_and_delete(self) -> None:
        from abby.core.cache import get_db_connection, sync_cache

        self.init_vault()

        note_file = self.create_note(
            domain="01 - Projects",
            filename="NoteA.md",
            title="Note A",
            body="Links to [[Target One]].",
        )
        sync_cache(self.vault_root)

        db_path = self.vault_root / ".system/cache/vault.db"
        conn = get_db_connection(db_path)
        try:
            cur = conn.execute(
                "SELECT target_title FROM note_links WHERE source_path = '01 - Projects/NoteA.md';"
            )
            self.assertEqual(cur.fetchall(), [("Target One",)])
        finally:
            conn.close()

        # Edit note to change link
        note_file.write_text(
            "---\ntitle: Note A\nstatus: active\ntype: project-note\n---\nLinks to [[Target Two]] and [[Target Three]].",
            encoding="utf-8",
        )
        sync_cache(self.vault_root)

        conn = get_db_connection(db_path)
        try:
            cur = conn.execute(
                "SELECT target_title FROM note_links WHERE source_path = '01 - Projects/NoteA.md' ORDER BY target_title;"
            )
            self.assertEqual(
                [r[0] for r in cur.fetchall()], ["Target Three", "Target Two"]
            )
        finally:
            conn.close()

        # Delete note
        note_file.unlink()
        sync_cache(self.vault_root)

        conn = get_db_connection(db_path)
        try:
            cur = conn.execute(
                "SELECT COUNT(*) FROM note_links WHERE source_path = '01 - Projects/NoteA.md';"
            )
            self.assertEqual(cur.fetchone()[0], 0)
        finally:
            conn.close()


class TestUserStory1LinksQuery(IsolatedVaultTestCase):
    """Tier 3: End-to-end and CLI tests for User Story 1 (links query and backlinks)."""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls._class_temp_dir = tempfile.TemporaryDirectory()
        cls.vault_root = Path(cls._class_temp_dir.name).resolve()
        os.environ["ABBY_VAULT_ROOT"] = str(cls.vault_root)

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
            domain="03 - Resources",
            filename="Architecture Guide.md",
            title="Architecture Guide",
            body="Comprehensive architecture guidelines.",
        )
        cls.create_note_at(
            cls.vault_root,
            domain="01 - Projects",
            filename="Database Migration.md",
            title="Database Migration",
            body="Database schema migration plans.",
        )
        cls.create_note_at(
            cls.vault_root,
            domain="01 - Projects",
            filename="Apollo.md",
            title="Apollo Kickoff",
            body=(
                "# Apollo Mission\n\n"
                "Read [[Architecture Guide|Our Architecture]] section [[Architecture Guide#Authentication]].\n"
                "Also review [Migration Guide](../01%20-%20Projects/Database%20Migration.md).\n"
                "Check out [[Deleted Research]] as well.\n"
            ),
        )
        cls.create_note_at(
            cls.vault_root,
            domain="01 - Projects",
            filename="Overview.md",
            title="Overview",
            body="Project overview.",
        )
        cls.create_note_at(
            cls.vault_root,
            domain="02 - Areas",
            filename="Overview.md",
            title="Overview",
            body="Area overview.",
        )
        cls.create_note_at(
            cls.vault_root,
            domain="01 - Projects",
            filename="AmbiguousCaller.md",
            title="Ambiguous Caller",
            body="See [[Overview]] for details.",
        )
        cls.create_note_at(
            cls.vault_root,
            domain="01 - Projects",
            filename="Roadmap.md",
            title="Roadmap",
            body="Project Roadmap.",
        )
        cls.create_note_at(
            cls.vault_root,
            domain="02 - Areas",
            filename="Roadmap.md",
            title="Roadmap",
            body="Area Roadmap.",
        )
        cls.create_note_at(
            cls.vault_root,
            domain="01 - Projects",
            filename="SelfNote.md",
            title="Self Note",
            body=(
                "# Self Note\n\n"
                "Links to own heading: [[#Heading 1]] and [[Self Note#Heading 2]].\n"
            ),
        )
        cls.create_note_at(
            cls.vault_root,
            domain="01 - Projects",
            filename="OtherNote.md",
            title="Other Note",
            body="Legitimate link to [[Self Note]].\n",
        )

        from abby.core.cache import sync_cache

        sync_cache(cls.vault_root)

    @classmethod
    def tearDownClass(cls) -> None:
        if "ABBY_VAULT_ROOT" in os.environ:
            del os.environ["ABBY_VAULT_ROOT"]
        cls._class_temp_dir.cleanup()
        super().tearDownClass()

    def setUp(self) -> None:
        pass

    def tearDown(self) -> None:
        pass

    def test_query_outbound_links_plain_text(self) -> None:
        code, out, err = CliRunner.invoke(["links", "01 - Projects/Apollo.md"])
        self.assertEqual(code, 0)
        self.assertIn("03 - Resources/Architecture Guide.md", out)
        self.assertIn("01 - Projects/Database Migration.md", out)
        self.assertIn("[unresolved] Deleted Research", out)

    def test_query_outbound_links_by_stem_and_details(self) -> None:
        code, out, err = CliRunner.invoke(["links", "Apollo", "--details"])
        self.assertEqual(code, 0)
        self.assertIn(
            '03 - Resources/Architecture Guide.md (wikilink, line 13, alias: "Our Architecture")',
            out,
        )
        self.assertIn("01 - Projects/Database Migration.md (markdown, line 14", out)
        self.assertIn("[unresolved] Deleted Research (wikilink, line 15", out)

    def test_query_outbound_links_json(self) -> None:
        code, out, err = CliRunner.invoke(["--json", "links", "Apollo"])
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertEqual(data["source_note"], "01 - Projects/Apollo.md")
        self.assertEqual(data["total_outbound"], 4)
        links = data["links"]
        targets = [l["target_title"] for l in links]
        self.assertIn("Architecture Guide", targets)
        self.assertIn("../01 - Projects/Database Migration.md", targets)
        self.assertIn("Deleted Research", targets)

    def test_query_backlinks_plain_text_and_details(self) -> None:
        code, out, err = CliRunner.invoke(
            ["links", "-b", "03 - Resources/Architecture Guide.md"]
        )
        self.assertEqual(code, 0)
        self.assertIn("01 - Projects/Apollo.md", out)

        # With --details
        code, out, err = CliRunner.invoke(
            ["links", "-b", "--details", "Architecture Guide"]
        )
        self.assertEqual(code, 0)
        self.assertIn("01 - Projects/Apollo.md", out)
        self.assertIn("wikilink", out)
        self.assertIn("line 13", out)

    def test_query_backlinks_json(self) -> None:
        code, out, err = CliRunner.invoke(
            ["links", "-b", "--json", "Architecture Guide"]
        )
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertEqual(data["target_note"], "03 - Resources/Architecture Guide.md")
        self.assertEqual(data["total_backlinks"], 2)  # Two occurrences in Apollo.md
        self.assertEqual(data["backlinks"][0]["source_path"], "01 - Projects/Apollo.md")

    def test_ambiguous_outbound_link_detection(self) -> None:
        # Plain text query
        code, out, err = CliRunner.invoke(["links", "AmbiguousCaller"])
        self.assertEqual(code, 0)
        self.assertIn(
            "[ambiguous] Overview (candidates: 01 - Projects/Overview.md, 02 - Areas/Overview.md)",
            out,
        )

        # JSON query
        code, out, err = CliRunner.invoke(["--json", "links", "AmbiguousCaller"])
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertTrue(data["links"][0]["is_ambiguous"])
        self.assertEqual(
            data["links"][0]["candidate_paths"],
            ["01 - Projects/Overview.md", "02 - Areas/Overview.md"],
        )

    def test_ambiguous_note_argument_rejection(self) -> None:
        code, out, err = CliRunner.invoke(["links", "Roadmap"])
        self.assertEqual(code, 1)
        self.assertIn("ambiguous", err.lower())
        self.assertIn("01 - Projects/Roadmap.md", err)
        self.assertIn("02 - Areas/Roadmap.md", err)

        # Exact path resolution should still succeed
        code, out, err = CliRunner.invoke(["links", "01 - Projects/Roadmap.md"])
        self.assertEqual(code, 0)

    def test_note_not_found_and_missing_arguments(self) -> None:
        # Note not found
        code, out, err = CliRunner.invoke(["links", "Nonexistent"])
        self.assertEqual(code, 1)
        self.assertIn("not found", err.lower())

        # Missing required note argument
        code, out, err = CliRunner.invoke(["links"])
        self.assertEqual(code, 2)
        self.assertIn("required", err.lower())

        # Invalid domain argument
        code, out, err = CliRunner.invoke(
            ["links", "Apollo", "--domain", "invalid_domain"]
        )
        self.assertEqual(code, 2)
        self.assertIn("invalid domain", err.lower())

    def test_domain_filtering(self) -> None:
        # Outbound query filtered by resources domain
        code, out, err = CliRunner.invoke(["links", "Apollo", "--domain", "resources"])
        self.assertEqual(code, 0)
        self.assertIn("03 - Resources/Architecture Guide.md", out)
        self.assertNotIn("01 - Projects/Database Migration.md", out)

        # Backlinks query filtered by projects domain
        code, out, err = CliRunner.invoke(
            ["links", "-b", "Architecture Guide", "--domain", "projects"]
        )
        self.assertEqual(code, 0)
        self.assertIn("01 - Projects/Apollo.md", out)

        # Backlinks query filtered by areas domain (expect 0 backlinks)
        code, out, err = CliRunner.invoke(
            ["links", "-b", "Architecture Guide", "--domain", "areas"]
        )
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), "")

    def test_self_referencing_links_excluded_from_backlinks(self) -> None:
        """Verify that internal links to self or own headings are excluded from incoming backlinks."""
        # In JSON mode
        code, out, err = CliRunner.invoke(["links", "-b", "--json", "Self Note"])
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertEqual(data["total_backlinks"], 1)
        self.assertEqual(len(data["backlinks"]), 1)
        self.assertEqual(
            data["backlinks"][0]["source_path"], "01 - Projects/OtherNote.md"
        )

        # In plain text mode
        code, out, err = CliRunner.invoke(["links", "-b", "Self Note"])
        self.assertEqual(code, 0)
        self.assertIn("01 - Projects/OtherNote.md", out)
        self.assertNotIn("01 - Projects/SelfNote.md", out)


if __name__ == "__main__":
    unittest.main()

